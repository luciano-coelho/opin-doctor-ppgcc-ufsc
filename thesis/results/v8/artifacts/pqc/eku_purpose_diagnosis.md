# "Verify return code 26 (unsuitable certificate purpose)" -- exact cause (Luciano, round 3, item 1)

No profile switch was needed: the three server certificates
(`mtls.crt`, `mtls_pqc.crt`, `mtls_hybrid.crt`) coexist on disk regardless of
which `CRYPTO_PROFILE` is currently active, so all three were inspected
directly, live, without touching the running gateway.

## Which certificate, which extension

`openssl verify -purpose sslserver -show_chain -verbose` on all three:

```
error 26 at 0 depth lookup: unsuitable certificate purpose
```

**Depth 0 = the leaf certificate itself** (not the CA, not an intermediate) --
identical result for Classic, PQC, and Hybrid. The exact field, read directly
with `openssl x509 -noout -ext extendedKeyUsage,keyUsage,basicConstraints`,
is the same on all three:

```
X509v3 Key Usage: critical
    Digital Signature
X509v3 Extended Key Usage:
    TLS Web Client Authentication
```

**The certificate's own Extended Key Usage declares only `clientAuth` --
never `serverAuth`.** `KeyUsage` (critical, Digital Signature) is otherwise
adequate for TLS; `BasicConstraints` is not the issue (confirmed absent/not
flagged in the `-text` output's own purpose breakdown, `SSL server CA : No`
only because this is a leaf, not a CA). `openssl verify -purpose sslserver`
checks specifically whether the leaf is suitable to act as a **server's**
certificate, and a certificate issued with only client-auth EKU fails that
check by the standard's own definition, independent of any PQC/Hybrid
property -- this is the same finding for Classic's own purely-RSA
certificate, so it predates and is unrelated to the post-quantum migration.

## Does the real client (Go, `tls_kem_proxy`) apply or bypass this check?

**Bypasses it entirely.** `thesis/scripts/tls_kem_proxy/main.go:212`:
`InsecureSkipVerify: true`, with the comment immediately above (`line 202`)
explaining why: "this lab's gateway presents a self-signed chain under its
own local CA." `InsecureSkipVerify` disables Go's `crypto/tls` certificate
verification altogether -- chain validation, purpose/EKU checking, and
hostname matching all skipped, not just the specific EKU check `openssl
verify` performs. The real campaign client never evaluates this certificate
property at all, under any profile; `openssl verify -purpose sslserver` is a
stricter, independent probe this project's own client was never configured
to run.

## Neutral statement for the report

The server certificates (Classic, PQC, and Hybrid alike) are issued with
Extended Key Usage limited to `clientAuth`, never `serverAuth` -- a property
of this lab's certificate-issuance tooling, present in all three profiles and
unrelated to the post-quantum migration itself. `openssl verify`'s own
`sslserver` purpose check correctly flags this when run as an independent
probe. The project's real client intentionally skips certificate
verification altogether (`InsecureSkipVerify: true`, documented in code for
a different, already-known reason -- the self-signed local CA), so this EKU
property has no effect on any measurement in this report.
