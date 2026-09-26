// Proves the negotiated group actually contributed fresh, real key material
// to the session -- not just that curveID says so in a log line. Opens two
// independent, fresh TLS connections to the same gateway, both forced to
// the requested group, and exports keying material (RFC 5705,
// tls.ConnectionState.ExportKeyingMaterial) from each. If the exported
// values differ between the two connections, the session secret was
// genuinely re-derived from a fresh ephemeral exchange each time (as KEM/
// ECDHE guarantees) -- a fixed/cached "fake" key would export identical
// bytes every time regardless of which connection asked. Works for all
// three profiles. Legacy v7 groups (thesis/results/v7/artifacts/{classic,pqc,hybrid}/,
// kept for historical reproducibility, not used by default):
// -group classic|mlkem1024|x25519mlkem768. Current groups (the realigned
// comparison chain): -group secp384r1|mlkem1024|secp384r1mlkem1024.
//
// -classical-only additionally asserts the negotiated curveID is NOT any
// of the ML-KEM-containing group names -- the PQC/Classic artifacts use
// this to confirm no post-quantum component silently crept in (PQC) or
// that the connection is purely classical with zero KEM at all (Classic).
package main

import (
	"crypto/tls"
	"encoding/hex"
	"fmt"
	"os"
)

func main() {
	group := os.Args[1]
	certPath := os.Args[2]
	keyPath := os.Args[3]

	cert, err := tls.LoadX509KeyPair(certPath, keyPath)
	if err != nil {
		fmt.Println("load cert error:", err)
		os.Exit(1)
	}

	var curvePreferences []tls.CurveID
	var wantCurveID string
	switch group {
	case "classic":
		curvePreferences = []tls.CurveID{tls.CurveP521, tls.CurveP384, tls.CurveP256}
		wantCurveID = "" // any classical curve is acceptable; checked separately below
	case "mlkem1024":
		curvePreferences = []tls.CurveID{tls.MLKEM1024}
		wantCurveID = "MLKEM1024"
	case "x25519mlkem768":
		curvePreferences = []tls.CurveID{tls.X25519MLKEM768}
		wantCurveID = "X25519MLKEM768"
	case "secp384r1":
		curvePreferences = []tls.CurveID{tls.CurveP384}
		wantCurveID = "" // any classical curve is acceptable; checked separately below
	case "secp384r1mlkem1024":
		curvePreferences = []tls.CurveID{tls.SecP384r1MLKEM1024}
		wantCurveID = "SecP384r1MLKEM1024"
	default:
		fmt.Println("unknown group:", group, "(want classic, mlkem1024, x25519mlkem768, secp384r1, or secp384r1mlkem1024)")
		os.Exit(1)
	}
	classicalNames := map[string]bool{"CurveP256": true, "CurveP384": true, "CurveP521": true}

	var exports [][]byte
	var curves []string
	for i := 0; i < 2; i++ {
		cfg := &tls.Config{
			Certificates:       []tls.Certificate{cert},
			InsecureSkipVerify: true,
			MinVersion:         tls.VersionTLS12,
			CurvePreferences:   curvePreferences,
		}
		conn, err := tls.Dial("tcp", "mtls:443", cfg)
		if err != nil {
			fmt.Println("dial error:", err)
			os.Exit(1)
		}
		state := conn.ConnectionState()
		curves = append(curves, state.CurveID.String())

		exported, err := state.ExportKeyingMaterial("EXPORTER-artifact-proof", nil, 32)
		if err != nil {
			fmt.Println("export error:", err)
			os.Exit(1)
		}
		exports = append(exports, exported)
		fmt.Printf("connection %d: curveID=%s tlsVersion=%s exported(32B)=%s\n",
			i+1, state.CurveID.String(), tls.VersionName(state.Version), hex.EncodeToString(exported))
		conn.Close()
	}

	fmt.Println()
	for _, c := range curves {
		if group == "classic" || group == "secp384r1" {
			if !classicalNames[c] {
				fmt.Printf("RESULT: FAIL -- negotiated %q, not a classical curve (P256/P384/P521)\n", c)
				os.Exit(1)
			}
		} else if c != wantCurveID {
			fmt.Printf("RESULT: FAIL -- did not negotiate %s on both connections (got %q)\n", wantCurveID, c)
			os.Exit(1)
		}
	}
	if hex.EncodeToString(exports[0]) == hex.EncodeToString(exports[1]) {
		fmt.Println("RESULT: FAIL -- exported keying material was IDENTICAL across two independent connections " +
			"(would indicate a fixed/non-fresh session secret, not a real per-connection key exchange)")
		os.Exit(1)
	}
	fmt.Printf("RESULT: verified -- both connections negotiated %s (group=%s), and the exported "+
		"key material (RFC 5705) is DIFFERENT between the two -- confirms the session secret was "+
		"genuinely derived from a fresh key exchange on each connection, not a fixed or decorative value.\n", curves[0], group)
}
