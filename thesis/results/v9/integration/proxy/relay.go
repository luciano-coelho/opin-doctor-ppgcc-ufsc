// relay.go adds persistent relay mode to the v9 proxy, for T6b (full
// local flow): opin_flow.py (Python/OpenSSL) cannot negotiate the
// ML-KEM/hybrid groups the v9 gateway requires, same reason
// thesis/scripts/tls_kem_proxy exists at all (see that file's own
// header comment). This mirrors its two-hop design (terminate a local,
// throwaway-cert TLS connection from Python, open one real mTLS
// connection upstream per accepted local connection, pipe bytes both
// ways) adapted for the v9 harness's 4 profiles, including hibrido-and
// (the real tls_kem_proxy predates the AND mechanism and has no
// equivalent). See DECISIONS.md, Decisao 17, for why this is a
// separate v9-specific relay rather than a change to the real
// tls_kem_proxy: that file is what the frozen v7/v8 data depends on,
// and the v9 gateway's own certs (Decisao 9/10/11) are not the ones
// tls_kem_proxy is hardcoded to present.
package main

import (
	"crypto/ecdsa"
	"crypto/elliptic"
	"crypto/rand"
	"crypto/tls"
	"crypto/x509"
	"crypto/x509/pkix"
	"encoding/pem"
	"io"
	"log"
	"math/big"
	"net"
	"time"
)

func runRelay(listen, target, profile, certDir string) {
	cfg, err := buildClientTLSConfig(profile, certDir, true, nil)
	if err != nil {
		log.Fatalf("proxy relay: %s: building upstream TLS config: %v", profile, err)
	}

	localTLSConfig := &tls.Config{Certificates: []tls.Certificate{generateLocalListenerCert()}}
	ln, err := tls.Listen("tcp", listen, localTLSConfig)
	if err != nil {
		log.Fatalf("proxy relay: listen %s: %v", listen, err)
	}
	log.Printf("proxy relay: profile=%s listening on %s -> %s", profile, listen, target)

	for {
		client, err := ln.Accept()
		if err != nil {
			log.Printf("proxy relay: accept: %v", err)
			continue
		}
		go handleRelayConn(client, target, cfg, profile)
	}
}

// handleRelayConn: one accepted (already locally-TLS-terminated)
// connection in, exactly one real upstream mTLS connection out --
// matches tls_kem_proxy's own handleConn, same reasoning (preserves
// requests.Session's per-pool connection reuse 1:1 against real mTLS
// handshakes).
func handleRelayConn(client net.Conn, target string, cfg *tls.Config, profile string) {
	defer client.Close()

	upstream, err := tls.Dial("tcp", target, cfg)
	if err != nil {
		log.Printf("proxy relay: %s: dial upstream %s: %v", profile, target, err)
		return
	}
	defer upstream.Close()

	cs := upstream.ConnectionState()
	want := expectedCurve[profile]
	if cs.CurveID != want {
		log.Printf("proxy relay: FATAL: %s negotiated group %s, expected exactly %s -- closing connection", profile, cs.CurveID, want)
		return
	}
	if profile == "hibrido-and" && !cs.DualAuthenticated {
		log.Printf("proxy relay: FATAL: %s DualAuthenticated=false on the client side -- closing connection", profile)
		return
	}
	log.Printf("proxy relay: %s upstream handshake OK curve=%s dualAuthenticated=%v tlsVersion=%s",
		profile, cs.CurveID, cs.DualAuthenticated, tls.VersionName(cs.Version))

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

// generateLocalListenerCert: a fresh, throwaway self-signed ECDSA
// P-256 certificate for the Python-facing listener only, so
// opin_flow.py's requests library sees a real https:// endpoint with
// cookies carrying the Secure attribute intact -- same reasoning and
// same mechanism as tls_kem_proxy's own generateLocalListenerCert.
func generateLocalListenerCert() tls.Certificate {
	key, err := ecdsa.GenerateKey(elliptic.P256(), rand.Reader)
	if err != nil {
		log.Fatalf("proxy relay: generate local listener key: %v", err)
	}
	template := &x509.Certificate{
		SerialNumber: big.NewInt(1),
		Subject:      pkix.Name{CommonName: "v9 proxy relay (local, throwaway)"},
		NotBefore:    time.Now().Add(-time.Hour),
		NotAfter:     time.Now().Add(24 * time.Hour),
		KeyUsage:     x509.KeyUsageDigitalSignature,
		ExtKeyUsage:  []x509.ExtKeyUsage{x509.ExtKeyUsageServerAuth},
		DNSNames:     []string{"localhost"},
		IPAddresses:  []net.IP{net.ParseIP("127.0.0.1")},
	}
	der, err := x509.CreateCertificate(rand.Reader, template, template, &key.PublicKey, key)
	if err != nil {
		log.Fatalf("proxy relay: create local listener cert: %v", err)
	}
	keyDER, err := x509.MarshalECPrivateKey(key)
	if err != nil {
		log.Fatalf("proxy relay: marshal local listener key: %v", err)
	}
	certPEM := pem.EncodeToMemory(&pem.Block{Type: "CERTIFICATE", Bytes: der})
	keyPEM := pem.EncodeToMemory(&pem.Block{Type: "EC PRIVATE KEY", Bytes: keyDER})
	cert, err := tls.X509KeyPair(certPEM, keyPEM)
	if err != nil {
		log.Fatalf("proxy relay: load local listener cert: %v", err)
	}
	return cert
}
