// proxy is the v9, T5, Fase 1 integration harness's client side -- a
// fork of thesis/scripts/tls_kem_proxy/main.go (origin commit
// a304d6980422e6a264d990302fd319b4862693ee), built against the patched
// go1.27.3 toolchain from thesis/results/v9/toolchain (the AND dual-
// certificate mechanism).
//
// SCOPE (see gateway/main.go's own header and DECISIONS.md, Decisao 12):
// the origin's actual job -- relaying opin_flow.py's local Python/OpenSSL
// TLS connection to a real mTLS connection, because Python can't negotiate
// the ML-KEM hybrid groups -- has no Python component to relay for in T5
// (no Python code runs in this harness). This fork keeps the origin's TLS-
// dial logic (cert/curve selection per profile, no local Python-facing
// listener) and performs one real HTTP-over-mTLS request directly, to
// prove the mechanism end to end: dial, verify the server, present the
// right client cert, negotiate exactly one KEX group, and (hibrido-and
// only) confirm DualAuthenticated=true. Re-integrating the local relay
// listener for the real opin_flow.py flow is T6/T8 work, not T5's.
package main

import (
	"crypto/tls"
	"crypto/x509"
	"flag"
	"fmt"
	"io"
	"log"
	"net/http"
	"os"
	"path/filepath"
)

var expectedCurve = map[string]tls.CurveID{
	"classico":    tls.CurveP384,
	"pqc":         tls.MLKEM1024,
	"hibrido-v8":  tls.SecP384r1MLKEM1024,
	"hibrido-and": tls.SecP384r1MLKEM1024,
}

func main() {
	profile := flag.String("profile", "", "classico|pqc|hibrido-v8|hibrido-and")
	certDir := flag.String("cert-dir", "/certs", "directory holding the certs make certs generated")
	target := flag.String("target", "mtls:443", "gateway address, host:port")
	flag.Parse()

	want, ok := expectedCurve[*profile]
	if !ok {
		log.Fatalf("proxy: unknown -profile %q (want classico, pqc, hibrido-v8, hibrido-and)", *profile)
	}

	cfg, err := buildClientTLSConfig(*profile, *certDir)
	if err != nil {
		log.Fatalf("proxy: %s: building TLS config: %v", *profile, err)
	}

	client := &http.Client{Transport: &http.Transport{TLSClientConfig: cfg}}

	resp, err := client.Get("https://" + *target + "/")
	if err != nil {
		log.Fatalf("proxy: %s: request to %s failed: %v", *profile, *target, err)
	}
	defer resp.Body.Close()
	body, _ := io.ReadAll(resp.Body)

	cs := resp.TLS
	if cs == nil {
		log.Fatalf("proxy: %s: response has no TLS connection state", *profile)
	}

	if cs.CurveID != want {
		log.Fatalf("proxy: FATAL: %s negotiated group %s, expected exactly %s", *profile, cs.CurveID, want)
	}

	if *profile == "hibrido-and" && !cs.DualAuthenticated {
		log.Fatalf("proxy: FATAL: %s DualAuthenticated=false on the client side", *profile)
	}

	if resp.StatusCode != http.StatusOK {
		log.Fatalf("proxy: %s: gateway returned status %d: %s", *profile, resp.StatusCode, body)
	}

	log.Printf("proxy: %s OK curve=%s dualAuthenticated=%v tlsVersion=%s gatewayResponse=%s",
		*profile, cs.CurveID, cs.DualAuthenticated, tls.VersionName(cs.Version), body)
	// Machine-parseable result line for the orchestration script's report.
	fmt.Printf("RESULT profile=%s status=%d curve=%s dualAuthenticated=%v\n",
		*profile, resp.StatusCode, cs.CurveID.String(), cs.DualAuthenticated)
}

// buildClientTLSConfig dispatches on profile name. DIFF vs. the origin
// (tls_kem_proxy's runRelay): InsecureSkipVerify is gone -- RootCAs is set
// explicitly per profile instead, so the server chain is genuinely
// verified (explicit T5 requirement, "cliente verifica o servidor... sem
// InsecureSkipVerify"). ServerName is still pinned to "mtls" explicitly
// (same reasoning the origin already documents: independent of whatever
// -target resolves to). Adds the 4th profile, hibrido-and (Config.Dual),
// which the origin predates.
func buildClientTLSConfig(profile, certDir string) (*tls.Config, error) {
	p := func(name string) string { return filepath.Join(certDir, name) }

	switch profile {
	case "classico":
		return singleChainClientConfig(p("classico_client.crt"), p("classico_client.key"), p("classico_ca.crt"), tls.CurveP384, tls.VersionTLS12)
	case "pqc":
		return singleChainClientConfig(p("pqc_client.crt"), p("pqc_client.key"), p("pqc_ca.crt"), tls.MLKEM1024, tls.VersionTLS13)
	case "hibrido-v8":
		return singleChainClientConfig(p("hibrido_v8_client.crt"), p("hibrido_v8_client.key"), p("hibrido_v8_ca.crt"), tls.SecP384r1MLKEM1024, tls.VersionTLS13)
	case "hibrido-and":
		return dualClientConfig(certDir)
	default:
		return nil, fmt.Errorf("unknown profile %q", profile)
	}
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
		Certificates:           []tls.Certificate{rsaCert},
		RootCAs:                rsaRoots,
		ServerName:              "mtls",
		MinVersion:              tls.VersionTLS13,
		MaxVersion:              tls.VersionTLS13,
		CurvePreferences:        []tls.CurveID{tls.SecP384r1MLKEM1024},
		SessionTicketsDisabled:  true,
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
