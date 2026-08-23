// Strong Nesting hybrid signature (PS256 + ML-DSA-65), per
// thesis/results/v4/ARCHITECTURE.md:
//   sigma1 = PS256_sign(message)
//   sigma2 = ML-DSA-65_sign(message || sigma1)     -- raw byte concatenation,
//                                                       not base64
//   signature = base64url(sigma1 || sigma2)
//
// oidc-provider/jose cannot produce this natively -- "MLDSA65-RSA2048-PSS-
// SHA256" is not a real JOSE algorithm, so no library's dispatch table knows
// it. The approach here: let oidc-provider build a completely normal PS256
// token internally (using the classic half of hybrid.json's two keys), then
// intercept it after the fact (see express.js's hybrid re-signing
// middleware), replace the header's alg/kid, and redo BOTH signature stages
// ourselves. oidc-provider's own PS256 signature is discarded -- it was
// computed over the old header, which is a different byte string.
import { createPrivateKey, createHash, sign as cryptoSign, constants, webcrypto } from 'node:crypto';
import { importJWK } from 'jose';
import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import path from 'node:path';

const __dirname = path.dirname(fileURLToPath(import.meta.url));

export const HYBRID_ALG = 'MLDSA65-RSA2048-PSS-SHA256';

const hybridProfile = JSON.parse(
  readFileSync(path.join(__dirname, '..', '..', 'crypto-profiles', 'hybrid.json'), 'utf8'),
);

const classicJwk = hybridProfile.classicSigningKey;
const pqcJwk = hybridProfile.pqcSigningKey;

const classicPrivateKey = createPrivateKey({ key: classicJwk, format: 'jwk' });
const pqcPrivateKeyPromise = importJWK(pqcJwk, 'ML-DSA-65');

// pk_hybrid = classicPk || pqcPk (Etapa 5's exact composition) -- raw public
// key bytes, not JWK objects: 256 bytes (RSA-2048 modulus n) + 1952 bytes
// (ML-DSA-65 raw public key), confirmed against both JWKs before writing
// this. The kid is derived from this same composed byte string so the
// signer (here) and the /jwks publisher (Etapa 5) can never disagree about
// which kid a given hybrid artifact was produced under.
const classicPkBytes = Buffer.from(classicJwk.n, 'base64url');
const pqcPkBytes = Buffer.from(pqcJwk.pub, 'base64url');
if (classicPkBytes.length !== 256) {
  throw new Error(`hybridSigning: expected 256-byte classic public key, got ${classicPkBytes.length}`);
}
if (pqcPkBytes.length !== 1952) {
  throw new Error(`hybridSigning: expected 1952-byte ML-DSA-65 public key, got ${pqcPkBytes.length}`);
}
export const HYBRID_PK_BYTES = Buffer.concat([classicPkBytes, pqcPkBytes]);
export const HYBRID_KID = createHash('sha256').update(HYBRID_PK_BYTES).digest('base64url');

function base64url(buf) {
  return Buffer.from(buf).toString('base64url');
}

function signPs256Raw(message) {
  return cryptoSign('sha256', message, {
    key: classicPrivateKey,
    padding: constants.RSA_PKCS1_PSS_PADDING,
    saltLength: constants.RSA_PSS_SALTLEN_DIGEST,
  });
}

// Signs the raw bytes directly via Node's native WebCrypto API -- NOT
// jose's CompactSign, which was tried first and is wrong for this: jose
// treats its argument as a JWS *payload* and signs
// `base64url(header) + "." + base64url(payload)`, not the bytes handed to
// it directly. That mismatch went undetected through Etapas 2/3 (both
// produced signatures of the exact right *length*, since ML-DSA-65
// signatures are fixed-size regardless of what's actually signed) until
// hybridVerification.js's independent verify implementation caught it:
// sigma1 always verified, sigma2 never did. Fixed by signing
// `message` directly with webcrypto.subtle.sign(), matching exactly what
// hybridVerification.js verifies it against. The private key import
// (jose's importJWK) is unaffected -- only the signing call itself
// changed from CompactSign to a direct WebCrypto sign.
async function signMlDsaRaw(message) {
  const pqcPrivateKey = await pqcPrivateKeyPromise;
  const sig = await webcrypto.subtle.sign({ name: 'ML-DSA-65' }, pqcPrivateKey, message);
  return Buffer.from(sig);
}

// Takes a compact JWS this process already produced with PS256 (oidc-
// provider's own internal signing pass) and re-signs it via Strong Nesting.
// Returns the new compact JWS string. Only touches tokens whose header
// really is `{"alg":"PS256",...}` -- anything else (JWE, or an unrelated
// string that merely looks like 3 dot-separated segments) is returned
// unchanged, since it isn't a signature this AS is responsible for.
export async function rehybridizeJwt(compactJwt) {
  const parts = compactJwt.split('.');
  if (parts.length !== 3) return compactJwt;
  const [oldHeaderB64, payloadB64] = parts;

  let header;
  try {
    header = JSON.parse(Buffer.from(oldHeaderB64, 'base64url').toString('utf8'));
  } catch {
    return compactJwt;
  }
  if (header.alg !== 'PS256') return compactJwt;

  const newHeader = { ...header, alg: HYBRID_ALG, kid: HYBRID_KID };
  const newHeaderB64 = base64url(Buffer.from(JSON.stringify(newHeader), 'utf8'));

  const message = Buffer.from(`${newHeaderB64}.${payloadB64}`, 'ascii');
  const sigma1 = signPs256Raw(message);
  const sigma2 = await signMlDsaRaw(Buffer.concat([message, sigma1]));
  const finalSig = base64url(Buffer.concat([sigma1, sigma2]));

  return `${newHeaderB64}.${payloadB64}.${finalSig}`;
}

// Compact-JWS detector for scanning arbitrary response bodies/URLs: three
// base64url segments separated by dots, each non-empty. Deliberately loose
// (doesn't try to fully validate JSON structure up front) -- rehybridizeJwt
// itself is the authority on whether a match is really a PS256 JWS worth
// touching, this just avoids running that check against every string in a
// response body.
export const COMPACT_JWS_RE = /^[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+$/;

// Walks a plain JSON-shaped value (object/array from oidc-provider's own
// response body, e.g. the /token JSON with an id_token field) and replaces
// any string that looks like a PS256 compact JWS in place, recursively.
export async function rehybridizeInPlace(value) {
  if (Array.isArray(value)) {
    for (let i = 0; i < value.length; i += 1) {
      if (typeof value[i] === 'string' && COMPACT_JWS_RE.test(value[i])) {
        value[i] = await rehybridizeJwt(value[i]);
      } else if (value[i] && typeof value[i] === 'object') {
        await rehybridizeInPlace(value[i]);
      }
    }
    return;
  }
  if (value && typeof value === 'object') {
    for (const key of Object.keys(value)) {
      const v = value[key];
      if (typeof v === 'string' && COMPACT_JWS_RE.test(v)) {
        value[key] = await rehybridizeJwt(v);
      } else if (v && typeof v === 'object') {
        await rehybridizeInPlace(v);
      }
    }
  }
}
