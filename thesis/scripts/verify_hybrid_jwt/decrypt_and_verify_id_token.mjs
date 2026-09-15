// Decrypts a real, captured id_token (a JWE, per Decision 10 --
// idTokenExternalSigningKey.js's own comment: "by then the id_token is
// already a 5-segment JWE") using client_one's OWN real RSA-OAEP private
// encryption key (mock-service-os/certs/client_one.jwks -- id_token
// encryption is TO the client, confidentiality from the AS to the relying
// party, not encrypted with the AS's own key; confirmed by the JWE header's
// kid matching client_one.jwks's enc entry exactly, not AS_ENC_JWK's), then
// verifies the inner JWS's signature according to the
// profile: PS256 (classic), ML-DSA-65 (pqc), or Strong Nesting PS256+ML-DSA-65
// (hybrid, reusing the project's own production verifyHybrid() from
// hybridVerification.js -- not a reimplementation).
//
// This is deliberately the SAME id_token artifact the SAD's step 7
// encryption dependency describes: the signature inside is migrated per
// profile, but the JWE wrapping it is RSA-OAEP in every profile, including
// pqc -- there is no post-quantum JOSE/COSE encryption standard to migrate
// to (see thesis/docs/Cruzamento_SAD_vs_Experimentos.md).
//
// Must run inside the `auth` container (jose + ML-DSA-65 WebCrypto support).
// Usage: node decrypt_and_verify_id_token.mjs <classic|pqc|hybrid> <id_token-file>
import { createPrivateKey, createPublicKey, verify as cryptoVerify, constants, webcrypto } from 'node:crypto';
import { compactDecrypt, importJWK } from 'jose';
import { readFileSync } from 'node:fs';

const [profile, idTokenPath] = process.argv.slice(2);
const jwe = readFileSync(idTokenPath, 'utf8').trim();

// pqc registers its own encryption key (client_one_pqc.jwks); classic and
// hybrid share the same one (client_one.jwks) -- confirmed by the JWE
// header's kid: pqc's differs, hybrid's is byte-identical to classic's,
// consistent with hybrid reusing classic's RSA identity everywhere else
// (Seção 2 dos READMEs de artifacts/).
const jwksFile = { classic: 'client_one.jwks', pqc: 'client_one_pqc.jwks', hybrid: 'client_one.jwks' }[profile];
const clientOneJwks = JSON.parse(readFileSync(`/home/node/app/${jwksFile}`, 'utf8'));
const clientEncJwk = clientOneJwks.keys.find((k) => k.use === 'enc');
const encPrivateKey = createPrivateKey({ key: clientEncJwk, format: 'jwk' });

console.log(`id_token: ${jwe.length} chars, ${jwe.split('.').length} segments (JWE compact serialization)`);
const jweHeader = JSON.parse(Buffer.from(jwe.split('.')[0], 'base64url').toString('utf8'));
console.log('JWE protected header:', JSON.stringify(jweHeader));

const { plaintext } = await compactDecrypt(jwe, encPrivateKey);
const innerJws = Buffer.from(plaintext).toString('utf8');
console.log(`Decrypted inner JWS: ${innerJws.length} chars, ${innerJws.split('.').length} segments`);

const [headerB64, payloadB64, sigB64] = innerJws.split('.');
const innerHeader = JSON.parse(Buffer.from(headerB64, 'base64url').toString('utf8'));
const payload = JSON.parse(Buffer.from(payloadB64, 'base64url').toString('utf8'));
console.log('Inner JWS header:', JSON.stringify(innerHeader));
console.log('Inner JWS payload (decoded, complete):', JSON.stringify(payload, null, 2));
const sigBytes = Buffer.from(sigB64, 'base64url');
console.log('Inner JWS signature length (bytes):', sigBytes.length);

let result;
if (profile === 'classic') {
  const classicProfile = JSON.parse(readFileSync('/home/node/app/classic.json', 'utf8'));
  const pubJwk = { kty: 'RSA', n: classicProfile.signingKey.n, e: classicProfile.signingKey.e };
  const ok = cryptoVerify(
    'sha256',
    Buffer.from(`${headerB64}.${payloadB64}`, 'ascii'),
    { key: createPublicKey({ key: pubJwk, format: 'jwk' }), padding: constants.RSA_PKCS1_PSS_PADDING, saltLength: constants.RSA_PSS_SALTLEN_DIGEST },
    sigBytes,
  );
  result = { valid: ok, reason: ok ? 'PS256 verified' : 'PS256 verification failed' };
} else if (profile === 'pqc') {
  const pqcProfile = JSON.parse(readFileSync('/home/node/app/pqc.json', 'utf8'));
  const pubJwk = { kty: 'AKP', alg: 'ML-DSA-65', pub: pqcProfile.signingKey.pub };
  const key = await importJWK(pubJwk, 'ML-DSA-65');
  const ok = await webcrypto.subtle.verify({ name: 'ML-DSA-65' }, key, sigBytes, Buffer.from(`${headerB64}.${payloadB64}`, 'ascii'));
  result = { valid: ok, reason: ok ? 'ML-DSA-65 verified' : 'ML-DSA-65 verification failed' };
} else if (profile === 'hybrid') {
  const { verifyHybrid } = await import('/home/node/app/utils/opin/hybridVerification.js');
  const hybridProfile = JSON.parse(readFileSync('/home/node/app/hybrid_as.json', 'utf8'));
  const classicPublicJwk = { kty: 'RSA', n: hybridProfile.classicSigningKey.n, e: hybridProfile.classicSigningKey.e };
  const pqcPublicJwk = { kty: 'AKP', alg: 'ML-DSA-65', pub: hybridProfile.pqcSigningKey.pub };
  result = await verifyHybrid(innerJws, classicPublicJwk, pqcPublicJwk);
} else {
  throw new Error(`unknown profile: ${profile}`);
}

console.log('VERIFICATION RESULT:', JSON.stringify(result, null, 2));
