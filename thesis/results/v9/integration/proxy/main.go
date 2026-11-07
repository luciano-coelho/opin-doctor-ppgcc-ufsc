// proxy is the v9, T5/T6, Fase 1 integration harness's client side -- a
// fork of thesis/scripts/tls_kem_proxy/main.go (origin commit
// a304d6980422e6a264d990302fd319b4862693ee). See DECISIONS.md, Decisao
// 12 (T5 scope/diff) and Decisao 13/14 (T6 instrumentation).
//
// T6 reworked this from T5's http.Client-based version to an explicit
// Dial()/Handshake() sequence, for the same reason as gateway/main.go:
// byte counts measured exactly at the Handshake() boundary, not wherever
// http.Transport happens to call it internally.
package main

import (
	"bufio"
	"crypto/tls"
	"crypto/x509"
	"encoding/json"
	"flag"
	"fmt"
	"log"
	"net"
	"os"
	"path/filepath"
	"sync/atomic"
	"time"
)

var expectedCurve = map[string]tls.CurveID{
	"classico":    tls.CurveP384,
	"pqc":         tls.MLKEM1024,
	"hibrido-v8":  tls.SecP384r1MLKEM1024,
	"hibrido-and": tls.SecP384r1MLKEM1024,
}

type result struct {
	Side                  string `json:"side"`
	Profile               string `json:"profile"`
	OK                    bool   `json:"ok"`
	Error                 string `json:"error,omitempty"`
	CurveID               string `json:"curveID"`
	DualAuthenticated     bool   `json:"dualAuthenticated"`
	TLSVersion            string `json:"tlsVersion"`
	TicketsDisabled       bool   `json:"ticketsDisabled"`
	HandshakeBytesIn      int64  `json:"handshakeBytesIn"`
	HandshakeBytesOut     int64  `json:"handshakeBytesOut"`
	HandshakeDurationUs   int64  `json:"handshakeDurationUs"`
	PostHandshakeBytesIn  int64  `json:"postHandshakeBytesIn"`
	PostHandshakeBytesOut int64  `json:"postHandshakeBytesOut"`
	HTTPStatus            int    `json:"httpStatus"`
}

func main() {
	profile := flag.String("profile", "", "classico|pqc|hibrido-v8|hibrido-and")
	certDir := flag.String("cert-dir", "/certs", "directory holding the certs make certs generated")
	target := flag.String("target", "mtls:443", "gateway address, host:port")
	ticketsDisabled := flag.Bool("tickets-disabled", true, "set Config.SessionTicketsDisabled (T6 diagnostic: pass -tickets-disabled=false to measure ticket overhead)")
	keylogPath := flag.String("keylog-path", "", "optional SSLKEYLOGFILE-style path for TLS secrets (T6 pcap cross-validation)")
	flag.Parse()

	want, ok := expectedCurve[*profile]
	if !ok {
		log.Fatalf("proxy: unknown -profile %q (want classico, pqc, hibrido-v8, hibrido-and)", *profile)
	}

	var keylog *os.File
	if *keylogPath != "" {
		var err error
		keylog, err = os.Create(*keylogPath)
		if err != nil {
			log.Fatalf("proxy: create keylog %s: %v", *keylogPath, err)
		}
		defer keylog.Close()
	}

	cfg, err := buildClientTLSConfig(*profile, *certDir, *ticketsDisabled, keylog)
	if err != nil {
		log.Fatalf("proxy: %s: building TLS config: %v", *profile, err)
	}

	raw, err := net.Dial("tcp", *target)
	if err != nil {
		log.Fatalf("proxy: %s: dial %s: %v", *profile, *target, err)
	}
	defer raw.Close()
	cc := &countingConn{Conn: raw}
	tlsConn := tls.Client(cc, cfg)

	t0 := time.Now()
	in0, out0 := cc.snapshot()
	if err := tlsConn.Handshake(); err != nil {
		log.Fatalf("proxy: %s: handshake failed: %v", *profile, err)
	}
	t1 := time.Now()
	in1, out1 := cc.snapshot()

	r := result{
		Side:                "proxy",
		Profile:             *profile,
		TicketsDisabled:     *ticketsDisabled,
		HandshakeBytesIn:    in1 - in0,
		HandshakeBytesOut:   out1 - out0,
		HandshakeDurationUs: t1.Sub(t0).Microseconds(),
	}

	cs := tlsConn.ConnectionState()
	r.CurveID = cs.CurveID.String()
	r.DualAuthenticated = cs.DualAuthenticated
	r.TLSVersion = tls.VersionName(cs.Version)

	if cs.CurveID != want {
		log.Fatalf("proxy: FATAL: %s negotiated group %s, expected exactly %s", *profile, cs.CurveID, want)
	}
	if *profile == "hibrido-and" && !cs.DualAuthenticated {
		log.Fatalf("proxy: FATAL: %s DualAuthenticated=false on the client side", *profile)
	}

	// Best-effort secondary signal only (see gateway/main.go's own
	// comment on the symmetric window there) -- a brief pause before
	// this process's own first deliberate write lets any session ticket
	// already in flight land and get counted here; the PRIMARY ticket-
	// cost number is the T6 diagnostic A/B (this same run repeated with
	// -tickets-disabled=false, diffing HandshakeBytesOut), not this
	// window, since Go's TLS 1.3 server sends tickets synchronously
	// within Handshake() in this toolchain -- confirmed in DECISIONS.md,
	// Decisao 14.
	// Only in diagnostic mode: a normal-mode run has no ticket to wait
	// for, and this delay would otherwise contaminate the gateway's own
	// requestDurationUs measurement with an artificial wait that has
	// nothing to do with real request-serving cost -- found live, the
	// first time this ran with the delay unconditional (requestDurationUs
	// came back ~100000us flat, exactly this sleep, not real work).
	if !*ticketsDisabled {
		time.Sleep(100 * time.Millisecond)
	}
	postIn0, postOut0 := in1, out1

	status, body, err := doRequest(tlsConn)
	if err != nil {
		log.Fatalf("proxy: %s: request failed: %v", *profile, err)
	}

	postIn1, postOut1 := cc.snapshot()
	r.PostHandshakeBytesIn = postIn1 - postIn0
	r.PostHandshakeBytesOut = postOut1 - postOut0
	r.HTTPStatus = status
	r.OK = status == 200

	b, _ := json.Marshal(r)
	fmt.Println(string(b))
	log.Printf("proxy: %s OK curve=%s dualAuthenticated=%v tlsVersion=%s gatewayResponse=%s",
		*profile, cs.CurveID, cs.DualAuthenticated, tls.VersionName(cs.Version), body)
	fmt.Printf("RESULT profile=%s status=%d curve=%s dualAuthenticated=%v\n",
		*profile, status, cs.CurveID.String(), cs.DualAuthenticated)
}

// doRequest hand-writes a single HTTP/1.1 request and parses just enough
// of the response to report status + body -- see gateway/main.go's
// serveOneResponse for why this avoids net/http here.
func doRequest(conn net.Conn) (status int, body string, err error) {
	if _, err := conn.Write([]byte("GET / HTTP/1.1\r\nHost: mtls\r\nConnection: close\r\n\r\n")); err != nil {
		return 0, "", fmt.Errorf("write request: %w", err)
	}
	r := bufio.NewReader(conn)
	statusLine, err := r.ReadString('\n')
	if err != nil {
		return 0, "", fmt.Errorf("read status line: %w", err)
	}
	if _, err := fmt.Sscanf(statusLine, "HTTP/1.1 %d", &status); err != nil {
		return 0, "", fmt.Errorf("parse status line %q: %w", statusLine, err)
	}
	for {
		line, err := r.ReadString('\n')
		if err != nil {
			return status, "", fmt.Errorf("read headers: %w", err)
		}
		if line == "\r\n" || line == "\n" {
			break
		}
	}
	rest := make([]byte, 4096)
	n, _ := r.Read(rest)
	return status, string(rest[:n]), nil
}

type countingConn struct {
	net.Conn
	in  atomic.Int64
	out atomic.Int64
}

func (c *countingConn) Read(b []byte) (int, error) {
	n, err := c.Conn.Read(b)
	c.in.Add(int64(n))
	return n, err
}

func (c *countingConn) Write(b []byte) (int, error) {
	n, err := c.Conn.Write(b)
	c.out.Add(int64(n))
	return n, err
}

func (c *countingConn) snapshot() (int64, int64) {
	return c.in.Load(), c.out.Load()
}

// buildClientTLSConfig dispatches on profile name. See Decisao 12's diff
// table (InsecureSkipVerify removed, RootCAs set per profile) and
// Decisao 13/14 for the T6 additions (ticketsDisabled, KeyLogWriter).
func buildClientTLSConfig(profile, certDir string, ticketsDisabled bool, keylog *os.File) (*tls.Config, error) {
	p := func(name string) string { return filepath.Join(certDir, name) }

	var cfg *tls.Config
	var err error
	switch profile {
	case "classico":
		cfg, err = singleChainClientConfig(p("classico_client.crt"), p("classico_client.key"), p("classico_ca.crt"), tls.CurveP384, tls.VersionTLS12)
	case "pqc":
		cfg, err = singleChainClientConfig(p("pqc_client.crt"), p("pqc_client.key"), p("pqc_ca.crt"), tls.MLKEM1024, tls.VersionTLS13)
	case "hibrido-v8":
		cfg, err = singleChainClientConfig(p("hibrido_v8_client.crt"), p("hibrido_v8_client.key"), p("hibrido_v8_ca.crt"), tls.SecP384r1MLKEM1024, tls.VersionTLS13)
	case "hibrido-and":
		cfg, err = dualClientConfig(certDir)
	default:
		return nil, fmt.Errorf("unknown profile %q", profile)
	}
	if err != nil {
		return nil, err
	}
	cfg.SessionTicketsDisabled = ticketsDisabled
	if !ticketsDisabled {
		// Go's client only advertises psk_key_exchange_modes (RFC 8446
		// 4.2.9) -- the signal the server's own shouldSendSessionTickets()
		// gates on -- when ClientSessionCache is non-nil (confirmed by
		// reading handshake_client.go in this toolchain, line ~376: `if
		// c.config.SessionTicketsDisabled || c.config.ClientSessionCache
		// == nil { return }`). Without this, a diagnostic run with
		// SessionTicketsDisabled=false on both sides still measures ZERO
		// ticket bytes -- found live, the first time this ran (see
		// DECISIONS.md, Decisao 14).
		cfg.ClientSessionCache = tls.NewLRUClientSessionCache(4)
	}
	if keylog != nil {
		cfg.KeyLogWriter = keylog
	}
	return cfg, nil
}

func singleChainClientConfig(certPath, keyPath, caPath string, curve tls.CurveID, minVersion uint16) (*tls.Config, error) {
	cert, err := tls.LoadX509KeyPair(certPath, keyPath)
	if err != nil {
		return nil, fmt.Errorf("load client cert/key (%s/%s): %w", certPath, keyPath, err)
	}
	roots, err := loadCAPool(caPath)
	if err != nil {
		return nil, fmt.Errorf("load server CA pool (%s): %w", caPath, err)
	}
	return &tls.Config{
		Certificates:     []tls.Certificate{cert},
		RootCAs:          roots,
		ServerName:       "mtls",
		MinVersion:       minVersion,
		MaxVersion:       tls.VersionTLS13,
		CurvePreferences: []tls.CurveID{curve},
	}, nil
}

func dualClientConfig(certDir string) (*tls.Config, error) {
	p := func(name string) string { return filepath.Join(certDir, name) }

	rsaCert, err := tls.LoadX509KeyPair(p("hibrido_and_rsa_client.crt"), p("hibrido_and_rsa_client.key"))
	if err != nil {
		return nil, fmt.Errorf("load RSA client cert/key: %w", err)
	}
	rsaRoots, err := loadCAPool(p("hibrido_and_rsa_ca.crt"))
	if err != nil {
		return nil, fmt.Errorf("load RSA server CA pool: %w", err)
	}
	mldsaCert, err := tls.LoadX509KeyPair(p("hibrido_and_mldsa_client.crt"), p("hibrido_and_mldsa_client.key"))
	if err != nil {
		return nil, fmt.Errorf("load ML-DSA-65 client cert/key: %w", err)
	}
	mldsaRoots, err := loadCAPool(p("hibrido_and_mldsa_ca.crt"))
	if err != nil {
		return nil, fmt.Errorf("load ML-DSA-65 server CA pool: %w", err)
	}

	return &tls.Config{
		Certificates:     []tls.Certificate{rsaCert},
		RootCAs:          rsaRoots,
		ServerName:       "mtls",
		MinVersion:       tls.VersionTLS13,
		MaxVersion:       tls.VersionTLS13,
		CurvePreferences: []tls.CurveID{tls.SecP384r1MLKEM1024},
		Dual: &tls.DualConfig{
			Certificates: []tls.Certificate{mldsaCert},
			RootCAs:      mldsaRoots,
			Require:      true,
		},
	}, nil
}

func loadCAPool(path string) (*x509.CertPool, error) {
	b, err := os.ReadFile(path)
	if err != nil {
		return nil, err
	}
	pool := x509.NewCertPool()
	if !pool.AppendCertsFromPEM(b) {
		return nil, fmt.Errorf("no certificates found in %s", path)
	}
	return pool, nil
}
