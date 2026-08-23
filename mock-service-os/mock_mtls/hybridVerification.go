package main

import (
	"crypto/mldsa"
	"crypto/x509"
	"crypto/x509/pkix"
	"encoding/asn1"
	"encoding/pem"
	"fmt"
	"log/slog"
	"math/big"
	"os"
)

// Strong Nesting adapted to X.509 certificates (Bindel, Herath, McKague &
// Stebila, 2017, PQCrypto; extension mechanism per Bindel, Braun, Gladiator,
// Stebila & Wiggers, "X.509-Compliant Hybrid Certificates for the
// Post-Quantum Transition", JOSS 4(40), 1606, 2019), applied here to the
// client mTLS certificate the gateway receives in hybrid mode. See
// certs/main.go's generateHybridCert for the signing side and
// thesis/results/v4/DECISIONS.md (Etapa 6) for the full writeup of why the
// signing order here is the reverse of the architecture doc's simplified
// prose.
var (
	oidAltSignatureValue = asn1.ObjectIdentifier{2, 5, 29, 74}
)

// tbsCertificateForSurgery mirrors RFC 5280 Section 4.1's TBSCertificate
// exactly. Every field except Extensions is an opaque asn1.RawValue -- this
// is only ever used to remove the AltSignatureValue extension and
// re-encode, never to interpret or change anything else about the TBS. DER
// is canonical (one encoding per abstract value), so re-marshaling the
// filtered struct reproduces, byte for byte, whatever preTBSCertificate the
// signer actually signed -- confirmed empirically against
// certs/main.go's own generateHybridCert output before wiring this in.
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
		return fmt.Errorf("hybrid mTLS: client certificate is missing the AltSignatureValue extension")
	}
	var altSig asn1.BitString
	if _, err := asn1.Unmarshal(altSigDER, &altSig); err != nil {
		return fmt.Errorf("hybrid mTLS: failed to unmarshal AltSignatureValue: %w", err)
	}

	preTBS, err := reconstructPreTBS(leaf.RawTBSCertificate)
	if err != nil {
		return fmt.Errorf("hybrid mTLS: failed to reconstruct preTBSCertificate: %w", err)
	}

	if err := mldsa.Verify(caAltPub, preTBS, altSig.Bytes, nil); err != nil {
		return fmt.Errorf("hybrid mTLS: ML-DSA-65 alt signature verification failed: %w", err)
	}
	return nil
}

// hybridVerifyPeerCertificateFunc returns the tls.Config.VerifyPeerCertificate
// callback for hybrid mode, or nil (no extra check) for classic/pqc -- the
// caller (tlsConfiguration) can assign this field unconditionally. Loading
// issuerCaPqcFilePath's public key once here, rather than per-handshake,
// matches how caCertPool() is already loaded once at startup.
func hybridVerifyPeerCertificateFunc() func([][]byte, [][]*x509.Certificate) error {
	if os.Getenv("CRYPTO_PROFILE") != "hybrid" {
		return nil
	}

	caPqcBytes, err := os.ReadFile(issuerCaPqcFilePath)
	if err != nil {
		slog.Error("hybrid mTLS: unable to read issuer_ca_pqc.crt", slog.String("err", err.Error()))
		os.Exit(1)
	}
	block, _ := pem.Decode(caPqcBytes)
	if block == nil {
		slog.Error("hybrid mTLS: unable to decode issuer_ca_pqc.crt PEM")
		os.Exit(1)
	}
	caPqcCert, err := x509.ParseCertificate(block.Bytes)
	if err != nil {
		slog.Error("hybrid mTLS: unable to parse issuer_ca_pqc.crt", slog.String("err", err.Error()))
		os.Exit(1)
	}
	caAltPub, ok := caPqcCert.PublicKey.(*mldsa.PublicKey)
	if !ok {
		slog.Error("hybrid mTLS: issuer_ca_pqc.crt's public key is not ML-DSA", slog.String("type", fmt.Sprintf("%T", caPqcCert.PublicKey)))
		os.Exit(1)
	}

	return func(rawCerts [][]byte, _ [][]*x509.Certificate) error {
		// No client cert presented: ClientAuth is VerifyClientCertIfGiven
		// (optional), so this is not itself an error -- nothing to AND-gate.
		if len(rawCerts) == 0 {
			return nil
		}
		leaf, err := x509.ParseCertificate(rawCerts[0])
		if err != nil {
			return fmt.Errorf("hybrid mTLS: failed to parse client certificate: %w", err)
		}
		if err := verifyHybridClientCert(leaf, caAltPub); err != nil {
			slog.Error("hybrid mTLS: client certificate rejected", slog.String("subject", leaf.Subject.String()), slog.String("err", err.Error()))
			return err
		}
		slog.Info("hybrid mTLS: client certificate AND gate passed (RSA + ML-DSA-65 both valid)", slog.String("subject", leaf.Subject.String()))
		return nil
	}
}
