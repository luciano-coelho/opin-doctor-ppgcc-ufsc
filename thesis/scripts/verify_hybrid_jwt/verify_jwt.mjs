// Verifies a real, captured payload-extension hybrid JWT (RS256 + ML-DSA-65)
// using the project's OWN production verifier
// (mock-service-os/mock_as/utils/opin/payloadExtensionVerification.js) --
// not a reimplementation, the exact function every sabatina in this thesis
// already relies on. Public key material is derived directly from the RS's
// own key-loading resource file (crypto-profiles/hybrid.json), the same
// computation insurance-server-lambdas's ResponseSigningService.java
// performs to answer /jwks -- used here because fetching the RS's live
// /jwks through the mTLS gateway returned 401 from a security filter this
// investigation did not chase down further (out of scope; the resource
// file is the exact source of truth backing that endpoint regardless).
//
// Must run where mock_as's own node_modules (jose, canonicalize) and
// payloadExtensionVerification.js are available -- i.e. inside the `auth`
// container. See thesis/results/v7/artifacts/hybrid/README.md, Section 2,
// for the exact `docker cp` + `docker exec` invocation.
//
// Usage: node verify_jwt.mjs <path-to-hybrid.json> <path-to-jwt-file>
import { createPublicKey } from 'node:crypto';
import { readFileSync } from 'node:fs';
import { verifyPayloadExtension } from '/home/node/app/utils/opin/payloadExtensionVerification.js';

const [hybridJsonPath, jwtPath] = process.argv.slice(2);
const hybridJson = JSON.parse(readFileSync(hybridJsonPath, 'utf8'));
const jwt = readFileSync(jwtPath, 'utf8').trim();

const classic = hybridJson.classicSigningKey;
const pqc = hybridJson.pqcSigningKey;

const classicPublicJwk = { kty: 'RSA', n: classic.n, e: classic.e, alg: 'RS256' };

const spkiDer = Buffer.from(pqc.x509PublicKeyBase64, 'base64');
const pqcRawJwk = createPublicKey({ key: spkiDer, format: 'der', type: 'spki' }).export({ format: 'jwk' });
const pqcPublicJwk = {
  kty: 'AKP',
  alg: 'ML-DSA-65',
  use: 'sig',
  kid: pqc.kid,
  pub: pqcRawJwk.pub || pqcRawJwk.x,
};

console.log('Classic (RS256) public JWK, derived from hybrid.json:', JSON.stringify(classicPublicJwk));
console.log('ML-DSA-65 public JWK, derived from hybrid.json via X.509 SPKI parsing:', JSON.stringify({ ...pqcPublicJwk, pub: pqcPublicJwk.pub.slice(0, 24) + '...(truncated)' }));

const result = await verifyPayloadExtension(jwt, classicPublicJwk, pqcPublicJwk);
console.log('VERIFICATION RESULT:', JSON.stringify(result, null, 2));
