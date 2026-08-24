// Signs a single JWT with ML-DSA-65, or verifies a raw ML-DSA-65 signature
// over arbitrary bytes, and prints the result to stdout.
//
// Exists because neither PyJWT nor `cryptography` (even its bundled,
// newer-than-system OpenSSL -- see thesis/scripts/README.md's "Virtual
// environment" section) expose ML-DSA signing/verification through their
// Python APIs. `jose` v6 delegates to Node's native node:crypto instead
// (ML-DSA support landed in Node >=24.7 / OpenSSL >=3.5), the same
// mechanism mock_as itself uses to sign/verify AS-issued tokens -- this
// container gives opin_flow.py (running on a host whose local Node is
// 22.x, also too old) the same capability for client_one's own ML-DSA-65
// signatures (client_assertion, PAR request object) in pqc mode, and for
// verifying the RS's hybrid-signed responses in hybrid mode (Etapa 4).
//
// Three input shapes on stdin, dispatched on which fields are present:
//   - {"jwk": {...private AKP JWK, incl. "priv"...}, "headers": {...},
//      "claims": {...}}                    -> sign a full JWT (unchanged
//                                              behavior, existing callers).
//      stdout: the compact JWS string.
//   - {"jwk": {...private AKP JWK, incl. "priv"...}, "message_b64": "..."}
//      (no "signature_b64")                -> sign raw, arbitrary bytes
//                                              directly (NOT a JWS payload
//                                              -- same raw-WebCrypto
//                                              reasoning as the verify
//                                              mode below, needed here so
//                                              opin_flow.py can produce
//                                              sigma2 = ML-DSA-65_sign(
//                                              message||sigma1) for Decision
//                                              9's client-side hybrid
//                                              signing).
//      stdout: base64 (not base64url) raw signature bytes.
//   - {"jwk": {...public AKP JWK, "pub" only...}, "message_b64": "...",
//      "signature_b64": "..."}              -> verify a raw ML-DSA-65
//                                              signature over base64-
//                                              encoded arbitrary bytes
//                                              (NOT a JWS payload -- see
//                                              hybridVerification.js for
//                                              why this has to be a raw
//                                              WebCrypto verify, not
//                                              jose's CompactVerify).
//      stdout: "true" or "false".
import { webcrypto } from 'node:crypto';
import { importJWK, SignJWT } from 'jose';

const input = JSON.parse(await new Promise((resolve, reject) => {
  let data = '';
  process.stdin.on('data', (chunk) => { data += chunk; });
  process.stdin.on('end', () => resolve(data));
  process.stdin.on('error', reject);
}));

if (input.message_b64 !== undefined && input.signature_b64 === undefined) {
  const key = await importJWK(input.jwk, input.jwk.alg || 'ML-DSA-65');
  const message = Buffer.from(input.message_b64, 'base64');
  const signature = await webcrypto.subtle.sign({ name: 'ML-DSA-65' }, key, message);
  process.stdout.write(Buffer.from(signature).toString('base64'));
} else if (input.message_b64 !== undefined) {
  const key = await importJWK(input.jwk, input.jwk.alg || 'ML-DSA-65');
  const message = Buffer.from(input.message_b64, 'base64');
  const signature = Buffer.from(input.signature_b64, 'base64');
  const valid = await webcrypto.subtle.verify({ name: 'ML-DSA-65' }, key, signature, message);
  process.stdout.write(valid ? 'true' : 'false');
} else {
  const { jwk, headers, claims } = input;
  const key = await importJWK(jwk, jwk.alg);

  const jwt = await new SignJWT(claims)
    .setProtectedHeader(headers)
    .sign(key);

  process.stdout.write(jwt);
}
