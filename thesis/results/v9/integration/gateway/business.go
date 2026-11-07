// business.go reinstates mock_mtls's HTTP business layer (reverse
// proxying to auth/mockapi, token introspection, the directory's
// root-ca.pem/issuer-ca.pem) for T6b -- ported from mock-service-os/
// mock_mtls/main.go (origin commit 478bda51815d8bf60ebd23fb83f592270aa04377),
// dropped by Decisao 12 (T5) as out of scope, now needed to run the
// real 44-HTTP-call flow end to end. See DECISIONS.md, Decisao 17.
//
// Deliberately NOT ported: SSA signing (signSsa/loadSsaKey, the jwx
// dependency) and the directory's /participants, /token,
// /{org_id}/application.jwks, /.well-known/openid-configuration --
// confirmed by reading thesis/scripts/opin_flow.py directly that its
// real flow (run_insurance_flow/run_person_flow) never calls any of
// these (its own header comment: "No SSA fetch in either flow...
// client_one is a statically pre-registered client, not going through
// DCR"; DIRECTORY_CONNECT_HOST is used only for root-ca.pem/
// issuer-ca.pem). Porting unused code would add surface area and risk
// without helping T6b's actual goal.
package main

import (
	"crypto/sha256"
	"encoding/base64"
	"encoding/json"
	"encoding/pem"
	"io"
	"log/slog"
	"net/http"
	"net/http/httputil"
	"net/url"
	"os"
	"strings"
	"time"
)

// businessMux wires up the same host-based routing original mock_mtls
// used (net/http.ServeMux dispatches on the request's Host header, not
// the client's resolved DNS name -- matls-auth.local and auth.local
// land on the identical handler).
func businessMux(rootCAPEM, issuerCAPEM []byte) *http.ServeMux {
	authURI := envOr("AUTH_URI", "http://auth:3000")
	apiURI := envOr("API_GATEWAY_URI", "http://mockapi:8080")

	mux := http.NewServeMux()
	mux.Handle("directory/", directoryHandler(rootCAPEM, issuerCAPEM))

	authProxy := reverseProxyHandler(authURI)
	mux.Handle("auth.local/", authProxy)
	mux.Handle("matls-auth.local/", authProxy)

	apiProxy := enforceAccessTokenMiddleware(reverseProxyHandler(apiURI))
	mux.Handle("api.local/", apiProxy)
	mux.Handle("matls-api.local/", apiProxy)
	mux.Handle("mtls/", apiProxy)

	return mux
}

// directoryHandler serves the REAL mock-service-os root/issuer CA
// files (mounted read-only at REAL_CERTS_DIR), not v9's own TLS certs.
// Found necessary live (DECISIONS.md, Decisao 17): opin_flow.py's own
// verify_ca_chain() cryptographically verifies these two files
// independently of the mTLS connection, against the REAL ca.crt read
// from a local file -- a v9-only, self-signed, 1-level CA (Decisao 11)
// can never satisfy that check, regardless of serving content, since
// it checks a signature relationship these endpoints are the only way
// this script learns about. Serving the real files here is a
// values-only "which file to read" choice (this handler, not any
// cryptographic or TLS-identity decision) -- it doesn't touch v9's own
// handshake certs/CAs at all.
func directoryHandler(rootCAPEM, issuerCAPEM []byte) http.Handler {
	mux := http.NewServeMux()
	serve := func(pem []byte) http.HandlerFunc {
		return func(w http.ResponseWriter, r *http.Request) {
			w.Header().Set("Content-Type", "application/x-pem-file")
			w.WriteHeader(http.StatusOK)
			_, _ = w.Write(pem)
		}
	}
	mux.HandleFunc("/root-ca.pem", serve(rootCAPEM))
	mux.HandleFunc("/issuer-ca.pem", serve(issuerCAPEM))
	return loggingMiddleware(mux)
}

func reverseProxyHandler(upstream string) http.Handler {
	target, err := url.Parse(upstream)
	if err != nil {
		slog.Error("reverseProxyHandler: bad upstream URL", "upstream", upstream, "err", err)
		os.Exit(1)
	}
	proxy := httputil.NewSingleHostReverseProxy(target)
	proxy.Director = func(req *http.Request) { setCustomHeaders(req, target) }
	return loggingMiddleware(proxy)
}

func setCustomHeaders(req *http.Request, target *url.URL) {
	req.Header.Set("X-Forwarded-Proto", "https")
	req.Header.Set("Host", req.Host)
	req.Header.Set("X-Real-IP", getRemoteIP(req))
	req.Header.Set("X-Forwarded-For", getForwardedFor(req))

	if req.TLS != nil && len(req.TLS.PeerCertificates) > 0 {
		clientCert := req.TLS.PeerCertificates[0]
		certPEM := pem.EncodeToMemory(&pem.Block{Type: "CERTIFICATE", Bytes: clientCert.Raw})
		certPEMString := strings.ReplaceAll(string(certPEM), "\n", " ")
		req.Header.Set("BANK-TLS-Certificate", certPEMString)
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
		req.Header.Set("User-Agent", "")
	}
}

func getRemoteIP(req *http.Request) string {
	host := req.RemoteAddr
	if i := strings.LastIndex(host, ":"); i != -1 {
		return host[:i]
	}
	return host
}

func getForwardedFor(req *http.Request) string {
	forwardedFor := req.Header.Get("X-Forwarded-For")
	ip := getRemoteIP(req)
	if forwardedFor != "" {
		return forwardedFor + ", " + ip
	}
	return ip
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

func loggingMiddleware(h http.Handler) http.Handler {
	return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		start := time.Now()
		rec := &statusRecorder{ResponseWriter: w, status: 200}
		h.ServeHTTP(rec, r)
		clientCert := "none"
		if r.TLS != nil && len(r.TLS.PeerCertificates) > 0 {
			clientCert = r.TLS.PeerCertificates[0].Subject.CommonName
		}
		// remoteAddr (the client's ephemeral TCP port) uniquely
		// identifies WHICH TLS connection served this request --
		// requests sharing a remoteAddr shared one connection
		// (keep-alive reuse); a request with a new remoteAddr opened a
		// fresh one. This is what Decisao 18's connection/request
		// cross-reference is built from.
		slog.Info("access log",
			"remoteAddr", r.RemoteAddr, "host", r.Host, "request", r.RequestURI, "method", r.Method,
			"status", rec.status, "clientCert", clientCert, "durationMs", time.Since(start).Milliseconds())
	})
}

type statusRecorder struct {
	http.ResponseWriter
	status int
}

func (rec *statusRecorder) WriteHeader(code int) {
	rec.status = code
	rec.ResponseWriter.WriteHeader(code)
}

// enforceAccessTokenMiddleware/introspectAndAddHeaders/
// verifyCertificateThumbprint/fetchAndAddUserInfo: ported unchanged
// from mock_mtls/main.go -- this is the RS-facing access-token check,
// calling back to the REAL auth service's own /token/introspection and
// /me, exactly as v7/v8 do. Nothing here depends on which TLS profile
// is active.
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

// introspectionHTTPClient: DisableKeepAlives, deliberately -- see
// mock_mtls/main.go's own comment on this (Decision, v8): a shared
// keep-alive client can reuse a connection auth's own Node server has
// already closed server-side under higher injected latency, surfacing
// as a confusing EOF. Not a concern T6b's local, 0ms runs are likely to
// hit, but kept for parity with the origin rather than dropped.
var introspectionHTTPClient = &http.Client{Transport: &http.Transport{DisableKeepAlives: true}}

func introspectAndAddHeaders(req *http.Request, token string) bool {
	authURI := envOr("AUTH_URI", "http://auth:3000")
	introspectionURL := authURI + "/token/introspection"
	clientID := "client"
	clientSecret := "1234"

	data := url.Values{}
	data.Set("token", token)

	introspectionReq, err := http.NewRequest("POST", introspectionURL, strings.NewReader(data.Encode()))
	if err != nil {
		slog.Error("Failed to create introspection request", "error", err.Error())
		return false
	}
	introspectionReq.SetBasicAuth(clientID, clientSecret)
	introspectionReq.Header.Set("Content-Type", "application/x-www-form-urlencoded")

	resp, err := introspectionHTTPClient.Do(introspectionReq)
	if err != nil {
		slog.Error("Failed to introspect token", "error", err.Error())
		return false
	}
	defer resp.Body.Close()

	if resp.StatusCode != http.StatusOK {
		slog.Error("Token introspection returned non-200 status", "status", resp.Status)
		return false
	}

	body, err := io.ReadAll(resp.Body)
	if err != nil {
		slog.Error("Failed to read introspection response body", "error", err.Error())
		return false
	}

	var introspectionResponse map[string]interface{}
	if err := json.Unmarshal(body, &introspectionResponse); err != nil {
		slog.Error("Failed to unmarshal introspection response", "error", err.Error())
		return false
	}

	if active, ok := introspectionResponse["active"].(bool); !ok || !active {
		slog.Error("Token is not active")
		return false
	}

	if cnf, ok := introspectionResponse["cnf"].(map[string]interface{}); ok {
		if x5tS256, ok := cnf["x5t#S256"].(string); ok {
			if !verifyCertificateThumbprint(req, x5tS256) {
				slog.Error("Client certificate thumbprint verification failed")
				return false
			}
		}
	}

	introspectionResponseBase64 := base64.StdEncoding.EncodeToString(body)
	req.Header.Set("X-Introspection-Response", introspectionResponseBase64)
	req.Header.Set("access_token", string(body))

	if _, ok := introspectionResponse["sub"].(string); ok {
		fetchAndAddUserInfo(req, token, authURI)
	}

	return true
}

func fetchAndAddUserInfo(req *http.Request, token, authURI string) {
	userInfoURL := authURI + "/me"

	userInfoReq, err := http.NewRequest("GET", userInfoURL, nil)
	if err != nil {
		slog.Error("Failed to create user info request", "error", err.Error())
		return
	}
	userInfoReq.Header.Set("Authorization", "Bearer "+token)

	resp, err := http.DefaultClient.Do(userInfoReq)
	if err != nil {
		slog.Error("Failed to fetch user info", "error", err.Error())
		return
	}
	defer resp.Body.Close()

	if resp.StatusCode != http.StatusOK {
		slog.Error("User info request returned non-200 status", "status", resp.Status)
		return
	}

	body, err := io.ReadAll(resp.Body)
	if err != nil {
		slog.Error("Failed to read user info response body", "error", err.Error())
		return
	}

	req.Header.Set("X-User-Info-Response", base64.StdEncoding.EncodeToString(body))
}

func verifyCertificateThumbprint(req *http.Request, x5tS256 string) bool {
	if req.TLS == nil || len(req.TLS.PeerCertificates) == 0 {
		return false
	}
	clientCert := req.TLS.PeerCertificates[0]
	hash := sha256.Sum256(clientCert.Raw)
	certThumbprint := base64.RawURLEncoding.EncodeToString(hash[:])
	return certThumbprint == x5tS256
}
