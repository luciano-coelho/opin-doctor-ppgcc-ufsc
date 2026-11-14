package main

import (
	"crypto/ecdsa"
	"crypto/elliptic"
	"crypto/rand"
	"crypto/tls"
	"crypto/x509"
	"crypto/x509/pkix"
	"encoding/pem"
	"math/big"
	"net"
	"testing"
	"time"
)

// Decisao 159, item (b): a REAL TLS 1.3 handshake over a real TCP
// loopback connection (not net.Pipe -- that is a synchronous,
// unbuffered conduit and would never reproduce the OS-socket-buffer
// race that caused the original leak), with a client that writes its
// first post-handshake bytes IMMEDIATELY after Handshake() returns --
// exactly the condition that made the pre-Decisao-159 counter read
// 1556B instead of 1485B for the Classico profile, 100% of the time,
// in the real measurement. 100 iterations, fresh connection each time
// (same as a real campaign: one handshake per connection) -- every
// single one must report the IDENTICAL `in` count.

func generateSelfSignedCertForTest(t *testing.T) tls.Certificate {
	t.Helper()
	key, err := ecdsa.GenerateKey(elliptic.P256(), rand.Reader)
	if err != nil {
		t.Fatalf("generate key: %v", err)
	}
	template := &x509.Certificate{
		SerialNumber: big.NewInt(1),
		Subject:      pkix.Name{CommonName: "counting-conn-test"},
		NotBefore:    time.Now().Add(-time.Hour),
		NotAfter:     time.Now().Add(time.Hour),
		KeyUsage:     x509.KeyUsageDigitalSignature,
		ExtKeyUsage:  []x509.ExtKeyUsage{x509.ExtKeyUsageServerAuth},
		DNSNames:     []string{"localhost"},
	}
	der, err := x509.CreateCertificate(rand.Reader, template, template, &key.PublicKey, key)
	if err != nil {
		t.Fatalf("create certificate: %v", err)
	}
	keyDER, err := x509.MarshalECPrivateKey(key)
	if err != nil {
		t.Fatalf("marshal key: %v", err)
	}
	certPEM := pem.EncodeToMemory(&pem.Block{Type: "CERTIFICATE", Bytes: der})
	keyPEM := pem.EncodeToMemory(&pem.Block{Type: "EC PRIVATE KEY", Bytes: keyDER})
	cert, err := tls.X509KeyPair(certPEM, keyPEM)
	if err != nil {
		t.Fatalf("load keypair: %v", err)
	}
	return cert
}

func TestCountingConnRecordFraming_RealHandshake_ImmediateWriteClient_100Iterations(t *testing.T) {
	cert := generateSelfSignedCertForTest(t)
	serverCfg := &tls.Config{
		Certificates: []tls.Certificate{cert},
		MinVersion:   tls.VersionTLS13,
		MaxVersion:   tls.VersionTLS13,
	}
	clientCfg := &tls.Config{
		InsecureSkipVerify: true, // test-only: no real CA chain needed, only the handshake/race matters
		MinVersion:         tls.VersionTLS13,
		MaxVersion:         tls.VersionTLS13,
	}

	const iterations = 100
	const firstRequestPayload = "GET / HTTP/1.1\r\nHost: counting-conn-test\r\n\r\n"

	ln, err := net.Listen("tcp", "127.0.0.1:0")
	if err != nil {
		t.Fatalf("listen: %v", err)
	}
	defer ln.Close()

	var inCounts []int64
	done := make(chan struct{})

	go func() {
		defer close(done)
		for i := 0; i < iterations; i++ {
			raw, err := ln.Accept()
			if err != nil {
				t.Errorf("iteration %d: accept: %v", i, err)
				return
			}
			cc := newCountingConn(raw)
			srvConn := tls.Server(cc, serverCfg)
			if err := srvConn.Handshake(); err != nil {
				t.Errorf("iteration %d: server handshake: %v", i, err)
				raw.Close()
				continue
			}
			cc.disableRecordFraming()
			in, _ := cc.snapshot()
			inCounts = append(inCounts, in)

			// drain the client's immediate post-handshake write so the
			// client side doesn't block, then close -- this project's
			// own request/response shape doesn't matter here, only
			// that SOMETHING arrives right after Finished.
			buf := make([]byte, len(firstRequestPayload))
			_, _ = srvConn.Read(buf)
			srvConn.Close()
		}
	}()

	for i := 0; i < iterations; i++ {
		raw, err := net.Dial("tcp", ln.Addr().String())
		if err != nil {
			t.Fatalf("iteration %d: dial: %v", i, err)
		}
		cliConn := tls.Client(raw, clientCfg)
		if err := cliConn.Handshake(); err != nil {
			t.Fatalf("iteration %d: client handshake: %v", i, err)
		}
		// Decisao 159's whole point: write IMMEDIATELY, no delay, to
		// maximize the chance the next record is already sitting in
		// the server's OS socket buffer by the time its last
		// handshake Read() executes.
		if _, err := cliConn.Write([]byte(firstRequestPayload)); err != nil {
			t.Fatalf("iteration %d: client write: %v", i, err)
		}
		cliConn.Close()
	}

	<-done

	if len(inCounts) != iterations {
		t.Fatalf("got %d successful handshakes, want %d", len(inCounts), iterations)
	}
	want := inCounts[0]
	for i, got := range inCounts {
		if got != want {
			t.Fatalf("iteration %d: in=%d, want %d (every iteration must report the IDENTICAL count -- "+
				"a divergence here is exactly the race Decisao 159 fixes)", i, got, want)
		}
	}
	t.Logf("all %d iterations: in=%d bytes (identical)", iterations, want)
}
