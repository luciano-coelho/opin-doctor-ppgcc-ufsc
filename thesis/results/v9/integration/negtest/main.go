// negtest runs the negative tests that close v8's validity gaps #2
// and #3 (DECISIONS.md, Decisao 16, item (b)) against the v9
// integration harness's REAL running gateway/proxy binaries -- not
// just the Go unit test suite (dual_test.go already covers (iv) for
// Hibrido-AND specifically; this exercises it, and the other three
// scenarios, through the actual TLS stack the v9 gateway/proxy use,
// across all 4 profiles).
package main

import (
	"crypto/mldsa"
	"crypto/rand"
	"crypto/rsa"
	"crypto/tls"
	"crypto/x509"
	"crypto/x509/pkix"
	"flag"
	"fmt"
	"log"
	"math/big"
	"net"
	"os"
	"path/filepath"
	"time"
)

var expectedCurve = map[string]tls.CurveID{
	"classico":    tls.CurveP384,
	"pqc":         tls.MLKEM1024,
	"hibrido-v8":  tls.SecP384r1MLKEM1024,
	"hibrido-and": tls.SecP384r1MLKEM1024,
}

func main() {
	scenario := flag.String("scenario", "", "no-client-cert|untrusted-client-ca|untrusted-server-ca|wrong-san|and-single-chain|matrix")
	profile := flag.String("profile", "", "classico|pqc|hibrido-v8|hibrido-and")
	target := flag.String("target", "mtls:443", "gateway address, host:port")
	certDir := flag.String("cert-dir", "/certs", "directory holding the certs make certs generated")
	clientMode := flag.String("client-mode", "", "matrix scenario only: classico|pqc|hibrido-v8|hibrido-and-strict|hibrido-and-nonstrict")
	serverMode := flag.String("server-mode", "", "matrix scenario only, label for the RESULT line only")
	flag.Parse()

	if *scenario == "matrix" {
		runMatrixProbe(*clientMode, *serverMode, *certDir, *target)
		return
	}

	if _, ok := expectedCurve[*profile]; !ok {
		log.Fatalf("negtest: unknown -profile %q", *profile)
	}

	var err error
	switch *scenario {
	case "no-client-cert":
		err = tryNoClientCert(*profile, *certDir, *target)
	case "untrusted-client-ca":
		err = tryUntrustedClientCA(*profile, *certDir, *target)
	case "untrusted-server-ca":
		err = tryUntrustedServerCA(*profile, *certDir, *target)
	case "wrong-san":
		err = tryWrongSAN(*profile, *certDir, *target)
	case "and-single-chain":
		if *profile != "hibrido-and" {
			log.Fatalf("negtest: and-single-chain only applies to hibrido-and")
		}
		err = tryANDSingleChain(*certDir, *target)
	case "and-bad-classical":
		if *profile != "hibrido-and" {
			log.Fatalf("negtest: and-bad-classical only applies to hibrido-and")
		}
		err = tryANDBadClassical(*certDir, *target)
	case "and-bad-pqc":
		if *profile != "hibrido-and" {
			log.Fatalf("negtest: and-bad-pqc only applies to hibrido-and")
		}
		err = tryANDBadPQC(*certDir, *target)
	default:
		log.Fatalf("negtest: unknown -scenario %q", *scenario)
	}

	if err == nil {
		fmt.Printf("RESULT scenario=%s profile=%s outcome=UNEXPECTED_SUCCESS error=none\n", *scenario, *profile)
		os.Exit(1)
	}
	fmt.Printf("RESULT scenario=%s profile=%s outcome=REJECTED error=%q\n", *scenario, *profile, err.Error())
}

// runMatrixProbe builds a client config for one of the 5 modes the T7
// interoperability matrix (DECISIONS.md, Decisao 19) covers, dials
// -target once, and reports what actually happened -- never exits
// non-zero on its own, since for this scenario both success AND
// failure are informative outcomes, not a pass/fail signal by
// themselves.
func runMatrixProbe(clientMode, serverMode, certDir, target string) {
	cfg, err := buildMatrixClientConfig(clientMode, certDir)
	if err != nil {
		fmt.Printf("RESULT matrix client=%s server=%s outcome=CONFIG_ERROR curve= dualAuthenticated=false error=%q\n", clientMode, serverMode, err.Error())
		return
	}
	conn, err := net.DialTimeout("tcp", target, 5*time.Second)
	if err != nil {
		fmt.Printf("RESULT matrix client=%s server=%s outcome=FAIL curve= dualAuthenticated=false error=%q\n", clientMode, serverMode, err.Error())
		return
	}
	defer conn.Close()
	tlsConn := tls.Client(conn, cfg)
	hsErr := tlsConn.Handshake()
	var cs tls.ConnectionState
	if hsErr == nil {
		cs = tlsConn.ConnectionState()
		// Same delayed-alert check as dial() -- a client-side
		// Handshake() success can still be followed by a server
		// rejection in TLS 1.3 (see dial()'s own comment).
		_ = conn.SetReadDeadline(time.Now().Add(2 * time.Second))
		buf := make([]byte, 1)
		_, readErr := tlsConn.Read(buf)
		if readErr != nil {
			if nerr, ok := readErr.(net.Error); !ok || !nerr.Timeout() {
				hsErr = fmt.Errorf("post-handshake rejection: %w", readErr)
			}
		}
	}
	if hsErr != nil {
		fmt.Printf("RESULT matrix client=%s server=%s outcome=FAIL curve=%s dualAuthenticated=%v error=%q\n",
			clientMode, serverMode, cs.CurveID, cs.DualAuthenticated, hsErr.Error())
		return
	}
	fmt.Printf("RESULT matrix client=%s server=%s outcome=SUCCESS curve=%s dualAuthenticated=%v error=none\n",
		clientMode, serverMode, cs.CurveID, cs.DualAuthenticated)
}

// buildMatrixClientConfig: classico/pqc/hibrido-v8 reuse baseConfig
// unchanged; the two Hibrido-AND variants differ only in Dual.Require,
// isolating that one variable the same way gateway/main.go's STRICT
// env var does server-side.
func buildMatrixClientConfig(mode, certDir string) (*tls.Config, error) {
	switch mode {
	case "classico", "pqc", "hibrido-v8":
		return baseConfig(mode, certDir), nil
	case "hibrido-and-strict":
		cfg := baseConfig("hibrido-and", certDir)
		cfg.Dual.Require = true
		return cfg, nil
	case "hibrido-and-nonstrict":
		cfg := baseConfig("hibrido-and", certDir)
		cfg.Dual.Require = false
		return cfg, nil
	default:
		return nil, fmt.Errorf("unknown client-mode %q", mode)
	}
}

func p(dir, name string) string { return filepath.Join(dir, name) }

func classicalCertKeyFiles(profile string) (cert, key, ca string) {
	switch profile {
	case "classico":
		return "classico_client.crt", "classico_client.key", "classico_ca.crt"
	case "pqc":
		return "pqc_client.crt", "pqc_client.key", "pqc_ca.crt"
	case "hibrido-v8":
		return "hibrido_v8_client.crt", "hibrido_v8_client.key", "hibrido_v8_ca.crt"
	case "hibrido-and":
		return "hibrido_and_rsa_client.crt", "hibrido_and_rsa_client.key", "hibrido_and_rsa_ca.crt"
	}
	return "", "", ""
}

func loadCAPool(path string) *x509.CertPool {
	b, err := os.ReadFile(path)
	if err != nil {
		log.Fatalf("negtest: read %s: %v", path, err)
	}
	pool := x509.NewCertPool()
	if !pool.AppendCertsFromPEM(b) {
		log.Fatalf("negtest: no certs in %s", path)
	}
	return pool
}

// baseConfig builds a CORRECT config for the profile (valid client
// cert, valid RootCAs, right curve, right ServerName) -- each scenario
// starts here and corrupts exactly one thing, so a rejection can only
// be attributed to that one change.
func baseConfig(profile, certDir string) *tls.Config {
	certFile, keyFile, caFile := classicalCertKeyFiles(profile)
	cert, err := tls.LoadX509KeyPair(p(certDir, certFile), p(certDir, keyFile))
	if err != nil {
		log.Fatalf("negtest: load %s/%s: %v", certFile, keyFile, err)
	}
	cfg := &tls.Config{
		Certificates:     []tls.Certificate{cert},
		RootCAs:          loadCAPool(p(certDir, caFile)),
		ServerName:       "mtls",
		MinVersion:       tls.VersionTLS12,
		MaxVersion:       tls.VersionTLS13,
		CurvePreferences: []tls.CurveID{expectedCurve[profile]},
	}
	if profile == "hibrido-and" {
		mldsaCert, err := tls.LoadX509KeyPair(p(certDir, "hibrido_and_mldsa_client.crt"), p(certDir, "hibrido_and_mldsa_client.key"))
		if err != nil {
			log.Fatalf("negtest: load hibrido_and_mldsa_client: %v", err)
		}
		cfg.Dual = &tls.DualConfig{
			Certificates: []tls.Certificate{mldsaCert},
			RootCAs:      loadCAPool(p(certDir, "hibrido_and_mldsa_ca.crt")),
			Require:      true,
		}
	}
	return cfg
}

// dial does NOT stop at a successful Handshake(): TLS 1.3's client
// finishes its own handshake (sends Finished) and can report success
// locally BEFORE the server finishes validating the client's
// Certificate/CertificateVerify and sends back a rejection alert --
// the same asymmetry this project's own dual_test.go already
// documented and worked around (dualHandshakePipe's bounded
// follow-up Read). A negative test that only checked Handshake()'s
// own return value would silently miss every rejection that arrives
// this way -- confirmed live, the first time this ran without the
// read below: no-client-cert and untrusted-client-ca both reported
// UNEXPECTED_SUCCESS for classico/pqc/hibrido-v8, which is wrong --
// the server DOES reject all of them, the client just has to read
// once more to see it.
func dial(cfg *tls.Config, target string) error {
	conn, err := net.DialTimeout("tcp", target, 5*time.Second)
	if err != nil {
		return fmt.Errorf("tcp dial: %w", err)
	}
	defer conn.Close()
	tlsConn := tls.Client(conn, cfg)
	if err := tlsConn.Handshake(); err != nil {
		return err
	}
	cs := tlsConn.ConnectionState()
	fmt.Printf("DEBUG raw-handshake-succeeded curve=%s dualAuthenticated=%v tlsVersion=%s\n", cs.CurveID, cs.DualAuthenticated, tls.VersionName(cs.Version))
	_ = conn.SetReadDeadline(time.Now().Add(2 * time.Second))
	buf := make([]byte, 1)
	_, err = tlsConn.Read(buf)
	if err == nil {
		return nil // genuinely accepted: server sent real data back
	}
	if nerr, ok := err.(net.Error); ok && nerr.Timeout() {
		return nil // no alert arrived within the window: genuinely accepted
	}
	return fmt.Errorf("handshake reported success but a server-side rejection followed: %w", err)
}

// (i) client with no client certificate at all -- RequireAndVerifyClientCert
// on the gateway must refuse it.
func tryNoClientCert(profile, certDir, target string) error {
	cfg := baseConfig(profile, certDir)
	cfg.Certificates = nil
	cfg.Dual = nil // hibrido-and: omit the PQ half too, not just the classical one
	return dial(cfg, target)
}

// (ii) client certificate signed by a CA the gateway never trusts.
// For hibrido-and specifically tests the CLASSICAL half untrusted
// (the PQ half stays real/valid) -- isolates that the classical
// chain's own independent verification catches it.
func tryUntrustedClientCA(profile, certDir, target string) error {
	cfg := baseConfig(profile, certDir)
	if profile == "pqc" {
		cfg.Certificates = []tls.Certificate{attackerMLDSACert()}
	} else {
		cfg.Certificates = []tls.Certificate{attackerRSACert()}
	}
	return dial(cfg, target)
}

// (iii) server certificate the client doesn't trust -- simulated by
// trusting only an unrelated attacker CA instead of the real one.
func tryUntrustedServerCA(profile, certDir, target string) error {
	cfg := baseConfig(profile, certDir)
	attackerCA := x509.NewCertPool()
	attackerCA.AddCert(attackerSelfSignedCA())
	cfg.RootCAs = attackerCA
	if cfg.Dual != nil {
		pqAttackerCA := x509.NewCertPool()
		pqAttackerCA.AddCert(attackerSelfSignedCA())
		cfg.Dual.RootCAs = pqAttackerCA
	}
	return dial(cfg, target)
}

// (iii, variant) server certificate's SAN doesn't match what the
// client expects -- real RootCAs, wrong ServerName.
func tryWrongSAN(profile, certDir, target string) error {
	cfg := baseConfig(profile, certDir)
	cfg.ServerName = "not-a-real-san.invalid"
	return dial(cfg, target)
}

// (iv) Hibrido-AND, strict mode: present ONLY the classical (RSA)
// chain, omit Dual entirely -- a single-chain adversary holding just
// the RSA key must not authenticate. Mirrors dual_test.go's
// TestDualClientMissingPQChain, exercised here against the real
// running gateway binary instead of the in-process unit test.
func tryANDSingleChain(certDir, target string) error {
	cfg := baseConfig("hibrido-and", certDir)
	cfg.Dual = nil
	return dial(cfg, target)
}

// (v) Decisao 52 (pedido independente, item 2a): o par duplo esta
// PRESENTE (Dual continua setado, Require=true) mas a metade
// CLASSICA e de um atacante sem nenhuma relacao com as CAs reais da
// v9 -- a metade PQC continua genuina. O gate AND precisa recusar
// mesmo assim (as DUAS metades tem que verificar E bater na mesma
// identidade, nao so "ambas presentes").
func tryANDBadClassical(certDir, target string) error {
	cfg := baseConfig("hibrido-and", certDir)
	cfg.Certificates = []tls.Certificate{attackerRSACert()}
	return dial(cfg, target)
}

// (vi) espelho de (v): metade PQC de um atacante, metade classica
// genuina.
func tryANDBadPQC(certDir, target string) error {
	cfg := baseConfig("hibrido-and", certDir)
	cfg.Dual.Certificates = []tls.Certificate{attackerMLDSACert()}
	return dial(cfg, target)
}

var attackerSerial int64 = 1

func nextAttackerSerial() *big.Int {
	attackerSerial++
	return big.NewInt(attackerSerial)
}

// attackerSelfSignedCA: a fresh RSA-2048 CA with no relationship to
// any of v9's real CAs -- reused as the CA for attackerRSACert() and
// as a fake "server CA" the client is told to trust in
// tryUntrustedServerCA.
func attackerSelfSignedCA() *x509.Certificate {
	cert, _ := attackerRSACAWithKey()
	return cert
}

func attackerRSACAWithKey() (*x509.Certificate, *rsa.PrivateKey) {
	key, err := rsa.GenerateKey(rand.Reader, 2048)
	if err != nil {
		log.Fatalf("negtest: generate attacker RSA CA key: %v", err)
	}
	tmpl := &x509.Certificate{
		SerialNumber:          nextAttackerSerial(),
		Subject:                pkix.Name{CommonName: "negtest-attacker-ca"},
		NotBefore:              time.Now().Add(-time.Hour),
		NotAfter:               time.Now().Add(24 * time.Hour),
		KeyUsage:               x509.KeyUsageCertSign | x509.KeyUsageDigitalSignature,
		BasicConstraintsValid:  true,
		IsCA:                   true,
	}
	der, err := x509.CreateCertificate(rand.Reader, tmpl, tmpl, &key.PublicKey, key)
	if err != nil {
		log.Fatalf("negtest: create attacker RSA CA: %v", err)
	}
	cert, err := x509.ParseCertificate(der)
	if err != nil {
		log.Fatalf("negtest: parse attacker RSA CA: %v", err)
	}
	return cert, key
}

// attackerRSACert: a leaf signed by attackerSelfSignedCA() -- valid
// shape, wrong (unrelated, untrusted) issuer.
func attackerRSACert() tls.Certificate {
	caCert, caKey := attackerRSACAWithKey()
	leafKey, err := rsa.GenerateKey(rand.Reader, 2048)
	if err != nil {
		log.Fatalf("negtest: generate attacker leaf key: %v", err)
	}
	tmpl := &x509.Certificate{
		SerialNumber: nextAttackerSerial(),
		Subject:      pkix.Name{CommonName: "negtest-attacker-leaf"},
		NotBefore:    time.Now().Add(-time.Hour),
		NotAfter:     time.Now().Add(24 * time.Hour),
		KeyUsage:     x509.KeyUsageDigitalSignature,
		ExtKeyUsage:  []x509.ExtKeyUsage{x509.ExtKeyUsageClientAuth},
	}
	der, err := x509.CreateCertificate(rand.Reader, tmpl, caCert, &leafKey.PublicKey, caKey)
	if err != nil {
		log.Fatalf("negtest: create attacker leaf: %v", err)
	}
	return tls.Certificate{Certificate: [][]byte{der}, PrivateKey: leafKey}
}

// attackerMLDSACert: same idea, ML-DSA-65 key material, for the pqc
// profile's client-cert-rejection test.
func attackerMLDSACert() tls.Certificate {
	caKey, err := mldsa.GenerateKey(mldsa.MLDSA65())
	if err != nil {
		log.Fatalf("negtest: generate attacker ML-DSA CA key: %v", err)
	}
	caTmpl := &x509.Certificate{
		SerialNumber:          nextAttackerSerial(),
		Subject:                pkix.Name{CommonName: "negtest-attacker-mldsa-ca"},
		NotBefore:              time.Now().Add(-time.Hour),
		NotAfter:               time.Now().Add(24 * time.Hour),
		KeyUsage:               x509.KeyUsageCertSign | x509.KeyUsageDigitalSignature,
		BasicConstraintsValid:  true,
		IsCA:                   true,
	}
	caDER, err := x509.CreateCertificate(rand.Reader, caTmpl, caTmpl, caKey.PublicKey(), caKey)
	if err != nil {
		log.Fatalf("negtest: create attacker ML-DSA CA: %v", err)
	}
	caCert, err := x509.ParseCertificate(caDER)
	if err != nil {
		log.Fatalf("negtest: parse attacker ML-DSA CA: %v", err)
	}

	leafKey, err := mldsa.GenerateKey(mldsa.MLDSA65())
	if err != nil {
		log.Fatalf("negtest: generate attacker ML-DSA leaf key: %v", err)
	}
	leafTmpl := &x509.Certificate{
		SerialNumber: nextAttackerSerial(),
		Subject:      pkix.Name{CommonName: "negtest-attacker-mldsa-leaf"},
		NotBefore:    time.Now().Add(-time.Hour),
		NotAfter:     time.Now().Add(24 * time.Hour),
		KeyUsage:     x509.KeyUsageDigitalSignature,
		ExtKeyUsage:  []x509.ExtKeyUsage{x509.ExtKeyUsageClientAuth},
	}
	leafDER, err := x509.CreateCertificate(rand.Reader, leafTmpl, caCert, leafKey.PublicKey(), caKey)
	if err != nil {
		log.Fatalf("negtest: create attacker ML-DSA leaf: %v", err)
	}
	return tls.Certificate{Certificate: [][]byte{leafDER}, PrivateKey: leafKey}
}
