// go_handshake_probe makes ONE real HTTPS request to the gateway and exits
// -- it exists solely to produce a single, controlled mTLS handshake whose
// byte count the gateway's own access log will report, using a chosen
// client certificate, SNI, and curve preference independently of each
// other. This is the tool behind the "Go-clássico" baseline (thesis/
// results/v6/Level 1/DECISIONS.md): the same Go TLS client `tls_kem_proxy`
// uses, configured with classical-only CurvePreferences instead of a KEM
// group, so handshake_bytes can be compared client-implementation-for-
// client-implementation against the profile's real KEM measurement --
// never against v5's Python-measured number, which is a different TLS
// stack entirely (see the DECISIONS.md entry for why that comparison is
// invalid).
//
// SNI deliberately defaults to "matls-api.local": that is the one hostname
// mock_mtls's GetConfigForClient (mock-service-os/mock_mtls/main.go) always
// answers with classical-only CurvePreferences, regardless of
// CRYPTO_PROFILE (Decision 1, this directory) -- offering only classical
// groups against any *other* SNI while the gateway runs pqc/hybrid would
// fail the handshake outright (no common group), by design (no silent
// downgrade). Presenting the profile's real external client certificate
// over that internal-carve-out SNI is an artificial combination that never
// occurs in the real system -- it exists here only to get a same-cert,
// same-client, classical-only data point for comparison. Never mistake a
// probe run for real traffic: it makes no attempt to look like a real
// participant's flow, is not counted in N_mTLS, and this tool is not part
// of the OPIN system it measures.
package main

import (
	"crypto/tls"
	"flag"
	"fmt"
	"io"
	"net/http"
	"os"
)

func main() {
	target := flag.String("target", "mtls:443", "gateway address, host:port")
	sni := flag.String("sni", "matls-api.local", "TLS SNI to send")
	hostHeader := flag.String("host", "auth.local", "HTTP Host header (gateway routing)")
	path := flag.String("path", "/jwks", "HTTP path to request")
	certPath := flag.String("cert", "", "client certificate PEM path")
	keyPath := flag.String("key", "", "client key PEM path")
	curveName := flag.String("curve", "classical", "classical, mlkem1024, or x25519mlkem768")
	flag.Parse()

	cfg := &tls.Config{InsecureSkipVerify: true, ServerName: *sni}
	if *certPath != "" {
		cert, err := tls.LoadX509KeyPair(*certPath, *keyPath)
		if err != nil {
			fmt.Println("load client cert:", err)
			os.Exit(1)
		}
		cfg.Certificates = []tls.Certificate{cert}
	}
	switch *curveName {
	case "classical":
		cfg.CurvePreferences = []tls.CurveID{tls.CurveP521, tls.CurveP384, tls.CurveP256}
	case "mlkem1024":
		cfg.MinVersion = tls.VersionTLS13
		cfg.CurvePreferences = []tls.CurveID{tls.MLKEM1024}
	case "x25519mlkem768":
		cfg.MinVersion = tls.VersionTLS13
		cfg.CurvePreferences = []tls.CurveID{tls.X25519MLKEM768}
	default:
		fmt.Println("unknown -curve", *curveName)
		os.Exit(1)
	}

	client := &http.Client{Transport: &http.Transport{TLSClientConfig: cfg}}
	req, _ := http.NewRequest("GET", "https://"+*target+*path, nil)
	req.Host = *hostHeader
	resp, err := client.Do(req)
	if err != nil {
		fmt.Println("request error:", err)
		os.Exit(1)
	}
	body, _ := io.ReadAll(resp.Body)
	resp.Body.Close()
	fmt.Printf("status=%d bodylen=%d sni=%s curve=%s\n", resp.StatusCode, len(body), *sni, *curveName)
}
