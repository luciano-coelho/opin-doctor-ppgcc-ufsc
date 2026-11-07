// business_server.go: T6b's serving loop -- explicit per-connection
// Handshake() (so CurveID/DualAuthenticated are still checked and
// logged on every connection, same requirement as "measure" mode,
// Decisao 12/14), then hand the already-handshaken *tls.Conn off to a
// real http.Server/ServeMux for full HTTP routing with keep-alive
// (opin_flow.py reuses each mTLS connection across several HTTP
// requests -- T5/T6's one-request-per-connection serveOneResponse
// can't support that). Calling (*tls.Conn).Handshake() a second time
// (net/http's own internal call, once it sees an *tls.Conn) is a
// documented no-op once the handshake has already completed -- safe.
package main

import (
	"crypto/tls"
	"fmt"
	"log"
	"net"
	"net/http"
	"os"
	"path/filepath"
)

func runBusinessMode(profile, certDir, listen string) {
	want, ok := expectedCurve[profile]
	if !ok {
		log.Fatalf("gateway: unknown CRYPTO_PROFILE %q (want classico, pqc, hibrido-v8, hibrido-and)", profile)
	}

	cfg, err := buildServerTLSConfig(profile, certDir, true, nil)
	if err != nil {
		log.Fatalf("gateway: %s: building TLS config: %v", profile, err)
	}
	if err := attachInternalCallerCarveOut(cfg, profile); err != nil {
		log.Fatalf("gateway: attaching matls-api.local internal-caller carve-out: %v", err)
	}

	realCertsDir := envOr("REAL_CERTS_DIR", "/real-certs")
	rootName, issuerName := realCAFilesForProfile(profile)
	rootCAPEM, err := os.ReadFile(filepath.Join(realCertsDir, rootName))
	if err != nil {
		log.Fatalf("gateway: reading real root CA (%s) for directory handler: %v", rootName, err)
	}
	issuerCAPEM, err := os.ReadFile(filepath.Join(realCertsDir, issuerName))
	if err != nil {
		log.Fatalf("gateway: reading real issuer CA (%s) for directory handler: %v", issuerName, err)
	}
	mux := businessMux(rootCAPEM, issuerCAPEM)

	ln, err := net.Listen("tcp", listen)
	if err != nil {
		log.Fatalf("gateway: listen %s: %v", listen, err)
	}
	log.Printf("gateway (business mode): profile=%s listening on %s (expected group %s)", profile, listen, want)

	pl := &preHandshakenListener{ch: make(chan net.Conn), closed: make(chan struct{})}
	server := &http.Server{Handler: mux}
	go func() {
		log.Fatal(server.Serve(pl))
	}()

	for {
		raw, err := ln.Accept()
		if err != nil {
			log.Printf("gateway: accept: %v", err)
			continue
		}
		go acceptBusinessConn(raw, cfg, profile, want, pl)
	}
}

func acceptBusinessConn(raw net.Conn, cfg *tls.Config, profile string, want tls.CurveID, pl *preHandshakenListener) {
	cc := &countingConn{Conn: raw}
	tlsConn := tls.Server(cc, cfg)
	if err := tlsConn.Handshake(); err != nil {
		log.Printf("gateway: %s: handshake failed: %v", profile, err)
		_ = raw.Close()
		return
	}
	cs := tlsConn.ConnectionState()
	// internalCallerConfig connections (matls-api.local, auth's own
	// reentrant call) negotiate the classical carve-out's own group,
	// not the profile's -- only enforce the profile's expected group
	// for everything else.
	if cs.ServerName != internalCallerSNI && cs.CurveID != want {
		log.Printf("gateway: FATAL: %s negotiated group %s, expected exactly %s -- closing connection", profile, cs.CurveID, want)
		_ = tlsConn.Close()
		return
	}
	if profile == "hibrido-and" && cs.ServerName != internalCallerSNI && !cs.DualAuthenticated {
		log.Printf("gateway: FATAL: %s DualAuthenticated=false -- closing connection", profile)
		_ = tlsConn.Close()
		return
	}
	// handshakeBytesIn/Out: measured the same way T6 does (Decisao 14),
	// via the countingConn wrapped around raw above -- added here so
	// Decisao 18's per-connection table has a real number, not just
	// "yes/no" per connection.
	hsIn, hsOut := cc.snapshot()
	clientCertCN := "none"
	if len(cs.PeerCertificates) > 0 {
		clientCertCN = cs.PeerCertificates[0].Subject.CommonName
	}
	log.Printf("gateway: %s connection OK remoteAddr=%s sni=%q curve=%s dualAuthenticated=%v clientCert=%q handshakeBytesIn=%d handshakeBytesOut=%d",
		profile, raw.RemoteAddr(), cs.ServerName, cs.CurveID, cs.DualAuthenticated, clientCertCN, hsIn, hsOut)
	pl.ch <- tlsConn
}

// preHandshakenListener feeds already-handshaken *tls.Conn values to a
// single, shared http.Server.Serve() call -- Accept() blocks until
// acceptBusinessConn hands one off.
type preHandshakenListener struct {
	ch     chan net.Conn
	closed chan struct{}
}

func (l *preHandshakenListener) Accept() (net.Conn, error) {
	select {
	case c := <-l.ch:
		return c, nil
	case <-l.closed:
		return nil, net.ErrClosed
	}
}
func (l *preHandshakenListener) Close() error { close(l.closed); return nil }
func (l *preHandshakenListener) Addr() net.Addr {
	return &net.TCPAddr{IP: net.IPv4zero, Port: 0}
}

// internalCallerSNI: auth's own InsurerAdapter.getConsent() (mock_as/
// utils/opin/adapter.js) reaches this gateway as a TLS client over
// this SNI to fetch the consent from the RS -- mirrors mock_mtls's own
// GetConfigForClient carve-out (Decision 5/6 there), reinstated here
// because T6b brings the real, unmodified auth service back.
const internalCallerSNI = "matls-api.local"

// attachInternalCallerCarveOut sets cfg.GetConfigForClient so a
// connection whose ClientHello SNI is internalCallerSNI gets a
// DIFFERENT, purely classical config presenting the REAL production
// server cert (mock-service-os/certs/mtls.crt) and trusting the REAL
// production CA (ca.crt) -- auth's own client cert for this call
// (op.crt) is signed by that real CA, not by any of v9's own freshly
// generated ones, so the main per-profile config (which only trusts
// v9's own CAs) would reject it. REAL_CERTS_DIR must be mounted
// read-only from mock-service-os/certs -- never copied, never
// versioned here.
func attachInternalCallerCarveOut(cfg *tls.Config, profile string) error {
	realCertsDir := envOr("REAL_CERTS_DIR", "/real-certs")

	cert, err := tls.LoadX509KeyPair(filepath.Join(realCertsDir, "mtls.crt"), filepath.Join(realCertsDir, "mtls.key"))
	if err != nil {
		return fmt.Errorf("load real mtls.crt/.key for internal-caller carve-out: %w", err)
	}
	// ClientCAs: always trust the real classical ca.crt (op.crt's
	// issuer); ALSO trust root_ca_pqc.crt under the pqc profile
	// specifically -- mirrors the original mock_mtls/main.go exactly:
	// internalCallerConfig there is `:= *cfg` (inherits the MAIN
	// config's own ClientCAs, which caCertPool() already widens to
	// include root_ca_pqc.crt whenever CRYPTO_PROFILE=pqc), not a
	// separately hardcoded pool -- found live (DECISIONS.md, Decisao
	// 17) when a hardcoded ca.crt-only pool rejected auth's own
	// reentrant call under pqc, which (confirmed via localstack's
	// setup_ssm.sh) presents op_pqc.crt there, issued by root_ca_pqc,
	// not ca.crt.
	caPool, err := loadCAPool(filepath.Join(realCertsDir, "ca.crt"))
	if err != nil {
		return fmt.Errorf("load real ca.crt for internal-caller carve-out: %w", err)
	}
	if profile == "pqc" {
		pqcRootPEM, err := os.ReadFile(filepath.Join(realCertsDir, "root_ca_pqc.crt"))
		if err != nil {
			return fmt.Errorf("load real root_ca_pqc.crt for internal-caller carve-out: %w", err)
		}
		if !caPool.AppendCertsFromPEM(pqcRootPEM) {
			return fmt.Errorf("root_ca_pqc.crt: no certificates found")
		}
	}

	internalCfg := cfg.Clone()
	internalCfg.Certificates = []tls.Certificate{cert}
	internalCfg.ClientCAs = caPool
	// Clear the main config's hibrido-v8 AND-gate callback (Clone()
	// copies it): that callback checks the client cert's ML-DSA alt
	// signature against v9's OWN freshly generated CA key
	// (hibrido_v8_ca_mldsa.crt), but the internal caller presents a
	// REAL production dual-signed cert (op_hybrid.crt under hybrid)
	// signed by a completely different, real ML-DSA CA key -- found
	// live (DECISIONS.md, Decisao 17): "ML-DSA-65 alt signature
	// verification failed" on every hybrid-profile internal call until
	// this was cleared. The internal caller was never part of either
	// profile's v9-specific identity scheme to begin with.
	internalCfg.VerifyPeerCertificate = nil
	internalCfg.CurvePreferences = []tls.CurveID{tls.CurveP521, tls.CurveP384, tls.CurveP256}
	internalCfg.MinVersion = tls.VersionTLS12
	internalCfg.Dual = nil // the internal caller never presents a dual cert

	cfg.GetConfigForClient = func(hello *tls.ClientHelloInfo) (*tls.Config, error) {
		if hello.ServerName == internalCallerSNI {
			return internalCfg, nil
		}
		return nil, nil
	}
	return nil
}

// realCAFilesForProfile picks which of mock-service-os/certs' real
// root/issuer CA pairs to serve at /root-ca.pem and /issuer-ca.pem --
// see directoryHandler's own comment for why these must be the REAL
// files, not v9's own. opin_flow.py's verify_ca_chain() only branches
// on "pqc" vs everything else (treating classic/hybrid identically,
// verified against the real ca.crt); hibrido-and falls into that same
// "everything else" branch, so classic's own pair satisfies it exactly
// as well as hybrid's would -- picked per-profile below anyway, for
// the closest available match rather than defaulting all three to the
// same pair.
func realCAFilesForProfile(profile string) (root, issuer string) {
	switch profile {
	case "pqc":
		return "root_ca_pqc.crt", "issuer_ca_pqc.crt"
	case "hibrido-v8":
		return "root_ca_hybrid.crt", "issuer_ca_hybrid.crt"
	default: // classico, hibrido-and
		return "root_ca.crt", "issuer_ca.crt"
	}
}
