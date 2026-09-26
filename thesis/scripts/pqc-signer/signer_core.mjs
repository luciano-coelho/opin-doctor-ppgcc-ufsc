// The actual ML-DSA-65 sign/verify dispatch, shared by both entry points:
// sign.mjs (one-shot CLI, `docker run --rm -i`, unchanged since v2 --
// used by hybrid_verify.py and the one-off artifacts/ capture scripts,
// where a fresh container per call costs nothing because there's only
// one or a handful of calls) and server.mjs (a persistent HTTP service,
// used by opin_flow.py's hot statistical loop -- 8 calls per full flow
// execution, where spawning a fresh container per call was the ~94%
// contributor to the PQC/Híbrido latency delta over Clássico that this
// split exists to fix).
//
// Extracted verbatim from what was sign.mjs's own body -- same three
// input shapes, same three output shapes, same algorithm.
// Nothing about *how* a signature is produced changes here, only *how
// often a process gets spawned to produce one* (that split lives in
// sign.mjs vs. server.mjs, not in this file).
import { webcrypto } from 'node:crypto';
import { importJWK, SignJWT } from 'jose';

export async function handleRequest(input) {
  if (input.message_b64 !== undefined && input.signature_b64 === undefined) {
    const key = await importJWK(input.jwk, input.jwk.alg || 'ML-DSA-65');
    const message = Buffer.from(input.message_b64, 'base64');
    const signature = await webcrypto.subtle.sign({ name: 'ML-DSA-65' }, key, message);
    return Buffer.from(signature).toString('base64');
  }
  if (input.message_b64 !== undefined) {
    const key = await importJWK(input.jwk, input.jwk.alg || 'ML-DSA-65');
    const message = Buffer.from(input.message_b64, 'base64');
    const signature = Buffer.from(input.signature_b64, 'base64');
    const valid = await webcrypto.subtle.verify({ name: 'ML-DSA-65' }, key, signature, message);
    return valid ? 'true' : 'false';
  }
  const { jwk, headers, claims } = input;
  const key = await importJWK(jwk, jwk.alg);
  return await new SignJWT(claims).setProtectedHeader(headers).sign(key);
}
