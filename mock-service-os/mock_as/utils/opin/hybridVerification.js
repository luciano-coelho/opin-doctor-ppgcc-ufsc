// Strong Nesting verification (PS256 + ML-DSA-65), the inverse of
// hybridSigning.js's rehybridizeJwt(), per thesis/results/v4/
// Arquitetura_Tecnica_Experimento3_Strong_Nesting.docx:
//   decompose signature -> sigma1 (first 256 bytes, PS256/RSA-2048) and
//     sigma2 (remaining 3309 bytes, ML-DSA-65)
//   verify sigma1 against the original message with the classic public key
//   reconstruct message || sigma1
//   verify sigma2 against that reconstruction with the ML-DSA-65 public key
//   AND gate: accept only if both verifications pass
//
// This is a pure, standalone function -- NOT wired into oidc-provider's
// request handling. Doing that would mean intercepting and rewriting the
// raw Koa/Node request stream before oidc-provider parses it (the
// signing side only had to replace an already-built ctx.body/redirect,
// which is comparatively safe; rewriting an incoming stream in-flight is
// a materially riskier piece of engineering). Deferred until there's a
// real caller to test it against (Etapa 7's hybrid-aware opin_flow.py) --
// see DECISIONS.md.
import { createPublicKey, verify as cryptoVerify, constants, webcrypto } from 'node:crypto';
import { importJWK } from 'jose';

const CLASSIC_SIG_BYTES = 256; // RSA-2048 PS256 signature length, fixed.

export async function verifyHybrid(compactJwt, classicPublicJwk, pqcPublicJwk) {
  const parts = compactJwt.split('.');
  if (parts.length !== 3) {
    return { valid: false, reason: 'not a 3-segment compact JWS' };
  }
  const [headerB64, payloadB64, sigB64] = parts;
  const message = Buffer.from(`${headerB64}.${payloadB64}`, 'ascii');

  let combined;
  try {
    combined = Buffer.from(sigB64, 'base64url');
  } catch {
    return { valid: false, reason: 'signature segment is not valid base64url' };
  }
  if (combined.length <= CLASSIC_SIG_BYTES) {
    return { valid: false, reason: `combined signature too short (${combined.length} bytes)` };
  }
  const sigma1 = combined.subarray(0, CLASSIC_SIG_BYTES);
  const sigma2 = combined.subarray(CLASSIC_SIG_BYTES);

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
