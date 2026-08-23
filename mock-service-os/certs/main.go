package main

import (
	"crypto/mldsa"
	"crypto/rand"
	"crypto/rsa"
	"crypto/sha256"
	"crypto/x509"
	"crypto/x509/pkix"
	"encoding/asn1"
	"encoding/json"
	"encoding/pem"
	"flag"
	"fmt"
	"log"
	"math/big"
	"net"
	"os"
	"path/filepath"
	"runtime"
	"time"

	"github.com/google/uuid"
	"github.com/luikyv/go-oidc/pkg/goidc"
)

// Custom certificate fields.
var (
	oidLDAPUID        = asn1.ObjectIdentifier{0, 9, 2342, 19200300, 100, 1, 1}
	oidX500UID        = asn1.ObjectIdentifier{2, 5, 4, 45}
	oidOrganizationID = asn1.ObjectIdentifier{2, 5, 4, 97}

	// ITU-T X.509 (2019, 5th edition, hybrid-certificate amendment) / Bindel,
	// Braun, Gladiator, Stebila, Wiggers, "X.509-Compliant Hybrid
	// Certificates for the Post-Quantum Transition", JOSS 4(40), 1606, 2019
	// -- the three standard, published extension OIDs this scheme names.
	oidSubjectAltPublicKeyInfo = asn1.ObjectIdentifier{2, 5, 29, 72}
	oidAltSignatureAlgorithm   = asn1.ObjectIdentifier{2, 5, 29, 73}
	oidAltSignatureValue       = asn1.ObjectIdentifier{2, 5, 29, 74}

	// ML-DSA-65's own OID (NIST CSOR / FIPS 204). Confirmed via
	// `openssl asn1parse` on the already-committed client_one_pqc.crt to
	// match exactly what Go's own crypto/x509 already emits for a native
	// ML-DSA-65 SubjectPublicKeyInfo: a bare `SEQUENCE { OID }`, no trailing
	// NULL parameter (unlike RSA's AlgorithmIdentifier).
	oidMLDSA65 = asn1.ObjectIdentifier{2, 16, 840, 1, 101, 3, 4, 3, 18}
)

// bareAlgorithmIdentifier is RFC 5280's AlgorithmIdentifier with no
// parameters -- used both for AltSignatureAlgorithm's own content and inside
// hybridSubjectPublicKeyInfo, matching the parameter-less form ML-DSA-65
// already uses everywhere else in this codebase (see oidMLDSA65 above).
type bareAlgorithmIdentifier struct {
	Algorithm asn1.ObjectIdentifier
}

// hybridSubjectPublicKeyInfo mirrors RFC 5280's ordinary SubjectPublicKeyInfo
// shape exactly (AlgorithmIdentifier + BIT STRING) -- SubjectAltPublicKeyInfo
// reuses that same structure verbatim, just under a different extension OID,
// per Bindel et al. (2019).
type hybridSubjectPublicKeyInfo struct {
	Algorithm bareAlgorithmIdentifier
	PublicKey asn1.BitString
}

// Builds the two hybrid extensions whose content never depends on any
// signature (unlike AltSignatureValue, built separately below once sigma_alt
// exists): SubjectAltPublicKeyInfo carries the leaf's OWN ML-DSA-65 public
// key (this participant's alt identity -- distinct from the CA's own
// ML-DSA-65 keypair, which signs, but never appears as a subject key here),
// AltSignatureAlgorithm names the alt algorithm used for AltSignatureValue.
func hybridExtensions(altPub *mldsa.PublicKey) (subjectAltPubKeyExt, altSigAlgExt pkix.Extension) {
	spki := hybridSubjectPublicKeyInfo{
		Algorithm: bareAlgorithmIdentifier{Algorithm: oidMLDSA65},
		PublicKey: asn1.BitString{Bytes: altPub.Bytes(), BitLength: len(altPub.Bytes()) * 8},
	}
	spkiDER, err := asn1.Marshal(spki)
	if err != nil {
		log.Fatalf("hybrid: failed to marshal SubjectAltPublicKeyInfo: %v", err)
	}
	subjectAltPubKeyExt = pkix.Extension{Id: oidSubjectAltPublicKeyInfo, Critical: false, Value: spkiDER}

	algIDDER, err := asn1.Marshal(bareAlgorithmIdentifier{Algorithm: oidMLDSA65})
	if err != nil {
		log.Fatalf("hybrid: failed to marshal AltSignatureAlgorithm: %v", err)
	}
	altSigAlgExt = pkix.Extension{Id: oidAltSignatureAlgorithm, Critical: false, Value: algIDDER}
	return subjectAltPubKeyExt, altSigAlgExt
}

// altSignatureValueExtension wraps a raw ML-DSA-65 signature as the
// AltSignatureValue extension's content: a plain BIT STRING, per Bindel et
// al. (2019).
func altSignatureValueExtension(sig []byte) pkix.Extension {
	der, err := asn1.Marshal(asn1.BitString{Bytes: sig, BitLength: len(sig) * 8})
	if err != nil {
		log.Fatalf("hybrid: failed to marshal AltSignatureValue: %v", err)
	}
	return pkix.Extension{Id: oidAltSignatureValue, Critical: false, Value: der}
}

// extractTBSBytes parses a Certificate's outer SEQUENCE { tbsCertificate,
// signatureAlgorithm, signatureValue } and returns the raw encoded bytes of
// its tbsCertificate field -- exactly the bytes an X.509 signature is
// computed over. Needed because crypto/x509.CreateCertificate signs and
// finalizes a whole certificate in one atomic call with no way to get at the
// to-be-signed bytes on their own; this recovers them after the fact by
// DER-parsing an already-finished (possibly throwaway) certificate.
func extractTBSBytes(certDER []byte) []byte {
	var cert struct {
		TBSCertificate     asn1.RawValue
		SignatureAlgorithm asn1.RawValue
		SignatureValue     asn1.BitString
	}
	if _, err := asn1.Unmarshal(certDER, &cert); err != nil {
		log.Fatalf("hybrid: failed to unmarshal certificate for TBS extraction: %v", err)
	}
	return cert.TBSCertificate.FullBytes
}

func main() {
	_, filename, _, _ := runtime.Caller(0)
	sourceDir := filepath.Dir(filename)
	certsDir := filepath.Join(sourceDir, "./certs")
	// Create the "certs" directory if it doesn't exist.
	err := os.MkdirAll(certsDir, os.ModePerm)
	if err != nil {
		log.Fatalf("Failed to create certs directory: %v", err)
	}

	orgID := flag.String("org_id", uuid.NewString(), "Organization ID")
	pqcClientOnly := flag.Bool("pqc-client-only", false, "Only generate client_one_pqc.crt/.key (ML-DSA-65), signed by the existing ca.crt/ca.key on disk. Does not touch the CA or any other cert -- see thesis/results/experiment2 - PQC/DECISIONS.md.")
	pqcName := flag.String("pqc-name", "", "Only generate <name>.crt/.key (ML-DSA-65), signed by the existing ca.crt/ca.key on disk -- same mechanism as -pqc-client-only, generalized to any cert (e.g. op_pqc, mtls_pqc). Does not touch the CA or any other cert.")
	resignAll := flag.Bool("resign-all", false, "Regenerate the CA (5-year validity, fresh key) and re-sign every existing RSA/ML-DSA-65 leaf cert this tool knows about with it, reusing each leaf's existing private key unchanged -- no new leaf key material, only new certificates. Fixes an expired CA without invalidating any already-measured cert/key size. mongo.pem and postgres.crt are NOT RSA/ML-DSA-65 leafs this tool originally generated (different SANs/key size) and are handled separately. See thesis/results/v4/DECISIONS.md.")
	hybridName := flag.String("hybrid-name", "", "Generate <name>_hybrid.crt/.key: a classical RSA certificate carrying three additional X.509 extensions per Bindel et al. (2019), signed twice (RSA + ML-DSA-65) by the existing local CA (ca.crt/ca.key + issuer_ca_pqc.crt/.key). Reuses <name>.key (RSA) and <name>_pqc.key (ML-DSA-65) as the subject's existing key material -- both must already exist on disk. Does not touch the CA or any other cert. See thesis/results/v4/DECISIONS.md.")
	flag.Parse()

	if *resignAll {
		resignEverything(sourceDir, *orgID)
		return
	}

	if *hybridName != "" {
		caCertRSA, caKeyRSA := loadCACert(sourceDir)
		caKeyMLDSA := loadMLDSAKeyPEM(filepath.Join(sourceDir, "issuer_ca_pqc.key"))
		subjectRSAKey := loadRSAKeyPEM(filepath.Join(sourceDir, *hybridName+".key"))
		subjectMLDSAKey := loadMLDSAKeyPEM(filepath.Join(sourceDir, *hybridName+"_pqc.key"))
		generateHybridCert(*hybridName, *orgID, caCertRSA, caKeyRSA, caKeyMLDSA, subjectRSAKey, subjectMLDSAKey, sourceDir)
		return
	}

	if *pqcClientOnly {
		// sourceDir, not certsDir: the existing certs (ca.crt etc.) live
		// directly alongside main.go on disk -- certsDir's "./certs" nesting
		// only makes sense inside the Dockerfile's build-stage /app layout,
		// not when running this tool directly against the committed certs.
		caCert, caKey := loadCACert(sourceDir)
		generateClientCertPQC("client_one_pqc", *orgID, caCert, caKey, sourceDir)
		return
	}

	if *pqcName != "" {
		caCert, caKey := loadCACert(sourceDir)
		generateClientCertPQC(*pqcName, *orgID, caCert, caKey, sourceDir)
		return
	}

	caCert, caKey := generateCACert("ca", certsDir)

	_, _ = generateCert("mtls", *orgID, caCert, caKey, certsDir)

	_, _ = generateCert("op", *orgID, caCert, caKey, certsDir)

	clientOneCert, clientOneKey := generateCert("client_one", *orgID, caCert, caKey, certsDir)
	generateJWKS("client_one", clientOneCert, clientOneKey, certsDir)

	clientTwoCert, clientTwoKey := generateCert("client_two", *orgID, caCert, caKey, certsDir)
	generateJWKS("client_two", clientTwoCert, clientTwoKey, certsDir)
}

// Loads the existing CA cert+key from disk, instead of generating a new one --
// used by -pqc-client-only so the whole environment's existing trust chain
// (mongo, postgres, op, mtls, client_one/two certs, all signed by this same
// CA) doesn't get invalidated by a fresh self-signed CA.
func loadCACert(dir string) (*x509.Certificate, *rsa.PrivateKey) {
	certPEM, err := os.ReadFile(filepath.Join(dir, "ca.crt"))
	if err != nil {
		log.Fatalf("Failed to read ca.crt: %v", err)
	}
	certBlock, _ := pem.Decode(certPEM)
	if certBlock == nil {
		log.Fatalf("Failed to decode ca.crt PEM")
	}
	caCert, err := x509.ParseCertificate(certBlock.Bytes)
	if err != nil {
		log.Fatalf("Failed to parse ca.crt: %v", err)
	}

	keyPEM, err := os.ReadFile(filepath.Join(dir, "ca.key"))
	if err != nil {
		log.Fatalf("Failed to read ca.key: %v", err)
	}
	keyBlock, _ := pem.Decode(keyPEM)
	if keyBlock == nil {
		log.Fatalf("Failed to decode ca.key PEM")
	}
	caKeyAny, err := x509.ParsePKCS8PrivateKey(keyBlock.Bytes)
	if err != nil {
		log.Fatalf("Failed to parse ca.key: %v", err)
	}
	caKey, ok := caKeyAny.(*rsa.PrivateKey)
	if !ok {
		log.Fatalf("ca.key is not an RSA private key (got %T)", caKeyAny)
	}
	return caCert, caKey
}

// Generates an ML-DSA-65 client certificate signed by the existing (RSA) CA.
// Mixing a classical issuer signature with a post-quantum subject public key
// is ordinary, valid X.509 -- the two are independent fields -- and matches
// Etapa 3.1: only the client's own key/cert moves to PQC, the CA doesn't.
func generateClientCertPQC(
	name, orgID string,
	caCert *x509.Certificate,
	caKey *rsa.PrivateKey,
	dir string,
) (
	*x509.Certificate,
	*mldsa.PrivateKey,
) {
	key, err := mldsa.GenerateKey(mldsa.MLDSA65())
	if err != nil {
		log.Fatalf("Failed to generate ML-DSA-65 private key: %v", err)
	}

	cert := &x509.Certificate{
		SerialNumber: big.NewInt(time.Now().UnixNano()),
		Subject: pkix.Name{
			CommonName: name,
			ExtraNames: []pkix.AttributeTypeAndValue{
				{
					Type:  oidX500UID,
					Value: name,
				},
				{
					Type:  oidLDAPUID,
					Value: uuid.NewString(),
				},
				{
					Type:  oidOrganizationID,
					Value: orgID,
				},
			},
		},
		DNSNames: []string{
			"auth.local",
			"matls-auth.local",
			"api.local",
			"matls-api.local",
			"directory",
			"directory.local",
			"keystore",
		},
		IPAddresses: []net.IP{net.ParseIP("127.0.0.1"), net.ParseIP("::1")},
		NotBefore:   time.Now(),
		NotAfter:    time.Now().Add(365 * 24 * time.Hour),
		KeyUsage:    x509.KeyUsageDigitalSignature,
		ExtKeyUsage: []x509.ExtKeyUsage{x509.ExtKeyUsageClientAuth},
	}

	certBytes, err := x509.CreateCertificate(
		rand.Reader,
		cert,
		caCert,
		key.Public(),
		caKey,
	)
	if err != nil {
		log.Fatalf("Failed to create ML-DSA-65 certificate: %v", err)
	}
	cert.Raw = certBytes

	keyBytes, err := x509.MarshalPKCS8PrivateKey(key)
	if err != nil {
		log.Fatalf("Failed to marshal ML-DSA-65 key: %v", err)
	}
	savePEMFile(filepath.Join(dir, name+".key"), "PRIVATE KEY", keyBytes)
	savePEMFile(filepath.Join(dir, name+".crt"), "CERTIFICATE", certBytes)

	fmt.Printf("Generated ML-DSA-65 key and certificate for %s (signed by existing CA)\n", name)
	return cert, key
}

// Generates a hybrid mTLS certificate: a classical RSA certificate carrying
// three additional, non-critical X.509 extensions per Bindel et al. (2019)
// -- SubjectAltPublicKeyInfo (the leaf's own ML-DSA-65 public key),
// AltSignatureAlgorithm, and AltSignatureValue (the CA's ML-DSA-65 signature
// over the certificate) -- signed twice by the same logical local CA: once
// with its RSA keypair (as always), once with its ML-DSA-65 keypair
// (reusing the existing issuer_ca_pqc.key/.crt as that CA's alt keypair,
// per Section 7 of thesis/results/v4/Arquitetura_Tecnica_Experimento3_
// Strong_Nesting.docx -- "a mesma autoridade certificadora local... uma
// segunda vez com ML-DSA-65").
//
// Signing order matches the real, standard ITU-T/Bindel et al. (2019)
// mechanism, NOT Section 7's simplified prose (which describes the reverse
// order) -- confirmed with the user as a documented divergence (see
// thesis/results/v4/DECISIONS.md) after finding that the prose's order is
// actually incompatible with how crypto/tls's own unmodified certificate
// verification works: Go's TLS stack always re-verifies the RSA
// signatureValue against cert.RawTBSCertificate as literally received, so
// that RSA signature MUST cover the complete, final TBSCertificate
// (including AltSignatureValue) for an ordinary, hybrid-unaware mTLS
// handshake to keep succeeding unmodified. The alt (ML-DSA-65) signature is
// therefore computed FIRST, over a "preTBSCertificate" that has the first
// two extensions but not yet AltSignatureValue (which doesn't exist yet);
// the RSA signature is computed LAST, over the complete, final
// TBSCertificate with all three extensions present -- exactly the property
// that lets an old, PQC-unaware verifier's one RSA check still
// cryptographically cover the two PQC extensions too, undetectably-tampered
// extensions included.
//
// Implementation: two real calls to x509.CreateCertificate against the same
// template (same serial number, same NotBefore/NotAfter, computed once and
// reused -- so the two calls differ ONLY in whether AltSignatureValue is
// present), not a single hand-built TBS. The first call's only purpose is
// producing real, correctly DER-encoded bytes for the two-extension
// preTBSCertificate (extracted via extractTBSBytes); its own RSA signature
// is discarded entirely. The second call is the real, final certificate.
func generateHybridCert(
	name, orgID string,
	caCertRSA *x509.Certificate,
	caKeyRSA *rsa.PrivateKey,
	caKeyMLDSA *mldsa.PrivateKey,
	subjectRSAKey *rsa.PrivateKey,
	subjectMLDSAKey *mldsa.PrivateKey,
	dir string,
) *x509.Certificate {
	subjectAltPubKeyExt, altSigAlgExt := hybridExtensions(subjectMLDSAKey.PublicKey())

	notBefore := time.Now()
	template := &x509.Certificate{
		SerialNumber: big.NewInt(time.Now().UnixNano()),
		Subject: pkix.Name{
			CommonName: name,
			ExtraNames: []pkix.AttributeTypeAndValue{
				{Type: oidX500UID, Value: name},
				{Type: oidLDAPUID, Value: uuid.NewString()},
				{Type: oidOrganizationID, Value: orgID},
			},
		},
		DNSNames: []string{
			"auth.local", "matls-auth.local", "api.local", "matls-api.local",
			"directory", "directory.local", "keystore",
		},
		IPAddresses:     []net.IP{net.ParseIP("127.0.0.1"), net.ParseIP("::1")},
		NotBefore:       notBefore,
		NotAfter:        notBefore.Add(longLivedValidity),
		KeyUsage:        x509.KeyUsageDigitalSignature,
		ExtKeyUsage:     []x509.ExtKeyUsage{x509.ExtKeyUsageClientAuth},
		ExtraExtensions: []pkix.Extension{subjectAltPubKeyExt, altSigAlgExt},
	}

	preCertDER, err := x509.CreateCertificate(rand.Reader, template, caCertRSA, &subjectRSAKey.PublicKey, caKeyRSA)
	if err != nil {
		log.Fatalf("hybrid %s: failed to create preTBS certificate: %v", name, err)
	}
	preTBS := extractTBSBytes(preCertDER)

	sigmaAlt, err := caKeyMLDSA.Sign(nil, preTBS, nil)
	if err != nil {
		log.Fatalf("hybrid %s: failed to compute ML-DSA-65 alt signature: %v", name, err)
	}

	template.ExtraExtensions = []pkix.Extension{subjectAltPubKeyExt, altSigAlgExt, altSignatureValueExtension(sigmaAlt)}
	certDER, err := x509.CreateCertificate(rand.Reader, template, caCertRSA, &subjectRSAKey.PublicKey, caKeyRSA)
	if err != nil {
		log.Fatalf("hybrid %s: failed to create final certificate: %v", name, err)
	}
	cert, err := x509.ParseCertificate(certDER)
	if err != nil {
		log.Fatalf("hybrid %s: failed to parse final certificate: %v", name, err)
	}

	keyBytes, err := x509.MarshalPKCS8PrivateKey(subjectRSAKey)
	if err != nil {
		log.Fatalf("hybrid %s: failed to marshal RSA key: %v", name, err)
	}
	savePEMFile(filepath.Join(dir, name+"_hybrid.key"), "PRIVATE KEY", keyBytes)
	savePEMFile(filepath.Join(dir, name+"_hybrid.crt"), "CERTIFICATE", certDER)

	fmt.Printf("Generated hybrid certificate for %s (RSA subject/CA key reused, ML-DSA-65 subject/CA key reused, signed twice)\n", name)
	return cert
}

// Generates a Certificate Authority (CA) key and self-signed certificate.
func generateCACert(name, dir string) (*x509.Certificate, *rsa.PrivateKey) {
	caTemplate := &x509.Certificate{
		SerialNumber: big.NewInt(time.Now().UnixNano()),
		Subject: pkix.Name{
			CommonName: name,
		},
		NotBefore:             time.Now(),
		NotAfter:              time.Now().Add(365 * 24 * time.Hour),
		KeyUsage:              x509.KeyUsageCertSign | x509.KeyUsageCRLSign,
		IsCA:                  true,
		BasicConstraintsValid: true,
	}

	return generateSelfSignedCert(name, caTemplate, dir)
}

func generateSelfSignedCert(
	name string,
	template *x509.Certificate,
	dir string,
) (
	*x509.Certificate,
	*rsa.PrivateKey,
) {
	key, err := rsa.GenerateKey(rand.Reader, 4096)
	if err != nil {
		log.Fatalf("Failed to generate CA private key: %v", err)
	}

	certBytes, err := x509.CreateCertificate(
		rand.Reader,
		template,
		template,
		&key.PublicKey,
		key,
	)
	if err != nil {
		log.Fatalf("Failed to create CA certificate: %v", err)
	}
	// This is important for when generation the claim "x5c" of the JWK
	// corresponding to this cert.
	template.Raw = certBytes

	keyBytes, err := x509.MarshalPKCS8PrivateKey(key)
	if err != nil {
		log.Fatalf("Failed to create CA key: %v", err)
	}
	savePEMFile(filepath.Join(dir, name+".key"), "PRIVATE KEY", keyBytes)
	savePEMFile(filepath.Join(dir, name+".crt"), "CERTIFICATE", certBytes)

	fmt.Printf("Generated self signed certificate and key for %s\n", name)
	return template, key
}

// Generates a certificate signed by the CA.
func generateCert(
	name, orgID string,
	caCert *x509.Certificate,
	caKey *rsa.PrivateKey,
	dir string,
) (
	*x509.Certificate,
	*rsa.PrivateKey,
) {
	key, err := rsa.GenerateKey(rand.Reader, 4096)
	if err != nil {
		log.Fatalf("Failed to generate private key: %v", err)
	}

	cert := &x509.Certificate{
		SerialNumber: big.NewInt(time.Now().UnixNano()),
		Subject: pkix.Name{
			CommonName: name,
			ExtraNames: []pkix.AttributeTypeAndValue{
				{
					Type:  oidX500UID,
					Value: name,
				},
				{
					Type:  oidLDAPUID,
					Value: uuid.NewString(),
				},
				{
					Type:  oidOrganizationID,
					Value: orgID,
				},
			},
		},
		DNSNames: []string{
			"auth.local",
			"matls-auth.local",
			"api.local",
			"matls-api.local",
			"directory",
			"directory.local",
			"keystore",
		},
		IPAddresses: []net.IP{net.ParseIP("127.0.0.1"), net.ParseIP("::1")},
		NotBefore:   time.Now(),
		NotAfter:    time.Now().Add(365 * 24 * time.Hour),
		KeyUsage:    x509.KeyUsageDigitalSignature,
		ExtKeyUsage: []x509.ExtKeyUsage{x509.ExtKeyUsageClientAuth},
	}

	// Create client certificate signed by the CA.
	certBytes, err := x509.CreateCertificate(
		rand.Reader,
		cert,
		caCert,
		&key.PublicKey,
		caKey,
	)
	if err != nil {
		log.Fatalf("Failed to create certificate: %v", err)
	}
	// This is important for when generation the claim "x5c" of the JWK
	// corresponding to this cert.
	cert.Raw = certBytes

	// Save private key and certificate.
	keyBytes, err := x509.MarshalPKCS8PrivateKey(key)
	if err != nil {
		log.Fatalf("Failed to create key: %v", err)
	}
	savePEMFile(filepath.Join(dir, name+".key"), "PRIVATE KEY", keyBytes)
	savePEMFile(filepath.Join(dir, name+".crt"), "CERTIFICATE", certBytes)

	fmt.Printf("Generated key and certificate for %s\n", name)
	return cert, key
}

// Saves data to a PEM file.
func savePEMFile(filename, blockType string, data []byte) {
	file, err := os.Create(filename)
	if err != nil {
		log.Fatalf("Failed to create %s: %v", filename, err)
	}
	defer file.Close()

	err = pem.Encode(file, &pem.Block{Type: blockType, Bytes: data})
	if err != nil {
		log.Fatalf("Failed to write PEM data to %s: %v", filename, err)
	}
}

func generateJWKS(
	name string,
	cert *x509.Certificate,
	key *rsa.PrivateKey,
	dir string,
) {
	sigJWK := goidc.JSONWebKey{
		Key:          key,
		KeyID:        uuid.NewString(),
		Algorithm:    string(goidc.PS256),
		Use:          string(goidc.KeyUsageSignature),
		Certificates: []*x509.Certificate{cert},
	}
	hash := sha256.New()
	_, _ = hash.Write(cert.Raw)
	sigJWK.CertificateThumbprintSHA256 = hash.Sum(nil)

	encKey := generateEncryptionJWK()
	jwks := goidc.JSONWebKeySet{
		Keys: []goidc.JSONWebKey{sigJWK, encKey},
	}

	jwksBytes, err := json.MarshalIndent(jwks, "", " ")
	if err != nil {
		log.Fatal(err)
	}

	err = os.WriteFile(filepath.Join(dir, name+".jwks"), jwksBytes, 0644)
	if err != nil {
		log.Fatal(err)
	}

	var publicJWKS goidc.JSONWebKeySet
	for _, jwk := range jwks.Keys {
		publicJWKS.Keys = append(publicJWKS.Keys, jwk.Public())
	}

	publicJWKSBytes, err := json.MarshalIndent(publicJWKS, "", " ")
	if err != nil {
		log.Fatal(err)
	}

	err = os.WriteFile(filepath.Join(dir, name+"_pub.jwks"), publicJWKSBytes, 0644)
	if err != nil {
		log.Fatal(err)
	}
}

// 5 years, not the original 1 -- the 1-year CA this tool used to generate
// expired mid-thesis (2026-08-21) and took down TLS for the entire
// environment (every cert here is signed by it), not just Experiment 3.
// See thesis/results/v4/DECISIONS.md.
const longLivedValidity = 5 * 365 * 24 * time.Hour

var resignRSANames = []string{"mtls", "op", "client_one", "client_two"}
var resignMLDSANames = []string{"mtls_pqc", "op_pqc", "client_one_pqc", "root_ca_pqc", "issuer_ca_pqc"}

// Regenerates the CA (fresh key, 5-year validity) and re-signs every leaf
// certificate this tool originally generated, reusing each leaf's existing
// private key unchanged -- only the certificate wrapper (issuer, validity,
// signature) is new. This preserves every already-measured JWK/cert byte
// size (client_cert_der_bytes(), JWK thumbprints, etc.) across Experiments
// 1 and 2's committed data, since none of those measurements depend on
// certificate validity dates or which CA signed them.
//
// mongo.pem/mongo.crt/postgres.crt are NOT touched here -- they were never
// generated by this tool (different SAN sets: DNS:mongodb/psql,localhost,
// 127.0.0.1 vs this tool's auth.local/api.local/directory/... list; 2048-bit
// RSA keys vs this tool's 4096-bit), and no generator script for them was
// found in the repository. They're re-signed separately with openssl,
// reusing their own existing keys the same way.
// The exact organizationIdentifier every committed RSA cert (mtls/op/
// client_one/client_two) already shares, extracted from the previously-
// committed certs before regenerating anything -- reusing it exactly
// (rather than a fresh random org_id, which would still be a valid X.509
// value but a different byte length) keeps every RSA cert's DER length
// byte-for-byte identical to what's already committed. The ML-DSA-65
// certs each originally got their own independent random org_id (not
// this one) since they were generated one at a time via separate
// `-pqc-name` invocations -- their DER length only depends on that
// org_id's *length* (a plain UUID, 36 chars, same as a fresh
// uuid.NewString() default), not its specific value, so those keep using
// the ordinary random default below.
const originalRSAOrgID = "OPIBR-76b370e3-def5-4798-8b6a-915cb5d6dd74"

func resignEverything(dir, _ string) {
	caTemplate := &x509.Certificate{
		SerialNumber:          big.NewInt(time.Now().UnixNano()),
		Subject:               pkix.Name{CommonName: "ca"},
		NotBefore:             time.Now(),
		NotAfter:              time.Now().Add(longLivedValidity),
		KeyUsage:              x509.KeyUsageCertSign | x509.KeyUsageCRLSign,
		IsCA:                  true,
		BasicConstraintsValid: true,
	}
	rawCACert, caKey := generateSelfSignedCert("ca", caTemplate, dir)
	// generateSelfSignedCert returns the same *x509.Certificate struct that
	// was passed in as a template -- it never had PublicKey/SubjectKeyId
	// populated (those exist only in the encoded DER, via rawCACert.Raw).
	// x509.CreateCertificate needs at least one of those two fields set on
	// the *parent* struct to emit an AuthorityKeyIdentifier extension on
	// children signed against it; passing the raw template silently omits
	// that extension from every child (caught by comparing DER byte lengths
	// against the previously-committed certs -- see DECISIONS.md). Re-
	// parsing from the actual DER bytes gives a fully populated struct.
	parsedCACert, err := x509.ParseCertificate(rawCACert.Raw)
	if err != nil {
		log.Fatalf("resign: failed to re-parse freshly generated CA cert: %v", err)
	}
	fmt.Println("Regenerated CA (ca.crt/ca.key, fresh key, 5-year validity)")

	// Reproducing an existing asymmetry, not introducing one: the original
	// mtls/op/client_one/client_two certs were all issued in one run of
	// generateCACert() -> generateCert(), passing the *raw* (unparsed)
	// template as parent -- so they never got an AuthorityKeyIdentifier
	// extension (parent.PublicKey/.SubjectKeyId were empty on that struct).
	// The ML-DSA-65 certs were each issued later via `-pqc-name`, which
	// calls loadCACert() -- x509.ParseCertificate on ca.crt from disk,
	// giving a fully populated struct -- so they DID get one. Matching
	// each original exactly (confirmed via DER byte-length comparison
	// against the previously-committed certs) means using rawCACert for
	// the RSA group and parsedCACert for the ML-DSA-65 group here, not the
	// same value for both.
	for _, name := range resignRSANames {
		resignRSACert(name, originalRSAOrgID, rawCACert, caKey, dir)
	}
	for _, name := range resignMLDSANames {
		resignMLDSACert(name, uuid.NewString(), parsedCACert, caKey, dir)
	}

	// client_one/client_two's JWKS embed the certificate (x5c) and its
	// SHA-256 thumbprint -- both changed by re-signing, even though the
	// underlying RSA signing key (and therefore its JWK thumbprint/kid,
	// wherever that's used instead of the x5t#S256) did not.
	for _, name := range []string{"client_one", "client_two"} {
		cert := loadCertPEM(filepath.Join(dir, name+".crt"))
		key := loadRSAKeyPEM(filepath.Join(dir, name+".key"))
		generateJWKS(name, cert, key, dir)
	}

	fmt.Println("Resign complete for: " + fmt.Sprint(append(append([]string{}, resignRSANames...), resignMLDSANames...)))
	fmt.Println("NOT touched (not this tool's cert format): mongo.pem, mongo.crt, postgres.crt -- re-sign separately.")
}

func loadCertPEM(path string) *x509.Certificate {
	certPEM, err := os.ReadFile(path)
	if err != nil {
		log.Fatalf("Failed to read %s: %v", path, err)
	}
	block, _ := pem.Decode(certPEM)
	if block == nil {
		log.Fatalf("Failed to decode PEM in %s", path)
	}
	cert, err := x509.ParseCertificate(block.Bytes)
	if err != nil {
		log.Fatalf("Failed to parse certificate in %s: %v", path, err)
	}
	return cert
}

func loadRSAKeyPEM(path string) *rsa.PrivateKey {
	keyPEM, err := os.ReadFile(path)
	if err != nil {
		log.Fatalf("Failed to read %s: %v", path, err)
	}
	block, _ := pem.Decode(keyPEM)
	if block == nil {
		log.Fatalf("Failed to decode PEM in %s", path)
	}
	keyAny, err := x509.ParsePKCS8PrivateKey(block.Bytes)
	if err != nil {
		log.Fatalf("Failed to parse key in %s: %v", path, err)
	}
	key, ok := keyAny.(*rsa.PrivateKey)
	if !ok {
		log.Fatalf("%s is not an RSA private key (got %T)", path, keyAny)
	}
	return key
}

func loadMLDSAKeyPEM(path string) *mldsa.PrivateKey {
	keyPEM, err := os.ReadFile(path)
	if err != nil {
		log.Fatalf("Failed to read %s: %v", path, err)
	}
	block, _ := pem.Decode(keyPEM)
	if block == nil {
		log.Fatalf("Failed to decode PEM in %s", path)
	}
	keyAny, err := x509.ParsePKCS8PrivateKey(block.Bytes)
	if err != nil {
		log.Fatalf("Failed to parse key in %s: %v", path, err)
	}
	key, ok := keyAny.(*mldsa.PrivateKey)
	if !ok {
		log.Fatalf("%s is not an ML-DSA private key (got %T)", path, keyAny)
	}
	return key
}

// Same certificate template generateCert() uses (identical DNSNames/
// IPAddresses/KeyUsage/ExtKeyUsage, since every cert this tool has ever
// issued shares that one generic template, differing only by CommonName) --
// but signs the *existing* key loaded from disk instead of generating a new
// one.
func resignRSACert(name, orgID string, caCert *x509.Certificate, caKey *rsa.PrivateKey, dir string) {
	key := loadRSAKeyPEM(filepath.Join(dir, name+".key"))

	cert := &x509.Certificate{
		SerialNumber: big.NewInt(time.Now().UnixNano()),
		Subject: pkix.Name{
			CommonName: name,
			ExtraNames: []pkix.AttributeTypeAndValue{
				{Type: oidX500UID, Value: name},
				{Type: oidLDAPUID, Value: uuid.NewString()},
				{Type: oidOrganizationID, Value: orgID},
			},
		},
		DNSNames: []string{
			"auth.local", "matls-auth.local", "api.local", "matls-api.local",
			"directory", "directory.local", "keystore",
		},
		IPAddresses: []net.IP{net.ParseIP("127.0.0.1"), net.ParseIP("::1")},
		NotBefore:   time.Now(),
		NotAfter:    time.Now().Add(longLivedValidity),
		KeyUsage:    x509.KeyUsageDigitalSignature,
		ExtKeyUsage: []x509.ExtKeyUsage{x509.ExtKeyUsageClientAuth},
	}

	certBytes, err := x509.CreateCertificate(rand.Reader, cert, caCert, &key.PublicKey, caKey)
	if err != nil {
		log.Fatalf("resign %s: failed to create certificate: %v", name, err)
	}
	savePEMFile(filepath.Join(dir, name+".crt"), "CERTIFICATE", certBytes)
	fmt.Printf("Re-signed %s.crt (same RSA key, new CA, 5-year validity)\n", name)
}

// Same template generateClientCertPQC() uses, signing the existing ML-DSA-65
// key loaded from disk instead of generating a new one.
func resignMLDSACert(name, orgID string, caCert *x509.Certificate, caKey *rsa.PrivateKey, dir string) {
	key := loadMLDSAKeyPEM(filepath.Join(dir, name+".key"))

	cert := &x509.Certificate{
		SerialNumber: big.NewInt(time.Now().UnixNano()),
		Subject: pkix.Name{
			CommonName: name,
			ExtraNames: []pkix.AttributeTypeAndValue{
				{Type: oidX500UID, Value: name},
				{Type: oidLDAPUID, Value: uuid.NewString()},
				{Type: oidOrganizationID, Value: orgID},
			},
		},
		DNSNames: []string{
			"auth.local", "matls-auth.local", "api.local", "matls-api.local",
			"directory", "directory.local", "keystore",
		},
		IPAddresses: []net.IP{net.ParseIP("127.0.0.1"), net.ParseIP("::1")},
		NotBefore:   time.Now(),
		NotAfter:    time.Now().Add(longLivedValidity),
		KeyUsage:    x509.KeyUsageDigitalSignature,
		ExtKeyUsage: []x509.ExtKeyUsage{x509.ExtKeyUsageClientAuth},
	}

	certBytes, err := x509.CreateCertificate(rand.Reader, cert, caCert, key.Public(), caKey)
	if err != nil {
		log.Fatalf("resign %s: failed to create certificate: %v", name, err)
	}
	savePEMFile(filepath.Join(dir, name+".crt"), "CERTIFICATE", certBytes)
	fmt.Printf("Re-signed %s.crt (same ML-DSA-65 key, new CA, 5-year validity)\n", name)
}

func generateEncryptionJWK() goidc.JSONWebKey {
	key, err := rsa.GenerateKey(rand.Reader, 4096)
	if err != nil {
		log.Fatalf("Failed to generate RSA private key: %v", err)
	}

	return goidc.JSONWebKey{
		Key:       key,
		KeyID:     uuid.NewString(),
		Algorithm: string(goidc.RSA_OAEP),
		Use:       string(goidc.KeyUsageEncryption),
	}
}
