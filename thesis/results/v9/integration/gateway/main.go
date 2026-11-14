// gateway is the v9, T5/T6, Fase 1 integration harness's server side --
// a fork of mock-service-os/mock_mtls/main.go (origin commit
// 478bda51815d8bf60ebd23fb83f592270aa04377). See DECISIONS.md, Decisao
// 12 (T5 scope/diff) and Decisao 13/14 (T6 instrumentation) for the
// full rationale.
//
// T6 reworked the connection handling from T5's http.Server-based
// version to an explicit Accept()/Handshake() loop: T6 requires byte
// counts measured EXACTLY at the Handshake() call boundary (so the
// first HTTP request's own bytes never leak into the handshake figure
// -- the measurement-boundary artifact Decision 78/79 of v8's
// DECISIONS.md documents and deliberately left unfixed there, for
// v7-comparability). That precision is not reachable through
// http.Server's own automatic TLS wrapping, which hides the Handshake()
// call inside net/http's internals.
package main

import (
	"bufio"
	"crypto/tls"
	"crypto/x509"
	"encoding/json"
	"fmt"
	"log"
	"net"
	"os"
	"path/filepath"
	"strconv"
	"sync/atomic"
	"time"
)

var expectedCurve = map[string]tls.CurveID{
	"classico":    tls.CurveP384,
	"pqc":         tls.MLKEM1024,
	"hibrido-v8":  tls.SecP384r1MLKEM1024,
	"hibrido-and": tls.SecP384r1MLKEM1024,
}

// result is the one structured line this process prints per connection,
// consumed by run_t6.sh. Mirrors proxy's own result struct field for
// field so the two sides' JSON lines diff cleanly in the report.
type result struct {
	Side                  string `json:"side"`
	Profile               string `json:"profile"`
	OK                     bool   `json:"ok"`
	Error                 string `json:"error,omitempty"`
	CurveID               string `json:"curveID"`
	DualAuthenticated     bool   `json:"dualAuthenticated"`
	TLSVersion            string `json:"tlsVersion"`
	TicketsDisabled       bool   `json:"ticketsDisabled"`
	HandshakeBytesIn      int64  `json:"handshakeBytesIn"`
	HandshakeBytesOut     int64  `json:"handshakeBytesOut"`
	HandshakeDurationUs   int64  `json:"handshakeDurationUs"`
	PostHandshakeBytesIn  int64  `json:"postHandshakeBytesIn"`
	PostHandshakeBytesOut int64  `json:"postHandshakeBytesOut"`
	RequestDurationUs     int64  `json:"requestDurationUs"`
}

func main() {
	profile := os.Getenv("CRYPTO_PROFILE")
	certDir := envOr("CERT_DIR", "/certs")
	listen := envOr("LISTEN", ":443")

	// T6b: full HTTP business layer (reverse proxy to auth/mockapi,
	// introspection, directory CA endpoints), keep-alive, real flow --
	// see business.go/business_server.go. Default ("measure") keeps
	// T5/T6's byte-boundary-precise, single-response behavior
	// unchanged, so run_t5.sh/run_t6.sh keep working exactly as before.
	if envOr("HTTP_MODE", "measure") == "business" {
		runBusinessMode(profile, certDir, listen)
		return
	}

	ticketsDisabled := envOr("TICKETS_DISABLED", "true") == "true"
	keylogPath := os.Getenv("KEYLOG_PATH")

	want, ok := expectedCurve[profile]
	if !ok {
		log.Fatalf("gateway: unknown CRYPTO_PROFILE %q (want classico, pqc, hibrido-v8, hibrido-and)", profile)
	}

	var keylog *os.File
	if keylogPath != "" {
		var err error
		keylog, err = os.Create(keylogPath)
		if err != nil {
			log.Fatalf("gateway: create keylog %s: %v", keylogPath, err)
		}
		defer keylog.Close()
	}

	cfg, err := buildServerTLSConfig(profile, certDir, ticketsDisabled, keylog)
	if err != nil {
		log.Fatalf("gateway: %s: building TLS config: %v", profile, err)
	}

	ln, err := net.Listen("tcp", listen)
	if err != nil {
		log.Fatalf("gateway: listen %s: %v", listen, err)
	}
	log.Printf("gateway: profile=%s listening on %s (expected group %s, ticketsDisabled=%v)", profile, listen, want, ticketsDisabled)

	for {
		raw, err := ln.Accept()
		if err != nil {
			log.Printf("gateway: accept: %v", err)
			continue
		}
		go handleConn(raw, cfg, profile, want, ticketsDisabled)
	}
}

func handleConn(raw net.Conn, cfg *tls.Config, profile string, want tls.CurveID, ticketsDisabled bool) {
	defer raw.Close()
	cc := newCountingConn(raw)
	tlsConn := tls.Server(cc, cfg)

	t0 := time.Now()
	in0, out0 := cc.snapshot()
	err := tlsConn.Handshake()
	cc.disableRecordFraming() // Decisao 159: so a leitura DURANTE o handshake precisa ser record-aware
	t1 := time.Now()
	in1, out1 := cc.snapshot()

	r := result{
		Side:                  "gateway",
		Profile:               profile,
		TicketsDisabled:       ticketsDisabled,
		HandshakeBytesIn:      in1 - in0,
		HandshakeBytesOut:     out1 - out0,
		HandshakeDurationUs:   t1.Sub(t0).Microseconds(),
	}

	if err != nil {
		r.Error = err.Error()
		emit(r)
		return
	}

	cs := tlsConn.ConnectionState()
	r.CurveID = cs.CurveID.String()
	r.DualAuthenticated = cs.DualAuthenticated
	r.TLSVersion = tls.VersionName(cs.Version)

	if cs.CurveID != want {
		r.Error = fmt.Sprintf("negotiated group %s, expected exactly %s", cs.CurveID, want)
		emit(r)
		return
	}
	if profile == "hibrido-and" && !cs.DualAuthenticated {
		r.Error = "DualAuthenticated=false on the server side for hibrido-and"
		emit(r)
		return
	}

	// Post-handshake window: whatever the server itself writes (session
	// tickets, if enabled) between Handshake() returning and this
	// process's own first deliberate write (the HTTP response below) --
	// isolates ticket bytes from the handshake figure above, rather than
	// hoping they land inside one window or the other. With
	// ticketsDisabled=true this should read ~0; the T6 diagnostic run
	// (ticketsDisabled=false) quantifies the difference.
	postIn0, postOut0 := in1, out1

	tReq0 := time.Now()
	if err := serveOneResponse(tlsConn, profile, cs); err != nil {
		r.Error = err.Error()
		emit(r)
		return
	}
	r.RequestDurationUs = time.Since(tReq0).Microseconds()

	postIn1, postOut1 := cc.snapshot()
	r.PostHandshakeBytesIn = postIn1 - postIn0
	r.PostHandshakeBytesOut = postOut1 - postOut0
	r.OK = true
	emit(r)
}

// serveOneResponse hand-writes a single HTTP/1.1 response -- deliberately
// not net/http, so nothing above this file's own counting wrapper can
// call Handshake() a second time or otherwise blur the byte-counting
// boundary T6 requires. Reads and discards the request (don't care about
// its content, this harness tests TLS, not HTTP routing -- see Decisao
// 12's scope note) up to the blank line ending the headers.
func serveOneResponse(conn net.Conn, profile string, cs tls.ConnectionState) error {
	r := bufio.NewReader(conn)
	for {
		line, err := r.ReadString('\n')
		if err != nil {
			return fmt.Errorf("read request: %w", err)
		}
		if line == "\r\n" || line == "\n" {
			break
		}
	}
	body := fmt.Sprintf(`{"profile":%q,"curve":%q,"dualAuthenticated":%t,"tlsVersion":%q}`,
		profile, cs.CurveID.String(), cs.DualAuthenticated, tls.VersionName(cs.Version))
	resp := "HTTP/1.1 200 OK\r\n" +
		"Content-Type: application/json\r\n" +
		"Content-Length: " + strconv.Itoa(len(body)) + "\r\n" +
		"Connection: close\r\n\r\n" + body
	_, err := conn.Write([]byte(resp))
	return err
}

func emit(r result) {
	b, _ := json.Marshal(r)
	fmt.Println(string(b))
}

func envOr(key, fallback string) string {
	if v := os.Getenv(key); v != "" {
		return v
	}
	return fallback
}

// countingConn tallies bytes crossing the wire in each direction, below
// crypto/tls -- every byte the TLS handshake (or anything after it)
// reads or writes is counted. atomic counters: handleConn's goroutine is
// the only reader/writer per connection, but snapshot() may be called
// concurrently with ongoing I/O (right at the Handshake() boundary).
//
// Decisao 159 (achado da rodada anterior, prova decisiva: contador do
// gateway leu 1556B pro Classico onde a captura decifrada -- fonte de
// verdade, 40/40 conexoes/4 perfis -- leu exatamente 1485B, sempre
// +71B, sempre o tamanho da primeira escrita pos-handshake do
// cliente). Causa raiz, achada no PROPRIO crypto/tls vendorizado
// (nunca no and.patch): readFromUntil (conn.go) cresce o buffer de
// leitura `needs + bytes.MinRead` (512B) de proposito, "melhor esforco
// pra buscar o que ja estiver esperando no fio" -- se a proxima
// escrita do cliente (a primeira requisicao HTTP) ja chegou ao buffer
// do SO nesse instante, aquela leitura unica do crypto/tls pega bytes
// de DOIS records (o ultimo do handshake E o primeiro de application
// data pos-handshake), e countingConn.Read() (antes desta correcao)
// contava tudo que aquela unica Read() devolvesse, sem saber onde um
// record termina e o outro comeca.
//
// Correcao (sem tocar crypto/tls, and.patch nem o pin do toolchain):
// enquanto `framingActive` for true (do Accept() at o Handshake()
// retornar -- ver disableRecordFraming()), Read() nunca faz uma leitura
// bruta maior do que o que falta pro record TLS atual (cabecalho de 5B
// -- tipo, versao, tamanho, SEMPRE em claro, inclusive no TLS 1.3, RFC
// 8446 Secao 5.1 -- e depois exatamente o corpo declarado). Isso
// funciona por uma garantia do proprio contrato de net.Conn.Read: uma
// chamada nunca devolve MAIS bytes do que o tamanho do buffer passado
// -- fatiando esse buffer pro que falta do record atual, uma leitura
// bruta fisicamente nao pode alcancar bytes do PROXIMO record, nao
// importa quantos bytes extras o crypto/tls teria pedido nem quantos
// bytes extras ja estejam esperando no buffer do SO. Depois que o
// Handshake() retorna, framingActive vira false e Read() volta a ser
// passthrough irrestrito, exatamente como antes desta correcao --
// in/out continuam significando bytes lidos/escritos ATE O FIM do
// handshake, enquadramento de record incluido (cabecalho conta, e
// sempre contado).
const tlsRecordHeaderLen = 5

type countingConn struct {
	net.Conn
	in  atomic.Int64
	out atomic.Int64

	framingActive bool // true do Accept() at Handshake() retornar; so a goroutine da conexao toca isto, nunca concorrente
	headerBuf     [tlsRecordHeaderLen]byte
	headerLen     int // bytes do cabecalho do record ATUAL ja lidos (e ja devolvidos ao chamador)
	bodyRemaining int // bytes do CORPO do record atual ainda por ler (0 com headerLen==5 == record totalmente servido)
}

func newCountingConn(raw net.Conn) *countingConn {
	return &countingConn{Conn: raw, framingActive: true}
}

// disableRecordFraming: chamado exatamente uma vez por conexao, logo
// depois que Handshake() retorna (sucesso ou erro) -- dali em diante
// Read() e passthrough irrestrito de novo, igual a antes da Decisao
// 159 (acima de qualquer record ja parcialmente lido/contado: o
// enquadramento so precisa ser exato DENTRO do handshake, nunca depois).
func (c *countingConn) disableRecordFraming() {
	c.framingActive = false
}

func (c *countingConn) Read(b []byte) (int, error) {
	if !c.framingActive || len(b) == 0 {
		n, err := c.Conn.Read(b)
		c.in.Add(int64(n))
		return n, err
	}
	return c.readFramed(b)
}

// readFramed: serve no maximo o que falta de UM record TLS por
// chamada, nunca cruzando pro proximo record nesta mesma chamada --
// ver o comentario de countingConn acima pro raciocinio completo.
func (c *countingConn) readFramed(b []byte) (int, error) {
	if c.headerLen < tlsRecordHeaderLen {
		n, err := c.Conn.Read(b[:min(len(b), tlsRecordHeaderLen-c.headerLen)])
		if n > 0 {
			copy(c.headerBuf[c.headerLen:], b[:n])
			c.headerLen += n
			c.in.Add(int64(n))
			if c.headerLen == tlsRecordHeaderLen {
				c.bodyRemaining = int(c.headerBuf[3])<<8 | int(c.headerBuf[4])
			}
		}
		return n, err
	}
	if c.bodyRemaining == 0 {
		// Corpo do record atual totalmente servido (inclui o caso de
		// um record de comprimento 0, legal em TLS) -- reseta pro
		// cabecalho do PROXIMO record e tenta de novo, na mesma
		// chamada (b ainda tem espaco, garantido pelo check len(b)==0
		// no inicio de Read()).
		c.headerLen = 0
		return c.readFramed(b)
	}
	toRead := min(c.bodyRemaining, len(b))
	n, err := c.Conn.Read(b[:toRead])
	c.bodyRemaining -= n
	c.in.Add(int64(n))
	if err == nil && c.bodyRemaining == 0 {
		c.headerLen = 0 // record servido por inteiro -- proxima chamada comeca um cabecalho novo
	}
	return n, err
}

func (c *countingConn) Write(b []byte) (int, error) {
	n, err := c.Conn.Write(b)
	c.out.Add(int64(n))
	return n, err
}

func (c *countingConn) snapshot() (int64, int64) {
	return c.in.Load(), c.out.Load()
}

// buildServerTLSConfig dispatches on profile name. See Decisao 12's diff
// table for the full rationale; T6 additions on top of that: ticketsDisabled
// (point 1 of Luciano's T5-follow-up message -- tickets off in ALL 4
// profiles by default, overridable for the T6 diagnostic run that
// quantifies their cost) and an optional KeyLogWriter (T6's keylog +
// pcap cross-validation requirement).
func buildServerTLSConfig(profile, certDir string, ticketsDisabled bool, keylog *os.File) (*tls.Config, error) {
	p := func(name string) string { return filepath.Join(certDir, name) }

	var cfg *tls.Config
	var err error
	switch profile {
	case "classico":
		// Adendo a Etapa 1 do piloto v9 (achado real da verificacao
		// independente EQD): este era o unico dos 4 perfis com MinVersion
		// < MaxVersion (TLS12..TLS13) -- o canal genuinamente ADMITIA
		// negociar TLS 1.2, mesmo que dois stacks Go modernos normalmente
		// assentem em 1.3. Fixado em TLS13..TLS13, igual aos outros 3.
		cfg, err = singleChainServerConfig(p("classico_server.crt"), p("classico_server.key"), p("classico_ca.crt"), tls.CurveP384, tls.VersionTLS13, nil)
	case "pqc":
		cfg, err = singleChainServerConfig(p("pqc_server.crt"), p("pqc_server.key"), p("pqc_ca.crt"), tls.MLKEM1024, tls.VersionTLS13, nil)
	case "hibrido-v8":
		verify := hybridVerifyPeerCertificateFunc(p("hibrido_v8_ca_mldsa.crt"))
		cfg, err = singleChainServerConfig(p("hibrido_v8_server.crt"), p("hibrido_v8_server.key"), p("hibrido_v8_ca.crt"), tls.SecP384r1MLKEM1024, tls.VersionTLS13, verify)
	case "hibrido-and":
		cfg, err = dualServerConfig(certDir)
	default:
		return nil, fmt.Errorf("unknown profile %q", profile)
	}
	if err != nil {
		return nil, err
	}
	cfg.SessionTicketsDisabled = ticketsDisabled
	if keylog != nil {
		cfg.KeyLogWriter = keylog
	}
	return cfg, nil
}

func singleChainServerConfig(certPath, keyPath, caPath string, curve tls.CurveID, minVersion uint16, verifyPeer func([][]byte, [][]*x509.Certificate) error) (*tls.Config, error) {
	cert, err := tls.LoadX509KeyPair(certPath, keyPath)
	if err != nil {
		return nil, fmt.Errorf("load server cert/key (%s/%s): %w", certPath, keyPath, err)
	}
	clientCAs, err := loadCAPool(caPath)
	if err != nil {
		return nil, fmt.Errorf("load client CA pool (%s): %w", caPath, err)
	}
	return &tls.Config{
		Certificates:          []tls.Certificate{cert},
		ClientCAs:             clientCAs,
		ClientAuth:            tls.RequireAndVerifyClientCert,
		MinVersion:            minVersion,
		MaxVersion:            tls.VersionTLS13,
		CurvePreferences:      []tls.CurveID{curve},
		VerifyPeerCertificate: verifyPeer,
	}, nil
}

func dualServerConfig(certDir string) (*tls.Config, error) {
	p := func(name string) string { return filepath.Join(certDir, name) }

	rsaCert, err := tls.LoadX509KeyPair(p("hibrido_and_rsa_server.crt"), p("hibrido_and_rsa_server.key"))
	if err != nil {
		return nil, fmt.Errorf("load RSA server cert/key: %w", err)
	}
	rsaClientCAs, err := loadCAPool(p("hibrido_and_rsa_ca.crt"))
	if err != nil {
		return nil, fmt.Errorf("load RSA client CA pool: %w", err)
	}
	mldsaCert, err := tls.LoadX509KeyPair(p("hibrido_and_mldsa_server.crt"), p("hibrido_and_mldsa_server.key"))
	if err != nil {
		return nil, fmt.Errorf("load ML-DSA-65 server cert/key: %w", err)
	}
	mldsaClientCAs, err := loadCAPool(p("hibrido_and_mldsa_ca.crt"))
	if err != nil {
		return nil, fmt.Errorf("load ML-DSA-65 client CA pool: %w", err)
	}

	return &tls.Config{
		Certificates:     []tls.Certificate{rsaCert},
		ClientCAs:        rsaClientCAs,
		ClientAuth:       tls.RequireAndVerifyClientCert,
		MinVersion:       tls.VersionTLS13,
		MaxVersion:       tls.VersionTLS13,
		CurvePreferences: []tls.CurveID{tls.SecP384r1MLKEM1024},
		Dual: &tls.DualConfig{
			Certificates: []tls.Certificate{mldsaCert},
			ClientCAs:    mldsaClientCAs,
			// STRICT (new, T7 interoperability matrix, Decisao 19):
			// default "true" preserves every existing behavior
			// (Hibrido-AND has always meant strict in this project);
			// STRICT=false exists only so the matrix can show what a
			// non-strict Hibrido-AND server actually does, never used
			// outside that one-off test.
			Require: envOr("STRICT", "true") == "true",
		},
	}, nil
}

func loadCAPool(path string) (*x509.CertPool, error) {
	b, err := os.ReadFile(path)
	if err != nil {
		return nil, err
	}
	pool := x509.NewCertPool()
	if !pool.AppendCertsFromPEM(b) {
		return nil, fmt.Errorf("no certificates found in %s", path)
	}
	return pool, nil
}
