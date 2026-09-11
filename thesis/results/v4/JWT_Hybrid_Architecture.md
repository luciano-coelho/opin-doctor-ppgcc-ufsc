# JWT Hybrid Architecture — Payload Extension (Decision 13)

This document describes the hybrid JWT signature architecture used in Experiment 3
from Decision 13 onward: RS256 as the outer, standards-shaped signature, with the
post-quantum signature carried as an extension inside the payload itself. It
replaces Strong Nesting (Etapa 2, ML-DSA-65 as the outer/last signature) for every
hybrid JWT artifact except the id_token and JARM, which remain on Strong Nesting
for reasons explained in Section 5. Full implementation history, investigation
notes, and the corrected discovery-gap fix are in `DECISIONS.md`, Decision 13 —
this document is the standalone architectural reference, not a replacement for
that narrative.

All data in this document is captured live from the running system
(`CRYPTO_PROFILE=hybrid`), not fabricated — Section 3 in particular is a single,
real, cryptographically re-verified JWT the Resource Server issued during a live
`opin_flow.py` run.

---

## 1. Architecture overview

### The principle

A payload-extension hybrid JWT carries both signatures, but not side by side in
the JWS signature segment the way Strong Nesting does. Instead:

- The classical signature (RS256) is the **only** thing in the JWS's own
  signature segment, and it is computed **last**, over the complete
  `base64url(header) + "." + base64url(payload)` input — where `payload` already
  contains the post-quantum signature, embedded as an ordinary claim.
- The post-quantum signature (ML-DSA-65) is computed **first**, over the claims
  *before* that claim exists, and its result is what gets embedded.

Because RS256 signs last and covers the whole payload, it transitively covers the
`pqc` claim too — any tampering with the post-quantum half invalidates the
classical signature as well, even though the two operations happen in the
opposite order from Strong Nesting. This is the same ordering principle Etapa 6's
hybrid X.509 certificates already use (ML-DSA-65 first over a preTBS, RSA last
over the complete TBS, per Bindel, Braun, Gladiator, Stebila & Wiggers, 2019) —
Decision 13 applies it to JWTs for the first time in this project.

The header reverts to an entirely ordinary `{"alg": "RS256", "typ": "JWT"}` — no
custom algorithm string, nothing for a verifier to recognize as unusual before it
even starts.

### Why this order was chosen

The advisor proposed this composition specifically to prioritize
**full backward compatibility** over Strong Nesting's stronger security
guarantee, aligned with the SAD's (System Architecture Document) gradual
migration principle: participants at different stages of post-quantum migration
must be able to interoperate without breaking. Under Strong Nesting, the
signature segment itself is non-standard — a header verifier does not know how to
split `sigma1‖sigma2` apart, so a token can only ever be validated by
hybrid-aware code. Under payload extension, an entirely ordinary, unmodified
RS256 verifier — one that has never heard of ML-DSA-65, JCS, or this thesis —
accepts the token as-is, ignoring `pqc` as just another claim it doesn't
recognize. This is demonstrated concretely in Section 4.

### The security-property tradeoff

This ordering is not free: it trades **SUF-CMA** (strong unforgeability,
Strong Nesting's property) for **EUF-CMA** (existential unforgeability).

- **SUF-CMA** (Bindel, Herath, McKague & Stebila, 2017, PQCrypto): nobody can
  produce a *second* valid signature over an *already-signed* message, even
  holding the first signature. Strong Nesting achieves this because ML-DSA-65
  signs `message‖sigma1` — the classical signature is baked into what the
  post-quantum half covers, so there is only ever one valid combined signature
  per message.
- **EUF-CMA**: nobody can forge a signature over a *new* message, but a second,
  different-looking signature over the *same* message is not excluded by the
  primitive alone. Payload extension only achieves EUF-CMA: the two signatures
  are computed over related but distinguishable inputs (JCS-canonical claims vs.
  the full header+payload), so a formal SUF-CMA proof does not carry over
  automatically.

**Why this is an acceptable trade in this specific context**: Brendel, Cremers,
Jackson & Zhao ("The Provable Security of Ed25519", 2021, IEEE S&P) show that
SUF-CMA vs. EUF-CMA is not a binary "secure vs. insecure" choice — many real
protocols only ever need EUF-CMA, and demanding SUF-CMA everywhere is often
stricter than the actual threat model requires. The concrete risk SUF-CMA
defends against — an attacker recombining a classical signature from one context
with a post-quantum signature from another to forge a "new" valid combined
signature — does not apply here: none of OPIN's consent artifacts ever circulate
with their classical and post-quantum signatures detached from one another for
an attacker to recombine. (Formal protocol analyses that assume SUF-CMA as a
base building block — e.g. Bhargavan et al.'s line of work — are exactly the
kind of context where this substitution would need to be re-justified; OPIN's
own consent-flow protocol is not one of them.) See `DECISIONS.md`, Decision 13,
for the full analysis and the complete reference list (Section 7 below).

---

## 2. Signing flow, step by step

1. **Generate the claims.** The issuer (Resource Server or client) builds the
   ordinary JSON claims exactly as it always has — no `pqc` field yet.
2. **Canonicalize via JCS (RFC 8785).** The claims are serialized into their
   RFC 8785 JSON Canonicalization Scheme form — the one, unique byte
   representation for that JSON value, independent of which language's JSON
   library produced the original claims object. This step exists specifically
   so verification (Section 4) can reproduce the exact same bytes later,
   despite Node, Java, and Python all having different default serialization
   behavior (key order, number formatting, whitespace).
3. **Sign with ML-DSA-65.** The post-quantum private key signs the canonical
   bytes from step 2 directly (a raw signature over those bytes, not a JWS of
   its own).
4. **Insert into `payload.pqc`.** The signature is embedded into the claims as
   `{"pqc": {"alg": "ML-DSA-65", "signature": "<base64url>"}}` — the claims
   object now includes this extension.
5. **Sign the complete payload with RS256.** The classical private key signs
   the ordinary JWS input, `base64url(header) + "." + base64url(payload)`,
   where `payload` is the step-4 object (claims + `pqc`) as actually
   transmitted. This is the *only* signature that ends up in the JWS's own
   signature segment — a completely standard RS256 signature.

Implemented independently on three sides, each producing byte-identical results
for the same logical operation: `ResponseSigningService.java` (Resource
Server), `opin_flow.py`'s `_sign_jwt_hybrid()` (client, for `client_assertion`
and the PAR request object), and conceptually mirrored in
`payloadExtensionVerification.js`'s reverse direction (Authorization Server,
verification side). JCS itself is never hand-rolled — each side uses an
established reference library: `canonicalize` (npm) on the AS,
`io.github.erdtman:java-json-canonicalization` (the JCS specification author's
own reference implementation) on the RS, `rfc8785` (PyPI) on the client.

---

## 3. A real, complete example

Captured live from a running `CRYPTO_PROFILE=hybrid` flow — a genuine Resource
Server response (`GET .../insurance-person/{id}/premium`), not a fabricated
sample. Independently re-verified after capture (Section 4 shows the exact
verification steps); both signatures check out valid.

### Header (decoded)

```json
{"alg": "RS256", "kid": "mZi6awCMmw-lTxi5N3k9d6i_Wa5veP2IZyMvNolkcvQ", "typ": "JWT"}
```

Nothing marks this as anything other than an ordinary RS256 JWT header — that is
the point.

### Payload (decoded, complete)

```json
{
  "data": {
    "amount": { "amount": "16", "unitType": "PORCENTAGEM" },
    "paymentsQuantity": 4,
    "coverages": [
      {
        "branch": "0111",
        "code": "CIRURGIA",
        "premiumAmount": { "amount": "1680.71", "unitType": "PORCENTAGEM" }
      }
    ],
    "payments": [
      {
        "movementDate": "2023-10-01",
        "movementType": "COMPENSACAO_FINANCEIRA",
        "movementOrigin": "EMISSAO_DIRETA",
        "movementPaymentsNumber": 1,
        "amount": {
          "amount": "680.71",
          "unitType": "MONETARIO",
          "unit": { "code": "Br", "description": "BRL" }
        },
        "maturityDate": "2023-10-01",
        "tellerId": "string",
        "tellerIdType": "CPF",
        "tellerIdTypeOthers": "RNE",
        "tellerName": "string",
        "financialInstitutionCode": "string",
        "paymentType": "BOLETO"
      }
    ]
  },
  "links": {
    "self": "https://api.local/open-insurance/insurance-person/v2/insurance-person/40664fd9-08dd-4cb9-a19f-59acb6a4df69/premium"
  },
  "meta": { "totalRecords": 1, "totalPages": 1 },
  "pqc": {
    "alg": "ML-DSA-65",
    "signature": "CJy5_RDA2loqyG3xOuBmalPqetlrzoISeyBzZolBbzV5X6EKCiAQdRbpYlKjwAc_9kEOPCyMUej012JL8t8H2pphbkX-IfJxMV5IydjeFiMu_qZoKqAN1OnOa-65EjG12VPPb-VTFMCYQ8EauNdePPvwc8_CbJzpQBrBR0SENKRMHGleb7n0zI_A4vqUSLPbzIQrd1_sZQ6wYIh8ni8sBng51mWAcWgs0Inz6QTRZzEqA4gx4ZvCJ7kN6uIR9IL-W8sVJztgq9_7qYF8O7FCoiG0Nq1Rvz-1ewqh38rzwoTAmmDqzHUy3mb1EsJ0GvY_-pSNiJ5XahjjvdLJQcN7kmYa4mzbuQ4tgIATJQJ-nt3gXg5Td8GVs63qQvA3ZQ6Be7KgxleO_qF2RoNKJtyeN9_e7VxCCrFqq4tgDPht88fhQnJNVO7grdDDSndiALhnxV7CxSuAS7gzvoPApZ4rPfCMZzq2cPi9oqdCX6NyWqA3b-MpE39yC0xNEJqnxRaL7DO68HzOQviarjibBrFx9srkChhlFZoggATgQ_niA26YJuYVS24qznO3JyVdMg4AJnfVIxwI2dafXQwbNfOgbElfCUlpJZzf16fCtou_KyN-F7VqEYrCphwTGQgY7ImftQlcsa3FbA0c0_8aXJxzyB7iBtMHMwWf4MFn8stRUGD9tFFr4bSkR0qUO8AGUPuSyfUvORhY4qllG_qzBs_zWF3agVYf9A8MoSWQ_ciCNue--HWIGj16NfWBkIZjIlK5sDfuwcy...(4412 base64url characters total — the raw 3309-byte ML-DSA-65 signature, base64url-encoded)"
}
```

The `pqc.signature` value above is truncated for legibility (full value is 4412
characters); the byte counts are exact and independently confirmed (Section 4).

### The exact bytes ML-DSA-65 actually signed (step 2/3 of Section 2)

The JCS-canonical form of the claims *without* `pqc` — this is not the same
byte string as the decoded payload above (compare key ordering: `data` before
`links` before `meta` in both, but JCS also sorts every *nested* object's keys
alphabetically, e.g. `amount`/`unitType` and `financialInstitutionCode` before
`maturityDate` before `movementDate`, regardless of the order they were
originally written in):

```json
{"data":{"amount":{"amount":"16","unitType":"PORCENTAGEM"},"coverages":[{"branch":"0111","code":"CIRURGIA","premiumAmount":{"amount":"1680.71","unitType":"PORCENTAGEM"}}],"payments":[{"amount":{"amount":"680.71","unit":{"code":"Br","description":"BRL"},"unitType":"MONETARIO"},"financialInstitutionCode":"string","maturityDate":"2023-10-01","movementDate":"2023-10-01","movementOrigin":"EMISSAO_DIRETA","movementPaymentsNumber":1,"movementType":"COMPENSACAO_FINANCEIRA","paymentType":"BOLETO","tellerId":"string","tellerIdType":"CPF","tellerIdTypeOthers":"RNE","tellerName":"string"}],"paymentsQuantity":4},"links":{"self":"https://api.local/open-insurance/insurance-person/v2/insurance-person/40664fd9-08dd-4cb9-a19f-59acb6a4df69/premium"},"meta":{"totalPages":1,"totalRecords":1}}
```

782 bytes.

### The full compact token

`header.payload.signature`, 7430 characters total:

- **header segment** (106 chars, complete):
  `eyJhbGciOiJSUzI1NiIsImtpZCI6Im1aaTZhd0NNbXctbFR4aTVOM2s5ZDZpX1dhNXZlUDJJWnlNdk5vbGtjdlEiLCJ0eXAiOiJKV1QifQ`
- **payload segment**: 6980 characters (the base64url encoding of the complete
  JSON in the box above, `pqc` included) — omitted here in full for legibility,
  shown decoded above instead.
- **signature segment** (342 chars, complete — the RS256 signature, decodes to
  exactly 256 raw bytes, matching the RS's RSA-2048 key):
  `gVtZarOwMztuLQp-CUO-hN-YVsLeQg0xwCeJlLMHeZkQZZQDg8lvCqlc5idUMoGrMB4vSvaJFFM9RFlo0Vpzp2Ml4pCQiGU5se4bEH-oQj6Bscoh5xBAGbUSpIQzSZGcbFVafa7rUjTR9LJUMTPkGoa1ImKITGMrmycZGqtakcgQsGkktOE0XPCOn-tfAxuV-HVoRm_uRQSLmPuawar4pqNVdw5JTIMRwBwsskQXstLpMs-zjHOpauf0R1saKDJVciSzLgTXavKpN0e0jWuP2WKWpsCp4-uqohUYCfGtYcN6tf5NExmQif9IsAi2xqstmUCD5y8J1uXIsBaQs0Yn8w`

For scale: this token is 7430 bytes total, of which 4412 (59%) is the
base64url-encoded ML-DSA-65 signature alone — see the JWT-average discussion in
`DECISIONS.md`'s Decision 13 for why the payload-extension scheme costs
noticeably more bytes than Strong Nesting for the exact same cryptographic
content (the post-quantum signature gets base64url-encoded twice instead of
once).

---

## 4. Verification flow, step by step

### Legacy verifier (RS256-only, no knowledge of `pqc`)

1. Fetch the RS's `/jwks`, find the entry whose `kid` matches the token header
   (`mZi6awCMmw-...`) and whose `kty`/`alg` are compatible with RS256 — the
   plain `{"kty": "RSA", "alg": "RS256", ...}` entry (Section 6 explains why
   this entry has to exist at all).
2. Verify the RS256 signature over `base64url(header) + "." + base64url(payload)`
   using that key — a completely ordinary JWS verification, no special code.
3. Parse the payload as JSON. `pqc` is present but unrecognized — an ordinary
   verifier either ignores unknown claims (the common case) or, if it validates
   against a strict schema that doesn't expect `pqc`, may reject it for
   *schema* reasons unrelated to signature validity. As far as the *signature*
   is concerned, this verifier accepts the token.

Demonstrated directly, live, with `jose`'s own generic `compactVerify` and
`createLocalJWKSet` (no project-specific code involved) in `DECISIONS.md`'s
Decision 13 — both a fresh RS-issued token and a fresh client-issued token were
accepted this way after the discovery-gap fix (Section 6).

### PQC-aware verifier (RS256 + ML-DSA-65, AND-gated)

1. Verify RS256 exactly as above (step 1-2) — if this fails, reject
   immediately; nothing below matters.
2. Extract `payload.pqc.signature` and its declared `alg`. If `pqc` is absent,
   treat the token as **not hybrid-shaped** (fell through as a legitimately
   classical-only artifact under this scheme's backward-compatible framing —
   see `DECISIONS.md`, Decision 13, on why this differs from an outright
   rejection).
3. Remove `pqc` from a copy of the parsed payload, and re-serialize the
   remainder through the exact same RFC 8785 canonicalization used at signing
   time (Section 2, step 2). This reproduces the precise byte string ML-DSA-65
   originally signed, regardless of which language produced the original
   token.
4. Verify the ML-DSA-65 signature over those canonical bytes using the
   corresponding public key.
5. **AND gate**: accept only if both step 1 and step 4 succeeded. If RS256
   passed but ML-DSA-65 failed, this is a genuine downgrade/tamper signal — the
   AS's own inbound middleware (`clientHybridAuth.js`) rejects such requests
   outright (HTTP 400) rather than silently falling back to RS256-only
   acceptance, since that would turn the AND gate into an OR gate. See the
   worked example in Section 3: `RS256 valid: true`, `ML-DSA-65 valid: true`,
   both independently confirmed against the RS's own key material.

Implemented in `mock-service-os/mock_as/utils/opin/payloadExtensionVerification.js`
(reused as the production verifier throughout this project's own sabatinas, not
just described here) and mirrored for signing on the RS/client sides as
described in Section 2.

---

## 5. The id_token/JARM exception

The id_token and JARM (JWT Secured Authorization Response Mode) are the only
two hybrid artifacts in this project that remain on **Strong Nesting** —
untouched by Decision 13. This is a deliberate scope decision, not a gap left
by oversight.

**Why**: both are built through oidc-provider's internal `IdToken` class
(`lib/models/id_token.js`; JARM's own response-mode handler
(`lib/response_modes/jwt.js`) literally instantiates the same class). That
class exposes no public, documented extension point to inject an additional
claim (the `pqc` field this scheme needs) into the payload *before* its native
signing pass runs — confirmed by reading oidc-provider 9.5.1's own source
directly. `extraTokenClaims`, the hook this project already uses elsewhere,
only applies to opaque/JWT-formatted access tokens, a different code path
entirely. Decision 10's `ExternalSigningKey` mechanism — which *is* how id_token
gets its Strong Nesting signature today — does not help here either: its
`sign(data)` hook receives the header and payload already fully serialized,
with no way to modify the payload from inside it, only to supply alternate
signature bytes over what oidc-provider already fixed.

The only remaining path would be monkey-patching `IdToken.prototype.payload`
at boot time — reaching into undocumented library internals rather than a
supported extension point, and fragile to any future oidc-provider upgrade
that restructures this class. Weighed against the benefit (migrating two
already-working artifacts to a scheme whose main advantage — standard-verifier
compatibility — id_token/JARM arguably need less than client-facing artifacts,
since they are typically consumed by the same relying party that requested
them, already hybrid-aware by construction), this was judged disproportionate.
**Decision: id_token and JARM keep Strong Nesting exactly as Decision 10 left
them** — combined `alg: "MLDSA65-RSA2048-PSS-SHA256"` header, `sigma1‖sigma2`
raw-concatenated in the signature segment, ML-DSA-65 last. Re-verified live
after every subsequent change in this thesis (most recently as part of this
decision's own sabatina) to confirm the exception holds in practice, not just
on paper.

---

## 6. The key-discovery gap — found, and closed

### The problem

Decision 13's first "legacy verifier" validation used a flawed test: it
imported each classical public key by hand, with `alg: "RS256"` hardcoded by
the test itself, rather than letting a real JWKS-discovery flow pick the key
and its declared algorithm. Corrected to use `jose.createLocalJWKSet` — real
`kid`-based discovery, no manual override — against each JWKS exactly as
published, and the result reversed:

- **RS's `/jwks`** published only the composed `kty: "HYBRID"` entry — no plain
  RSA key at all for a standard library's RS256 verification path to
  recognize. **Rejected**, `ERR_JWKS_NO_MATCHING_KEY`.
- **`client_one`'s registered JWKS** still carried `"alg": "PS256"` on its
  signing key (the file is shared with classic mode, where PS256 is still
  correct) while the token header said `"RS256"`. **Rejected**,
  `ERR_JWKS_NO_MATCHING_KEY`.

In other words: the scheme's central promise — "an ordinary verifier accepts
this without adaptation" — held only for this project's own internal
verification (which reads key material directly from known files, never
through real `kid`+`alg` JWKS discovery), not for an external relying party
doing standard discovery. Section 4's "legacy verifier" walkthrough above
describes the *corrected*, now-passing state.

### The fix

- **RS `/jwks`** now publishes **two** entries under the same `kid` — the
  original composed `kty: "HYBRID"` key, unchanged, plus a new plain
  `{"kty": "RSA", "alg": "RS256", ...}` entry built from the exact `n`/`e`
  the RS256 signature is actually computed with:

  ```json
  {"kty":"HYBRID","alg":"MLDSA65-RSA2048-PSS-SHA256","use":"sig","kid":"mZi6awCMmw-...","pk_hybrid":"1KEH2RKcHf2dRKmVcfNB_6vV...(truncated)"}
  {"kty":"RSA","use":"sig","alg":"RS256","kid":"mZi6awCMmw-...","n":"1KEH2RKcHf2dRKmVcfNB_6vV...(truncated)","e":"AQAB"}
  ```

  (Live capture, same `kid` on both entries — deliberately, since that is the
  `kid` every payload-extension-signed RS token's header actually carries.
  Standard JOSE key-selection logic filters by expected `kty` before `kid`, so
  the two entries never collide during selection: an RS256 verifier looks for
  `kty: "RSA"` first and finds only the second entry.)

- **Client**: a new, committed file, `client_one_hybrid_pub.jwks` —
  byte-identical to `client_one_pub.jwks` except `"alg": "PS256"` →
  `"alg": "RS256"` on the signing key, same `kid`/`n`/`e` — mirrors the
  existing `client_one_pqc_pub.jwks` pattern (one JWKS variant per profile,
  never mutating the shared classic-mode file). `mongo-seed/start.sh`
  registers this file for hybrid mode instead of the classic-mode one.

### Re-tested, same corrected methodology, both now pass

```
client_one_hybrid_pub.jwks: registered alg RS256 matches token header RS256
  -> jose.createLocalJWKSet ACCEPTED
RS's live /jwks (fetched fresh): kty:"HYBRID" entry + kty:"RSA",alg:"RS256" entry
  -> jose.createLocalJWKSet ACCEPTED
```

Confirmed this fix changes no measured byte content in the actual signed/
transmitted artifacts (only what gets published as discovery metadata) — a
fresh scenario re-run matched the already-collected data byte-for-byte. Full
details, including the original failing output, in `DECISIONS.md`, Decision
13.

**Still open**: the AS's own `/jwks` publishes only the single composed key —
not fixed, because no AS-issued artifact currently uses the payload-extension
scheme (id_token/JARM, the only AS-issued hybrid artifacts, stay on Strong
Nesting per Section 5). The broader design question of whether the composed
single-entry publication still makes sense at all, now that the two signatures
verify independently of each other, remains open for a future decision.

---

## 7. References

- Bindel, N., Herath, U., McKague, M., & Stebila, D. (2017). *Transitioning to
  a Quantum-Resistant Public Key Infrastructure.* PQCrypto 2017. — Strong
  Nesting's original composition and its SUF-CMA proof; the baseline this
  decision deliberately moves away from.
- Bindel, N., Braun, J., Gladiator, L., Stebila, D., & Wiggers, T. (2019).
  *X.509-Compliant Hybrid Certificates for the Post-Quantum Transition.*
  Journal of Open Source Software (JOSS), 4(40), 1606. — the ML-DSA-first/
  RSA-last ordering principle this decision applies to JWTs, and the
  three-extension X.509 mechanism Etapa 6 already implements.
- Bhargavan, K., et al. — formal protocol analyses assuming SUF-CMA as a base
  building block; cited as the category of context where this decision's
  substitution would need re-justification, and why OPIN's own consent-flow
  protocol is not such a context.
- Brendel, J., Cremers, C., Jackson, D., & Zhao, M. (2021). *The Provable
  Security of Ed25519: Theory and Practice.* IEEE Symposium on Security and
  Privacy (S&P). — SUF-CMA vs. EUF-CMA in practice, and the basis for treating
  this as a legitimate, named tradeoff rather than an ad hoc weakening.
- F1000Research — review article on strong-unforgeability signature schemes,
  grounding the SUF-CMA/EUF-CMA distinction as an established topic in the
  signature-scheme literature.
- OpenID Foundation, Financial-grade API Working Group. *JWT Secured
  Authorization Response Mode for OAuth 2.0 (JARM).* — the mechanism Section 5
  identifies as one of the two Strong-Nesting exceptions.
- IETF RFC 8785. *JSON Canonicalization Scheme (JCS).* — the canonicalization
  standard adopted for the ML-DSA-65-signed portion of every payload-extension
  artifact (Section 2), implemented via each language's reference library
  rather than hand-rolled, specifically to avoid the cross-language
  serialization divergence this decision's investigation phase identified as
  a real risk.
