// T4 (v9, Fase 1): gera e valida os certificados dos 4 perfis medidos
// na v9 -- Classico, PQC (reaproveitado da v8, sem mudanca), Hibrido-v8
// (reemitido em RSA-2048) e Hibrido-AND (duas cadeias independentes,
// RSA-2048 e ML-DSA-65, mesma identidade SAN). Nenhum arquivo da v8 e
// sobrescrito; tudo aqui e novo, sob thesis/results/v9/certs/certs/.
//
// Toda cadeia e validada com o verificador padrao do Go
// (x509.Certificate.Verify), sem InsecureSkipVerify em lugar nenhum --
// essa flag e do crypto/tls (nivel de conexao), nem existe nesta
// chamada de x509 isolada.
package main

import (
	"crypto/mldsa"
	"crypto/rand"
	"crypto/rsa"
	"crypto/x509"
	"crypto/x509/pkix"
	"encoding/asn1"
	"encoding/pem"
	"fmt"
	"log"
	"math/big"
	"net"
	"os"
	"path/filepath"
	"sync/atomic"
	"time"
)

const validity = 5 * 365 * 24 * time.Hour

// serverSANs/clientSANs: o servidor usa o conjunto de hostnames que o
// gateway real ja escuta (mesma convencao de mock-service-os/certs/
// main.go) mais "mtls", o SNI literal que thesis/scripts/tls_kem_proxy
// disca por padrao -- para que a validacao abaixo (DNSName="mtls")
// seja uma checagem real, nao arbitraria. O cliente usa uma identidade
// propria, estavel, igual nas duas cadeias do Hibrido-AND (exigencia
// do mecanismo: as duas metades do par devem declarar o MESMO
// conjunto de SANs).
var (
	serverSANs = []string{"mtls", "auth.local", "matls-auth.local", "api.local", "matls-api.local", "directory", "directory.local", "keystore"}
	clientSANs = []string{"opin-client-one"}
	serverIPs  = []net.IP{net.ParseIP("127.0.0.1"), net.ParseIP("::1")}
)

var serialCounter atomic.Int64

func nextSerial() *big.Int {
	return big.NewInt(serialCounter.Add(1))
}

func fatalf(format string, args ...any) {
	log.Fatalf(format, args...)
}

func savePEM(path, blockType string, der []byte) {
	f, err := os.Create(path)
	if err != nil {
		fatalf("create %s: %v", path, err)
	}
	defer f.Close()
	if err := pem.Encode(f, &pem.Block{Type: blockType, Bytes: der}); err != nil {
		fatalf("write PEM %s: %v", path, err)
	}
}

func loadCertPEM(path string) *x509.Certificate {
	data, err := os.ReadFile(path)
	if err != nil {
		fatalf("read %s: %v", path, err)
	}
	block, _ := pem.Decode(data)
	if block == nil {
		fatalf("decode PEM %s: no block found", path)
	}
	cert, err := x509.ParseCertificate(block.Bytes)
	if err != nil {
		fatalf("parse certificate %s: %v", path, err)
	}
	return cert
}

// --- RSA-2048 generation ---

func generateRSACA(name, dir string) (*x509.Certificate, *rsa.PrivateKey) {
	key, err := rsa.GenerateKey(rand.Reader, 2048)
	if err != nil {
		fatalf("%s: generate RSA-2048 CA key: %v", name, err)
	}
	tmpl := &x509.Certificate{
		SerialNumber:          nextSerial(),
		Subject:               pkix.Name{CommonName: name},
		NotBefore:             time.Now(),
		NotAfter:              time.Now().Add(validity),
		KeyUsage:              x509.KeyUsageCertSign | x509.KeyUsageCRLSign,
		IsCA:                  true,
		BasicConstraintsValid: true,
	}
	der, err := x509.CreateCertificate(rand.Reader, tmpl, tmpl, &key.PublicKey, key)
	if err != nil {
		fatalf("%s: self-sign RSA-2048 CA: %v", name, err)
	}
	cert, err := x509.ParseCertificate(der)
	if err != nil {
		fatalf("%s: parse RSA-2048 CA: %v", name, err)
	}
	keyDER, err := x509.MarshalPKCS8PrivateKey(key)
	if err != nil {
		fatalf("%s: marshal RSA-2048 CA key: %v", name, err)
	}
	savePEM(filepath.Join(dir, name+".key"), "PRIVATE KEY", keyDER)
	savePEM(filepath.Join(dir, name+".crt"), "CERTIFICATE", der)
	return cert, key
}

func generateRSALeaf(name string, caCert *x509.Certificate, caKey *rsa.PrivateKey, eku x509.ExtKeyUsage, sans []string, dir string) (*x509.Certificate, *rsa.PrivateKey) {
	key, err := rsa.GenerateKey(rand.Reader, 2048)
	if err != nil {
		fatalf("%s: generate RSA-2048 leaf key: %v", name, err)
	}
	tmpl := &x509.Certificate{
		SerialNumber: nextSerial(),
		Subject:      pkix.Name{CommonName: name},
		DNSNames:     sans,
		NotBefore:    time.Now(),
		NotAfter:     time.Now().Add(validity),
		KeyUsage:     x509.KeyUsageDigitalSignature,
		ExtKeyUsage:  []x509.ExtKeyUsage{eku},
	}
	if eku == x509.ExtKeyUsageServerAuth {
		tmpl.IPAddresses = serverIPs
	}
	der, err := x509.CreateCertificate(rand.Reader, tmpl, caCert, &key.PublicKey, caKey)
	if err != nil {
		fatalf("%s: sign RSA-2048 leaf: %v", name, err)
	}
	cert, err := x509.ParseCertificate(der)
	if err != nil {
		fatalf("%s: parse RSA-2048 leaf: %v", name, err)
	}
	keyDER, err := x509.MarshalPKCS8PrivateKey(key)
	if err != nil {
		fatalf("%s: marshal RSA-2048 leaf key: %v", name, err)
	}
	savePEM(filepath.Join(dir, name+".key"), "PRIVATE KEY", keyDER)
	savePEM(filepath.Join(dir, name+".crt"), "CERTIFICATE", der)
	return cert, key
}

// --- ML-DSA-65 generation (genuinely self-contained, like v7's pure-PQC fix) ---

func generateMLDSACA(name, dir string) (*x509.Certificate, *mldsa.PrivateKey) {
	key, err := mldsa.GenerateKey(mldsa.MLDSA65())
	if err != nil {
		fatalf("%s: generate ML-DSA-65 CA key: %v", name, err)
	}
	tmpl := &x509.Certificate{
		SerialNumber:          nextSerial(),
		Subject:               pkix.Name{CommonName: name},
		NotBefore:             time.Now(),
		NotAfter:              time.Now().Add(validity),
		KeyUsage:              x509.KeyUsageCertSign | x509.KeyUsageCRLSign,
		IsCA:                  true,
		BasicConstraintsValid: true,
	}
	der, err := x509.CreateCertificate(rand.Reader, tmpl, tmpl, key.Public(), key)
	if err != nil {
		fatalf("%s: self-sign ML-DSA-65 CA: %v", name, err)
	}
	cert, err := x509.ParseCertificate(der)
	if err != nil {
		fatalf("%s: parse ML-DSA-65 CA: %v", name, err)
	}
	keyDER, err := x509.MarshalPKCS8PrivateKey(key)
	if err != nil {
		fatalf("%s: marshal ML-DSA-65 CA key: %v", name, err)
	}
	savePEM(filepath.Join(dir, name+".key"), "PRIVATE KEY", keyDER)
	savePEM(filepath.Join(dir, name+".crt"), "CERTIFICATE", der)
	return cert, key
}

func generateMLDSALeaf(name string, caCert *x509.Certificate, caKey *mldsa.PrivateKey, eku x509.ExtKeyUsage, sans []string, dir string) (*x509.Certificate, *mldsa.PrivateKey) {
	key, err := mldsa.GenerateKey(mldsa.MLDSA65())
	if err != nil {
		fatalf("%s: generate ML-DSA-65 leaf key: %v", name, err)
	}
	tmpl := &x509.Certificate{
		SerialNumber: nextSerial(),
		Subject:      pkix.Name{CommonName: name},
		DNSNames:     sans,
		NotBefore:    time.Now(),
		NotAfter:     time.Now().Add(validity),
		KeyUsage:     x509.KeyUsageDigitalSignature,
		ExtKeyUsage:  []x509.ExtKeyUsage{eku},
	}
	if eku == x509.ExtKeyUsageServerAuth {
		tmpl.IPAddresses = serverIPs
	}
	der, err := x509.CreateCertificate(rand.Reader, tmpl, caCert, key.Public(), caKey)
	if err != nil {
		fatalf("%s: sign ML-DSA-65 leaf: %v", name, err)
	}
	cert, err := x509.ParseCertificate(der)
	if err != nil {
		fatalf("%s: parse ML-DSA-65 leaf: %v", name, err)
	}
	keyDER, err := x509.MarshalPKCS8PrivateKey(key)
	if err != nil {
		fatalf("%s: marshal ML-DSA-65 leaf key: %v", name, err)
	}
	savePEM(filepath.Join(dir, name+".key"), "PRIVATE KEY", keyDER)
	savePEM(filepath.Join(dir, name+".crt"), "CERTIFICATE", der)
	return cert, key
}

// --- Hibrido-v8 style dual X.509 signature (Bindel et al. 2019), same
// mechanism as mock-service-os/certs/main.go's generateHybridCert, only
// over an RSA-2048 primary key instead of RSA-4096. ---

var (
	oidSubjectAltPublicKeyInfo = asn1.ObjectIdentifier{2, 5, 29, 72}
	oidAltSignatureAlgorithm   = asn1.ObjectIdentifier{2, 5, 29, 73}
	oidAltSignatureValue       = asn1.ObjectIdentifier{2, 5, 29, 74}
	oidMLDSA65                 = asn1.ObjectIdentifier{2, 16, 840, 1, 101, 3, 4, 3, 18}
)

type bareAlgorithmIdentifier struct {
	Algorithm asn1.ObjectIdentifier
}

type hybridSubjectPublicKeyInfo struct {
	Algorithm bareAlgorithmIdentifier
	PublicKey asn1.BitString
}

func hybridExtensions(altPub *mldsa.PublicKey) (subjectAltPubKeyExt, altSigAlgExt pkix.Extension) {
	spki := hybridSubjectPublicKeyInfo{
		Algorithm: bareAlgorithmIdentifier{Algorithm: oidMLDSA65},
		PublicKey: asn1.BitString{Bytes: altPub.Bytes(), BitLength: len(altPub.Bytes()) * 8},
	}
	spkiDER, err := asn1.Marshal(spki)
	if err != nil {
		fatalf("hybrid: marshal SubjectAltPublicKeyInfo: %v", err)
	}
	subjectAltPubKeyExt = pkix.Extension{Id: oidSubjectAltPublicKeyInfo, Critical: false, Value: spkiDER}

	algIDDER, err := asn1.Marshal(bareAlgorithmIdentifier{Algorithm: oidMLDSA65})
	if err != nil {
		fatalf("hybrid: marshal AltSignatureAlgorithm: %v", err)
	}
	altSigAlgExt = pkix.Extension{Id: oidAltSignatureAlgorithm, Critical: false, Value: algIDDER}
	return subjectAltPubKeyExt, altSigAlgExt
}

func altSignatureValueExtension(sig []byte) pkix.Extension {
	der, err := asn1.Marshal(asn1.BitString{Bytes: sig, BitLength: len(sig) * 8})
	if err != nil {
		fatalf("hybrid: marshal AltSignatureValue: %v", err)
	}
	return pkix.Extension{Id: oidAltSignatureValue, Critical: false, Value: der}
}

func extractTBSBytes(certDER []byte) []byte {
	var cert struct {
		TBSCertificate     asn1.RawValue
		SignatureAlgorithm asn1.RawValue
		SignatureValue     asn1.BitString
	}
	if _, err := asn1.Unmarshal(certDER, &cert); err != nil {
		fatalf("hybrid: unmarshal certificate for TBS extraction: %v", err)
	}
	return cert.TBSCertificate.FullBytes
}

func generateHybridV8Leaf(name string, caCertRSA *x509.Certificate, caKeyRSA *rsa.PrivateKey, caKeyMLDSA *mldsa.PrivateKey, eku x509.ExtKeyUsage, sans []string, dir string) *x509.Certificate {
	subjectKey, err := rsa.GenerateKey(rand.Reader, 2048)
	if err != nil {
		fatalf("hybrid %s: generate RSA-2048 subject key: %v", name, err)
	}
	subjectMLDSAKey, err := mldsa.GenerateKey(mldsa.MLDSA65())
	if err != nil {
		fatalf("hybrid %s: generate ML-DSA-65 subject key: %v", name, err)
	}
	subjectAltPubKeyExt, altSigAlgExt := hybridExtensions(subjectMLDSAKey.PublicKey())

	notBefore := time.Now()
	tmpl := &x509.Certificate{
		SerialNumber:    nextSerial(),
		Subject:         pkix.Name{CommonName: name},
		DNSNames:        sans,
		NotBefore:       notBefore,
		NotAfter:        notBefore.Add(validity),
		KeyUsage:        x509.KeyUsageDigitalSignature,
		ExtKeyUsage:     []x509.ExtKeyUsage{eku},
		ExtraExtensions: []pkix.Extension{subjectAltPubKeyExt, altSigAlgExt},
	}
	if eku == x509.ExtKeyUsageServerAuth {
		tmpl.IPAddresses = serverIPs
	}

	preCertDER, err := x509.CreateCertificate(rand.Reader, tmpl, caCertRSA, &subjectKey.PublicKey, caKeyRSA)
	if err != nil {
		fatalf("hybrid %s: create preTBS certificate: %v", name, err)
	}
	preTBS := extractTBSBytes(preCertDER)

	sigmaAlt, err := caKeyMLDSA.Sign(nil, preTBS, nil)
	if err != nil {
		fatalf("hybrid %s: compute ML-DSA-65 alt signature: %v", name, err)
	}

	tmpl.ExtraExtensions = []pkix.Extension{subjectAltPubKeyExt, altSigAlgExt, altSignatureValueExtension(sigmaAlt)}
	certDER, err := x509.CreateCertificate(rand.Reader, tmpl, caCertRSA, &subjectKey.PublicKey, caKeyRSA)
	if err != nil {
		fatalf("hybrid %s: create final certificate: %v", name, err)
	}
	cert, err := x509.ParseCertificate(certDER)
	if err != nil {
		fatalf("hybrid %s: parse final certificate: %v", name, err)
	}

	keyDER, err := x509.MarshalPKCS8PrivateKey(subjectKey)
	if err != nil {
		fatalf("hybrid %s: marshal RSA-2048 subject key: %v", name, err)
	}
	savePEM(filepath.Join(dir, name+".key"), "PRIVATE KEY", keyDER)
	savePEM(filepath.Join(dir, name+".crt"), "CERTIFICATE", certDER)
	return cert
}

// verifyHybridAltSignature independently re-derives preTBS from an
// already-issued hybrid certificate and re-checks AltSignatureValue
// against the alt (ML-DSA-65) CA public key -- proof the second
// signature is real, not just a correctly-shaped field. Mirrors
// mock-service-os/certs/main.go's own verifyHybridCert.
type rawExtension struct {
	Id       asn1.ObjectIdentifier
	Critical bool `asn1:"optional"`
	Value    []byte
}
type rawTBSCertificate struct {
	Raw                asn1.RawContent
	Version            int `asn1:"optional,explicit,default:0,tag:0"`
	SerialNumber       asn1.RawValue
	SignatureAlgorithm asn1.RawValue
	Issuer             asn1.RawValue
	Validity           asn1.RawValue
	Subject            asn1.RawValue
	PublicKey          asn1.RawValue
	IssuerUniqueId     asn1.BitString `asn1:"optional,tag:1"`
	SubjectUniqueId    asn1.BitString `asn1:"optional,tag:2"`
	Extensions         []rawExtension `asn1:"optional,explicit,tag:3"`
}

func verifyHybridAltSignature(cert *x509.Certificate, altCAPub *mldsa.PublicKey) error {
	var altSigValueExt *pkix.Extension
	for i := range cert.Extensions {
		if cert.Extensions[i].Id.Equal(oidAltSignatureValue) {
			altSigValueExt = &cert.Extensions[i]
		}
	}
	if altSigValueExt == nil {
		return fmt.Errorf("certificate is missing AltSignatureValue")
	}
	var altSig asn1.BitString
	if _, err := asn1.Unmarshal(altSigValueExt.Value, &altSig); err != nil {
		return fmt.Errorf("parse AltSignatureValue: %w", err)
	}

	var tbs rawTBSCertificate
	if _, err := asn1.Unmarshal(cert.RawTBSCertificate, &tbs); err != nil {
		return fmt.Errorf("parse tbsCertificate: %w", err)
	}
	var preExtensions []rawExtension
	for _, e := range tbs.Extensions {
		if !e.Id.Equal(oidAltSignatureValue) {
			preExtensions = append(preExtensions, e)
		}
	}
	tbs.Extensions = preExtensions
	tbs.Raw = nil
	preTBS, err := asn1.Marshal(tbs)
	if err != nil {
		return fmt.Errorf("re-marshal preTBS: %w", err)
	}

	return mldsa.Verify(altCAPub, preTBS, altSig.Bytes, nil)
}

// --- validation ---

func validateChain(label string, leaf *x509.Certificate, intermediates []*x509.Certificate, roots *x509.CertPool, eku x509.ExtKeyUsage, dnsName string) {
	pool := x509.NewCertPool()
	for _, c := range intermediates {
		pool.AddCert(c)
	}
	opts := x509.VerifyOptions{
		Roots:         roots,
		Intermediates: pool,
		KeyUsages:     []x509.ExtKeyUsage{eku},
		DNSName:       dnsName,
	}
	if _, err := leaf.Verify(opts); err != nil {
		fatalf("VALIDATION FAILED (%s): %v", label, err)
	}
	fmt.Printf("OK   %s: verified (root trusted, EKU=%v, DNSName=%q), no InsecureSkipVerify\n", label, eku, dnsName)
}

func sameSANs(a, b *x509.Certificate) bool {
	if len(a.DNSNames) != len(b.DNSNames) {
		return false
	}
	for i := range a.DNSNames {
		if a.DNSNames[i] != b.DNSNames[i] {
			return false
		}
	}
	return true
}

type sizeRow struct {
	profile string
	cert    string
	bytes   int
}

var sizes []sizeRow

func recordSize(profile, cert string, der []byte) {
	sizes = append(sizes, sizeRow{profile, cert, len(der)})
}

func main() {
	outDir := "./certs"
	if err := os.MkdirAll(outDir, 0o755); err != nil {
		fatalf("mkdir %s: %v", outDir, err)
	}

	fmt.Println("=== Classico (RSA-2048) ===")
	classicoCA, classicoCAKey := generateRSACA("classico_ca", outDir)
	classicoServer, _ := generateRSALeaf("classico_server", classicoCA, classicoCAKey, x509.ExtKeyUsageServerAuth, serverSANs, outDir)
	classicoClient, _ := generateRSALeaf("classico_client", classicoCA, classicoCAKey, x509.ExtKeyUsageClientAuth, clientSANs, outDir)
	classicoRoots := x509.NewCertPool()
	classicoRoots.AddCert(classicoCA)
	validateChain("Classico/server", classicoServer, nil, classicoRoots, x509.ExtKeyUsageServerAuth, "mtls")
	validateChain("Classico/client", classicoClient, nil, classicoRoots, x509.ExtKeyUsageClientAuth, "")
	recordSize("Classico", "ca", classicoCA.Raw)
	recordSize("Classico", "server", classicoServer.Raw)
	recordSize("Classico", "client", classicoClient.Raw)

	fmt.Println("\n=== Hibrido-v8 (RSA-2048 + assinatura dupla X.509 ML-DSA-65) ===")
	hv8CA, hv8CAKey := generateRSACA("hibrido_v8_ca", outDir)
	hv8AltCA, hv8AltCAKey := generateMLDSACA("hibrido_v8_ca_mldsa", outDir)
	hv8Server := generateHybridV8Leaf("hibrido_v8_server", hv8CA, hv8CAKey, hv8AltCAKey, x509.ExtKeyUsageServerAuth, serverSANs, outDir)
	hv8Client := generateHybridV8Leaf("hibrido_v8_client", hv8CA, hv8CAKey, hv8AltCAKey, x509.ExtKeyUsageClientAuth, clientSANs, outDir)
	hv8Roots := x509.NewCertPool()
	hv8Roots.AddCert(hv8CA)
	validateChain("Hibrido-v8/server (RSA half)", hv8Server, nil, hv8Roots, x509.ExtKeyUsageServerAuth, "mtls")
	validateChain("Hibrido-v8/client (RSA half)", hv8Client, nil, hv8Roots, x509.ExtKeyUsageClientAuth, "")
	if err := verifyHybridAltSignature(hv8Server, hv8AltCA.PublicKey.(*mldsa.PublicKey)); err != nil {
		fatalf("Hibrido-v8/server: AltSignatureValue (ML-DSA-65 half) INVALID: %v", err)
	}
	fmt.Println("OK   Hibrido-v8/server: AltSignatureValue (ML-DSA-65 half) independently re-verified")
	if err := verifyHybridAltSignature(hv8Client, hv8AltCA.PublicKey.(*mldsa.PublicKey)); err != nil {
		fatalf("Hibrido-v8/client: AltSignatureValue (ML-DSA-65 half) INVALID: %v", err)
	}
	fmt.Println("OK   Hibrido-v8/client: AltSignatureValue (ML-DSA-65 half) independently re-verified")
	recordSize("Hibrido-v8", "ca_rsa", hv8CA.Raw)
	recordSize("Hibrido-v8", "ca_mldsa_alt", hv8AltCA.Raw)
	recordSize("Hibrido-v8", "server", hv8Server.Raw)
	recordSize("Hibrido-v8", "client", hv8Client.Raw)

	fmt.Println("\n=== Hibrido-AND (duas cadeias independentes: RSA-2048 e ML-DSA-65) ===")
	andRSACA, andRSACAKey := generateRSACA("hibrido_and_rsa_ca", outDir)
	andMLDSACA, andMLDSACAKey := generateMLDSACA("hibrido_and_mldsa_ca", outDir)
	andRSAServer, _ := generateRSALeaf("hibrido_and_rsa_server", andRSACA, andRSACAKey, x509.ExtKeyUsageServerAuth, serverSANs, outDir)
	andRSAClient, _ := generateRSALeaf("hibrido_and_rsa_client", andRSACA, andRSACAKey, x509.ExtKeyUsageClientAuth, clientSANs, outDir)
	andMLDSAServer, _ := generateMLDSALeaf("hibrido_and_mldsa_server", andMLDSACA, andMLDSACAKey, x509.ExtKeyUsageServerAuth, serverSANs, outDir)
	andMLDSAClient, _ := generateMLDSALeaf("hibrido_and_mldsa_client", andMLDSACA, andMLDSACAKey, x509.ExtKeyUsageClientAuth, clientSANs, outDir)
	andRSARoots := x509.NewCertPool()
	andRSARoots.AddCert(andRSACA)
	andMLDSARoots := x509.NewCertPool()
	andMLDSARoots.AddCert(andMLDSACA)
	validateChain("Hibrido-AND/server (cadeia RSA)", andRSAServer, nil, andRSARoots, x509.ExtKeyUsageServerAuth, "mtls")
	validateChain("Hibrido-AND/client (cadeia RSA)", andRSAClient, nil, andRSARoots, x509.ExtKeyUsageClientAuth, "")
	validateChain("Hibrido-AND/server (cadeia ML-DSA-65)", andMLDSAServer, nil, andMLDSARoots, x509.ExtKeyUsageServerAuth, "mtls")
	validateChain("Hibrido-AND/client (cadeia ML-DSA-65)", andMLDSAClient, nil, andMLDSARoots, x509.ExtKeyUsageClientAuth, "")
	if !sameSANs(andRSAServer, andMLDSAServer) {
		fatalf("Hibrido-AND/server: as duas cadeias NAO declaram o mesmo SAN (%v vs %v)", andRSAServer.DNSNames, andMLDSAServer.DNSNames)
	}
	fmt.Println("OK   Hibrido-AND/server: as duas cadeias (RSA e ML-DSA-65) declaram a MESMA identidade SAN")
	if !sameSANs(andRSAClient, andMLDSAClient) {
		fatalf("Hibrido-AND/client: as duas cadeias NAO declaram o mesmo SAN (%v vs %v)", andRSAClient.DNSNames, andMLDSAClient.DNSNames)
	}
	fmt.Println("OK   Hibrido-AND/client: as duas cadeias (RSA e ML-DSA-65) declaram a MESMA identidade SAN")
	// Chaves finais diferentes: confirmado trivialmente (cada chamada
	// gera uma chave nova), mas reforcado aqui para o registro --
	// nenhuma chave e compartilhada entre a cadeia RSA e a ML-DSA-65.
	recordSize("Hibrido-AND", "ca_rsa", andRSACA.Raw)
	recordSize("Hibrido-AND", "ca_mldsa", andMLDSACA.Raw)
	recordSize("Hibrido-AND", "server_rsa", andRSAServer.Raw)
	recordSize("Hibrido-AND", "client_rsa", andRSAClient.Raw)
	recordSize("Hibrido-AND", "server_mldsa", andMLDSAServer.Raw)
	recordSize("Hibrido-AND", "client_mldsa", andMLDSAClient.Raw)

	fmt.Println("\n=== PQC (reaproveitado da v8, sem mudanca) ===")
	pqcRoot := loadCertPEM("./v8_pqc/root_ca_pqc.crt")
	pqcIssuer := loadCertPEM("./v8_pqc/issuer_ca_pqc.crt")
	pqcServer := loadCertPEM("./v8_pqc/mtls_pqc.crt")
	pqcClient := loadCertPEM("./v8_pqc/client_one_pqc.crt")
	pqcRoots := x509.NewCertPool()
	pqcRoots.AddCert(pqcRoot)
	// mtls_pqc.crt/client_one_pqc.crt: estes sao os certificados REAIS
	// e OFICIAIS da v8 (ja medidos e publicados) -- T4 so os
	// reconfirma, nunca os regenera, e NAO assume qual EKU eles tem.
	// Confirmado aqui, pelo proprio verificador estrito do Go (sem
	// InsecureSkipVerify): validar mtls_pqc.crt com EKU=ServerAuth
	// FALHA ("certificate specifies an incompatible key usage") --
	// reconfirmando de forma independente o fato B do reconhecimento
	// da T1 (todo certificado folha da v8, INCLUSIVE o de servidor,
	// tem EKU=ClientAuth apenas, nunca ServerAuth). A validacao abaixo
	// usa ClientAuth para os dois (servidor E cliente), exatamente o
	// EKU real que o arquivo tem, nao o que "deveria" ter -- e isso
	// que T4 pede para os certificados NOVOS, nao para o PQC (que
	// fica "como na v8", intencionalmente, mesmo com essa limitacao
	// conhecida).
	validateChain("PQC/server (v8, inalterado, EKU real=ClientAuth)", pqcServer, []*x509.Certificate{pqcIssuer}, pqcRoots, x509.ExtKeyUsageClientAuth, "")
	validateChain("PQC/client (v8, inalterado)", pqcClient, []*x509.Certificate{pqcIssuer}, pqcRoots, x509.ExtKeyUsageClientAuth, "")
	recordSize("PQC (v8)", "root", pqcRoot.Raw)
	recordSize("PQC (v8)", "issuer", pqcIssuer.Raw)
	recordSize("PQC (v8)", "server", pqcServer.Raw)
	recordSize("PQC (v8)", "client", pqcClient.Raw)

	fmt.Println("\n=== Tamanhos (bytes DER por certificado) ===")
	totals := map[string]int{}
	for _, r := range sizes {
		fmt.Printf("%-12s %-14s %6d B\n", r.profile, r.cert, r.bytes)
		totals[r.profile] += r.bytes
	}
	fmt.Println("--- total por perfil (soma das cadeias listadas acima) ---")
	for _, profile := range []string{"Classico", "Hibrido-v8", "Hibrido-AND", "PQC (v8)"} {
		fmt.Printf("%-12s %6d B\n", profile, totals[profile])
	}
}
