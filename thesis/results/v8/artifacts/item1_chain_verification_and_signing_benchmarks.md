# Item 1/4 (round 4): offline chain-verification and signing microbenchmarks

Both benchmarks below are **offline, added estimates of what a cost WOULD be
if performed** -- neither is a measurement taken during the real campaign.
Run after the fleet was destroyed (Decision 117), against the real local
certificate/key material in `mock-service-os/certs/`, inside the same
`golang:1.27-rc-alpine` Docker image used throughout this project, so the
exact same Go `crypto/x509`, `crypto/rsa`, and `crypto/mldsa` implementations
measure the numbers quoted in the main report.

## Why these estimates exist at all

- **Chain verification**: the real client sets `InsecureSkipVerify: true`
  (`tls_kem_proxy/main.go:212`), so it never validates the server's
  certificate chain; T_fluxo therefore never includes this cost. Section 2 /
  Limitations quote this benchmark only as a "what it would cost" figure.
- **RSA-4096 vs. ML-DSA-65 signing**: no per-operation timer exists inside
  Go's TLS 1.3 handshake internals (unlike the JWT-level operations in
  Section 6's CPU-per-operation table), so the server's own certificate-
  signing cost during the handshake cannot be read directly from any
  campaign log. This benchmark isolates that one operation, using the real
  server private keys, to let Section 6 qualify (not merely assert) the
  RSA-4096-dominance hypothesis for Classic's/Hybrid's handshake cost.

## Benchmark 1: X.509 chain verification, per profile

`leaf.Verify(x509.VerifyOptions{Roots, Intermediates, KeyUsages:
[ExtKeyUsageAny]})`, `KeyUsages` set to `ExtKeyUsageAny` specifically to
bypass the client-auth-only EKU restriction found in Section 2 (`Verify
return code: 26`) -- this benchmark times the chain-WALK cost alone, not the
EKU/purpose check a real TLS stack would also apply. One untimed warm-up
call, then n=2000 timed iterations per profile.

```go
package main

import (
	"crypto/x509"
	"encoding/pem"
	"fmt"
	"os"
	"time"
)

func loadCert(path string) *x509.Certificate {
	data, err := os.ReadFile(path)
	if err != nil {
		panic(err)
	}
	block, _ := pem.Decode(data)
	if block == nil {
		panic("no PEM block in " + path)
	}
	cert, err := x509.ParseCertificate(block.Bytes)
	if err != nil {
		panic(err)
	}
	return cert
}

func bench(label string, leaf *x509.Certificate, roots *x509.CertPool, intermediates *x509.CertPool, n int) {
	opts := x509.VerifyOptions{
		Roots:         roots,
		Intermediates: intermediates,
		KeyUsages:     []x509.ExtKeyUsage{x509.ExtKeyUsageAny},
	}
	if _, err := leaf.Verify(opts); err != nil {
		fmt.Printf("%s: VERIFY ERROR (not timed): %v\n", label, err)
		return
	}
	times := make([]time.Duration, n)
	for i := 0; i < n; i++ {
		start := time.Now()
		if _, err := leaf.Verify(opts); err != nil {
			panic(err)
		}
		times[i] = time.Since(start)
	}
	var total time.Duration
	min_, max_ := times[0], times[0]
	for _, t := range times {
		total += t
		if t < min_ {
			min_ = t
		}
		if t > max_ {
			max_ = t
		}
	}
	mean := total / time.Duration(n)
	fmt.Printf("%s: n=%d mean=%v min=%v max=%v\n", label, n, mean, min_, max_)
}

func main() {
	certsDir := "/certs"
	n := 2000

	classicLeaf := loadCert(certsDir + "/client_one.crt")
	classicRoot := x509.NewCertPool()
	classicRoot.AddCert(loadCert(certsDir + "/ca.crt"))
	bench("classic (RSA chain, client_one.crt -> ca.crt)", classicLeaf, classicRoot, x509.NewCertPool(), n)

	pqcLeaf := loadCert(certsDir + "/client_one_pqc.crt")
	pqcRoot := x509.NewCertPool()
	pqcRoot.AddCert(loadCert(certsDir + "/root_ca_pqc.crt"))
	pqcIntermediates := x509.NewCertPool()
	pqcIntermediates.AddCert(loadCert(certsDir + "/issuer_ca_pqc.crt"))
	bench("pqc (ML-DSA-65 chain, client_one_pqc.crt -> issuer_ca_pqc.crt -> root_ca_pqc.crt)", pqcLeaf, pqcRoot, pqcIntermediates, n)

	hybridLeaf := loadCert(certsDir + "/client_one_hybrid.crt")
	hybridRoot := x509.NewCertPool()
	hybridRoot.AddCert(loadCert(certsDir + "/ca.crt"))
	bench("hybrid (RSA primary chain only, client_one_hybrid.crt -> ca.crt)", hybridLeaf, hybridRoot, x509.NewCertPool(), n)
}
```

Command (git-bash; `MSYS_NO_PATHCONV=1` + `//app` needed to stop git-bash's
POSIX-path rewriting from breaking `-w`):

```
MSYS_NO_PATHCONV=1 docker run --rm -v "$(pwd):/app" -v ".../mock-service-os/certs:/certs" -w //app golang:1.27-rc-alpine sh -c "go run main.go"
```

Output:

```
classic (RSA chain, client_one.crt -> ca.crt): n=2000 mean=241.057µs min=191.323µs max=1.317417ms
pqc (ML-DSA-65 chain, client_one_pqc.crt -> issuer_ca_pqc.crt -> root_ca_pqc.crt): n=2000 mean=157.038µs min=143.699µs max=1.732417ms
hybrid (RSA primary chain only, client_one_hybrid.crt -> ca.crt): n=2000 mean=236.819µs min=182.843µs max=1.294907ms
```

## Benchmark 2: real private-key signing, RSA-4096 vs. ML-DSA-65

Uses the project's **real server certificate private keys**
(`mock-service-os/certs/mtls.key`, RSA-4096, and `mtls_pqc.key`, ML-DSA-65),
confirmed by `openssl rsa -text`/key OID inspection before running. RSA
signs with PSS (`SaltLength: PSSSaltLengthEqualsHash`, SHA-256) over a
32-byte digest -- the same scheme and digest size TLS 1.3's own
`CertificateVerify` message uses; signing time is driven by the RSA modulus,
not by message content, so a placeholder digest is representative. ML-DSA-65
signs in pure mode (`sk.Sign(nil, message, nil)`), matching this project's
own pure-mode convention in `hybridVerification.go`'s `mldsa.Verify(...,
nil)` calls. One untimed warm-up call, then n=2000 timed iterations per key.

```go
package main

import (
	"crypto"
	"crypto/mldsa"
	"crypto/rand"
	"crypto/rsa"
	"crypto/sha256"
	"crypto/x509"
	"encoding/pem"
	"fmt"
	"os"
	"time"
)

func loadRSAKey(path string) *rsa.PrivateKey {
	data, _ := os.ReadFile(path)
	block, _ := pem.Decode(data)
	keyAny, err := x509.ParsePKCS8PrivateKey(block.Bytes)
	if err != nil {
		panic(err)
	}
	return keyAny.(*rsa.PrivateKey)
}

func loadMLDSAKey(path string) *mldsa.PrivateKey {
	data, _ := os.ReadFile(path)
	block, _ := pem.Decode(data)
	keyAny, err := x509.ParsePKCS8PrivateKey(block.Bytes)
	if err != nil {
		panic(err)
	}
	return keyAny.(*mldsa.PrivateKey)
}

func summarize(label string, times []time.Duration) {
	var total time.Duration
	min_, max_ := times[0], times[0]
	for _, t := range times {
		total += t
		if t < min_ {
			min_ = t
		}
		if t > max_ {
			max_ = t
		}
	}
	mean := total / time.Duration(len(times))
	fmt.Printf("%s: n=%d mean=%v min=%v max=%v\n", label, len(times), mean, min_, max_)
}

func main() {
	certsDir := "/certs"
	n := 2000

	rsaKey := loadRSAKey(certsDir + "/mtls.key")
	digest := sha256.Sum256([]byte("tls1.3 certificateverify transcript hash placeholder"))
	opts := &rsa.PSSOptions{SaltLength: rsa.PSSSaltLengthEqualsHash, Hash: crypto.SHA256}
	if _, err := rsaKey.Sign(rand.Reader, digest[:], opts); err != nil {
		panic(err)
	}
	rsaTimes := make([]time.Duration, n)
	for i := 0; i < n; i++ {
		start := time.Now()
		rsaKey.Sign(rand.Reader, digest[:], opts)
		rsaTimes[i] = time.Since(start)
	}
	summarize("rsa-4096-pss-sign (mtls.key, real server key)", rsaTimes)

	mldsaKey := loadMLDSAKey(certsDir + "/mtls_pqc.key")
	msg := []byte("tls1.3 certificateverify transcript hash placeholder, padded to a representative digest-sized input")
	if _, err := mldsaKey.Sign(nil, msg, nil); err != nil {
		panic(err)
	}
	mldsaTimes := make([]time.Duration, n)
	for i := 0; i < n; i++ {
		start := time.Now()
		mldsaKey.Sign(nil, msg, nil)
		mldsaTimes[i] = time.Since(start)
	}
	summarize("mldsa-65-sign (mtls_pqc.key, real server key)", mldsaTimes)
}
```

Output:

```
rsa-4096-pss-sign (mtls.key, real server key): n=2000 mean=5.944638ms min=4.779089ms max=17.66055ms
mldsa-65-sign (mtls_pqc.key, real server key): n=2000 mean=688.16µs min=136.776µs max=5.199236ms
```

## Reading these numbers together with Section 6's own handshake-duration table

Classic's and Hybrid's median handshake duration at sa-east-1/L0 (43.62ms
and 45.99ms respectively) sit close together and far above PQC's (10.32ms).
Per Section 2's own finding, Hybrid's live TLS handshake authenticates via
its **RSA-4096 primary signature** (the ML-DSA-65 `AltSignatureValue` is a
non-critical extension the handshake itself never checks) -- so Classic and
Hybrid share the same real signing key type at the TLS layer, while PQC's is
pure ML-DSA-65. This benchmark's own RSA-4096-vs-ML-DSA-65 signing-time gap
(5.94ms vs 0.69ms, a 5.25ms difference) is **directionally consistent** with
that pattern and is, among the operations this project can isolate and
measure at all, the single largest one -- but it explains only roughly
5.25/33.3 =~ 16% of the 33.3ms Classic-minus-PQC gap in the real handshake
duration itself. The qualified conclusion used in Section 6: this is real,
measured, consistent-in-direction evidence that RSA-4096 signing is **a**
contributor, not a demonstration that it is **the** dominant one in
wall-clock terms -- the remaining ~84% of the gap stays in the existing
"handshake residual ... not attributed" limitation.
