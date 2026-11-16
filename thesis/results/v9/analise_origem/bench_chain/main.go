// Degrau 1, Etapa 1, item 5: microbenchmark LOCAL de validacao de
// cadeia de certificados por perfil -- usa SOMENTE os .crt publicos ja
// commitados em thesis/results/v9/certs/generated/ (nunca uma chave
// privada). Mede x509.Verify() do leaf de cliente contra o pool da CA
// do proprio perfil -- a MESMA verificacao padrao que o lado servidor
// do gateway real faz (ClientAuth=VerifyClientCertIfGiven). Para
// Hibrido-AND, a verificacao ADICIONAL do AltSignatureValue ML-DSA-65
// (callback customizado fora do x509.Verify padrao) NAO e reproduzida
// aqui -- fica como limitacao de escopo explicita, nao estimada.
package main

import (
	"crypto/x509"
	"encoding/pem"
	"fmt"
	"os"
	"time"
)

func loadCert(path string) *x509.Certificate {
	raw, err := os.ReadFile(path)
	if err != nil {
		panic(err)
	}
	block, _ := pem.Decode(raw)
	if block == nil {
		panic("no PEM block in " + path)
	}
	cert, err := x509.ParseCertificate(block.Bytes)
	if err != nil {
		panic(err)
	}
	return cert
}

func bench(name string, n int, leafPath, caPath string) {
	leaf := loadCert(leafPath)
	ca := loadCert(caPath)
	pool := x509.NewCertPool()
	pool.AddCert(ca)
	opts := x509.VerifyOptions{Roots: pool, KeyUsages: []x509.ExtKeyUsage{x509.ExtKeyUsageAny}}

	// uma verificacao de aquecimento pra confirmar que a cadeia e valida antes de medir
	if _, err := leaf.Verify(opts); err != nil {
		fmt.Printf("%-30s ERRO: %v\n", name, err)
		return
	}
	start := time.Now()
	for i := 0; i < n; i++ {
		leaf.Verify(opts)
	}
	elapsed := time.Since(start)
	nsPerOp := float64(elapsed.Nanoseconds()) / float64(n)
	fmt.Printf("%-30s %10d %14.0f ns/op %14.0f ops/s\n", name, n, nsPerOp, 1e9/nsPerOp)
}

func main() {
	n := 2000
	dir := "/certs/"
	fmt.Printf("%-30s %10s %18s %18s\n", "operacao", "n", "ns/op", "ops/s")
	bench("Classic: client vs CA (RSA)", n, dir+"classico_client.crt", dir+"classico_ca.crt")
	bench("PQC: client vs CA (ML-DSA-65)", n, dir+"pqc_client.crt", dir+"pqc_ca.crt")
	bench("Control: client vs CA (RSA)", n, dir+"hibrido_v8_client.crt", dir+"hibrido_v8_ca.crt")
	bench("Hybrid: client vs CA (RSA, primaria)", n, dir+"hibrido_and_rsa_client.crt", dir+"hibrido_and_rsa_ca.crt")
	fmt.Println()
	fmt.Println("LIMITACAO DE ESCOPO: a verificacao ADICIONAL do AltSignatureValue ML-DSA-65 do Hibrido-AND")
	fmt.Println("(callback customizado hybridVerifyPeerCertificateFunc, fora do x509.Verify padrao) NAO")
	fmt.Println("foi reproduzida neste microbenchmark -- so a cadeia RSA primaria foi medida.")
}
