// Verifies a real, captured client_assertion (private_key_jwt, the JWT the
// CLIENT signs to authenticate itself when calling POST /token or /request)
// -- the artifact the SAD's step 8 (token de acesso) actually describes:
// the access_token itself is opaque (see the note in
// thesis/docs/Cruzamento_SAD_vs_Experimentos.md), the real signature that
// authenticates the client lives here instead.
//
// classic: plain PS256 against client_one_pub.jwks's sig key.
// pqc: plain ML-DSA-65 against client_one_pqc_pub.jwks's sig key.
// hybrid: payload-extension (RS256 + `pqc` claim, Decision 13) via the
// project's OWN production verifier (payloadExtensionVerification.js, the
// exact function mock_as/utils/opin/clientHybridAuth.js calls on every real
// inbound client_assertion) against client_one_hybrid_pub.jwks +
// client_one_pqc_pub.jwks -- not a reimplementation.
//
// Must run inside the `auth` container (jose, ML-DSA-65 WebCrypto,
// payloadExtensionVerification.js all live there).
// Usage: node verify_client_assertion.mjs <classic|pqc|hybrid> <assertion-file>
import { createPublicKey, verify as cryptoVerify, constants, webcrypto } from 'node:crypto';
import { importJWK } from 'jose';
import { readFileSync } from 'node:fs';

const [profile, assertionPath] = process.argv.slice(2);
const jwt = readFileSync(assertionPath, 'utf8').trim();
const [headerB64, payloadB64, sigB64] = jwt.split('.');
const header = JSON.parse(Buffer.from(headerB64, 'base64url').toString('utf8'));
const payload = JSON.parse(Buffer.from(payloadB64, 'base64url').toString('utf8'));
console.log('Header:', JSON.stringify(header));
console.log('Payload (decoded, complete):', JSON.stringify(payload, null, 2));
console.log('Signature length (bytes):', Buffer.from(sigB64, 'base64url').length);

let result;
if (profile === 'classic') {
  const jwks = JSON.parse(readFileSync('/certs/client_one_pub.jwks', 'utf8'));
  const sigJwk = jwks.keys.find((k) => k.use === 'sig');
  const ok = cryptoVerify(
    'sha256',
    Buffer.from(`${headerB64}.${payloadB64}`, 'ascii'),
    { key: createPublicKey({ key: sigJwk, format: 'jwk' }), padding: constants.RSA_PKCS1_PSS_PADDING, saltLength: constants.RSA_PSS_SALTLEN_DIGEST },
    Buffer.from(sigB64, 'base64url'),
  );
  result = { valid: ok, reason: ok ? 'PS256 verified' : 'PS256 verification failed' };
} else if (profile === 'pqc') {
  const jwks = JSON.parse(readFileSync('/certs/client_one_pqc_pub.jwks', 'utf8'));
  const sigJwk = jwks.keys.find((k) => k.kty === 'AKP');
  const key = await importJWK({ kty: 'AKP', alg: 'ML-DSA-65', pub: sigJwk.pub }, 'ML-DSA-65');
  const ok = await webcrypto.subtle.verify({ name: 'ML-DSA-65' }, key, Buffer.from(sigB64, 'base64url'), Buffer.from(`${headerB64}.${payloadB64}`, 'ascii'));
  result = { valid: ok, reason: ok ? 'ML-DSA-65 verified' : 'ML-DSA-65 verification failed' };
} else if (profile === 'hybrid') {
  const { verifyPayloadExtension } = await import('/home/node/app/utils/opin/payloadExtensionVerification.js');
  const classicJwks = JSON.parse(readFileSync('/certs/client_one_hybrid_pub.jwks', 'utf8'));
  const pqcJwks = JSON.parse(readFileSync('/certs/client_one_pqc_pub.jwks', 'utf8'));
  const classicPublicJwk = classicJwks.keys.find((k) => k.kty === 'RSA' && k.use === 'sig');
  const pqcPublicJwk = pqcJwks.keys.find((k) => k.kty === 'AKP');
  result = await verifyPayloadExtension(jwt, classicPublicJwk, pqcPublicJwk);
} else {
  throw new Error(`unknown profile: ${profile}`);
}

console.log('VERIFICATION RESULT:', JSON.stringify(result, null, 2));
