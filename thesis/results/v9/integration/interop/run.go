package main

import (
	"crypto/mldsa"
	"crypto/tls"
	"crypto/x509"
	"fmt"
	"net"
	"strings"
	"time"
)

// modeMaterial: everything one participant ("mode") needs to act as
// either client or server in the interoperability configuration --
// all six modes share BOTH CA pools and offer ALL THREE KEX groups,
// unlike the measurement harness's own single-group, single-CA
// profiles.
type modeMaterial struct {
	name           string
	serverCert     *tls.Certificate // nil for the impostor-as-server case (not used)
	clientCert     *tls.Certificate
	dualCert       *tls.Certificate // non-nil only for hibrido-and modes
	dualRequire    bool
	dualPresent    bool // false for "rsa-unico-impostor": no Dual material at all
	authPathLabel  string
}

func main() {
	// Shared trust roots -- the whole point of this configuration.
	rsaCACert, rsaCAKey := rsaCA()
	mldsaCACert, mldsaCAKey := mldsaCA()

	classicalPool := x509.NewCertPool()
	classicalPool.AddCert(rsaCACert)
	pqPool := x509.NewCertPool()
	pqPool.AddCert(mldsaCACert)
	bothPool := x509.NewCertPool()
	bothPool.AddCert(rsaCACert)
	bothPool.AddCert(mldsaCACert)

	classicoServer := rsaLeaf("classico-server", rsaCACert, rsaCAKey, x509.ExtKeyUsageServerAuth)
	classicoClient := rsaLeaf("classico-client", rsaCACert, rsaCAKey, x509.ExtKeyUsageClientAuth)
	pqcServer := mldsaLeaf("pqc-server", mldsaCACert, mldsaCAKey, x509.ExtKeyUsageServerAuth)
	pqcClient := mldsaLeaf("pqc-client", mldsaCACert, mldsaCAKey, x509.ExtKeyUsageClientAuth)
	hv8Server := hybridLeaf("hibrido-v8-server", rsaCACert, rsaCAKey, mldsaCAKey, x509.ExtKeyUsageServerAuth)
	hv8Client := hybridLeaf("hibrido-v8-client", rsaCACert, rsaCAKey, mldsaCAKey, x509.ExtKeyUsageClientAuth)
	andRSAServer := rsaLeaf("and-rsa-server", rsaCACert, rsaCAKey, x509.ExtKeyUsageServerAuth)
	andRSAClient := rsaLeaf("and-rsa-client", rsaCACert, rsaCAKey, x509.ExtKeyUsageClientAuth)
	andMLDSAServer := mldsaLeaf("and-mldsa-server", mldsaCACert, mldsaCAKey, x509.ExtKeyUsageServerAuth)
	andMLDSAClient := mldsaLeaf("and-mldsa-client", mldsaCACert, mldsaCAKey, x509.ExtKeyUsageClientAuth)

	modes := map[string]modeMaterial{
		"classico": {
			name: "classico", serverCert: &classicoServer, clientCert: &classicoClient,
			authPathLabel: "RSA",
		},
		"pqc": {
			name: "pqc", serverCert: &pqcServer, clientCert: &pqcClient,
			authPathLabel: "ML-DSA",
		},
		"hibrido-v8": {
			name: "hibrido-v8", serverCert: &hv8Server, clientCert: &hv8Client,
			authPathLabel: "RSA+ML-DSA (gate X.509)",
		},
		"hibrido-and-estrito": {
			name: "hibrido-and-estrito", serverCert: &andRSAServer, clientCert: &andRSAClient,
			dualCert: &andMLDSAServer, dualRequire: true, dualPresent: true,
			authPathLabel: "dual (RSA+ML-DSA)",
		},
		"hibrido-and-nao-estrito": {
			name: "hibrido-and-nao-estrito", serverCert: &andRSAServer, clientCert: &andRSAClient,
			dualCert: &andMLDSAServer, dualRequire: false, dualPresent: true,
			authPathLabel: "dual (RSA+ML-DSA)",
		},
		"rsa-unico-impostor": {
			name: "rsa-unico-impostor", serverCert: &andRSAServer, clientCert: &andRSAClient,
			dualPresent: false, authPathLabel: "RSA (sem Dual)",
		},
	}

	// Dual client certs differ by role (server leaf vs client leaf) --
	// store the client-facing one separately for the client config.
	dualClientCert := map[string]*tls.Certificate{
		"hibrido-and-estrito":     &andMLDSAClient,
		"hibrido-and-nao-estrito": &andMLDSAClient,
	}

	buildServerConfig := func(m modeMaterial) *tls.Config {
		cfg := &tls.Config{
			Certificates:     []tls.Certificate{*m.serverCert},
			ClientCAs:        bothPool,
			ClientAuth:       tls.RequireAndVerifyClientCert,
			MinVersion:       tls.VersionTLS12,
			MaxVersion:       tls.VersionTLS13,
			CurvePreferences: allGroups,
		}
		if m.name == "hibrido-v8" {
			cfg.VerifyPeerCertificate = hybridVerifyFunc(mldsaCACert.PublicKey.(*mldsa.PublicKey))
		}
		if m.dualPresent {
			cfg.Dual = &tls.DualConfig{
				Certificates: []tls.Certificate{*m.dualCert},
				ClientCAs:    pqPool,
				Require:      m.dualRequire,
			}
		}
		return cfg
	}

	_ = classicalPool // kept for clarity/possible future narrowing; bothPool is what's actually used

	buildClientConfig := func(m modeMaterial) *tls.Config {
		cfg := &tls.Config{
			Certificates:     []tls.Certificate{*m.clientCert},
			RootCAs:          bothPool,
			ServerName:       "interop",
			MinVersion:       tls.VersionTLS12,
			MaxVersion:       tls.VersionTLS13,
			CurvePreferences: allGroups,
		}
		if m.dualPresent {
			cfg.Dual = &tls.DualConfig{
				Certificates: []tls.Certificate{*dualClientCert[m.name]},
				RootCAs:      pqPool,
				Require:      m.dualRequire,
			}
		}
		return cfg
	}

	order := []string{"classico", "pqc", "hibrido-v8", "hibrido-and-estrito", "hibrido-and-nao-estrito"}

	// Start one listener per legitimate server mode.
	listeners := map[string]net.Listener{}
	for _, name := range order {
		ln, err := net.Listen("tcp", "127.0.0.1:0")
		must(err)
		listeners[name] = ln
		go serveForever(ln, buildServerConfig(modes[name]), modes[name])
	}

	fmt.Printf("%-24s %-24s %-9s %-40s %-24s %-10s %-s\n", "cliente", "servidor", "resultado", "motivo", "caminho_auth", "dual_auth", "downgrade")
	for _, clientName := range order {
		for _, serverName := range order {
			runOne(clientName, serverName, buildClientConfig(modes[clientName]), listeners[serverName].Addr().String())
		}
	}

	// The two critical impostor rows.
	runOne("rsa-unico-impostor", "hibrido-and-estrito", buildClientConfig(modes["rsa-unico-impostor"]), listeners["hibrido-and-estrito"].Addr().String())
	runOne("rsa-unico-impostor", "hibrido-and-nao-estrito", buildClientConfig(modes["rsa-unico-impostor"]), listeners["hibrido-and-nao-estrito"].Addr().String())
}

// serveForever: writes one ack byte immediately after a successful
// Handshake() -- deliberately NOT a bounded Read() racing against the
// client's own bounded Read(). A first version read on both ends with
// matching 2s deadlines and whichever side's deadline fired first
// decided the outcome -- pure timing noise, not a real protocol
// difference, found live when strict-vs-strict (which must succeed)
// came back FALHA half the time. Writing removes the race: a client
// that completed the TLS handshake for real always receives genuine
// bytes, never a coin flip between "timeout" and "EOF from an
// unrelated deadline."
func serveForever(ln net.Listener, cfg *tls.Config, m modeMaterial) {
	for {
		raw, err := ln.Accept()
		if err != nil {
			return
		}
		go func() {
			defer raw.Close()
			tlsConn := tls.Server(raw, cfg)
			if err := tlsConn.Handshake(); err != nil {
				return
			}
			_ = raw.SetWriteDeadline(time.Now().Add(2 * time.Second))
			_, _ = tlsConn.Write([]byte{1})
		}()
	}
}

func runOne(clientMode, serverMode string, clientCfg *tls.Config, target string) {
	conn, err := net.DialTimeout("tcp", target, 3*time.Second)
	if err != nil {
		printRow(clientMode, serverMode, "FALHA", "tcp: "+err.Error(), "-", "-", "nao")
		return
	}
	defer conn.Close()
	tlsConn := tls.Client(conn, clientCfg)
	if err := tlsConn.Handshake(); err != nil {
		printRow(clientMode, serverMode, "FALHA", err.Error(), "-", "-", "nao")
		return
	}
	cs := tlsConn.ConnectionState()
	// Delayed-alert check, same reasoning as negtest's dial().
	_ = conn.SetReadDeadline(time.Now().Add(2 * time.Second))
	buf := make([]byte, 1)
	_, readErr := tlsConn.Read(buf)
	if readErr != nil {
		if nerr, ok := readErr.(net.Error); !ok || !nerr.Timeout() {
			printRow(clientMode, serverMode, "FALHA", "handshake OK mas rejeitado depois: "+readErr.Error(), "-", fmt.Sprintf("%v", cs.DualAuthenticated), "nao")
			return
		}
	}
	downgrade := "nao"
	if clientMode == "rsa-unico-impostor" && !cs.DualAuthenticated {
		downgrade = "SIM -- autenticou sem provar posse ML-DSA-65"
	}
	printRow(clientMode, serverMode, "SUCESSO", fmt.Sprintf("grupo=%s", cs.CurveID), authPathFor(clientMode, cs), fmt.Sprintf("%v", cs.DualAuthenticated), downgrade)
}

func authPathFor(clientMode string, cs tls.ConnectionState) string {
	if cs.DualAuthenticated {
		return "dual (RSA+ML-DSA)"
	}
	switch clientMode {
	case "classico", "rsa-unico-impostor", "hibrido-and-estrito", "hibrido-and-nao-estrito":
		return "RSA"
	case "pqc":
		return "ML-DSA"
	case "hibrido-v8":
		return "RSA+ML-DSA (gate X.509)"
	}
	return "?"
}

func printRow(client, server, outcome, reason, authPath, dualAuth, downgrade string) {
	reason = strings.ReplaceAll(reason, "\n", " ")
	fmt.Printf("%-24s %-24s %-9s %-40s %-24s %-10s %-s\n", client, server, outcome, reason, authPath, dualAuth, downgrade)
}
