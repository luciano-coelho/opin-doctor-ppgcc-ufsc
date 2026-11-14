package main

import (
	"crypto/tls"
	"crypto/x509"
	"os"
	"testing"
)

// TestInternalCarveOutPresentsServerPurposedCert is a regression guard for
// the real bug found this round: attachInternalCallerCarveOut used to load
// mtls.crt (ExtKeyUsage=ClientAuth only, shared template with op.crt/
// client_one.crt/client_two.crt) as its SERVER identity for the
// matls-api.local internal carve-out. Go's crypto/tls never checked EKU
// purpose, so it worked silently; Node's TLS stack does, and rejected it
// with "unsuitable certificate purpose" the moment adapter.js's
// rejectUnauthorized went from false to true. Fixed by generating a
// dedicated mtls_internal_server.crt (ExtKeyUsage=ServerAuth). This test
// drives the real GetConfigForClient callback with a fake ClientHelloInfo
// (ServerName=matls-api.local, same as a real internal call) and asserts
// the leaf certificate it hands back really carries ServerAuth -- never
// trusts the filename alone.
func TestInternalCarveOutPresentsServerPurposedCert(t *testing.T) {
	realCertsDir := os.Getenv("REAL_CERTS_DIR")
	if realCertsDir == "" {
		t.Skip("REAL_CERTS_DIR not set -- skipping (needs mock-service-os/certs mounted)")
	}

	cfg := &tls.Config{}
	if err := attachInternalCallerCarveOut(cfg, "classico"); err != nil {
		t.Fatalf("attachInternalCallerCarveOut: %v", err)
	}

	internalCfg, err := cfg.GetConfigForClient(&tls.ClientHelloInfo{ServerName: internalCallerSNI})
	if err != nil {
		t.Fatalf("GetConfigForClient(%q): %v", internalCallerSNI, err)
	}
	if internalCfg == nil {
		t.Fatalf("GetConfigForClient(%q) returned a nil config", internalCallerSNI)
	}
	if len(internalCfg.Certificates) != 1 {
		t.Fatalf("expected exactly 1 certificate on the internal carve-out config, got %d", len(internalCfg.Certificates))
	}

	leaf, err := x509.ParseCertificate(internalCfg.Certificates[0].Certificate[0])
	if err != nil {
		t.Fatalf("parsing the internal carve-out's leaf certificate: %v", err)
	}

	hasServerAuth := false
	for _, eku := range leaf.ExtKeyUsage {
		if eku == x509.ExtKeyUsageServerAuth {
			hasServerAuth = true
		}
		if eku == x509.ExtKeyUsageClientAuth {
			t.Errorf("internal carve-out's server cert (subject=%s) carries ExtKeyUsageClientAuth -- "+
				"this is the exact shared-template cert this fix was meant to stop reusing here (mtls.crt), "+
				"never mtls_internal_server.crt's own dedicated ServerAuth-only template", leaf.Subject)
		}
	}
	if !hasServerAuth {
		t.Errorf("internal carve-out's server cert (subject=%s) does not carry ExtKeyUsageServerAuth -- "+
			"Node's TLS stack (adapter.js, rejectUnauthorized=true) will reject it with "+
			"\"unsuitable certificate purpose\", exactly like it did before this fix", leaf.Subject)
	}
}

// TestInternalCarveOutAppliesToAllFourProfiles: the carve-out's cert choice
// is profile-INDEPENDENT (business_server.go's own doc comment: "for every
// profile unconditionally") -- confirmed here across all 4 real profile
// names this gateway accepts, never assumed from testing just one.
func TestInternalCarveOutAppliesToAllFourProfiles(t *testing.T) {
	realCertsDir := os.Getenv("REAL_CERTS_DIR")
	if realCertsDir == "" {
		t.Skip("REAL_CERTS_DIR not set -- skipping (needs mock-service-os/certs mounted)")
	}

	for _, profile := range []string{"classico", "pqc", "hibrido-v8", "hibrido-and"} {
		cfg := &tls.Config{}
		if err := attachInternalCallerCarveOut(cfg, profile); err != nil {
			t.Fatalf("attachInternalCallerCarveOut(%s): %v", profile, err)
		}
		internalCfg, err := cfg.GetConfigForClient(&tls.ClientHelloInfo{ServerName: internalCallerSNI})
		if err != nil || internalCfg == nil || len(internalCfg.Certificates) != 1 {
			t.Fatalf("profile %s: carve-out config is not usable (err=%v, cfg=%v)", profile, err, internalCfg)
		}
		leaf, err := x509.ParseCertificate(internalCfg.Certificates[0].Certificate[0])
		if err != nil {
			t.Fatalf("profile %s: parsing leaf cert: %v", profile, err)
		}
		found := false
		for _, eku := range leaf.ExtKeyUsage {
			if eku == x509.ExtKeyUsageServerAuth {
				found = true
			}
		}
		if !found {
			t.Errorf("profile %s: internal carve-out's cert lacks ExtKeyUsageServerAuth", profile)
		}
	}
}
