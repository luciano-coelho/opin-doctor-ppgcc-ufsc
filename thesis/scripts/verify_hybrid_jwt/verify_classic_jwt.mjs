// Verifies a real, captured PS256 JWT (Classic profile) against the RS's
// real public key, derived from the same resource file
// (crypto-profiles/classic.json) ResponseSigningService.java loads to sign.
// Confirms the signature is genuinely valid (not just correctly shaped) and
// that no `pqc` claim is present -- the negative control for the hybrid/pqc
// artifacts in this same folder tree.
//
// Usage: node verify_classic_jwt.mjs <path-to-classic.json> <path-to-jwt-file>
import { createPublicKey, verify as cryptoVerify, constants } from 'node:crypto';
import { readFileSync } from 'node:fs';

const [classicJsonPath, jwtPath] = process.argv.slice(2);
const classicJson = JSON.parse(readFileSync(classicJsonPath, 'utf8'));
const jwt = readFileSync(jwtPath, 'utf8').trim();

const publicJwk = { kty: 'RSA', n: classicJson.n, e: classicJson.e };
console.log('Classic (PS256) public JWK, derived from classic.json:', JSON.stringify(publicJwk));

const parts = jwt.split('.');
const message = Buffer.from(`${parts[0]}.${parts[1]}`, 'ascii');
const sig = Buffer.from(parts[2], 'base64url');

const ok = cryptoVerify(
  'sha256',
  message,
  {
    key: createPublicKey({ key: publicJwk, format: 'jwk' }),
    padding: constants.RSA_PKCS1_PSS_PADDING,
    saltLength: 32,
  },
  sig,
);

const payload = JSON.parse(Buffer.from(parts[1], 'base64url').toString('utf8'));
const hasPqc = Object.prototype.hasOwnProperty.call(payload, 'pqc');

console.log('VERIFICATION RESULT:', JSON.stringify({
  valid: ok,
  reason: ok ? 'PS256 verified' : 'PS256 verification failed',
  hasPqcClaim: hasPqc,
}, null, 2));
