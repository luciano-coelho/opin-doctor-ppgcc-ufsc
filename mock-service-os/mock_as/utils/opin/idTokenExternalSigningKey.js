// Decision 10 (thesis/results/v4/DECISIONS.md): closes the last gap from
// Decision 2 -- the id_token is built and signed entirely inside
// oidc-provider's own internal code (lib/models/id_token.js), then
// immediately JWE-encrypted, all before the outbound rehybridization
// middleware (hybridSigning.js's rehybridizeInPlace) ever sees the HTTP
// response -- by then the id_token is already a 5-segment JWE, which never
// matches the outbound middleware's 3-segment compact-JWS detector. There is
// no event/hook between signing and encryption (confirmed against
// oidc-provider 9.5.1's source), but there IS an official one for the
// signing step itself: `features.externalSigningSupport` +
// `ExternalSigningKey` (both exported from the `oidc-provider` package's own
// public entry point). When a key registered in `jwks.keys` is an
// `ExternalSigningKey` instance, oidc-provider hands its own JWS signing
// input (`base64url(header) + "." + base64url(payload)`, the exact
// unmodified bytes) to this class's `sign()` method and uses whatever bytes
// come back as the signature -- verbatim, no shape validation.
//
// The id_token's header alg has to stay "PS256": oidc-provider validates
// the client's registered `id_token_signed_response_alg` against its own
// kty/alg table before ever calling into this class, and doesn't recognize
// the combined alg string. This is the SAME asymmetry already accepted for
// client_assertion/the PAR request object (Decision 9) -- header looks
// ordinary, only the signature's decoded length (3565 bytes, sigma1||sigma2)
// reveals Strong Nesting is in use.
//
// Confirmed via oidc-provider's own source (lib/models/id_token.js) that
// `keystore.selectForSign({alg, use: 'sig'})` is called with no `kid`, for
// BOTH id_token AND the JARM authorization response (both resolve to the
// same alg string in hybrid mode, since idTokenSigningAlgValues and
// authorizationSigningAlgValues are both internalSigningAlgs) -- there is no
// way to scope a second signing key to just one of them via the public API.
// Rather than relying on array-order/stable-sort tie-breaking (fragile,
// undocumented behavior) to keep this key from also being picked for JARM,
// configuration.js REPLACES the plain internalSigningKey JWK with this
// class entirely in hybrid mode, so there is exactly one PS256-capable
// signing key candidate, full stop. If it does end up handling JARM too,
// that's harmless: express.js's existing outbound middleware unconditionally
// rebuilds JARM's header and signature from scratch regardless of what
// arrives, so JARM still ends up correctly hybrid-signed under the combined
// alg header either way -- just with one redundant (thrown-away) signing
// pass, not a correctness risk.
import { createPublicKey } from 'node:crypto';
import { ExternalSigningKey } from 'oidc-provider';
import { CLASSIC_PUBLIC_JWK, CLASSIC_KID, signStrongNesting } from './hybridSigning.js';

const classicPublicKeyObject = createPublicKey({ key: CLASSIC_PUBLIC_JWK, format: 'jwk' });

export class HybridIdTokenSigningKey extends ExternalSigningKey {
  constructor() {
    super();
    this.kid = CLASSIC_KID;
    this.alg = 'PS256';
  }

  keyObject() {
    return classicPublicKeyObject;
  }

  // data = Buffer.from(`${base64url(header)}.${base64url(payload)}`) --
  // oidc-provider's own real JWS signing input, unmodified. Returns
  // sigma1||sigma2 (raw bytes); oidc-provider base64url-encodes whatever
  // this returns and appends it as the signature segment verbatim.
  async sign(data) {
    return signStrongNesting(Buffer.from(data));
  }
}
