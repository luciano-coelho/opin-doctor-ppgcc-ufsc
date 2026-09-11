// tls_kem_proxy is test-harness infrastructure, not part of the OPIN
// system itself -- it exists only because opin_flow.py's Python/OpenSSL
// stack cannot negotiate the ML-KEM hybrid TLS groups the mock_mtls gateway
// now offers under CRYPTO_PROFILE=pqc/hybrid (see thesis/results/v6/Level 1/
// ARCHITECTURE.md, Fase 0). It mirrors the same "delegate to a Go helper"
// pattern opin_flow.py's _run_pqc_signer() already uses for ML-DSA-65
// signing, applied here to a TLS connection instead of a signature.
//
// The Python-facing side always speaks TLS too, with a throwaway
// self-signed cert generated fresh on every startup -- NOT plain HTTP, even
// though this hop never uses the ML-KEM groups the gateway hop does. A
// first version used plain HTTP here and broke the login flow: oidc-provider
// sets its interaction-session cookie with the Secure attribute, and
// Python's own cookie jar (http.cookiejar, which requests uses
// unconditionally) silently drops Secure cookies on a plain-HTTP connection
// -- confirmed live, reproduced consistently, the fix confirmed by
// switching this listener to TLS. opin_flow.py already connects with
// verify=False (thesis/scripts/opin_flow.py's do_call()), so an
// self-signed, unverified local cert costs nothing there.
//
// Two modes, chosen by -stub:
//
//   - Relay mode (default): a TLS-to-TLS tunnel. Terminates the local TLS
//     connection from opin_flow.py, dials one real mTLS connection to the
//     gateway using the requested client cert and KEM group, then pipes the
//     decrypted bytes bidirectionally for the lifetime of that connection.
//     Because this never parses HTTP, the exact bytes opin_flow.py sends
//     (Host header included) reach the gateway unchanged -- gateway-side
//     routing works exactly as it does without this proxy in the middle.
//     One accepted local connection produces exactly one upstream mTLS
//     connection, which is the property that lets requests.Session()'s own
//     per-pool connection reuse (thesis/results/v6/Level 1/ARCHITECTURE.md,
//     Fase 2 item 2) carry through unchanged: however many connections
//     Python's Sessions open to this proxy is exactly how many real mTLS
//     handshakes happen against the gateway -- expected to be 6 per full
//     flow execution (N_mTLS), never 1 and never 28.
//
//   - Stub mode (-stub): answers every request immediately with a fixed
//     response and never dials the gateway at all. Exists solely for the
//     Fase 4 calibration the user required before any pilot run: measuring
//     how much time this proxy process itself adds (Python -> proxy ->
//     Python, entirely local) in isolation from the real mTLS connection's
//     own cost, so "negligible" is a measured number, not an assumption.
//     Also terminates local TLS (matching relay mode) so the calibration
//     reflects the same local-hop cost the real path pays, TLS handshake
//     included.
package main

import (
	"crypto/ecdsa"
	"crypto/elliptic"
	"crypto/rand"
	"crypto/tls"
	"crypto/x509"
	"crypto/x509/pkix"
	"encoding/pem"
	"flag"
	"io"
	"log"
	"math/big"
	"net"
	"net/http"
	"time"
)

func main() {
	listen := flag.String("listen", ":8443", "local address to listen on (TLS, throwaway self-signed cert)")
	target := flag.String("target", "mtls:443", "gateway address to relay to, host:port (ignored in -stub mode)")
	certPath := flag.String("cert", "", "client certificate PEM path (ignored in -stub mode)")
	keyPath := flag.String("key", "", "client key PEM path (ignored in -stub mode)")
	curveName := flag.String("curve", "", "one of: mlkem1024, x25519mlkem768 (ignored in -stub mode)")
	stub := flag.Bool("stub", false, "stub/echo mode -- answer directly, never touch the gateway (Fase 4 calibration)")
	flag.Parse()

	localTLSConfig := &tls.Config{Certificates: []tls.Certificate{generateLocalListenerCert()}}

	if *stub {
		runStub(*listen, localTLSConfig)
		return
	}
	runRelay(*listen, *target, *certPath, *keyPath, *curveName, localTLSConfig)
}

// generateLocalListenerCert makes a fresh, throwaway self-signed
// ECDSA P-256 certificate for the Python-facing listener only -- this
// never touches the ML-KEM question at all (it's the opposite side of the
// tunnel from the gateway hop), it exists purely so opin_flow.py sees a
// real https:// endpoint, cookies with the Secure attribute included.
func generateLocalListenerCert() tls.Certificate {
	key, err := ecdsa.GenerateKey(elliptic.P256(), rand.Reader)
	if err != nil {
		log.Fatalf("tls_kem_proxy: generate local listener key: %v", err)
	}
	template := &x509.Certificate{
		SerialNumber: big.NewInt(1),
		Subject:      pkix.Name{CommonName: "tls_kem_proxy (local, throwaway)"},
		NotBefore:    time.Now().Add(-time.Hour),
		NotAfter:     time.Now().Add(24 * time.Hour),
		KeyUsage:     x509.KeyUsageDigitalSignature,
		ExtKeyUsage:  []x509.ExtKeyUsage{x509.ExtKeyUsageServerAuth},
		DNSNames:     []string{"localhost"},
		IPAddresses:  []net.IP{net.ParseIP("127.0.0.1")},
	}
	der, err := x509.CreateCertificate(rand.Reader, template, template, &key.PublicKey, key)
	if err != nil {
		log.Fatalf("tls_kem_proxy: create local listener cert: %v", err)
	}
	keyDER, err := x509.MarshalECPrivateKey(key)
	if err != nil {
		log.Fatalf("tls_kem_proxy: marshal local listener key: %v", err)
	}
	certPEM := pem.EncodeToMemory(&pem.Block{Type: "CERTIFICATE", Bytes: der})
	keyPEM := pem.EncodeToMemory(&pem.Block{Type: "EC PRIVATE KEY", Bytes: keyDER})
	cert, err := tls.X509KeyPair(certPEM, keyPEM)
	if err != nil {
		log.Fatalf("tls_kem_proxy: load local listener cert: %v", err)
	}
	return cert
}

// runStub answers every incoming request immediately with a small, fixed,
// valid HTTP response -- reading and discarding the body first, mirroring
// the one piece of per-request work a real relay can't skip, so the
// isolated number this produces is a fair floor for "cost of this process
// existing," not an artificially cheaper one.
func runStub(listen string, localTLSConfig *tls.Config) {
	mux := http.NewServeMux()
	mux.HandleFunc("/", func(w http.ResponseWriter, r *http.Request) {
		_, _ = io.Copy(io.Discard, r.Body)
		w.Header().Set("Content-Type", "application/json")
		w.WriteHeader(http.StatusOK)
		_, _ = w.Write([]byte(`{}`))
	})
	server := &http.Server{Addr: listen, Handler: mux, TLSConfig: localTLSConfig}
	log.Printf("tls_kem_proxy: stub mode on %s (echo only, gateway never contacted)", listen)
	log.Fatal(server.ListenAndServeTLS("", ""))
}

func runRelay(listen, target, certPath, keyPath, curveName string, localTLSConfig *tls.Config) {
	cert, err := tls.LoadX509KeyPair(certPath, keyPath)
	if err != nil {
		log.Fatalf("tls_kem_proxy: load client cert %s/%s: %v", certPath, keyPath, err)
	}

	// "classical" exists for the T_fluxo isolation baseline (thesis/
	// results/v6/Level 1/DECISIONS.md): same proxy, same two-hop
	// architecture, same client cert -- only the curve differs -- so the
	// KEM's own latency cost can be separated from the cost of the proxy
	// hop existing at all, mirroring how the Go-clássico handshake_bytes
	// baseline already isolates the same variable for size.
	var curvePreferences []tls.CurveID
	minVersion := uint16(tls.VersionTLS13)
	switch curveName {
	case "classical":
		curvePreferences = []tls.CurveID{tls.CurveP521, tls.CurveP384, tls.CurveP256}
		minVersion = tls.VersionTLS12 // matches the gateway's own Classic floor; still negotiates 1.3 in practice
	case "mlkem1024":
		curvePreferences = []tls.CurveID{tls.MLKEM1024}
	case "x25519mlkem768":
		curvePreferences = []tls.CurveID{tls.X25519MLKEM768}
	default:
		log.Fatalf("tls_kem_proxy: unknown -curve %q (want classical, mlkem1024, or x25519mlkem768)", curveName)
	}

	// InsecureSkipVerify: this lab's gateway presents a self-signed chain
	// under its own local CA -- opin_flow.py's own do_call() already
	// connects with verify=False for the same reason (thesis/scripts/
	// opin_flow.py's do_call() signature), so this matches existing
	// practice rather than loosening it further. CurvePreferences
	// deliberately lists only the intended group(s) for this run: no
	// mixing classical and KEM together, so an incompatible peer fails the
	// handshake visibly instead of silently downgrading.
	upstreamTLSConfig := &tls.Config{
		Certificates:       []tls.Certificate{cert},
		InsecureSkipVerify: true,
		MinVersion:         minVersion,
		CurvePreferences:   curvePreferences,
	}
	if curveName == "classical" {
		// The gateway only accepts classical-only curves while
		// CRYPTO_PROFILE=pqc/hybrid on the matls-api.local SNI carve-out
		// (mock_mtls's GetConfigForClient, Decision 1) -- any other SNI
		// gets the profile's own KEM-only requirement and would reject
		// this client outright. tls.Dial would otherwise default SNI to
		// the literal dial target ("mtls"), which does not match. This
		// only overrides the TLS-layer SNI; the actual HTTP Host header
		// inside (auth.local/api.local/...) still travels through
		// unmodified, since this proxy never parses HTTP -- gateway
		// routing is unaffected.
		upstreamTLSConfig.ServerName = "matls-api.local"
	}

	ln, err := tls.Listen("tcp", listen, localTLSConfig)
	if err != nil {
		log.Fatalf("tls_kem_proxy: listen %s: %v", listen, err)
	}
	log.Printf("tls_kem_proxy: relay mode on %s -> %s (curve=%s)", listen, target, curveName)

	for {
		client, err := ln.Accept()
		if err != nil {
			log.Printf("tls_kem_proxy: accept: %v", err)
			continue
		}
		go handleConn(client, target, upstreamTLSConfig)
	}
}

// handleConn is the one-connection-in, one-mTLS-connection-out tunnel:
// exactly one upstream handshake per accepted (already locally-TLS-
// terminated) connection, reused via plain io.Copy piping for every
// request Python sends over that same connection -- never a new handshake
// per HTTP call.
func handleConn(client net.Conn, target string, tlsConfig *tls.Config) {
	defer client.Close()

	upstream, err := tls.Dial("tcp", target, tlsConfig)
	if err != nil {
		log.Printf("tls_kem_proxy: dial upstream %s: %v", target, err)
		return
	}
	defer upstream.Close()

	cs := upstream.ConnectionState()
	log.Printf("tls_kem_proxy: upstream handshake complete version=%s curve=%s cipher=%s",
		tls.VersionName(cs.Version), cs.CurveID.String(), tls.CipherSuiteName(cs.CipherSuite))

	done := make(chan struct{}, 2)
	go func() {
		_, _ = io.Copy(upstream, client)
		_ = upstream.Close()
		done <- struct{}{}
	}()
	go func() {
		_, _ = io.Copy(client, upstream)
		_ = client.Close()
		done <- struct{}{}
	}()
	<-done
	<-done
}
