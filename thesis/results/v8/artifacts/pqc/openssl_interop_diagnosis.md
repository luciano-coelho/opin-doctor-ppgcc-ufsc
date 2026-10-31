# PQC/OpenSSL interoperability diagnosis (Luciano, 2026-10-31, correcting Decision 115/116)

**Correction to earlier text**: Decision 115/116 and the final report's Section 2
labeled PQC's failure to negotiate with plain `openssl s_client -groups mlkem1024`
a "real cross-implementation finding... not a project defect." **That framing was
wrong.** Diagnosed properly now, with the fleet live, split into the three
independent pieces Luciano asked for: **interoperability exists**. The earlier
probe's own command was missing one required flag.

## (a) Key exchange alone

`openssl s_client -connect localhost:443 -servername mtls -cert client_one_pqc.crt
-key client_one_pqc.key -CAfile ca.crt -tls1_3 -groups MLKEM1024` (no `-sigalgs`):
**fails**, `SSL alert number 40` (fatal handshake_failure), sent by the SERVER
immediately after ClientHello. `-msg` shows OpenSSL's own ClientHello offering
group `0x0202` (514) in its `key_share`/`supported_groups` extensions -- the exact
same codepoint Go's `crypto/tls` registers for `MLKEM1024` (`common.go:158:
MLKEM1024 CurveID = 514`, confirmed by grepping the real `golang:1.27-rc-alpine`
image used throughout this project). **The group codepoints match exactly --
this was never a key-exchange incompatibility.**

## (b) TLS signature algorithms -- the actual cause

OpenSSL's `-groups MLKEM1024` alone does not add ML-DSA-65 to the ClientHello's
`signature_algorithms` extension; by default OpenSSL offers only
`RSA-PSS/ECDSA/Ed25519/Ed448`. The PQC profile's server certificate
(`mtls_pqc.crt`) is signed with ML-DSA-65 and has no other signature scheme to
offer for its `CertificateVerify` step -- with no `id-ml-dsa-65` in the client's
offered list, there is no mutually acceptable signature algorithm, and the server
fails the handshake. **Confirmed directly**: adding `-sigalgs MLDSA65` to the same
command succeeds immediately -- `Shared Requested Signature Algorithms:
id-ml-dsa-65`, `Peer signature type: mldsa65`, `Negotiated TLS1.3 group:
MLKEM1024`, full application data exchanged (11,272 bytes read). Isolated the
other direction too: `-sigalgs MLDSA65` **without** `-groups MLKEM1024` also
fails (`Negotiated TLS1.3 group: <NULL>`, no common group, as expected -- OpenSSL's
default groups don't include MLKEM1024 either). **Both flags are independently
required; neither alone is sufficient.**

## (c) Certificate and chain

`openssl verify -CAfile <root_ca_pqc.crt + issuer_ca_pqc.crt> mtls_pqc.crt` ->
**`mtls_pqc.crt: OK`** -- the real ML-DSA-65 PQC chain verifies cleanly with
OpenSSL's own `verify` command, no errors. In the live connection (both flags
set), the one remaining `Verify return code: 26 (unsuitable certificate purpose)`
is the **same pre-existing EKU/purpose quirk already found and documented for
Classic and Hybrid** (Decision 116) -- this lab CA's certificates don't carry an
explicit `serverAuth` extended-key-usage extension OpenSSL's modern default
purpose-checking expects; it is not new, not PQC-specific, and not a security
issue given this project's own `InsecureSkipVerify=true` client design
(documented in `tls_kem_proxy/main.go`).

## Conclusion

**This is a test-configuration gap in the earlier probe, not an OpenSSL
limitation and not a gateway defect.** Once the ClientHello offers both
`MLKEM1024` (key exchange) and `id-ml-dsa-65` (signature algorithm) --
exactly what the real client (`tls_kem_proxy`, Go's own `crypto/tls`) already
does automatically -- OpenSSL 3.5.8 and this project's Go gateway interoperate
completely for the PQC profile, with no codepoint mismatch, no library
incompatibility, and a cleanly verifying certificate chain. The real client was
never affected by this gap; it only affected the independent `openssl s_client`
verification probe added in Decision 115/116, whose own command was incomplete.

Full raw output: `openssl_s_client_probe_fixed.txt` (this directory).
