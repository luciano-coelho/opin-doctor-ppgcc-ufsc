// Derives the RS's own PQC-profile JWKS entry directly from pqc.json,
// mirroring ResponseSigningService.java's loadMlDsa65Signer().publicJwk()
// exactly (kty AKP, alg ML-DSA-65, use sig, kid copied verbatim from
// pqc.json, pub = base64url of the raw ML-DSA-65 public key extracted from
// the X.509 SPKI) -- used to prove the JWKS entry an RS /jwks endpoint
// would publish is the SAME key (same kid, same pub bytes) that produced
// the real signature verify_pqc_jwt.mjs already validated.
// Usage: node derive_pqc_jwks.mjs <path-to-pqc.json>
import { createPublicKey } from 'node:crypto';
import { readFileSync } from 'node:fs';

const [pqcJsonPath] = process.argv.slice(2);
const pqcJson = JSON.parse(readFileSync(pqcJsonPath, 'utf8'));

const spkiDer = Buffer.from(pqcJson.x509PublicKeyBase64, 'base64');
const rawJwk = createPublicKey({ key: spkiDer, format: 'der', type: 'spki' }).export({ format: 'jwk' });

const jwks = {
  keys: [
    {
      kty: 'AKP',
      alg: 'ML-DSA-65',
      use: 'sig',
      kid: pqcJson.kid,
      pub: rawJwk.pub || rawJwk.x,
    },
  ],
};

console.log(JSON.stringify(jwks, null, 2));
