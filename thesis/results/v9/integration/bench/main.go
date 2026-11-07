// bench is the v9, T6, Fase 1 CPU microbenchmark tool: measures the
// per-operation cost (sign, verify, KEX) of the primitives each profile
// actually uses in its handshake, isolated from network/wall-clock
// handshake time. Uses freshly generated keys of the same type/params
// each profile's real certs use (RSA-2048+PSS-SHA256, ML-DSA-65,
// ECDH P-384, ML-KEM-1024) -- the specific key material doesn't affect
// CPU cost, only the algorithm/parameter set does, so this does not
// depend on thesis/results/v9/certs' generated output.
package main

import (
	"crypto"
	"crypto/ecdh"
	"crypto/mldsa"
	"crypto/mlkem"
	"crypto/rand"
	"crypto/rsa"
	"crypto/sha256"
	"flag"
	"fmt"
	"time"
)

const payloadSize = 32 // a SHA-256 digest's worth, what CertificateVerify actually signs over

func main() {
	iterations := flag.Int("n", 2000, "iterations per operation")
	flag.Parse()

	fmt.Printf("%-28s %10s %14s %14s\n", "operacao", "n", "ns/op", "ops/s")

	run("RSA-2048 keygen", max(*iterations/20, 50), benchRSAKeygen)
	rsaKey, rsaPub := mustRSAKey()
	payload := mustRandom(payloadSize)
	sig := mustRSASign(rsaKey, payload)
	run("RSA-2048 sign (PSS-SHA256)", *iterations, func() { benchRSASign(rsaKey, payload) })
	run("RSA-2048 verify (PSS-SHA256)", *iterations, func() { benchRSAVerify(rsaPub, payload, sig) })

	run("ML-DSA-65 keygen", max(*iterations/20, 50), benchMLDSAKeygen)
	mldsaKey, err := mldsa.GenerateKey(mldsa.MLDSA65())
	if err != nil {
		panic(err)
	}
	mldsaSig := mustMLDSASign(mldsaKey, payload)
	run("ML-DSA-65 sign", *iterations, func() { benchMLDSASign(mldsaKey, payload) })
	run("ML-DSA-65 verify", *iterations, func() { benchMLDSAVerify(mldsaKey.PublicKey(), payload, mldsaSig) })

	run("ECDH P-384 keygen", *iterations, benchECDHKeygen)
	peerPriv := mustECDHKey()
	run("ECDH P-384 compute (KEX)", *iterations, func() { benchECDHCompute(peerPriv) })

	run("ML-KEM-1024 keygen", *iterations, benchMLKEMKeygen)
	dk := mustMLKEMKey()
	ek := dk.EncapsulationKey()
	run("ML-KEM-1024 encapsulate", *iterations, func() { benchMLKEMEncapsulate(ek) })
	_, ct := ek.Encapsulate()
	run("ML-KEM-1024 decapsulate", *iterations, func() { benchMLKEMDecapsulate(dk, ct) })

	fmt.Println()
	fmt.Println("Custo de KEX por perfil (soma das operacoes acima que o handshake realmente executa):")
	fmt.Println("  Classico     (CurveP384):            1x ECDH P-384 keygen + 1x ECDH P-384 compute")
	fmt.Println("  PQC          (MLKEM1024):             1x ML-KEM-1024 keygen (cliente) + 1x encapsulate (servidor) + 1x decapsulate (cliente)")
	fmt.Println("  Hibrido/AND  (SecP384r1MLKEM1024):    soma das duas linhas acima (combinador concatena os dois segredos)")
}

func max(a, b int) int {
	if a > b {
		return a
	}
	return b
}

func run(name string, n int, op func()) {
	start := time.Now()
	for i := 0; i < n; i++ {
		op()
	}
	elapsed := time.Since(start)
	nsPerOp := float64(elapsed.Nanoseconds()) / float64(n)
	opsPerSec := 1e9 / nsPerOp
	fmt.Printf("%-28s %10d %14.0f %14.0f\n", name, n, nsPerOp, opsPerSec)
}

func mustRandom(n int) []byte {
	b := make([]byte, n)
	if _, err := rand.Read(b); err != nil {
		panic(err)
	}
	return b
}

func mustRSAKey() (*rsa.PrivateKey, *rsa.PublicKey) {
	k, err := rsa.GenerateKey(rand.Reader, 2048)
	if err != nil {
		panic(err)
	}
	return k, &k.PublicKey
}

var pssOpts = &rsa.PSSOptions{SaltLength: rsa.PSSSaltLengthEqualsHash, Hash: crypto.SHA256}

func mustRSASign(k *rsa.PrivateKey, payload []byte) []byte {
	h := sha256.Sum256(payload)
	sig, err := rsa.SignPSS(rand.Reader, k, crypto.SHA256, h[:], pssOpts)
	if err != nil {
		panic(err)
	}
	return sig
}

func benchRSAKeygen() { mustRSAKey() }

func benchRSASign(k *rsa.PrivateKey, payload []byte) { mustRSASign(k, payload) }

func benchRSAVerify(pub *rsa.PublicKey, payload, sig []byte) {
	h := sha256.Sum256(payload)
	if err := rsa.VerifyPSS(pub, crypto.SHA256, h[:], sig, pssOpts); err != nil {
		panic(err)
	}
}

func benchMLDSAKeygen() {
	if _, err := mldsa.GenerateKey(mldsa.MLDSA65()); err != nil {
		panic(err)
	}
}

func mustMLDSASign(k *mldsa.PrivateKey, payload []byte) []byte {
	sig, err := k.Sign(nil, payload, nil)
	if err != nil {
		panic(err)
	}
	return sig
}

func benchMLDSASign(k *mldsa.PrivateKey, payload []byte) { mustMLDSASign(k, payload) }

func benchMLDSAVerify(pub *mldsa.PublicKey, payload, sig []byte) {
	if err := mldsa.Verify(pub, payload, sig, nil); err != nil {
		panic(err)
	}
}

func mustECDHKey() *ecdh.PrivateKey {
	k, err := ecdh.P384().GenerateKey(rand.Reader)
	if err != nil {
		panic(err)
	}
	return k
}

func benchECDHKeygen() { mustECDHKey() }

func benchECDHCompute(peer *ecdh.PrivateKey) {
	me, err := ecdh.P384().GenerateKey(rand.Reader)
	if err != nil {
		panic(err)
	}
	if _, err := me.ECDH(peer.PublicKey()); err != nil {
		panic(err)
	}
}

func mustMLKEMKey() *mlkem.DecapsulationKey1024 {
	dk, err := mlkem.GenerateKey1024()
	if err != nil {
		panic(err)
	}
	return dk
}

func benchMLKEMKeygen() { mustMLKEMKey() }

func benchMLKEMEncapsulate(ek *mlkem.EncapsulationKey1024) {
	ek.Encapsulate()
}

func benchMLKEMDecapsulate(dk *mlkem.DecapsulationKey1024, ct []byte) {
	if _, err := dk.Decapsulate(ct); err != nil {
		panic(err)
	}
}
