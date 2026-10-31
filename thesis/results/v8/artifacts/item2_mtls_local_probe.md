# Item 1 (round 5): local mTLS probe -- 3 profiles x 4 cases

Run against this project's own **local** docker-compose stack (the same
v7 lab environment, `insurance-server-lambdas`), **not** the destroyed
AWS fleet (Decision 117) -- per Luciano's own instruction, "sem tag, sem
frota." The gateway (`mtls` container) was switched between
`CRYPTO_PROFILE=classic/pqc/hybrid` via
`CRYPTO_PROFILE=<profile> docker compose --profile main up -d
--force-recreate --no-deps mtls`, and the probe below connected to it
from inside a `golang:1.27-rc-alpine` container, dialing
`host.docker.internal:443` (Docker Desktop's host-reachable DNS name) --
the exact same `crypto/tls` stack `tls_kem_proxy/main.go` uses for the
real campaign client, so MLKEM1024/SecP384r1MLKEM1024 negotiation for
PQC/Hybrid works automatically.

## Result

| Case | Classic | PQC | Hybrid |
|---|---|---|---|
| (a) Wrong-CA client cert | `REJECTED: tls: unknown certificate authority` | `REJECTED: tls: unknown certificate authority` | `REJECTED: tls: unknown certificate authority` |
| (b) Expired client cert | `REJECTED: tls: expired certificate` | `REJECTED: tls: expired certificate` | `REJECTED: tls: expired certificate` |
| (c) No client cert | `ACCEPTED` (anonymous; HTTP 401 on the probe's own bogus `GET /`) | `ACCEPTED` (anonymous) | `ACCEPTED` (anonymous) |
| (d) Valid client cert (real per-profile cert) | `ACCEPTED` (HTTP 401 on the probe's own bogus `GET /` -- same response as (c), unrelated to the cert) | `ACCEPTED` | `ACCEPTED` |

**Consistent across all three profiles, confirming Section 2 item 5's claim empirically, not just by reading the code:** the server's real chain-verification of the client's certificate (wrong-CA, expired) behaves identically regardless of `CRYPTO_PROFILE`, and a client presenting no certificate at all is accepted (`ClientAuth: VerifyClientCertIfGiven` is the optional level) -- **no result here contradicted Section 2 item 5; no text correction was needed from this test.**

## A real methodological pitfall found and fixed along the way (worth recording)

The first version of this probe reported **all four cases as `ACCEPTED`**
for every profile, including the wrong-CA and expired certs -- which
would have *contradicted* Section 2 item 5 and the server-side code read
there. Investigated directly rather than accepted at face value, two real
bugs were found, both in the probe itself, not in the gateway:

1. **TLS 1.3's own handshake shape.** Go's client-side `handshake()`
   (`handshake_client_tls13.go:46-160`) sends the client's own
   Certificate/CertificateVerify/Finished and marks the handshake complete
   **without ever reading anything back from the server** -- `tls.Dial()`
   returning success only means the probe's own outgoing flight was sent,
   not that the server accepted it. The server's `processCertsFromClient()`
   runs after receiving the client's Finished; any rejection only surfaces
   on a later `Read()`/`Write()`. Fixed by making the probe perform a real
   HTTP round-trip (`GET / HTTP/1.1`) immediately after `Dial()` succeeds,
   to force any already-queued fatal alert to arrive.
2. **Go's own client-side certificate filtering.** Even after fix 1, the
   wrong-CA case still showed `ACCEPTED`. Cause: the default
   `getClientCertificate()` (`handshake_client.go:1274`) runs
   `CertificateRequestInfo.SupportsCertificate()`, which matches the
   configured certificate's issuer against the server's own advertised
   `AcceptableCAs` (from its `ClientCAs`) -- and **silently sends an empty
   certificate instead** if nothing matches, rather than sending the
   mismatched cert and letting the server decide. Setting `cfg.Certificates`
   the normal way means the wrong-CA cert never reaches the wire at all.
   Fixed by using `cfg.GetClientCertificate` to force the configured
   (possibly-defective) certificate through unconditionally -- what an
   actual non-conforming or malicious client, or `openssl s_client`, would
   do, and what this test needs to see the server's real behavior.

Both fixes are already in the committed `probe.go` source below; the
table above is from the corrected version.

## Go source

`gencerts/main.go` (generates the two defect certs):

```go
// Generates the two "defect" client certificates: (a) wrong-CA, (b)
// expired. Both are plain RSA-2048 with clientAuth EKU -- deliberately
// NOT profile-specific, since the defect being tested (wrong trust
// anchor / expired validity) is checked by the SAME Go code path
// (processCertsFromClient) regardless of CRYPTO_PROFILE; the (d) valid
// case uses each profile's own real client cert from
// mock-service-os/certs/ instead.
package main

import (
	"crypto/rand"
	"crypto/rsa"
	"crypto/x509"
	"crypto/x509/pkix"
	"encoding/pem"
	"math/big"
	"os"
	"time"
)

func writePEM(path, blockType string, bytes []byte) {
	f, err := os.Create(path)
	if err != nil {
		panic(err)
	}
	defer f.Close()
	if err := pem.Encode(f, &pem.Block{Type: blockType, Bytes: bytes}); err != nil {
		panic(err)
	}
}

func loadRealCA(crtPath, keyPath string) (*x509.Certificate, *rsa.PrivateKey) {
	crtPEM, _ := os.ReadFile(crtPath)
	block, _ := pem.Decode(crtPEM)
	cert, err := x509.ParseCertificate(block.Bytes)
	if err != nil {
		panic(err)
	}
	keyPEM, _ := os.ReadFile(keyPath)
	kblock, _ := pem.Decode(keyPEM)
	keyAny, err := x509.ParsePKCS8PrivateKey(kblock.Bytes)
	if err != nil {
		panic(err)
	}
	return cert, keyAny.(*rsa.PrivateKey)
}

func main() {
	outDir, certsDir := "/out", "/certs"

	// (a) wrong-CA: a brand-new throwaway CA + leaf, never loaded into
	// mock_mtls's caCertPool().
	rogueCAKey, _ := rsa.GenerateKey(rand.Reader, 2048)
	rogueCATpl := &x509.Certificate{
		SerialNumber: big.NewInt(1), Subject: pkix.Name{CommonName: "rogue-test-ca"},
		NotBefore: time.Now().Add(-1 * time.Hour), NotAfter: time.Now().Add(24 * time.Hour),
		IsCA: true, KeyUsage: x509.KeyUsageCertSign | x509.KeyUsageDigitalSignature,
		BasicConstraintsValid: true,
	}
	rogueCADER, _ := x509.CreateCertificate(rand.Reader, rogueCATpl, rogueCATpl, &rogueCAKey.PublicKey, rogueCAKey)
	rogueCACert, _ := x509.ParseCertificate(rogueCADER)

	wrongCAKey, _ := rsa.GenerateKey(rand.Reader, 2048)
	wrongCALeafTpl := &x509.Certificate{
		SerialNumber: big.NewInt(2), Subject: pkix.Name{CommonName: "client_one_wrongca_test"},
		NotBefore: time.Now().Add(-1 * time.Hour), NotAfter: time.Now().Add(24 * time.Hour),
		KeyUsage: x509.KeyUsageDigitalSignature, ExtKeyUsage: []x509.ExtKeyUsage{x509.ExtKeyUsageClientAuth},
	}
	wrongCALeafDER, _ := x509.CreateCertificate(rand.Reader, wrongCALeafTpl, rogueCACert, &wrongCAKey.PublicKey, rogueCAKey)
	writePEM(outDir+"/wrongca_client.crt", "CERTIFICATE", wrongCALeafDER)
	wrongCAKeyDER, _ := x509.MarshalPKCS8PrivateKey(wrongCAKey)
	writePEM(outDir+"/wrongca_client.key", "PRIVATE KEY", wrongCAKeyDER)

	// (b) expired: signed by the REAL CA (ca.crt/ca.key) -- chain-of-trust
	// is genuinely valid; the ONLY defect is validity dates, both in 2020.
	realCACert, realCAKey := loadRealCA(certsDir+"/ca.crt", certsDir+"/ca.key")
	expiredKey, _ := rsa.GenerateKey(rand.Reader, 2048)
	expiredTpl := &x509.Certificate{
		SerialNumber: big.NewInt(3), Subject: pkix.Name{CommonName: "client_one_expired_test"},
		NotBefore: time.Date(2020, 1, 1, 0, 0, 0, 0, time.UTC), NotAfter: time.Date(2020, 1, 2, 0, 0, 0, 0, time.UTC),
		KeyUsage: x509.KeyUsageDigitalSignature, ExtKeyUsage: []x509.ExtKeyUsage{x509.ExtKeyUsageClientAuth},
	}
	expiredDER, _ := x509.CreateCertificate(rand.Reader, expiredTpl, realCACert, &expiredKey.PublicKey, realCAKey)
	writePEM(outDir+"/expired_client.crt", "CERTIFICATE", expiredDER)
	expiredKeyDER, _ := x509.MarshalPKCS8PrivateKey(expiredKey)
	writePEM(outDir+"/expired_client.key", "PRIVATE KEY", expiredKeyDER)
}
```

`probe/main.go` (the corrected probe, both fixes applied):

```go
// Dials the real local mtls gateway with a given client cert/key (or
// none) and reports the TLS alert/result. Uses Go's own crypto/tls (same
// stack tls_kem_proxy/main.go uses for the real campaign client).
package main

import (
	"crypto/tls"
	"fmt"
	"os"
)

func main() {
	label, certPath, keyPath, profile := os.Args[1], os.Args[2], os.Args[3], os.Args[4]

	// Matches tls_kem_proxy/main.go's own per-profile CurvePreferences --
	// PQC/Hybrid servers only offer MLKEM1024/SecP384r1MLKEM1024
	// (mock_mtls/main.go:140/174).
	var curves []tls.CurveID
	switch profile {
	case "classic":
		curves = []tls.CurveID{tls.CurveP384}
	case "pqc":
		curves = []tls.CurveID{tls.MLKEM1024}
	case "hybrid":
		curves = []tls.CurveID{tls.SecP384r1MLKEM1024}
	default:
		panic("unknown profile " + profile)
	}

	cfg := &tls.Config{InsecureSkipVerify: true, ServerName: "mtls", CurvePreferences: curves}
	if certPath != "" {
		cert, err := tls.LoadX509KeyPair(certPath, keyPath)
		if err != nil {
			fmt.Printf("%s\tLOAD_ERROR\t%v\n", label, err)
			return
		}
		// GetClientCertificate, not cfg.Certificates: see "methodological
		// pitfall" item 2 above -- forces this (possibly-defective)
		// cert through unconditionally, bypassing Go's own
		// acceptable-CA client-side filter.
		cfg.GetClientCertificate = func(*tls.CertificateRequestInfo) (*tls.Certificate, error) {
			return &cert, nil
		}
	}

	conn, err := tls.Dial("tcp", "host.docker.internal:443", cfg)
	if err != nil {
		fmt.Printf("%s\tREJECTED_AT_DIAL\t%v\n", label, err)
		return
	}
	// See "methodological pitfall" item 1 above: a real round-trip is
	// required to see the server's post-handshake verification result.
	if _, err := conn.Write([]byte("GET / HTTP/1.1\r\nHost: mtls\r\nConnection: close\r\n\r\n")); err != nil {
		fmt.Printf("%s\tREJECTED_ON_WRITE\t%v\n", label, err)
		conn.Close()
		return
	}
	buf := make([]byte, 256)
	nr, err := conn.Read(buf)
	if err != nil {
		fmt.Printf("%s\tREJECTED_ON_READ\t%v\n", label, err)
		conn.Close()
		return
	}
	fmt.Printf("%s\tACCEPTED\tresp=%q\n", label, string(buf[:nr]))
	conn.Close()
}
```

## Raw output (all 12 runs, in order)

```
pqc|valid	ACCEPTED	resp="HTTP/1.1 401 Unauthorized..."
pqc|wrongca	REJECTED_ON_READ	remote error: tls: unknown certificate authority
pqc|expired	REJECTED_ON_READ	remote error: tls: expired certificate
pqc|nocert	ACCEPTED	resp="HTTP/1.1 401 Unauthorized..."
classic|valid	ACCEPTED	resp="HTTP/1.1 401 Unauthorized..."
classic|wrongca	REJECTED_ON_READ	remote error: tls: unknown certificate authority
classic|expired	REJECTED_ON_READ	remote error: tls: expired certificate
classic|nocert	ACCEPTED	resp="HTTP/1.1 401 Unauthorized..."
hybrid|valid	ACCEPTED	resp="HTTP/1.1 401 Unauthorized..."
hybrid|wrongca	REJECTED_ON_READ	remote error: tls: unknown certificate authority
hybrid|expired	REJECTED_ON_READ	remote error: tls: expired certificate
hybrid|nocert	ACCEPTED	resp="HTTP/1.1 401 Unauthorized..."
```

The `401 Unauthorized` on every `ACCEPTED` case is this probe's own bogus
`GET /` (not a real OPIN endpoint) -- identical for valid and no-cert
alike, confirming it is unrelated to certificate presence; it is an
application-layer response, not a TLS-layer one, and is not evidence
about client-cert enforcement one way or the other.
