package main

// Forked from mock-service-os/mock_mtls/hybridVerification.go (commit
// 7c722f6347b48a8d6a100b9197b7dc99f9146be5), unchanged except
// hybridVerifyPeerCertificateFunc's signature below -- see its own
// comment and DECISIONS.md, Decisao 12, for the diff against the
// original.

import (
	"crypto/mldsa"
	"crypto/x509"
	"crypto/x509/pkix"
	"encoding/asn1"
	"encoding/pem"
	"fmt"
	"log"
	"math/big"
	"os"
)

// Strong Nesting adapted to X.509 certificates (Bindel, Herath, McKague &
// Stebila, 2017, PQCrypto; extension mechanism per Bindel, Braun, Gladiator,
// Stebila & Wiggers, "X.509-Compliant Hybrid Certificates for the
// Post-Quantum Transition", JOSS 4(40), 1606, 2019), applied here to the
// client mTLS certificate the gateway receives in hibrido-v8 mode. See
// thesis/results/v9/certs/main.go's generateHybridV8Leaf for the signing
// side.
var (
	oidAltSignatureValue = asn1.ObjectIdentifier{2, 5, 29, 74}
)

// tbsCertificateForSurgery mirrors RFC 5280 Section 4.1's TBSCertificate
// exactly. Every field except Extensions is an opaque asn1.RawValue -- this
// is only ever used to remove the AltSignatureValue extension and
// re-encode, never to interpret or change anything else about the TBS. DER
// is canonical (one encoding per abstract value), so re-marshaling the
// filtered struct reproduces, byte for byte, whatever preTBSCertificate the
// signer actually signed.
type tbsCertificateForSurgery struct {
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

// reconstructPreTBS takes a hybrid certificate's final TBSCertificate bytes
// (three extensions: SubjectAltPublicKeyInfo, AltSignatureAlgorithm,
// AltSignatureValue) and returns what it was before AltSignatureValue was
// added -- exactly the bytes the CA's ML-DSA-65 key signed.
func reconstructPreTBS(finalTBS []byte) ([]byte, error) {
	var tbs tbsCertificateForSurgery
	if _, err := asn1.Unmarshal(finalTBS, &tbs); err != nil {
		return nil, fmt.Errorf("failed to unmarshal TBSCertificate: %w", err)
	}
	var filtered []pkix.Extension
	removed := 0
	for _, ext := range tbs.Extensions {
		if ext.Id.Equal(oidAltSignatureValue) {
			removed++
			continue
		}
		filtered = append(filtered, ext)
	}
	if removed != 1 {
		return nil, fmt.Errorf("expected exactly one AltSignatureValue extension, found %d", removed)
	}
	tbs.Extensions = filtered
	tbs.Raw = nil // force a genuine re-encode instead of replaying finalTBS verbatim
	newTBS, err := asn1.Marshal(tbs)
	if err != nil {
		return nil, fmt.Errorf("failed to re-marshal TBSCertificate: %w", err)
	}
	return newTBS, nil
}

func findExtension(cert *x509.Certificate, oid asn1.ObjectIdentifier) ([]byte, bool) {
	for _, ext := range cert.Extensions {
		if ext.Id.Equal(oid) {
			return ext.Value, true
		}
	}
	return nil, false
}

// verifyHybridClientCert implements the AND gate: the primary RSA signature
// is NOT re-checked here -- crypto/tls's own, unmodified chain verification
// (ClientAuth + ClientCAs, already configured) already did that before this
// function is ever called (VerifyPeerCertificate runs "after normal
// certificate verification", per crypto/tls's own documentation). This
// function only adds the second, ML-DSA-65 half: reconstruct preTBS from
// the received leaf certificate and verify AltSignatureValue against it
// using the CA's ML-DSA-65 public key. The connection is accepted only if
// both halves are valid -- rejecting here (returning a non-nil error) aborts
// the handshake, exactly like a failed RSA chain check would.
func verifyHybridClientCert(leaf *x509.Certificate, caAltPub *mldsa.PublicKey) error {
	altSigDER, ok := findExtension(leaf, oidAltSignatureValue)
	if !ok {
		return fmt.Errorf("hibrido-v8 mTLS: client certificate is missing the AltSignatureValue extension")
	}
	var altSig asn1.BitString
	if _, err := asn1.Unmarshal(altSigDER, &altSig); err != nil {
		return fmt.Errorf("hibrido-v8 mTLS: failed to unmarshal AltSignatureValue: %w", err)
	}

	preTBS, err := reconstructPreTBS(leaf.RawTBSCertificate)
	if err != nil {
		return fmt.Errorf("hibrido-v8 mTLS: failed to reconstruct preTBSCertificate: %w", err)
	}

	if err := mldsa.Verify(caAltPub, preTBS, altSig.Bytes, nil); err != nil {
		return fmt.Errorf("hibrido-v8 mTLS: ML-DSA-65 alt signature verification failed: %w", err)
	}
	return nil
}

// hybridVerifyPeerCertificateFunc returns the tls.Config.VerifyPeerCertificate
// callback for hibrido-v8 mode.
//
// DIFF vs. the original (mock_mtls, commit 7c722f6347b4): the original took
// no arguments, read CRYPTO_PROFILE itself to decide whether to activate,
// and read a package-level const (issuerCaPqcFilePath) for the CA cert
// path. This fork takes caMldsaCertPath explicitly instead -- this harness's
// main.go already dispatches on CRYPTO_PROFILE/profile name before calling
// this function, so the activation check would be redundant, and this
// harness's cert layout (thesis/results/v9/certs/main.go's output) uses a
// different path/filename than mock_mtls's. Pure plumbing change: the
// cryptographic logic above (verifyHybridClientCert, reconstructPreTBS) is
// byte-for-byte identical to the original.
func hybridVerifyPeerCertificateFunc(caMldsaCertPath string) func([][]byte, [][]*x509.Certificate) error {
	caPqcBytes, err := os.ReadFile(caMldsaCertPath)
	if err != nil {
		log.Fatalf("hibrido-v8 mTLS: unable to read %s: %v", caMldsaCertPath, err)
	}
	block, _ := pem.Decode(caPqcBytes)
	if block == nil {
		log.Fatalf("hibrido-v8 mTLS: unable to decode %s PEM", caMldsaCertPath)
	}
	caPqcCert, err := x509.ParseCertificate(block.Bytes)
	if err != nil {
		log.Fatalf("hibrido-v8 mTLS: unable to parse %s: %v", caMldsaCertPath, err)
	}
	caAltPub, ok := caPqcCert.PublicKey.(*mldsa.PublicKey)
	if !ok {
		log.Fatalf("hibrido-v8 mTLS: %s's public key is not ML-DSA (got %T)", caMldsaCertPath, caPqcCert.PublicKey)
	}

	return func(rawCerts [][]byte, _ [][]*x509.Certificate) error {
		// No client cert presented: shouldn't happen here since the gateway
		// requires RequireAndVerifyClientCert in every profile (T5 requirement),
		// but guard anyway rather than panic on an empty slice.
		if len(rawCerts) == 0 {
			return fmt.Errorf("hibrido-v8 mTLS: no client certificate presented")
		}
		leaf, err := x509.ParseCertificate(rawCerts[0])
		if err != nil {
			return fmt.Errorf("hibrido-v8 mTLS: failed to parse client certificate: %w", err)
		}
		if err := verifyHybridClientCert(leaf, caAltPub); err != nil {
			log.Printf("hibrido-v8 mTLS: client certificate rejected (subject=%s): %v", leaf.Subject.String(), err)
			return err
		}
		log.Printf("hibrido-v8 mTLS: client certificate AND gate passed (RSA + ML-DSA-65 both valid, subject=%s)", leaf.Subject.String())
		return nil
	}
}
