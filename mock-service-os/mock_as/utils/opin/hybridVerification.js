// Strong Nesting verification (PS256 + ML-DSA-65), the inverse of
// hybridSigning.js's rehybridizeJwt(), per thesis/results/v4/
// ARCHITECTURE.md:
//   decompose signature -> sigma1 (first 256 bytes, PS256/RSA-2048) and
//     sigma2 (remaining 3309 bytes, ML-DSA-65)
//   verify sigma1 against the original message with the classic public key
//   reconstruct message || sigma1
//   verify sigma2 against that reconstruction with the ML-DSA-65 public key
//   AND gate: accept only if both verifications pass
//
// verifyHybrid() started as a pure, standalone function (Etapa 4) -- now
// also wired into oidc-provider's request handling for real, via
// truncateIfHybrid() below and clientHybridAuth.js's inbound middleware
// (Etapa 7's Decision 9 extension: hybridizing the client's own
// client_assertion/PAR request object).
import { createPublicKey, verify as cryptoVerify, constants, webcrypto } from 'node:crypto';
import { importJWK } from 'jose';

// A PS256 signature is exactly as many bytes as the RSA modulus -- 256 for
// the AS/RS's own RSA-2048 signing keys (classic.json/hybrid.json), but
// client_one's own key is RSA-4096 (512 bytes): it's the same key already
// used for client_one's mTLS certificate, not a fresh 2048-bit key minted
// for JWS. Hardcoding 256 here silently broke verification the moment
// this function was reused for the client-to-AS direction (Decision 9) --
// confirmed empirically (`combined sig length: 3821` = 512 + 3309, not the
// 256 + 3309 = 3565 every AS/RS-issued artifact has). Deriving it from the
// actual key's own modulus makes this function correct for either key
// size, not just the one it happened to be written against first.
function classicSigBytesFor(classicPublicJwk) {
  return Buffer.from(classicPublicJwk.n, 'base64url').length;
}

export async function verifyHybrid(compactJwt, classicPublicJwk, pqcPublicJwk) {
  const parts = compactJwt.split('.');
  if (parts.length !== 3) {
    return { valid: false, reason: 'not a 3-segment compact JWS' };
  }
  const [headerB64, payloadB64, sigB64] = parts;
  const message = Buffer.from(`${headerB64}.${payloadB64}`, 'ascii');
  const classicSigBytes = classicSigBytesFor(classicPublicJwk);

  let combined;
  try {
    combined = Buffer.from(sigB64, 'base64url');
  } catch {
    return { valid: false, reason: 'signature segment is not valid base64url' };
  }
  if (combined.length <= classicSigBytes) {
    return { valid: false, reason: `combined signature too short (${combined.length} bytes)` };
  }
  const sigma1 = combined.subarray(0, classicSigBytes);
  const sigma2 = combined.subarray(classicSigBytes);

  const classicOk = cryptoVerify(
    'sha256',
    message,
    {
      key: createPublicKey({ key: classicPublicJwk, format: 'jwk' }),
      padding: constants.RSA_PKCS1_PSS_PADDING,
      saltLength: constants.RSA_PSS_SALTLEN_DIGEST,
    },
    sigma1,
  );
  if (!classicOk) {
    return { valid: false, reason: 'sigma1 (PS256) verification failed' };
  }

  // ML-DSA-65 verification is done via Node's native WebCrypto API
  // directly (not jose's CompactVerify), because jose's JWS-shaped API
  // recomputes its own signing input from a header/payload it parses --
  // it has no entry point for "verify this signature against this raw
  // byte string", which is exactly what verifying sigma2 over
  // message||sigma1 requires. The key import itself still goes through
  // jose's importJWK() (the same call hybridSigning.js already uses
  // successfully for the private half) rather than a hand-rolled
  // webcrypto.subtle.importKey() -- jose does its own AKP-JWK-to-
  // WebCrypto-key normalization before calling into WebCrypto, which a
  // naive direct import silently gets wrong (import succeeds, no error,
  // but produces a key that never verifies -- confirmed empirically).
  // jose's return value for an asymmetric JWK is already a CryptoKey,
  // directly usable with webcrypto.subtle.verify().
  const pqcKey = await importJWK(pqcPublicJwk, 'ML-DSA-65');
  const messagePlusSigma1 = Buffer.concat([message, sigma1]);
  const pqcOk = await webcrypto.subtle.verify({ name: 'ML-DSA-65' }, pqcKey, sigma2, messagePlusSigma1);
  if (!pqcOk) {
    return { valid: false, reason: 'sigma2 (ML-DSA-65) verification failed' };
  }

  return { valid: true, reason: 'both sigma1 and sigma2 verified' };
}

// Client-to-AS direction (Decision 9): the client signs client_assertion/
// the PAR request object with an ordinary `alg: "PS256"` header from the
// start (the AS can only verify what the client signed, never re-sign it
// -- see DECISIONS.md for the full reasoning), so a hybrid-signed artifact
// here is indistinguishable from a classical one at the header level. The
// only tell is the signature segment's decoded length: exactly the
// signer's RSA modulus size for an ordinary PS256 signature, more than
// that for sigma1||sigma2. This
// function passes non-hybrid-shaped input through untouched (so a
// genuinely classical assertion in a mixed environment keeps working),
// and only decomposes/verifies/AND-gates when the signature is actually
// longer than one classical signature's worth of bytes. On success, it
// returns the SAME header and payload with the signature truncated back
// down to sigma1 alone -- a real, ordinary, independently-valid PS256
// signature over that exact header+payload -- for oidc-provider's own
// unmodified verification to accept next.
export async function truncateIfHybrid(compactJwt, classicPublicJwk, pqcPublicJwk) {
  const parts = compactJwt.split('.');
  if (parts.length !== 3) {
    return { truncated: null, reason: 'not a 3-segment compact JWS' };
  }
  const [headerB64, payloadB64, sigB64] = parts;
  const classicSigBytes = classicSigBytesFor(classicPublicJwk);

  let combined;
  try {
    combined = Buffer.from(sigB64, 'base64url');
  } catch {
    return { truncated: null, reason: 'signature segment is not valid base64url' };
  }
  if (combined.length <= classicSigBytes) {
    // Ordinary classical signature -- nothing to do here.
    return { truncated: null, reason: 'not hybrid-shaped (signature is classical-length)' };
  }

  const result = await verifyHybrid(compactJwt, classicPublicJwk, pqcPublicJwk);
  if (!result.valid) {
    return { truncated: null, reason: result.reason };
  }

  const sigma1 = combined.subarray(0, classicSigBytes);
  const sigma1B64 = Buffer.from(sigma1).toString('base64url');
  return { truncated: `${headerB64}.${payloadB64}.${sigma1B64}`, reason: 'verified, truncated to sigma1' };
}
