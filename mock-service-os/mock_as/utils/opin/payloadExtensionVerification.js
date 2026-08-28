// Payload-extension verification (RS256 + ML-DSA-65 via a `pqc` claim),
// per thesis/results/v4/DECISIONS.md (Decision 13) -- replaces Strong
// Nesting (hybridVerification.js/hybridSigning.js) for every hybrid
// artifact EXCEPT the id_token and JARM, which stay Strong Nesting (see
// the same decision for why: both depend on an oidc-provider extension
// point -- injecting a claim into the payload before its native signing
// pass -- that the library does not expose publicly).
//
// Signing order (the deliberate inversion from Strong Nesting): ML-DSA-65
// signs first, over the RFC 8785 (JCS) canonical bytes of the claims
// WITHOUT the `pqc` extension; RS256 signs last, over the ordinary
// `base64url(header) + "." + base64url(payload)` JWS signing input, where
// `payload` already has `pqc` embedded. The result is an entirely
// ordinary RS256 JWT -- `pqc` is just an extra claim an unmodified
// verifier ignores.
//
// JCS, not any language's default JSON serialization, for the
// ML-DSA-65-signed portion specifically: verification has to remove
// `pqc` from the received payload and RE-SERIALIZE the remainder to
// reproduce the exact bytes that were signed, and only a canonical
// serialization guarantees that reconstruction is byte-identical
// regardless of which of this project's three languages (Node here,
// Java on the RS, Python on the client) produced the original signature.
// See DECISIONS.md for the full reasoning and the RFC 8785 reference.
import { createPublicKey, verify as cryptoVerify, constants, webcrypto } from 'node:crypto';
import { importJWK } from 'jose';
import canonicalize from 'canonicalize';

export async function verifyPayloadExtension(compactJws, classicPublicJwk, pqcPublicJwk) {
  const parts = compactJws.split('.');
  if (parts.length !== 3) {
    return { valid: false, reason: `not a 3-segment compact JWS (${parts.length})` };
  }
  const [headerB64, payloadB64, sigB64] = parts;
  const message = Buffer.from(`${headerB64}.${payloadB64}`, 'ascii');

  let sig;
  try {
    sig = Buffer.from(sigB64, 'base64url');
  } catch {
    return { valid: false, reason: 'signature segment is not valid base64url' };
  }

  const rs256Ok = cryptoVerify(
    'sha256',
    message,
    {
      key: createPublicKey({ key: classicPublicJwk, format: 'jwk' }),
      padding: constants.RSA_PKCS1_PADDING,
    },
    sig,
  );
  if (!rs256Ok) {
    return { valid: false, reason: 'RS256 verification failed' };
  }

  let payload;
  try {
    payload = JSON.parse(Buffer.from(payloadB64, 'base64url').toString('utf8'));
  } catch {
    return { valid: false, reason: 'payload is not valid JSON' };
  }

  const pqcClaim = payload.pqc;
  if (!pqcClaim || typeof pqcClaim.signature !== 'string') {
    return { valid: false, reason: 'missing payload.pqc.signature -- not hybrid-shaped', hybridShaped: false };
  }

  let pqcSig;
  try {
    pqcSig = Buffer.from(pqcClaim.signature, 'base64url');
  } catch {
    return { valid: false, reason: 'payload.pqc.signature is not valid base64url', hybridShaped: true };
  }

  const { pqc: _pqc, ...claimsWithoutPqc } = payload;
  const canonicalBytes = Buffer.from(canonicalize(claimsWithoutPqc), 'utf8');

  const pqcKey = await importJWK(pqcPublicJwk, 'ML-DSA-65');
  const pqcOk = await webcrypto.subtle.verify({ name: 'ML-DSA-65' }, pqcKey, pqcSig, canonicalBytes);
  if (!pqcOk) {
    return { valid: false, reason: 'ML-DSA-65 (payload.pqc.signature) verification failed', hybridShaped: true };
  }

  return { valid: true, reason: 'both RS256 and ML-DSA-65 verified', hybridShaped: true };
}
