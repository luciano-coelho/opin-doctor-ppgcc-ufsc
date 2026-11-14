package main

import (
	"bufio"
	"bytes"
	"crypto/tls"
	"fmt"
	"io"
	"net/http/httptest"
	"os"
	"path/filepath"
	"strconv"
	"strings"
	"testing"
)

// ca_handler_test.go: automated regression test for the hibrido-and
// PKI/CA-distribution fix (business_server.go's realCAFilesForProfile/
// readAndConcatCAFiles + business.go's directoryHandler). Exercises the
// REAL files from REAL_CERTS_DIR (same env var/default the gateway
// itself uses), never synthetic fixtures -- a wrong byte count in the
// real certs would fail this test the same way a wrong code path
// would.
//
// response_bytes here is computed the SAME way the real campaign's
// Python client computes it (opin_flow.py, baseline_automation.
// header_bytes()): sum of "Name: value\r\n" for every response header
// line actually received, PLUS the raw (dechunked) body length -- read
// off the raw TCP bytes, not through net/http.Client (which silently
// drops Content-Length from resp.Header after parsing it, found live
// in this test's first version, undercounting by exactly the size of
// that one header). Confirmed separately against the real running
// gateway+proxy (Docker, loopback, outside this test binary): the real
// response has no Content-Length at all -- Content-Type + Date +
// "Transfer-Encoding: chunked", a body-size-independent 103B of
// headers, true for both the old single-certificate bodies and
// hibrido-and's new 2-certificate bundle.

func realCertsDirForTest(t *testing.T) string {
	t.Helper()
	if d := os.Getenv("REAL_CERTS_DIR"); d != "" {
		return d
	}
	t.Skip("REAL_CERTS_DIR not set -- skipping (needs mock-service-os/certs mounted)")
	return ""
}

func TestRealCAFilesForProfile(t *testing.T) {
	cases := []struct {
		profile    string
		wantRoot   []string
		wantIssuer []string
	}{
		{"classico", []string{"root_ca_rsa2048.crt"}, []string{"issuer_ca_rsa2048.crt"}},
		{"pqc", []string{"root_ca_pqc.crt"}, []string{"issuer_ca_pqc.crt"}},
		{"hibrido-v8", []string{"root_ca_hybrid.crt"}, []string{"issuer_ca_hybrid.crt"}},
		{"hibrido-and", []string{"root_ca_rsa2048.crt", "root_ca_pqc.crt"}, []string{"issuer_ca_rsa2048.crt", "issuer_ca_pqc.crt"}},
	}
	for _, c := range cases {
		root, issuer := realCAFilesForProfile(c.profile)
		if fmt.Sprint(root) != fmt.Sprint(c.wantRoot) {
			t.Errorf("%s: root files = %v, want %v", c.profile, root, c.wantRoot)
		}
		if fmt.Sprint(issuer) != fmt.Sprint(c.wantIssuer) {
			t.Errorf("%s: issuer files = %v, want %v", c.profile, issuer, c.wantIssuer)
		}
	}
}

func TestHibridoAndBundleIsTwoBlocksRSAThenMLDSA(t *testing.T) {
	dir := realCertsDirForTest(t)
	rootNames, issuerNames := realCAFilesForProfile("hibrido-and")
	rootBundle, err := readAndConcatCAFiles(dir, rootNames)
	if err != nil {
		t.Fatalf("reading root bundle: %v", err)
	}
	issuerBundle, err := readAndConcatCAFiles(dir, issuerNames)
	if err != nil {
		t.Fatalf("reading issuer bundle: %v", err)
	}

	for name, bundle := range map[string][]byte{"root-ca.pem": rootBundle, "issuer-ca.pem": issuerBundle} {
		blocks := bytes.Count(bundle, []byte("-----BEGIN CERTIFICATE-----"))
		if blocks != 2 {
			t.Errorf("%s: got %d CERTIFICATE blocks, want exactly 2", name, blocks)
		}
		firstBeginIdx := bytes.Index(bundle, []byte("-----BEGIN CERTIFICATE-----"))
		secondBeginIdx := bytes.Index(bundle[firstBeginIdx+1:], []byte("-----BEGIN CERTIFICATE-----")) + firstBeginIdx + 1
		firstBlock := bundle[firstBeginIdx:secondBeginIdx]
		secondBlock := bundle[secondBeginIdx:]
		// RSA half: sha256WithRSAEncryption OID (1.2.840.113549.1.1.11)
		// is NOT trivially greppable from base64 text directly, so we
		// assert by SIZE/ORDER against the real files instead, which is
		// what realCAFilesForProfile's own documented order guarantees
		// (RSA file name listed first in the slice).
		rsaFile, err := os.ReadFile(filepath.Join(dir, rootNames[0]))
		if err != nil {
			t.Fatalf("reading %s: %v", rootNames[0], err)
		}
		pqcFile, err := os.ReadFile(filepath.Join(dir, rootNames[1]))
		if err != nil {
			t.Fatalf("reading %s: %v", rootNames[1], err)
		}
		if name == "root-ca.pem" {
			if !bytes.Equal(firstBlock, rsaFile) {
				t.Errorf("root-ca.pem: first block is not byte-identical to %s (RSA, expected first)", rootNames[0])
			}
			if !bytes.Equal(secondBlock, pqcFile) {
				t.Errorf("root-ca.pem: second block is not byte-identical to %s (ML-DSA-65, expected second)", rootNames[1])
			}
		}
	}
}

func TestDirectoryHandlerResponseBytes(t *testing.T) {
	dir := realCertsDirForTest(t)

	cases := []struct {
		profile         string
		wantRootBytes   int
		wantIssuerBytes int
	}{
		{"classico", 1809, 1823},
		{"pqc", 8104, 8116},
		{"hibrido-v8", 9440, 9444},
		{"hibrido-and", 9810, 9836},
	}

	for _, c := range cases {
		rootNames, issuerNames := realCAFilesForProfile(c.profile)
		rootPEM, err := readAndConcatCAFiles(dir, rootNames)
		if err != nil {
			t.Fatalf("%s: reading root bundle: %v", c.profile, err)
		}
		issuerPEM, err := readAndConcatCAFiles(dir, issuerNames)
		if err != nil {
			t.Fatalf("%s: reading issuer bundle: %v", c.profile, err)
		}

		// Raw TCP round trip -- deliberately NOT net/http.Client: Go's
		// client parses Content-Length out of resp.Header into
		// resp.ContentLength and does not put it back (confirmed live,
		// first version of this test), which would silently undercount
		// response_bytes relative to what the real campaign's Python
		// client actually sees on the wire (confirmed live, separately,
		// against the real running gateway+proxy in business mode: the
		// real response has NO Content-Length at all -- Content-Type +
		// Date + "Transfer-Encoding: chunked", exactly 103B of headers,
		// body-size-independent). Reading the raw bytes ourselves
		// matches that reality regardless of which header strategy Go's
		// server picks.
		// httptest.NewTLSServer, not NewServer: Go's http.Server picks
		// chunked vs Content-Length framing differently over a *tls.Conn
		// than over a plain TCP listener (found live, first version of
		// this test, over plain HTTP: Content-Length framing, 122B of
		// headers -- NOT what the real gateway's TLS-terminated
		// preHandshakenListener connections produce, confirmed
		// separately against the real running gateway+proxy: chunked,
		// 103B). The real gateway only ever serves this handler over
		// TLS, so the test must too.
		srv := httptest.NewTLSServer(directoryHandler(rootPEM, issuerPEM))

		for _, tc := range []struct {
			path string
			want int
		}{
			{"/root-ca.pem", c.wantRootBytes},
			{"/issuer-ca.pem", c.wantIssuerBytes},
		} {
			got, bodyLen, headerBytes := rawResponseBytes(t, srv.Listener.Addr().String(), tc.path)
			if got != tc.want {
				t.Errorf("%s %s: response_bytes = %d (body=%dB, headers=%dB), want %d",
					c.profile, tc.path, got, bodyLen, headerBytes, tc.want)
			} else {
				t.Logf("%s %s: response_bytes = %d OK (body=%dB, headers=%dB)",
					c.profile, tc.path, got, bodyLen, headerBytes)
			}
		}
		srv.Close()
	}
}

// rawResponseBytes dials addr directly, issues a raw HTTP/1.1 GET, and
// measures EXACTLY what baseline_automation.py's header_bytes() measures
// client-side: the sum of "Name: value\r\n" for every header LINE
// actually received (status line excluded), plus the fully-received
// body length (chunk-decoded if the response is chunked, matching
// requests/urllib3's own automatic dechunking).
func rawResponseBytes(t *testing.T, addr, path string) (responseBytes, bodyLen, headerBytes int) {
	t.Helper()
	conn, err := tls.Dial("tcp", addr, &tls.Config{InsecureSkipVerify: true})
	if err != nil {
		t.Fatalf("dial %s: %v", addr, err)
	}
	defer conn.Close()

	if _, err := fmt.Fprintf(conn, "GET %s HTTP/1.1\r\nHost: directory\r\n\r\n", path); err != nil {
		t.Fatalf("write request: %v", err)
	}

	r := bufio.NewReader(conn)
	statusLine, err := r.ReadString('\n')
	if err != nil {
		t.Fatalf("read status line: %v", err)
	}
	headers := map[string]string{}
	for {
		line, err := r.ReadString('\n')
		if err != nil {
			t.Fatalf("read header line: %v", err)
		}
		if line == "\r\n" {
			break
		}
		headerBytes += len(line)
		parts := strings.SplitN(strings.TrimRight(line, "\r\n"), ":", 2)
		if len(parts) == 2 {
			headers[strings.TrimSpace(parts[0])] = strings.TrimSpace(parts[1])
		}
	}
	_ = statusLine

	var body []byte
	if strings.EqualFold(headers["Transfer-Encoding"], "chunked") {
		for {
			sizeLine, err := r.ReadString('\n')
			if err != nil {
				t.Fatalf("read chunk size: %v", err)
			}
			sizeLine = strings.TrimRight(sizeLine, "\r\n")
			size, err := strconv.ParseInt(sizeLine, 16, 64)
			if err != nil {
				t.Fatalf("parse chunk size %q: %v", sizeLine, err)
			}
			if size == 0 {
				break
			}
			chunk := make([]byte, size)
			if _, err := io.ReadFull(r, chunk); err != nil {
				t.Fatalf("read chunk data: %v", err)
			}
			body = append(body, chunk...)
			if _, err := r.ReadString('\n'); err != nil { // trailing \r\n after each chunk
				t.Fatalf("read chunk trailer: %v", err)
			}
		}
	} else if cl, ok := headers["Content-Length"]; ok {
		n, err := strconv.Atoi(cl)
		if err != nil {
			t.Fatalf("parse Content-Length %q: %v", cl, err)
		}
		body = make([]byte, n)
		if _, err := io.ReadFull(r, body); err != nil {
			t.Fatalf("read body: %v", err)
		}
	} else {
		body, _ = io.ReadAll(r)
	}

	return headerBytes + len(body), len(body), headerBytes
}
