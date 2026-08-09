// Signs a single JWT with ML-DSA-65 and prints the compact JWS to stdout.
//
// Exists because neither PyJWT nor `cryptography` (even its bundled,
// newer-than-system OpenSSL -- see thesis/scripts/README.md's "Virtual
// environment" section) expose ML-DSA signing through their Python APIs.
// `jose` v6 delegates to Node's native node:crypto instead (ML-DSA support
// landed in Node >=24.7 / OpenSSL >=3.5), the same mechanism mock_as
// itself uses to sign AS-issued tokens -- this container gives
// opin_flow.py (running on a host whose local Node is 22.x, also too old)
// the same capability for client_one's own ML-DSA-65 signatures
// (client_assertion, PAR request object) in pqc mode.
//
// stdin: {"jwk": {...private AKP JWK, incl. "priv"...}, "headers": {...},
//          "claims": {...}}
// stdout: the compact JWS string, nothing else.
import { importJWK, SignJWT } from 'jose';

const input = JSON.parse(await new Promise((resolve, reject) => {
  let data = '';
  process.stdin.on('data', (chunk) => { data += chunk; });
  process.stdin.on('end', () => resolve(data));
  process.stdin.on('error', reject);
}));

const { jwk, headers, claims } = input;
const key = await importJWK(jwk, jwk.alg);

const jwt = await new SignJWT(claims)
  .setProtectedHeader(headers)
  .sign(key);

process.stdout.write(jwt);
