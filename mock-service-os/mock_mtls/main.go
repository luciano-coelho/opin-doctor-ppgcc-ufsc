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
)

func init() {
	if os.Getenv("CRYPTO_PROFILE") == "pqc" {
		serverCertFilePath = "certs/mtls_pqc.crt"
		serverKeyFilePath = "certs/mtls_pqc.key"
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
		InsecureSkipVerify: true,
		ClientCAs:          caCerts,
		ClientAuth:         tls.VerifyClientCertIfGiven,
		MinVersion:         tls.VersionTLS12,
		MaxVersion:         tls.VersionTLS13,
		CurvePreferences:   []tls.CurveID{tls.CurveP521, tls.CurveP384, tls.CurveP256},

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

	// Purely observational hook: fires right after the ClientHello is parsed,
	// before certificate exchange/verification, giving us a precise handshake
	// start time keyed by remote address. Returning (nil, nil) tells the TLS
	// stack "no per-client override, use cfg as-is" -- this does not alter
	// negotiation behavior in any way (cipher suites/versions/certs unchanged).
	cfg.GetConfigForClient = func(hello *tls.ClientHelloInfo) (*tls.Config, error) {
		if hello.Conn != nil {
			handshakeStartTimes.Store(hello.Conn.RemoteAddr().String(), time.Now())
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

func introspectAndAddHeaders(req *http.Request, token string) bool {
	introspectionURL := "http://auth:3000/token/introspection"
	clientID := "client"
	clientSecret := "1234"

	data := url.Values{}
	data.Set("token", token)

	client := &http.Client{}
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
