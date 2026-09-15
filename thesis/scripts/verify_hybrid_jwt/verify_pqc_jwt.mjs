// Verifies a real, captured pure-PQC JWT (alg: "ML-DSA-65", no RSA component
// at all) using Node's own native ML-DSA-65 WebCrypto support -- the same
// primitive mock_as/utils/opin/payloadExtensionVerification.js uses for the
// PQC half of the hybrid scheme (see verify_jwt.mjs), applied directly here
// since a pure-PQC JWT has only one signature to check, not two -- there is
// no payload-extension/canonicalization step to reproduce.
//
// Public key material is derived directly from the RS's own key-loading
// resource file (crypto-profiles/pqc.json's x509PublicKeyBase64), the exact
// computation ResponseSigningService.java's loadMlDsa65Signer() performs --
// used here for the same reason verify_jwt.mjs documents (the RS's live
// /jwks returned 401 from an undiagnosed filter, out of scope).
//
// Must run where Node's ML-DSA-65 WebCrypto support is available (Node 24+,
// --experimental-webcrypto or built-in) -- i.e. inside the `auth` container,
// same as verify_jwt.mjs. See thesis/results/v7/artifacts/pqc/README.md.
//
// Usage: node verify_pqc_jwt.mjs <path-to-pqc.json> <path-to-jwt-file>
import { createPublicKey, webcrypto } from 'node:crypto';
import { readFileSync } from 'node:fs';

const [pqcJsonPath, jwtPath] = process.argv.slice(2);
const pqcJson = JSON.parse(readFileSync(pqcJsonPath, 'utf8'));
const jwt = readFileSync(jwtPath, 'utf8').trim();

const [headerB64, payloadB64, sigB64] = jwt.split('.');
const signingInput = Buffer.from(`${headerB64}.${payloadB64}`, 'ascii');
const signature = Buffer.from(sigB64, 'base64url');

const spkiDer = Buffer.from(pqcJson.x509PublicKeyBase64, 'base64');
const rawJwk = createPublicKey({ key: spkiDer, format: 'der', type: 'spki' }).export({ format: 'jwk' });
const pqcPublicJwk = {
  kty: 'AKP',
  alg: 'ML-DSA-65',
  use: 'sig',
  kid: pqcJson.kid,
  pub: rawJwk.pub || rawJwk.x,
};

console.log('ML-DSA-65 public JWK, derived from pqc.json via X.509 SPKI parsing:',
  JSON.stringify({ ...pqcPublicJwk, pub: pqcPublicJwk.pub.slice(0, 24) + '...(truncated)' }));
console.log('Header:', Buffer.from(headerB64, 'base64url').toString('utf8'));
console.log('Signing input length (bytes):', signingInput.length, '  Signature length (bytes):', signature.length);

const key = await webcrypto.subtle.importKey(
  'jwk', pqcPublicJwk, { name: 'ML-DSA-65' }, false, ['verify'],
);
const valid = await webcrypto.subtle.verify({ name: 'ML-DSA-65' }, key, signature, signingInput);

const payload = JSON.parse(Buffer.from(payloadB64, 'base64url').toString('utf8'));
console.log('VERIFICATION RESULT:', JSON.stringify({
  valid,
  reason: valid ? 'ML-DSA-65 verified' : 'ML-DSA-65 signature INVALID',
  hasClassicComponent: false,
  payloadTopLevelKeys: Object.keys(payload),
}, null, 2));
