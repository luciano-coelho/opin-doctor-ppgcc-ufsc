package main

import (
	"crypto/sha256"
	"crypto/tls"
	"crypto/x509"
	"encoding/base64"
	"encoding/json"
	"encoding/pem"
	"fmt"
	"io"
	"log"
	"log/slog"
	"net"
	"net/http"
	"net/http/httputil"
	"net/url"
	"os"
	"strings"
	"sync"
	"sync/atomic"
	"time"

	"github.com/lestrrat-go/jwx/v3/jwa"
	"github.com/lestrrat-go/jwx/v3/jwk"
	"github.com/lestrrat-go/jwx/v3/jws"
)

const (
	caCertFilePath            = "certs/ca.crt"
	clientOnePublicJWKSPath   = "certs/client_one_pub.jwks"
	authURI                   = "http://auth:3000"
	participantsFilePath      = "mocks/participants.json"
	softwareStatementFilePath = "mocks/software_statement.json"

	// Local ML-DSA-65 stand-ins for Raidiam's real, external sandbox PKI
	// (crl.sandbox.pki.opinbrasil.com.br). Only ever served/requested when
	// CRYPTO_PROFILE=pqc -- opin_flow.py decides which URL to call, this
	// gateway just serves the content unconditionally if asked. See
	// thesis/results/v2/experiment2 - PQC/DECISIONS.md, Decision 11.
	//
	// issuerCaPqcFilePath has a SECOND, unrelated use: hybridVerification.go
	// reads it to get the CA's own ML-DSA-65 public key for the client
	// certificate AND gate -- that must always stay this pure-ML-DSA-65 cert,
	// in every profile, regardless of what /issuer-ca.pem itself serves.
	// Deliberately kept a `const`, not folded into the CRYPTO_PROFILE-keyed
	// serving vars below, so the two uses can never accidentally couple.
	rootCaPqcFilePath   = "certs/root_ca_pqc.crt"
	issuerCaPqcFilePath = "certs/issuer_ca_pqc.crt"
)

// What /root-ca.pem and /issuer-ca.pem actually serve -- profile-keyed like
// serverCertFilePath below, defaulting to the pqc stand-ins and gaining a
// hybrid case in init(). Kept separate from rootCaPqcFilePath/
// issuerCaPqcFilePath above (which name one fixed file each, PQC-only) so
// this can vary by profile without touching the AND gate's own CA key
// source. See thesis/results/v4/DECISIONS.md.
var (
	rootCaServeFilePath   = rootCaPqcFilePath
	issuerCaServeFilePath = issuerCaPqcFilePath
)

var (
	apiURI    = os.Getenv("API_GATEWAY_URI")
	ssaJwkURL = os.Getenv("SSA_JWK_URL")
	ssaJWK    jwk.Key

	// classic (RSA-4096, Experiment 1) or pqc (ML-DSA-65, Experiment 2) --
	// picks which server certificate the gateway itself presents during the
	// TLS handshake. See thesis/results/v2/experiment2 - PQC/DECISIONS.md,
	// Decision 10.
	serverCertFilePath = "certs/mtls.crt"
	serverKeyFilePath  = "certs/mtls.key"

	// serverCurvePreferences/serverMinVersion: the TLS key-exchange group(s)
	// the gateway negotiates. Classical by default (Clássico's own, correct
	// baseline); pqc and hybrid override these in init() below to cover
	// Nível 1 (the HNDL-relevant key exchange, distinct from the
	// certificate's signature) -- see thesis/results/v6/Level 1/
	// ARCHITECTURE.md, Fase 1/2. Each profile's key exchange now matches
	// that profile's own signature philosophy: pqc gets pure MLKEM1024 (no
	// classical component, mirroring its pure ML-DSA-65 signature), hybrid
	// gets the combined group (mirroring its RSA+ML-DSA-65 dual signature).
	// No classical fallback in either list, deliberately: a client that
	// can't negotiate the intended group must fail visibly, not silently
	// downgrade -- the same "no silent fallback" principle the hybrid
	// certificate's AND gate already applies.
	//
	// This default, Clássico's own list, is pinned to exactly one curve,
	// P-384 -- so Clássico, PQC, and Híbrido form a clean,
	// one-variable-at-a-time comparison chain (see hybrid's own
	// serverCurvePreferences override in init() below for the other half of
	// that chain). The client side of this negotiation
	// (thesis/scripts/tls_kem_proxy) only ever offers P-384 for Clássico, so
	// this narrowing changes nothing about what the harness actually
	// measures -- it makes the gateway's own accepted set match that
	// reality instead of silently tolerating a wider one nothing here
	// exercises.
	//
	// EXCEPTION, deliberate and SNI-scoped: GetConfigForClient below (see its
	// own comment and internalCallerConfig) pins exactly one caller -- any
	// connection whose ClientHello sets ServerName "matls-api.local" (auth's
	// own InsurerAdapter.getConsent(), which Node's TLS stack cannot make
	// negotiate MLKEM1024/hybrid groups) -- to internalCallerConfig's own
	// wider classical list ([P521, P384, P256], unaffected by the narrowing
	// above -- this internal call was never part of what the comparison
	// chain measures), regardless of CRYPTO_PROFILE. This is the ONLY
	// source of classical key exchange under pqc/hybrid; confirmed live
	// that every single classical handshake logged under those profiles
	// carries this exact SNI, one-to-one, no exceptions. It does not apply
	// to the client-facing traffic opin_flow.py's tls_kem_proxy drives
	// (different SNI), which is what artifacts/*/README.md's handshake
	// evidence (Seção 4) is about.
	serverCurvePreferences = []tls.CurveID{tls.CurveP384}
	serverMinVersion       = uint16(tls.VersionTLS12)
)

func init() {
	switch os.Getenv("CRYPTO_PROFILE") {
	case "classic":
		// root_ca.crt/issuer_ca.crt: ordinary classical RSA leaf certs,
		// signed by the project's own local CA (ca.crt/ca.key), reusing
		// root_ca.key/issuer_ca.key -- the same RSA keypairs already used
		// as the classical half of root_ca_hybrid.crt/issuer_ca_hybrid.crt
		// above. Generated via certs/main.go -classic-name root_ca /
		// -classic-name issuer_ca. Eliminates the Classic profile's last
		// dependency on Raidiam's real, external sandbox host
		// (crl.sandbox.pki.opinbrasil.com.br) for root-ca.pem/issuer-ca.pem.
		// See thesis/results/v5/DECISIONS.md.
		rootCaServeFilePath = "certs/root_ca.crt"
		issuerCaServeFilePath = "certs/issuer_ca.crt"
	case "pqc":
		serverCertFilePath = "certs/mtls_pqc.crt"
		serverKeyFilePath = "certs/mtls_pqc.key"
		// Nível 1: pure ML-KEM, no classical curve alongside it, matching
		// this profile's pure ML-DSA-65 signature. Forces TLS 1.3 -- the
		// group doesn't exist in TLS 1.2 -- though the gateway already
		// negotiates 1.3 in practice even under classic's TLS 1.2 floor, so
		// this doesn't introduce a second new variable alongside the KEM.
		serverCurvePreferences = []tls.CurveID{tls.MLKEM1024}
		serverMinVersion = tls.VersionTLS13
	case "hybrid":
		// mtls_hybrid.crt/.key: an ordinary RSA cert/key pair as far as
		// crypto/tls itself is concerned -- the ML-DSA-65 material rides
		// along inertly as three non-critical X.509 extensions the TLS
		// handshake itself never looks at. See hybridExtensions.go and
		// thesis/results/v4/DECISIONS.md, Etapa 6.
		serverCertFilePath = "certs/mtls_hybrid.crt"
		serverKeyFilePath = "certs/mtls_hybrid.key"
		// root_ca_hybrid.crt/issuer_ca_hybrid.crt: the same dual nested
		// combiner (RSA + ML-DSA-65, three non-critical extensions) as
		// mtls_hybrid.crt above, generated via certs/main.go -hybrid-name
		// root_ca / -hybrid-name issuer_ca, reusing root_ca_pqc.key/
		// issuer_ca_pqc.key as each subject's own ML-DSA-65 identity. Closes
		// the symmetry gap left by Decision 12 (PQC-only stand-ins) --
		// hybrid mode was silently falling through to the real, external,
		// classical Raidiam sandbox host before this. See
		// thesis/results/v4/DECISIONS.md.
		rootCaServeFilePath = "certs/root_ca_hybrid.crt"
		issuerCaServeFilePath = "certs/issuer_ca_hybrid.crt"
		// Nível 1: the combined classical+PQC group, matching this
		// profile's own RSA+ML-DSA-65 dual signature.
		//
		// SecP384r1MLKEM1024 combines the exact classical curve (P-384)
		// Clássico is pinned to above with the exact ML-KEM parameter set
		// (ML-KEM-1024) PQC already uses, so Híbrido shares one full
		// component with each of the other two profiles. This is a
		// deliberate trade-off, not an oversight: X25519MLKEM768 is the
		// group real deployments actually negotiate (Chrome, Cloudflare) and
		// has that real-world representativeness; this codebase gives that
		// up in exchange for a clean internal comparison chain across all
		// three profiles -- SecP384r1MLKEM1024 is not being presented as a
		// market-standard group anywhere else in this codebase.
		serverCurvePreferences = []tls.CurveID{tls.SecP384r1MLKEM1024}
		serverMinVersion = tls.VersionTLS13
	}
}

// handshakeInfo holds the per-connection mTLS handshake metrics, captured
// once when a connection's handshake completes and reused for every
// subsequent HTTP request that reuses that same keep-alive connection.
type handshakeInfo struct {
	start           time.Time
	end             time.Time
	tlsVersion      string
	cipherSuite     string
	curveID         string
	clientCertBytes int
	handshakeBytes  int
}

var (
	// handshakeStartTimes: remoteAddr -> time the TLS handshake began
	// (recorded from tls.Config.GetConfigForClient, which fires right after
	// the ClientHello is parsed, before certificate exchange/verification).
	handshakeStartTimes sync.Map
	// handshakeCache: remoteAddr -> handshakeInfo, recorded once the
	// handshake has completed (detected via http.Server's ConnState hook).
	handshakeCache sync.Map
	// connByteCounters: remoteAddr -> *countingConn, populated in
	// countingListener.Accept() for every raw connection so the wire-level
	// byte count for that connection's handshake can be read back once it
	// completes (see connStateHandshakeLogger).
	connByteCounters sync.Map
)

// countingConn wraps a raw net.Conn (the one returned by the TCP listener,
// *before* tls.NewListener wraps it) and tallies bytes crossing the wire in
// each direction. Since it sits below crypto/tls, every Read/Write the TLS
// handshake itself performs -- ClientHello, ServerHello, certificate
// exchange, key exchange, Finished -- is counted, with no awareness of TLS
// record boundaries needed.
type countingConn struct {
	net.Conn
	bytesRead    atomic.Int64
	bytesWritten atomic.Int64
}

func (c *countingConn) Read(b []byte) (int, error) {
	n, err := c.Conn.Read(b)
	c.bytesRead.Add(int64(n))
	return n, err
}

func (c *countingConn) Write(b []byte) (int, error) {
	n, err := c.Conn.Write(b)
	c.bytesWritten.Add(int64(n))
	return n, err
}

// countingListener wraps the raw TCP listener so every accepted connection
// is instrumented with a countingConn before tls.NewListener takes over.
type countingListener struct {
	net.Listener
}

func (l *countingListener) Accept() (net.Conn, error) {
	c, err := l.Listener.Accept()
	if err != nil {
		return nil, err
	}
	cc := &countingConn{Conn: c}
	connByteCounters.Store(c.RemoteAddr().String(), cc)
	return cc, nil
}

func main() {
	l := logger()
	slog.SetDefault(l)

	key, err := loadSsaKey()
	if err != nil {
		slog.Error("Could not fetch ssa_jwk from S3", slog.String("error", err.Error()))
		os.Exit(1)
	}
	ssaJWK = key
	slog.Info("Successfully fetched ssa_jwk from S3")

	mux := http.NewServeMux()

	dirHandler := directoryHandler()
	mux.Handle("directory/", dirHandler)

	go func() {
		_ = http.ListenAndServe(":80", mux)
	}()

	apiHandler := apiHandler()
	mux.Handle("api.local/", apiHandler)
	mux.Handle("matls-api.local/", apiHandler)
	mux.Handle("mtls/", apiHandler)

	mux.Handle("auth.local/", authHandler())
	mux.Handle("matls-auth.local/", authHandler())

	tlsConfig := tlsConfiguration()
	server := http.Server{
		Handler:   mux,
		ErrorLog:  slog.NewLogLogger(l.Handler(), slog.LevelError),
		TLSConfig: tlsConfig,
		ConnState: connStateHandshakeLogger,
	}
	ln, err := net.Listen("tcp", fmt.Sprintf(":%d", 443))
	if err != nil {
		os.Exit(1)
	}
	// Wrap the raw listener so every connection's wire bytes are counted
	// (see countingListener) before tls.NewListener performs the handshake
	// on top of it.
	countingLn := &countingListener{Listener: ln}
	slog.Info("Listening on port 443")
	slog.Error("server error", slog.String("err", server.Serve(tls.NewListener(countingLn, tlsConfig)).Error()))
}

func loadSsaKey() (jwk.Key, error) {
	if ssaJwkURL == "" {
		return nil, fmt.Errorf("SSA_JWK_URL environment variable not set")
	}

	resp, err := http.Get(ssaJwkURL)
	if err != nil {
		return nil, fmt.Errorf("failed to fetch ssa_jwk: %w", err)
	}
	defer resp.Body.Close()

	if resp.StatusCode != http.StatusOK {
		return nil, fmt.Errorf("ssa_jwk fetch returned status: %d", resp.StatusCode)
	}

	body, err := io.ReadAll(resp.Body)
	if err != nil {
		return nil, fmt.Errorf("failed to read ssa_jwk response body: %w", err)
	}

	key, err := jwk.ParseKey(body)
	if err != nil {
		return nil, fmt.Errorf("failed to parse ssa_jwk: %w", err)
	}

	return key, nil
}

func authHandler() http.Handler {
	// Auth Host
	parsedAuthHost, err := url.Parse("http://auth:3000")
	if err != nil {
		slog.Error("unable to upstream url", slog.String("err", err.Error()))
		os.Exit(1)
	}
	// Create reverse proxies with custom director to add headers
	authProxy := httputil.NewSingleHostReverseProxy(parsedAuthHost)

	// Add custom Director to set required headers
	authProxy.Director = func(req *http.Request) {
		setCustomHeaders(req, parsedAuthHost)
	}

	return loggingMiddleware(authProxy)
}

func apiHandler() http.Handler {
	apiHost, err := url.Parse(apiURI)
	if err != nil {
		slog.Error("unable to upstream url", slog.String("err", err.Error()))
		os.Exit(1)
	}
	// Create reverse proxies with custom director to add headers
	apiProxy := httputil.NewSingleHostReverseProxy(apiHost)

	// Add custom Director to set required headers
	apiProxy.Director = func(req *http.Request) {
		setCustomHeaders(req, apiHost)
	}
	apiProxyHandler := loggingMiddleware(apiProxy)
	apiProxyHandler = enforceAccessTokenMiddleware(apiProxyHandler)

	return apiProxyHandler
}

func directoryHandler() http.Handler {
	participantsBytes, err := os.ReadFile(participantsFilePath)
	if err != nil {
		slog.Info("unable to read participants.json", slog.String("err", err.Error()))
		participantsBytes = []byte(`{}`)
	}

	ssBytes, err := os.ReadFile(softwareStatementFilePath)
	if err != nil {
		slog.Info("unable to read software_statement.json", slog.String("err", err.Error()))
		ssBytes = []byte(`{}`)
	}
	var ss map[string]interface{}
	if err := json.Unmarshal(ssBytes, &ss); err != nil {
		slog.Info("unable to parse software_statement.json", slog.String("err", err.Error()))
		ss = map[string]any{}
	}

	clientJWKSBytes, err := os.ReadFile(clientOnePublicJWKSPath)
	if err != nil {
		slog.Info("unable to read client_one_pub.json", slog.String("err", err.Error()))
		clientJWKSBytes = []byte(`{}`)
	}

	rootCaServeBytes, err := os.ReadFile(rootCaServeFilePath)
	if err != nil {
		slog.Info("unable to read "+rootCaServeFilePath, slog.String("err", err.Error()))
		rootCaServeBytes = []byte{}
	}

	issuerCaServeBytes, err := os.ReadFile(issuerCaServeFilePath)
	if err != nil {
		slog.Info("unable to read "+issuerCaServeFilePath, slog.String("err", err.Error()))
		issuerCaServeBytes = []byte{}
	}

	mux := http.NewServeMux()

	mux.HandleFunc("/.well-known/openid-configuration", func(w http.ResponseWriter, r *http.Request) {
		w.Header().Set("Content-Type", "application/json")
		w.WriteHeader(http.StatusOK)
		_ = json.NewEncoder(w).Encode(map[string]any{
			"token_endpoint": "https://directory/token",
		})
	})

	mux.HandleFunc("/token", func(w http.ResponseWriter, r *http.Request) {
		w.Header().Set("Content-Type", "application/json")
		w.WriteHeader(http.StatusOK)
		_ = json.NewEncoder(w).Encode(map[string]any{
			"access_token": "token",
			"token_type":   "bearer",
		})
	})

	mux.HandleFunc("/participants", func(w http.ResponseWriter, r *http.Request) {
		w.Header().Set("Content-Type", "application/json")
		w.WriteHeader(http.StatusOK)
		if _, err := w.Write(participantsBytes); err != nil {
			http.Error(w, "failed to write response", http.StatusInternalServerError)
		}
	})

	mux.HandleFunc("/organisations/{org_id}/softwarestatements/{ss_id}/assertion", func(w http.ResponseWriter, r *http.Request) {
		w.Header().Set("Content-Type", "application/jwt")
		w.WriteHeader(http.StatusOK)
		ssa := signSsa(ss)
		if _, err := w.Write(ssa); err != nil {
			http.Error(w, "failed to write response", http.StatusInternalServerError)
		}
	})

	mux.HandleFunc("/{org_id}/application.jwks", func(w http.ResponseWriter, r *http.Request) {
		w.Header().Set("Content-Type", "application/json")
		w.WriteHeader(http.StatusOK)
		if _, err := w.Write(clientJWKSBytes); err != nil {
			http.Error(w, "failed to write response", http.StatusInternalServerError)
		}
	})

	// Local stand-ins for Raidiam's real sandbox PKI -- ML-DSA-65-only for
	// pqc, RSA+ML-DSA-65 dual nested combiner for hybrid -- see
	// rootCaServeFilePath/issuerCaServeFilePath's comment above.
	mux.HandleFunc("/root-ca.pem", func(w http.ResponseWriter, r *http.Request) {
		w.Header().Set("Content-Type", "application/x-pem-file")
		w.WriteHeader(http.StatusOK)
		if _, err := w.Write(rootCaServeBytes); err != nil {
			http.Error(w, "failed to write response", http.StatusInternalServerError)
		}
	})

	mux.HandleFunc("/issuer-ca.pem", func(w http.ResponseWriter, r *http.Request) {
		w.Header().Set("Content-Type", "application/x-pem-file")
		w.WriteHeader(http.StatusOK)
		if _, err := w.Write(issuerCaServeBytes); err != nil {
			http.Error(w, "failed to write response", http.StatusInternalServerError)
		}
	})

	return loggingMiddleware(mux)
}

func tlsConfiguration() *tls.Config {

	serverCertBytes, err := os.ReadFile(serverCertFilePath)
	if err != nil {
		slog.Error("unable to read mtls.crt", slog.String("err", err.Error()))
		os.Exit(1)
	}
	matlsBlock, _ := pem.Decode(serverCertBytes)
	if matlsBlock == nil {
		slog.Error("unable to decode mtls.crt")
		os.Exit(1)
	}
	serverBytes := matlsBlock.Bytes

	serverKeyBytes, err := os.ReadFile(serverKeyFilePath)
	if err != nil {
		slog.Error("unable to read mtls.key", slog.String("err", err.Error()))
		os.Exit(1)
	}
	serverKeyBlock, _ := pem.Decode(serverKeyBytes)
	if serverKeyBlock == nil {
		slog.Error("unable to decode mtls.key")
		os.Exit(1)
	}
	serverKey, err := x509.ParsePKCS8PrivateKey(serverKeyBlock.Bytes)
	if err != nil {
		slog.Error("unable to parse mtls.key", slog.String("err", err.Error()))
		os.Exit(1)
	}

	caCerts := caCertPool()
	cfg := &tls.Config{
		Certificates: []tls.Certificate{{
			Certificate: [][]byte{
				serverBytes,
			},
			PrivateKey: serverKey,
		}},
		InsecureSkipVerify:    true,
		ClientCAs:             caCerts,
		ClientAuth:            tls.VerifyClientCertIfGiven,
		MinVersion:            serverMinVersion,
		MaxVersion:            tls.VersionTLS13,
		CurvePreferences:      serverCurvePreferences,
		VerifyPeerCertificate: hybridVerifyPeerCertificateFunc(),

		CipherSuites: []uint16{
			//TLS 1.2
			tls.TLS_ECDHE_RSA_WITH_AES_256_GCM_SHA384,
			tls.TLS_RSA_WITH_AES_256_GCM_SHA384,
			tls.TLS_ECDHE_RSA_WITH_AES_128_GCM_SHA256,
			tls.TLS_RSA_WITH_AES_128_GCM_SHA256,
			//TLS 1.3 these are actually ignored, but kept here to provide clarity on what's enabled by default.
			tls.TLS_CHACHA20_POLY1305_SHA256,
			tls.TLS_AES_128_GCM_SHA256,
			tls.TLS_AES_256_GCM_SHA384,
		},
	}

	// internalCallerClassicConfig: a shallow copy of cfg with the key-exchange
	// dimension pinned back to classical, for exactly one caller --
	// auth's own InsurerAdapter.getConsent() (mock_as/utils/opin/adapter.js),
	// which reaches this gateway as a TLS *client* over matls-api.local to
	// fetch the consent from the RS. That call already uses a fixed
	// classical certificate "unrelated to CRYPTO_PROFILE" (Decision 5,
	// thesis/results/v5/size/DECISIONS.md) -- extending that same carve-out
	// to the key-exchange dimension here, not introducing a new one. See
	// thesis/results/v6/Level 1/DECISIONS.md for the incident this fixes:
	// pinning the whole gateway's CurvePreferences to the profile's new
	// group broke this call outright (Node's TLS client can't negotiate
	// MLKEM1024/X25519MLKEM768 any more than Python could), 100% of the
	// time, not the rare Decision-5/9 timing race it superficially
	// resembled (same InvalidGrant/getConsent error shape, different and
	// fully deterministic cause: TLS alert 40, handshake_failure).
	//
	// The fixed-classical certificate the comment above refers to is auth's
	// own CLIENT cert (from SSM) --
	// a completely different certificate from this gateway's own SERVER
	// cert, which `:= *cfg` below still inherits unmodified (i.e. the
	// profile's own serverCertFilePath: mtls.crt/mtls_pqc.crt/
	// mtls_hybrid.crt). Under classic and hybrid this happened to be
	// harmless -- hybrid's mtls_hybrid.crt is "an ordinary RSA cert/key
	// pair as far as crypto/tls itself is concerned" (see its own case in
	// init() above), so signing a classical-curve handshake with it is
	// unremarkable. Under pqc, mtls_pqc.crt's subject public key is a real
	// ML-DSA-65 key (confirmed: `openssl x509 -in mtls_pqc.crt -noout
	// -text` reports Public Key Algorithm OID 2.16.840.1.101.3.4.3.18,
	// which even this host's own OpenSSL 3.2.4 cannot parse) -- meaning
	// this "always classical" connection was, under pqc specifically,
	// still forcing a classical-curve TLS 1.2 handshake to be signed with
	// an ML-DSA-65 certificate that auth's mainstream Node/OpenSSL TLS
	// client was never meant to negotiate a signature scheme for. Found by
	// reproducing the "rare, pre-existing reentrant introspection race"
	// (v5 Decision 5) deliberately: 5/5 failures under pqc+140ms, 0/5
	// under pqc+0ms, 0/5 under classic+140ms, 0/5 under hybrid+140ms --
	// pqc is the only profile whose server cert here isn't RSA, and 140ms
	// is needed to widen the reentrant chain's wall-clock window enough
	// for whatever this mismatch costs to matter. Fixed by pinning
	// Certificates here too, not just CurvePreferences/MinVersion --
	// completing the "fully classical" intent this carve-out already
	// claimed for the key-exchange dimension, now true for the
	// certificate dimension as well, for all three profiles alike (not
	// just the two it happened to already hold for).
	internalServerCertBytes, err := os.ReadFile("certs/mtls.crt")
	if err != nil {
		slog.Error("internalCallerConfig: unable to read certs/mtls.crt", slog.String("err", err.Error()))
		os.Exit(1)
	}
	internalServerBlock, _ := pem.Decode(internalServerCertBytes)
	if internalServerBlock == nil {
		slog.Error("internalCallerConfig: unable to decode certs/mtls.crt")
		os.Exit(1)
	}
	internalServerKeyBytes, err := os.ReadFile("certs/mtls.key")
	if err != nil {
		slog.Error("internalCallerConfig: unable to read certs/mtls.key", slog.String("err", err.Error()))
		os.Exit(1)
	}
	internalServerKeyBlock, _ := pem.Decode(internalServerKeyBytes)
	if internalServerKeyBlock == nil {
		slog.Error("internalCallerConfig: unable to decode certs/mtls.key")
		os.Exit(1)
	}
	internalServerKey, err := x509.ParsePKCS8PrivateKey(internalServerKeyBlock.Bytes)
	if err != nil {
		slog.Error("internalCallerConfig: unable to parse certs/mtls.key", slog.String("err", err.Error()))
		os.Exit(1)
	}

	internalCallerConfig := *cfg
	internalCallerConfig.CurvePreferences = []tls.CurveID{tls.CurveP521, tls.CurveP384, tls.CurveP256}
	internalCallerConfig.MinVersion = tls.VersionTLS12
	internalCallerConfig.Certificates = []tls.Certificate{{
		Certificate: [][]byte{internalServerBlock.Bytes},
		PrivateKey:  internalServerKey,
	}}

	// Purely observational hook, plus (new) the one per-connection override
	// above: fires right after the ClientHello is parsed, before
	// certificate exchange/verification. Returning (nil, nil) tells the TLS
	// stack "no per-client override, use cfg as-is" for every caller except
	// the one matched by SNI below -- this does not alter negotiation
	// behavior for anyone else in any way (cipher suites/versions/certs
	// unchanged).
	cfg.GetConfigForClient = func(hello *tls.ClientHelloInfo) (*tls.Config, error) {
		if hello.Conn != nil {
			handshakeStartTimes.Store(hello.Conn.RemoteAddr().String(), time.Now())
		}
		if hello.ServerName == "matls-api.local" {
			slog.Info("GetConfigForClient: internal-caller classical carve-out applied",
				slog.String("sni", hello.ServerName), slog.String("remoteAddr", hello.Conn.RemoteAddr().String()))
			return &internalCallerConfig, nil
		}
		return nil, nil
	}

	return cfg
}

// connStateHandshakeLogger is registered as http.Server.ConnState. It fires
// on every connection state transition; we only care about the first
// transition to StateActive per connection (which happens after the TLS
// handshake completes, since the server needs decrypted bytes to detect an
// incoming request), and about cleaning up on close so the maps above don't
// grow unbounded over a long-running gateway process.
func connStateHandshakeLogger(c net.Conn, state http.ConnState) {
	remote := c.RemoteAddr().String()

	switch state {
	case http.StateActive:
		if _, alreadyRecorded := handshakeCache.Load(remote); alreadyRecorded {
			return
		}
		startVal, ok := handshakeStartTimes.Load(remote)
		if !ok {
			return
		}
		info := handshakeInfo{
			start: startVal.(time.Time),
			end:   time.Now(),
		}
		if tlsConn, ok := c.(*tls.Conn); ok {
			cs := tlsConn.ConnectionState()
			info.tlsVersion = tls.VersionName(cs.Version)
			info.cipherSuite = tls.CipherSuiteName(cs.CipherSuite)
			// CurveID: the key-exchange group actually negotiated -- this is
			// the ground truth for Nível 1's own proof (thesis/results/v6/
			// Level 1/ARCHITECTURE.md, Fase 3): confirms per-connection which
			// group was really used, not just which one the config asked for.
			info.curveID = cs.CurveID.String()
			if len(cs.PeerCertificates) > 0 {
				info.clientCertBytes = len(cs.PeerCertificates[0].Raw)
			}
		}
		// StateActive fires as soon as the server starts reading the first
		// request off this connection, i.e. right after the handshake's
		// Finished messages are processed -- the earliest point at which the
		// byte count read here is guaranteed to include the complete
		// handshake. It may also include a few early application-data bytes
		// if the client pipelined its first request into the same TCP
		// read/TLS record as the handshake's tail end; for the sizes
		// involved here (hundreds of bytes classical, kilobytes with PQC
		// certs/KEM material) that's noise, not a meaningful skew.
		if v, ok := connByteCounters.Load(remote); ok {
			cc := v.(*countingConn)
			info.handshakeBytes = int(cc.bytesRead.Load() + cc.bytesWritten.Load())
		}
		handshakeCache.Store(remote, info)

		slog.Info("mTLS handshake complete",
			slog.String("remoteAddr", remote),
			slog.Time("handshakeStart", info.start),
			slog.Time("handshakeEnd", info.end),
			slog.Int64("handshakeDurationMs", info.end.Sub(info.start).Milliseconds()),
			slog.String("tlsVersion", info.tlsVersion),
			slog.String("cipherSuite", info.cipherSuite),
			slog.String("curveID", info.curveID),
			slog.Int("clientCertBytes", info.clientCertBytes),
			slog.Int("mtlsHandshakeBytes", info.handshakeBytes),
		)

	case http.StateClosed, http.StateHijacked:
		handshakeStartTimes.Delete(remote)
		handshakeCache.Delete(remote)
		connByteCounters.Delete(remote)
	}
}

// lookupHandshakeInfo returns the cached handshake metrics for the
// connection a given request arrived on, if any were recorded.
func lookupHandshakeInfo(remoteAddr string) *handshakeInfo {
	v, ok := handshakeCache.Load(remoteAddr)
	if !ok {
		return nil
	}
	info := v.(handshakeInfo)
	return &info
}

func caCertPool() *x509.CertPool {
	caBytes, err := os.ReadFile(caCertFilePath)
	if err != nil {
		slog.Error("unable to read ca.crt", slog.String("err", err.Error()))
		os.Exit(1)
	}

	caCertPool := x509.NewCertPool()
	for block, rest := pem.Decode(caBytes); block != nil; block, rest = pem.Decode(rest) {
		switch block.Type {
		case "CERTIFICATE":
			cert, err := x509.ParseCertificate(block.Bytes)
			if err != nil {
				panic(err)
			}
			caCertPool.AddCert(cert)
			slog.Info("loaded certificate", slog.String("subject", cert.Subject.String()))

		default:
			panic("unknown block type " + block.Type)
		}
	}

	return caCertPool
}

func loggingMiddleware(h http.Handler) http.Handler {
	return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		// opinRequestStart/End bound the time this specific request spent
		// being handled -- i.e. from the moment the (already-completed)
		// mTLS handshake handed off a decrypted request to this handler,
		// until the response was written back. This is the "OPIN processing
		// time" half of the split; mtlsHandshake* below is the other half.
		opinRequestStart := time.Now()
		rec := &statusRecorder{ResponseWriter: w}
		h.ServeHTTP(rec, r)
		opinRequestEnd := time.Now()

		attrs := []slog.Attr{
			slog.String("remoteIP", r.RemoteAddr),
			slog.String("host", r.Host),
			slog.String("request", r.RequestURI),
			slog.String("query", r.URL.RawQuery),
			slog.String("method", r.Method),
			slog.String("status", fmt.Sprintf("%d", rec.status)),
			slog.String("userAgent", r.UserAgent()),
			slog.String("referer", r.Referer()),
			slog.Time("opinRequestStart", opinRequestStart),
			slog.Time("opinRequestEnd", opinRequestEnd),
			slog.Int64("opinDurationMs", opinRequestEnd.Sub(opinRequestStart).Milliseconds()),
		}
		// Handshake info is cached per-connection (see connStateHandshakeLogger);
		// for keep-alive connections, every request after the first reports the
		// same handshake timestamps -- that's expected, since only the first
		// request on a connection actually paid the handshake cost.
		if hs := lookupHandshakeInfo(r.RemoteAddr); hs != nil {
			attrs = append(attrs,
				slog.Time("mtlsHandshakeStart", hs.start),
				slog.Time("mtlsHandshakeEnd", hs.end),
				slog.Int64("mtlsHandshakeDurationMs", hs.end.Sub(hs.start).Milliseconds()),
				slog.String("tlsVersion", hs.tlsVersion),
				slog.String("cipherSuite", hs.cipherSuite),
				slog.String("curveID", hs.curveID),
				slog.Int("clientCertBytes", hs.clientCertBytes),
				slog.Int("mtlsHandshakeBytes", hs.handshakeBytes),
			)
		}
		if _, ok := h.(*httputil.ReverseProxy); ok {
			h.(*httputil.ReverseProxy).Director(r)
			attrs = append(attrs, slog.String("target", fmt.Sprintf("proxy:%s", r.URL.String())))
		}
		slog.LogAttrs(r.Context(), slog.LevelInfo, "access log", attrs...)
	})
}

func setCustomHeaders(req *http.Request, target *url.URL) {
	req.Header.Set("X-Forwarded-Proto", "https") // Adjust to "https" if using HTTPS
	req.Header.Set("Host", req.Host)
	req.Header.Set("X-Real-IP", getRemoteIP(req))
	req.Header.Set("X-Forwarded-For", getForwardedFor(req))

	// Extract and set the client's certificate and DN
	if len(req.TLS.PeerCertificates) > 0 {
		// The TLS Block Ensures that the correct ordering has taken place and that the leaf certificate will be at block 0
		clientCert := req.TLS.PeerCertificates[0]
		certPEM := pem.EncodeToMemory(&pem.Block{
			Type:  "CERTIFICATE",
			Bytes: clientCert.Raw,
		})
		// Base64 encode the certificate to ensure it's valid for HTTP headers
		certPEMString := strings.ReplaceAll(string(certPEM), "\n", " ")
		req.Header.Set("BANK-TLS-Certificate", string(certPEMString))
		req.Header.Set("X-BANK-Certificate-DN", clientCert.Subject.String())
		req.Header.Set("X-BANK-Certificate-Verify", "SUCCESS")
	}

	req.URL.Scheme = target.Scheme
	req.URL.Host = target.Host
	req.URL.Path = singleJoiningSlash(target.Path, req.URL.Path)
	if target.RawQuery == "" || req.URL.RawQuery == "" {
		req.URL.RawQuery = target.RawQuery + req.URL.RawQuery
	} else {
		req.URL.RawQuery = target.RawQuery + "&" + req.URL.RawQuery
	}
	if _, ok := req.Header["User-Agent"]; !ok {
		// explicitly disable User-Agent so it's not set to default value
		req.Header.Set("User-Agent", "")
	}
}

func getRemoteIP(req *http.Request) string {
	ip, _, err := net.SplitHostPort(req.RemoteAddr)
	if err != nil {
		return ""
	}
	return ip
}

func getForwardedFor(req *http.Request) string {
	forwardedFor := req.Header.Get("X-Forwarded-For")
	if forwardedFor != "" {
		return forwardedFor + ", " + getRemoteIP(req)
	}
	return getRemoteIP(req)
}

func enforceAccessTokenMiddleware(next http.Handler) http.Handler {
	return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		accessToken := getAccessToken(r)
		if accessToken == "" {
			slog.Error("No Authorization header, returning 401")
			http.Error(w, "Unauthorized", http.StatusUnauthorized)
			return
		}
		if !introspectAndAddHeaders(r, accessToken) {
			slog.Error("Introspection failed, returning 401")
			http.Error(w, "Unauthorized", http.StatusUnauthorized)
			return
		}
		next.ServeHTTP(w, r)
	})
}

func getAccessToken(req *http.Request) string {
	authHeader := req.Header.Get("Authorization")
	if authHeader == "" {
		authHeader = req.Header.Get("authorization")
	}
	if authHeader != "" && strings.HasPrefix(authHeader, "Bearer ") {
		return strings.TrimPrefix(authHeader, "Bearer ")
	}
	return ""
}

// introspectionHTTPClient: DisableKeepAlives, deliberately. `&http.Client{}`
// with no Transport set (the previous code here) uses Go's shared
// http.DefaultTransport, whose
// IdleConnTimeout defaults to 90s; auth's own Node http.Server has
// keepAliveTimeout=5000ms (Node's own default, never configured either
// way in this codebase). Any gap between two introspection calls of 5s
// or more -- routine under higher-latency scenarios, where the reentrant
// chain this feeds (auth's InsurerAdapter.getConsent(), mock_as/utils/
// opin/adapter.js) is naturally paced further apart -- means Node has
// already closed the pooled connection server-side by the time Go's
// client reuses it, producing exactly the `EOF` this function used to
// surface as "Failed to introspect token" -> a 401 -> InvalidGrant at the
// AS. Reproduced deliberately (8/8 failures under pqc+140ms with the old
// client, 0/8 after this fix, same test) and root-caused directly from
// this connection's own access log entries (successful introspections
// ~1-2s apart; the one that failed followed a ~4.6s gap -- consistent
// with, not merely coincident with, Node's 5s keepAliveTimeout).
// DisableKeepAlives (a fresh TCP connection per call, to a same-Docker-
// network container -- negligible cost) sidesteps the mismatch entirely,
// rather than trying to keep two independently-configured timeouts in
// two different languages/frameworks in sync.
var introspectionHTTPClient = &http.Client{Transport: &http.Transport{DisableKeepAlives: true}}

func introspectAndAddHeaders(req *http.Request, token string) bool {
	introspectionURL := "http://auth:3000/token/introspection"
	clientID := "client"
	clientSecret := "1234"

	data := url.Values{}
	data.Set("token", token)

	client := introspectionHTTPClient
	introspectionReq, err := http.NewRequest("POST", introspectionURL, strings.NewReader(data.Encode()))
	if err != nil {
		slog.Error("Failed to create introspection request", slog.String("error", err.Error()))
		return false
	}

	introspectionReq.SetBasicAuth(clientID, clientSecret)
	introspectionReq.Header.Set("Content-Type", "application/x-www-form-urlencoded")

	resp, err := client.Do(introspectionReq)
	if err != nil {
		slog.Error("Failed to introspect token", slog.String("error", err.Error()))
		return false
	}
	defer resp.Body.Close()

	if resp.StatusCode != http.StatusOK {
		slog.Error("Token introspection returned non-200 status", slog.String("status", resp.Status))
		return false
	}

	body, err := io.ReadAll(resp.Body)
	if err != nil {
		slog.Error("Failed to read introspection response body", slog.String("error", err.Error()))
		return false
	}

	var introspectionResponse map[string]interface{}
	if err := json.Unmarshal(body, &introspectionResponse); err != nil {
		slog.Error("Failed to unmarshal introspection response", slog.String("error", err.Error()))
		return false
	}

	slog.Info("Introspection response", slog.Any("response", introspectionResponse))

	if active, ok := introspectionResponse["active"].(bool); !ok || !active {
		slog.Error("Token is not active")
		return false
	}

	// Check x5t#S256 against client certificate's SHA-256 thumbprint
	if cnf, ok := introspectionResponse["cnf"].(map[string]interface{}); ok {
		if x5tS256, ok := cnf["x5t#S256"].(string); ok {
			if !verifyCertificateThumbprint(req, x5tS256) {
				slog.Error("Client certificate thumbprint verification failed")
				return false
			}
		}
	}

	// Base64 encode the introspection response and set as header
	introspectionResponseBase64 := base64.StdEncoding.EncodeToString(body)
	req.Header.Set("X-Introspection-Response", introspectionResponseBase64)
	//To be compliant with the lambda - to be removed
	req.Header.Set("access_token", string(body))

	// Check for 'sub' property and fetch user info if present
	if _, ok := introspectionResponse["sub"].(string); ok {
		fetchAndAddUserInfo(req, token)
	}

	return true
}

func fetchAndAddUserInfo(req *http.Request, token string) {
	userInfoURL := "http://auth/me"

	client := &http.Client{}
	userInfoReq, err := http.NewRequest("GET", userInfoURL, nil)
	if err != nil {
		slog.Error("Failed to create user info request", slog.String("error", err.Error()))
		return
	}

	userInfoReq.Header.Set("Authorization", "Bearer "+token)

	resp, err := client.Do(userInfoReq)
	if err != nil {
		slog.Error("Failed to fetch user info", slog.String("error", err.Error()))
		return
	}
	defer resp.Body.Close()

	if resp.StatusCode != http.StatusOK {
		slog.Error("User info request returned non-200 status", slog.String("status", resp.Status))
		return
	}

	body, err := io.ReadAll(resp.Body)
	if err != nil {
		slog.Error("Failed to read user info response body", slog.String("error", err.Error()))
		return
	}

	// Base64 encode the user info response and set as header
	userInfoResponseBase64 := base64.StdEncoding.EncodeToString(body)
	req.Header.Set("X-User-Info-Response", userInfoResponseBase64)
}

func verifyCertificateThumbprint(req *http.Request, x5tS256 string) bool {
	if len(req.TLS.PeerCertificates) == 0 {
		return false
	}

	clientCert := req.TLS.PeerCertificates[0]
	hash := sha256.Sum256(clientCert.Raw)
	certThumbprint := base64.RawURLEncoding.EncodeToString(hash[:])

	return certThumbprint == x5tS256
}

func logger() *slog.Logger {
	opts := &slog.HandlerOptions{
		Level: slog.LevelDebug,
	}
	handler := slog.NewJSONHandler(os.Stdout, opts)

	return slog.New(handler)
}

type statusRecorder struct {
	http.ResponseWriter
	status int
}

func (rec *statusRecorder) WriteHeader(code int) {
	rec.status = code
	rec.ResponseWriter.WriteHeader(code)
}

func singleJoiningSlash(a, b string) string {
	if a == "" || b == "" {
		return a + b
	}
	aslash := a[len(a)-1] == '/'
	bslash := b[0] == '/'
	switch {
	case aslash && bslash:
		return a + b[1:]
	case !aslash && !bslash:
		return a + "/" + b
	}
	return a + b
}

func signSsa(ss map[string]any) []byte {

	now := time.Now().Unix()
	ss["iat"] = now
	ss["exp"] = now + 3600
	ssa, _ := json.Marshal(ss)

	headers := jws.NewHeaders()
	_ = headers.Set(jws.TypeKey, "JWT")

	signed, err := jws.Sign(ssa, jws.WithKey(jwa.PS256(), ssaJWK, jws.WithProtectedHeaders(headers)))
	if err != nil {
		log.Fatalf("Erro ao assinar os dados: %v", err)
	}

	return signed
}
