// interop builds a SECOND, deliberately different configuration from
// the v9 measurement harness (gateway/proxy) -- DECISIONS.md, Decisao
// 21: "configuracao de interoperabilidade", used ONLY for this one
// test, never for measurement. The measurement config (T5) locks each
// profile to exactly one KEX group and its own dedicated CA, by
// design (clean, one-variable-at-a-time comparison) -- which means
// every cross-profile pairing fails for a CONFIGURATION reason
// (wrong group offered, unrelated CA), never tells you whether
// classical and migrated peers could ACTUALLY interoperate if they
// both offered every group and shared a trust root. This program
// builds that second world: one shared RSA-2048 CA, one shared
// ML-DSA-65 CA, every participant offers all three KEX groups and
// trusts both CAs, and measures what happens.
package main

import (
	"crypto/mldsa"
	"crypto/rand"
	"crypto/rsa"
	"crypto/tls"
	"crypto/x509"
	"crypto/x509/pkix"
	"encoding/asn1"
	"fmt"
	"math/big"
	"sync/atomic"
	"time"
)

const validity = 24 * time.Hour

var serial atomic.Int64

func nextSerial() *big.Int { return big.NewInt(serial.Add(1)) }

var allGroups = []tls.CurveID{tls.CurveP384, tls.MLKEM1024, tls.SecP384r1MLKEM1024}

// --- cert generation (in memory only, no files -- this test never
// touches disk, let alone commits anything) ---

func rsaCA() (*x509.Certificate, *rsa.PrivateKey) {
	key, err := rsa.GenerateKey(rand.Reader, 2048)
	must(err)
	tmpl := &x509.Certificate{
		SerialNumber: nextSerial(), Subject: pkix.Name{CommonName: "interop-shared-rsa-ca"},
		NotBefore: time.Now(), NotAfter: time.Now().Add(validity),
		KeyUsage: x509.KeyUsageCertSign | x509.KeyUsageCRLSign, IsCA: true, BasicConstraintsValid: true,
	}
	der, err := x509.CreateCertificate(rand.Reader, tmpl, tmpl, &key.PublicKey, key)
	must(err)
	cert, err := x509.ParseCertificate(der)
	must(err)
	return cert, key
}

func rsaLeaf(name string, ca *x509.Certificate, caKey *rsa.PrivateKey, eku x509.ExtKeyUsage) tls.Certificate {
	key, err := rsa.GenerateKey(rand.Reader, 2048)
	must(err)
	tmpl := &x509.Certificate{
		SerialNumber: nextSerial(), Subject: pkix.Name{CommonName: name},
		DNSNames: []string{"interop"}, NotBefore: time.Now(), NotAfter: time.Now().Add(validity),
		KeyUsage: x509.KeyUsageDigitalSignature, ExtKeyUsage: []x509.ExtKeyUsage{eku},
	}
	der, err := x509.CreateCertificate(rand.Reader, tmpl, ca, &key.PublicKey, caKey)
	must(err)
	return tls.Certificate{Certificate: [][]byte{der}, PrivateKey: key}
}

func mldsaCA() (*x509.Certificate, *mldsa.PrivateKey) {
	key, err := mldsa.GenerateKey(mldsa.MLDSA65())
	must(err)
	tmpl := &x509.Certificate{
		SerialNumber: nextSerial(), Subject: pkix.Name{CommonName: "interop-shared-mldsa-ca"},
		NotBefore: time.Now(), NotAfter: time.Now().Add(validity),
		KeyUsage: x509.KeyUsageCertSign | x509.KeyUsageCRLSign, IsCA: true, BasicConstraintsValid: true,
	}
	der, err := x509.CreateCertificate(rand.Reader, tmpl, tmpl, key.Public(), key)
	must(err)
	cert, err := x509.ParseCertificate(der)
	must(err)
	return cert, key
}

func mldsaLeaf(name string, ca *x509.Certificate, caKey *mldsa.PrivateKey, eku x509.ExtKeyUsage) tls.Certificate {
	key, err := mldsa.GenerateKey(mldsa.MLDSA65())
	must(err)
	tmpl := &x509.Certificate{
		SerialNumber: nextSerial(), Subject: pkix.Name{CommonName: name},
		DNSNames: []string{"interop"}, NotBefore: time.Now(), NotAfter: time.Now().Add(validity),
		KeyUsage: x509.KeyUsageDigitalSignature, ExtKeyUsage: []x509.ExtKeyUsage{eku},
	}
	der, err := x509.CreateCertificate(rand.Reader, tmpl, ca, key.Public(), caKey)
	must(err)
	return tls.Certificate{Certificate: [][]byte{der}, PrivateKey: key}
}

// --- Hibrido-v8 dual X.509 signature (Bindel et al. 2019), copied
// from thesis/results/v9/certs/main.go's own generateHybridV8Leaf --
// same mechanism, parameterized here on the SHARED CAs instead of
// Hibrido-v8's own dedicated ones. ---

var (
	oidSubjectAltPublicKeyInfo = asn1.ObjectIdentifier{2, 5, 29, 72}
	oidAltSignatureAlgorithm   = asn1.ObjectIdentifier{2, 5, 29, 73}
	oidAltSignatureValue       = asn1.ObjectIdentifier{2, 5, 29, 74}
	oidMLDSA65                 = asn1.ObjectIdentifier{2, 16, 840, 1, 101, 3, 4, 3, 18}
)

type bareAlgorithmIdentifier struct{ Algorithm asn1.ObjectIdentifier }
type hybridSPKI struct {
	Algorithm bareAlgorithmIdentifier
	PublicKey asn1.BitString
}

func hybridExtensions(altPub *mldsa.PublicKey) (pkix.Extension, pkix.Extension) {
	spkiDER, err := asn1.Marshal(hybridSPKI{bareAlgorithmIdentifier{oidMLDSA65}, asn1.BitString{Bytes: altPub.Bytes(), BitLength: len(altPub.Bytes()) * 8}})
	must(err)
	algIDDER, err := asn1.Marshal(bareAlgorithmIdentifier{oidMLDSA65})
	must(err)
	return pkix.Extension{Id: oidSubjectAltPublicKeyInfo, Value: spkiDER},
		pkix.Extension{Id: oidAltSignatureAlgorithm, Value: algIDDER}
}

func altSigExt(sig []byte) pkix.Extension {
	der, err := asn1.Marshal(asn1.BitString{Bytes: sig, BitLength: len(sig) * 8})
	must(err)
	return pkix.Extension{Id: oidAltSignatureValue, Value: der}
}

func extractTBS(certDER []byte) []byte {
	var cert struct {
		TBSCertificate     asn1.RawValue
		SignatureAlgorithm asn1.RawValue
		SignatureValue     asn1.BitString
	}
	_, err := asn1.Unmarshal(certDER, &cert)
	must(err)
	return cert.TBSCertificate.FullBytes
}

func hybridLeaf(name string, caRSA *x509.Certificate, caRSAKey *rsa.PrivateKey, caMLDSAKey *mldsa.PrivateKey, eku x509.ExtKeyUsage) tls.Certificate {
	key, err := rsa.GenerateKey(rand.Reader, 2048)
	must(err)
	altKey, err := mldsa.GenerateKey(mldsa.MLDSA65())
	must(err)
	spkiExt, algExt := hybridExtensions(altKey.PublicKey())

	tmpl := &x509.Certificate{
		SerialNumber: nextSerial(), Subject: pkix.Name{CommonName: name},
		DNSNames: []string{"interop"}, NotBefore: time.Now(), NotAfter: time.Now().Add(validity),
		KeyUsage: x509.KeyUsageDigitalSignature, ExtKeyUsage: []x509.ExtKeyUsage{eku},
		ExtraExtensions: []pkix.Extension{spkiExt, algExt},
	}
	preDER, err := x509.CreateCertificate(rand.Reader, tmpl, caRSA, &key.PublicKey, caRSAKey)
	must(err)
	sigmaAlt, err := caMLDSAKey.Sign(nil, extractTBS(preDER), nil)
	must(err)
	tmpl.ExtraExtensions = []pkix.Extension{spkiExt, algExt, altSigExt(sigmaAlt)}
	der, err := x509.CreateCertificate(rand.Reader, tmpl, caRSA, &key.PublicKey, caRSAKey)
	must(err)
	return tls.Certificate{Certificate: [][]byte{der}, PrivateKey: key}
}

// verifyHybridAltSig: same reconstruction as gateway/hybridVerification.go,
// used here to build the hibrido-v8 server's VerifyPeerCertificate.
func reconstructPreTBS(finalTBS []byte) []byte {
	type tbsSurgery struct {
		Raw                asn1.RawContent
		Version            int `asn1:"optional,explicit,default:0,tag:0"`
		SerialNumber       *big.Int
		SignatureAlgorithm pkix.AlgorithmIdentifier
		Issuer             asn1.RawValue
		Validity           asn1.RawValue
		Subject            asn1.RawValue
		PublicKey          asn1.RawValue
		Extensions         []pkix.Extension `asn1:"optional,explicit,tag:3"`
	}
	var tbs tbsSurgery
	_, err := asn1.Unmarshal(finalTBS, &tbs)
	must(err)
	var filtered []pkix.Extension
	for _, ext := range tbs.Extensions {
		if !ext.Id.Equal(oidAltSignatureValue) {
			filtered = append(filtered, ext)
		}
	}
	tbs.Extensions = filtered
	tbs.Raw = nil
	out, err := asn1.Marshal(tbs)
	must(err)
	return out
}

func hybridVerifyFunc(caAltPub *mldsa.PublicKey) func([][]byte, [][]*x509.Certificate) error {
	return func(rawCerts [][]byte, _ [][]*x509.Certificate) error {
		if len(rawCerts) == 0 {
			return fmt.Errorf("no client certificate presented")
		}
		leaf, err := x509.ParseCertificate(rawCerts[0])
		if err != nil {
			return err
		}
		var altSigDER []byte
		for _, ext := range leaf.Extensions {
			if ext.Id.Equal(oidAltSignatureValue) {
				altSigDER = ext.Value
			}
		}
		if altSigDER == nil {
			return fmt.Errorf("missing AltSignatureValue extension")
		}
		var altSig asn1.BitString
		if _, err := asn1.Unmarshal(altSigDER, &altSig); err != nil {
			return err
		}
		preTBS := reconstructPreTBS(leaf.RawTBSCertificate)
		return mldsa.Verify(caAltPub, preTBS, altSig.Bytes, nil)
	}
}

func must(err error) {
	if err != nil {
		panic(err)
	}
}
