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
// that one header).
//
// Header overhead is NOT a single constant across all 4 profiles
// (achado real desta rodada): confirmed separately against the real
// running gateway+proxy (Docker, loopback, outside this test binary),
// pqc/hibrido-v8/hibrido-and all still get Content-Type + Date +
// "Transfer-Encoding: chunked" (103B, body-size-independent). classico
// does NOT, since its new RSA-2048-only bodies (1.706B/1.720B) fall
// BELOW net/http's own bufferBeforeChunkingSize=2048 -- Go computes
// Content-Length directly instead (97B of headers: Content-Type +
// Date + Content-Length, whose own digit count happens not to matter
// here since it's a real header line summed byte for byte, not
// assumed). Never forced in the handler -- this is net/http's own,
// real, correct behavior; `wantFraming` below pins it per profile so
// a future change (cert size, or net/http's own threshold) is caught
// here instead of silently drifting.

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

// headerOverheadByFraming (Decisao 166, pedido do autor: a verificacao
// achou que `root_ca_rsa2048.crt`/`issuer_ca_rsa2048.crt` -- os ARQUIVOS
// REAIS que classico e hibrido-and servem, regenerados pelo gerador de
// mock-service-os/certs -- variam de tamanho entre lotes de geracao
// (confirmado ao vivo: o lote comitado hoje tem 1706B/1720B; um lote
// anterior, gerado numa worktree de verificacao diferente, tinha
// 1679B/1692B -- 27B/28B menor, consistente com uma diferenca real de
// conteudo do certificado, nao so o tamanho do serial ASN.1, que ficou
// estavel em 20 bytes nos dois casos RSA observados). `pqc`/`hibrido-v8`
// usam arquivos DIFERENTES -- root_ca_pqc.crt/root_ca_hybrid.crt --
// que nao regeneraram nesse mesmo lote, por isso bateram exatamente.
// O teste agora deriva o tamanho esperado do ARQUIVO REAL lido do
// disco (nunca de uma constante presa a um lote especifico) -- so o
// overhead de cabecalho HTTP por modo de enquadramento continua fixo
// aqui, porque esse numero e uma propriedade do net/http (Content-
// Type + Date + Content-Length/Transfer-Encoding), independente do
// conteudo do certificado.
var headerOverheadByFraming = map[string]int{
	"content-length": 97,
	"chunked":        103,
}

func TestDirectoryHandlerResponseBytes(t *testing.T) {
	dir := realCertsDirForTest(t)

	// wantFraming fixa o modo de enquadramento HTTP esperado por perfil
	// -- achado real (rodada anterior): o par RSA-2048 novo deixou os
	// corpos de classico abaixo de bufferBeforeChunkingSize=2048 do
	// proprio net/http do Go, a UNICA diferenca entre os 4 perfis que
	// faz isso -- Go passa a usar "Content-Length" em vez de
	// "Transfer-Encoding: chunked" so pra classico. Nunca forcado no
	// handler -- e o comportamento real e correto do net/http; fixado
	// aqui (nao derivado do tamanho do arquivo) pra que uma mudanca
	// futura (cert cruzando o limiar, ou o proprio net/http mudando
	// esse limiar) seja detectada por este teste, nunca passe
	// silenciosamente.
	cases := []struct {
		profile     string
		wantFraming string
	}{
		{"classico", "content-length"},
		{"pqc", "chunked"},
		{"hibrido-v8", "chunked"},
		{"hibrido-and", "chunked"},
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
		overhead := headerOverheadByFraming[c.wantFraming]
		wantRootBytes := len(rootPEM) + overhead
		wantIssuerBytes := len(issuerPEM) + overhead

		// Raw TCP round trip -- deliberately NOT net/http.Client: Go's
		// client parses Content-Length out of resp.Header into
		// resp.ContentLength and does not put it back (confirmed live,
		// first version of this test), which would silently undercount
		// response_bytes relative to what the real campaign's Python
		// client actually sees on the wire. Reading the raw bytes
		// ourselves matches that reality regardless of which header
		// strategy Go's server picks (chunked or Content-Length -- see
		// wantFraming/the comment above TestDirectoryHandlerResponseBytes
		// for when each applies).
		// httptest.NewTLSServer, not NewServer: Go's http.Server picks
		// chunked vs Content-Length framing differently over a *tls.Conn
		// than over a plain TCP listener for bodies AT/ABOVE the 2048B
		// threshold (found live, first version of this test, over plain
		// HTTP with the OLD, bigger classico body: Content-Length
		// framing, 122B of headers -- NOT what the real gateway's
		// TLS-terminated preHandshakenListener connections produced for
		// that same body, confirmed separately: chunked, 103B). The
		// real gateway only ever serves this handler over TLS, so the
		// test must too.
		srv := httptest.NewTLSServer(directoryHandler(rootPEM, issuerPEM))

		for _, tc := range []struct {
			path string
			want int
		}{
			{"/root-ca.pem", wantRootBytes},
			{"/issuer-ca.pem", wantIssuerBytes},
		} {
			got, bodyLen, headerBytes, framing := rawResponseBytes(t, srv.Listener.Addr().String(), tc.path)
			if got != tc.want {
				t.Errorf("%s %s: response_bytes = %d (body=%dB, headers=%dB, framing=%s), want %d",
					c.profile, tc.path, got, bodyLen, headerBytes, framing, tc.want)
			} else {
				t.Logf("%s %s: response_bytes = %d OK (body=%dB, headers=%dB, framing=%s)",
					c.profile, tc.path, got, bodyLen, headerBytes, framing)
			}
			if framing != c.wantFraming {
				t.Errorf("%s %s: framing = %q, want %q -- comportamento do net/http mudou (bufferBeforeChunkingSize?) ou o certificado mudou de tamanho sem atualizar este teste",
					c.profile, tc.path, framing, c.wantFraming)
			}
		}
		srv.Close()
	}
}

// TestDirectoryHandlerResponseBytesMatchesFrozenManifest (Decisao 166,
// item 2; recalculado na Decisao 167 -- pedido do Luciano, "LF
// canonico, renormalizar e recalcular"): verificacao SEPARADA e
// explicita, nunca misturada com TestDirectoryHandlerResponseBytes
// acima (que agora deriva o esperado dos arquivos reais, entao sempre
// passa mesmo se os arquivos forem regenerados com outro tamanho).
// Esta aqui e o gabarito CONGELADO do conjunto de certificados oficial
// da campanha (tag v9-campanha-oficial-congelada-v8) -- os mesmos
// response_bytes publicados nos relatorios da campanha. Se
// mock-service-os/certs for regenerado (qualquer lote novo), este teste
// -- so este -- quebra, apontando exatamente que o termo de PKI do
// gabarito precisa ser recalculado antes da proxima campanha official;
// TestDirectoryHandlerResponseBytes sozinho NUNCA detectaria isso.
//
// Os numeros abaixo (Decisao 167) substituem os da Decisao 166: aquele
// gabarito foi calculado sobre root_ca_rsa2048.crt/issuer_ca_rsa2048.
// crt com bytes CRLF obsoletos no disco local (1706B/1720B), nunca
// renormalizados apos o .gitattributes ganhar eol=lf -- o blob git ja
// era LF (1679B/1692B) desde antes da tag v6; so o checkout local
// desta maquina estava desatualizado (confirmado: delete+checkout
// reescreve correto, "git checkout --" sozinho e um no-op porque o
// index ja achava o arquivo "limpo"). Com os bytes corretos (LF,
// 1679B/1692B) classico e hibrido-and -- os dois perfis que usam
// root_ca_rsa2048.crt/issuer_ca_rsa2048.crt -- mudam; pqc e
// hibrido-v8 usam outros arquivos (root_ca_pqc.crt/root_ca_hybrid.
// crt), nunca afetados pelo CRLF, por isso o numero delas repete
// exatamente o da Decisao 166.
//
//	classico     root:  1679 (root_ca_rsa2048.crt)             + 97  (content-length) = 1776
//	classico     issuer: 1692 (issuer_ca_rsa2048.crt)            + 97  (content-length) = 1789
//	pqc          root:  8001 (root_ca_pqc.crt)                  + 103 (chunked)        = 8104
//	pqc          issuer: 8013 (issuer_ca_pqc.crt)                + 103 (chunked)        = 8116
//	hibrido-v8   root:  9337 (root_ca_hybrid.crt)                + 103 (chunked)        = 9440
//	hibrido-v8   issuer: 9341 (issuer_ca_hybrid.crt)              + 103 (chunked)        = 9444
//	hibrido-and  root:  1679 + 8001 (rsa2048 + pqc, concatenados) + 103 (chunked)        = 9783
//	hibrido-and  issuer: 1692 + 8013 (rsa2048 + pqc, concatenados) + 103 (chunked)        = 9808
func TestDirectoryHandlerResponseBytesMatchesFrozenManifest(t *testing.T) {
	dir := realCertsDirForTest(t)

	cases := []struct {
		profile         string
		wantRootBytes   int
		wantIssuerBytes int
	}{
		{"classico", 1776, 1789},
		{"pqc", 8104, 8116},
		{"hibrido-v8", 9440, 9444},
		{"hibrido-and", 9783, 9808},
	}
	wantFramingByProfile := map[string]string{
		"classico": "content-length", "pqc": "chunked", "hibrido-v8": "chunked", "hibrido-and": "chunked",
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
		overhead := headerOverheadByFraming[wantFramingByProfile[c.profile]]
		if got := len(rootPEM) + overhead; got != c.wantRootBytes {
			t.Errorf("%s root-ca.pem: response_bytes = %d, want %d (gabarito congelado) -- "+
				"o conjunto de mock-service-os/certs em uso NAO e mais o conjunto oficial congelado; "+
				"recalcule o termo de PKI do gabarito (Decisao 166) antes de qualquer campanha oficial",
				c.profile, got, c.wantRootBytes)
		}
		if got := len(issuerPEM) + overhead; got != c.wantIssuerBytes {
			t.Errorf("%s issuer-ca.pem: response_bytes = %d, want %d (gabarito congelado) -- "+
				"o conjunto de mock-service-os/certs em uso NAO e mais o conjunto oficial congelado; "+
				"recalcule o termo de PKI do gabarito (Decisao 166) antes de qualquer campanha oficial",
				c.profile, got, c.wantIssuerBytes)
		}
	}
}

// rawResponseBytes dials addr directly, issues a raw HTTP/1.1 GET, and
// measures EXACTLY what baseline_automation.py's header_bytes() measures
// client-side: the sum of "Name: value\r\n" for every header LINE
// actually received (status line excluded), plus the fully-received
// body length (chunk-decoded if the response is chunked, matching
// requests/urllib3's own automatic dechunking).
func rawResponseBytes(t *testing.T, addr, path string) (responseBytes, bodyLen, headerBytes int, framing string) {
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
		framing = "chunked"
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
		framing = "content-length"
		n, err := strconv.Atoi(cl)
		if err != nil {
			t.Fatalf("parse Content-Length %q: %v", cl, err)
		}
		body = make([]byte, n)
		if _, err := io.ReadFull(r, body); err != nil {
			t.Fatalf("read body: %v", err)
		}
	} else {
		framing = "neither (EOF-terminated)"
		body, _ = io.ReadAll(r)
	}

	return headerBytes + len(body), len(body), headerBytes, framing
}
