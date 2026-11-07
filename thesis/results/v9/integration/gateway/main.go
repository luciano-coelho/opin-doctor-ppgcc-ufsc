// gateway is the v9, T5, Fase 1 integration harness's server side -- a
// fork of mock-service-os/mock_mtls/main.go (origin commit
// 478bda51815d8bf60ebd23fb83f592270aa04377), built against the patched
// go1.27.3 toolchain from thesis/results/v9/toolchain (the AND dual-
// certificate mechanism) instead of mock_mtls's own golang:1.27-rc base.
//
// SCOPE, decided with Luciano before writing this file (see
// DECISIONS.md, Decisao 12): fork lives entirely under thesis/results/v9,
// never touches mock-service-os/mock_mtls or thesis/scripts/tls_kem_proxy
// -- the files the already-frozen v7/v8 official data depend on. This
// harness proves the TLS-layer mechanism (per-profile cert/curve
// selection, mutual verification, the dual AND gate) integrates and
// negotiates correctly; it does NOT reimplement mock_mtls's OPIN business
// routing (reverse-proxy to auth/mockapi, SSA signing, token
// introspection) -- that depends on the live Node stack and is out of
// T5's scope (the full 44-HTTP-call flow is registered for the T8
// equivalence checklist, not re-proven here). See DECISIONS.md, Decisao
// 12, for the full diff against the origin commit.
package main

import (
	"crypto/tls"
	"crypto/x509"
	"fmt"
	"log"
	"net"
	"net/http"
	"os"
	"path/filepath"
)

// expectedCurve: the single KEX group each profile must negotiate, per
// Luciano's explicit T5 requirement -- read back from
// ConnectionState.CurveID on every request and failed loudly on mismatch,
// not just configured as a preference and trusted blindly.
var expectedCurve = map[string]tls.CurveID{
	"classico":    tls.CurveP384,
	"pqc":         tls.MLKEM1024,
	"hibrido-v8":  tls.SecP384r1MLKEM1024,
	"hibrido-and": tls.SecP384r1MLKEM1024,
}

func main() {
	profile := os.Getenv("CRYPTO_PROFILE")
	certDir := envOr("CERT_DIR", "/certs")
	listen := envOr("LISTEN", ":443")

	if _, ok := expectedCurve[profile]; !ok {
		log.Fatalf("gateway: unknown CRYPTO_PROFILE %q (want classico, pqc, hibrido-v8, hibrido-and)", profile)
	}

	cfg, err := buildServerTLSConfig(profile, certDir)
	if err != nil {
		log.Fatalf("gateway: %s: building TLS config: %v", profile, err)
	}

	mux := http.NewServeMux()
	mux.HandleFunc("/", func(w http.ResponseWriter, r *http.Request) {
		cs := r.TLS
		if cs == nil {
			http.Error(w, "no TLS state on request", http.StatusInternalServerError)
			return
		}

		if want := expectedCurve[profile]; cs.CurveID != want {
			msg := fmt.Sprintf("FATAL: negotiated group %s, expected exactly %s for profile %s", cs.CurveID, want, profile)
			log.Println("gateway:", msg)
			http.Error(w, msg, http.StatusInternalServerError)
			return
		}

		if profile == "hibrido-and" && !cs.DualAuthenticated {
			msg := "FATAL: DualAuthenticated=false on the server side for hibrido-and"
			log.Println("gateway:", msg)
			http.Error(w, msg, http.StatusInternalServerError)
			return
		}

		w.Header().Set("Content-Type", "application/json")
		fmt.Fprintf(w, `{"profile":%q,"curve":%q,"dualAuthenticated":%t,"tlsVersion":%q,"peerCertCount":%d}`,
			profile, cs.CurveID.String(), cs.DualAuthenticated, tls.VersionName(cs.Version), len(cs.PeerCertificates))
		log.Printf("gateway: %s OK curve=%s dualAuthenticated=%v tlsVersion=%s peerCerts=%d",
			profile, cs.CurveID, cs.DualAuthenticated, tls.VersionName(cs.Version), len(cs.PeerCertificates))
	})

	ln, err := net.Listen("tcp", listen)
	if err != nil {
		log.Fatalf("gateway: listen %s: %v", listen, err)
	}
	log.Printf("gateway: profile=%s listening on %s (expected group %s)", profile, listen, expectedCurve[profile])

	server := &http.Server{Handler: mux, TLSConfig: cfg}
	log.Fatal(server.Serve(tls.NewListener(ln, cfg)))
}

func envOr(key, fallback string) string {
	if v := os.Getenv(key); v != "" {
		return v
	}
	return fallback
}

// buildServerTLSConfig dispatches on profile name and builds the matching
// tls.Config. DIFF vs. the origin (mock_mtls's tlsConfiguration()):
//   - ClientAuth is tls.RequireAndVerifyClientCert in every profile here
//     (origin: tls.VerifyClientCertIfGiven, optional) -- explicit T5
//     requirement ("servidor usa RequireAndVerifyClientCert em todos os
//     perfis").
//   - the internalCallerConfig/GetConfigForClient carve-out for
//     matls-api.local (origin's Node-client reentrant-call workaround) is
//     removed -- this harness has no live auth/mockapi backend making
//     that call, so there is nothing for the carve-out to apply to.
//   - cert/key loading uses tls.LoadX509KeyPair (already the pattern
//     thesis/scripts/tls_kem_proxy's own client side uses, proven against
//     ML-DSA-65 keys there) instead of the origin's manual PEM-decode +
//     x509.ParsePKCS8PrivateKey -- simplification, not a behavior change.
//   - CA pool loading uses x509.CertPool.AppendCertsFromPEM (stdlib
//     built-in) instead of the origin's hand-rolled PEM-block loop --
//     same simplification.
//   - adds the 4th profile, hibrido-and, which the origin does not have
//     (it predates the AND mechanism): Config.Dual, both chains
//     independently verified, SessionTicketsDisabled explicit (the AND
//     patch's shouldSendSessionTickets already suppresses tickets
//     whenever Dual.Require is true, server-side -- this sets the field
//     too, belt-and-suspenders, matching the literal requirement text).
func buildServerTLSConfig(profile, certDir string) (*tls.Config, error) {
	p := func(name string) string { return filepath.Join(certDir, name) }

	switch profile {
	case "classico":
		return singleChainServerConfig(p("classico_server.crt"), p("classico_server.key"), p("classico_ca.crt"), tls.CurveP384, tls.VersionTLS12, nil)
	case "pqc":
		return singleChainServerConfig(p("pqc_server.crt"), p("pqc_server.key"), p("pqc_ca.crt"), tls.MLKEM1024, tls.VersionTLS13, nil)
	case "hibrido-v8":
		verify := hybridVerifyPeerCertificateFunc(p("hibrido_v8_ca_mldsa.crt"))
		return singleChainServerConfig(p("hibrido_v8_server.crt"), p("hibrido_v8_server.key"), p("hibrido_v8_ca.crt"), tls.SecP384r1MLKEM1024, tls.VersionTLS13, verify)
	case "hibrido-and":
		return dualServerConfig(certDir)
	default:
		return nil, fmt.Errorf("unknown profile %q", profile)
	}
}

func singleChainServerConfig(certPath, keyPath, caPath string, curve tls.CurveID, minVersion uint16, verifyPeer func([][]byte, [][]*x509.Certificate) error) (*tls.Config, error) {
	cert, err := tls.LoadX509KeyPair(certPath, keyPath)
	if err != nil {
		return nil, fmt.Errorf("load server cert/key (%s/%s): %w", certPath, keyPath, err)
	}
	clientCAs, err := loadCAPool(caPath)
	if err != nil {
		return nil, fmt.Errorf("load client CA pool (%s): %w", caPath, err)
	}
	return &tls.Config{
		Certificates:          []tls.Certificate{cert},
		ClientCAs:             clientCAs,
		ClientAuth:            tls.RequireAndVerifyClientCert,
		MinVersion:            minVersion,
		MaxVersion:            tls.VersionTLS13,
		CurvePreferences:      []tls.CurveID{curve},
		VerifyPeerCertificate: verifyPeer,
	}, nil
}

func dualServerConfig(certDir string) (*tls.Config, error) {
	p := func(name string) string { return filepath.Join(certDir, name) }

	rsaCert, err := tls.LoadX509KeyPair(p("hibrido_and_rsa_server.crt"), p("hibrido_and_rsa_server.key"))
	if err != nil {
		return nil, fmt.Errorf("load RSA server cert/key: %w", err)
	}
	rsaClientCAs, err := loadCAPool(p("hibrido_and_rsa_ca.crt"))
	if err != nil {
		return nil, fmt.Errorf("load RSA client CA pool: %w", err)
	}
	mldsaCert, err := tls.LoadX509KeyPair(p("hibrido_and_mldsa_server.crt"), p("hibrido_and_mldsa_server.key"))
	if err != nil {
		return nil, fmt.Errorf("load ML-DSA-65 server cert/key: %w", err)
	}
	mldsaClientCAs, err := loadCAPool(p("hibrido_and_mldsa_ca.crt"))
	if err != nil {
		return nil, fmt.Errorf("load ML-DSA-65 client CA pool: %w", err)
	}

	return &tls.Config{
		Certificates:           []tls.Certificate{rsaCert},
		ClientCAs:               rsaClientCAs,
		ClientAuth:              tls.RequireAndVerifyClientCert,
		MinVersion:              tls.VersionTLS13,
		MaxVersion:              tls.VersionTLS13,
		CurvePreferences:        []tls.CurveID{tls.SecP384r1MLKEM1024},
		SessionTicketsDisabled:  true,
		Dual: &tls.DualConfig{
			Certificates: []tls.Certificate{mldsaCert},
			ClientCAs:    mldsaClientCAs,
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
