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
//
// verify_jwt/decrypt_and_verify_jwt (thesis/results/v8/DECISIONS.md,
// "fluxo completo" turn): opin_flow.py did not cryptographically verify
// ANY profile's signatures before this -- added here, not in Python,
// specifically so classic/pqc/hybrid verification all go through the
// SAME code path (this dispatch), the SAME call shape (one JSON POST),
// and the SAME key source (the AS/RS's own published JWKS) -- the
// architecture is then identical across profiles, so a measured timing
// difference reflects the algorithm, not "in-process Python" vs
// "separate Node process". classic's PS256 verification could run
// in-process in Python just fine; it is routed through this same
// service anyway, for that comparability, not because it needs to be.
import { webcrypto, createPublicKey, verify as cryptoVerify, constants } from 'node:crypto';
import { importJWK, SignJWT, jwtVerify, compactDecrypt } from 'jose';
import canonicalize from 'canonicalize';

// Hybrid artifacts use one of TWO independently-evolved dual-signature
// schemes (thesis/results/v4/DECISIONS.md, Decision 13): the AS's own
// id_token/JARM are Strong Nesting (a concatenated sigma1||sigma2), while
// the RS's own response bodies (a separate Java codebase) use payload
// extension (an ordinary RS256 JWS with ML-DSA-65 embedded as an extra
// `pqc` claim). See isStrongNestingShaped() below for why signature
// LENGTH, not header.alg, is what actually distinguishes them here.

// Strong Nesting verification (PS256 + ML-DSA-65) for SERVER-issued
// (AS/RS) artifacts -- mirrors mock-service-os/mock_as/utils/opin/
// hybridVerification.js's own verifyHybrid() exactly (same split point,
// same AND-gate), duplicated here rather than imported because the two
// live in separate, independently-deployed Node packages (same
// precedent as thesis/scripts/hybrid_verify.py's own Python mirror of
// that file). classicSigBytes is derived from the VERIFYING key's own
// modulus (not hardcoded to 256) -- hybridVerification.js's own fix for
// the same reason: correct regardless of which RSA key size actually
// signed a given artifact.
async function verifyStrongNesting(compactJwt, classicJwk, pqcJwk) {
  const parts = compactJwt.split('.');
  if (parts.length !== 3) {
    return { valid: false, reason: 'not a 3-segment compact JWS' };
  }
  const [headerB64, payloadB64, sigB64] = parts;
  const message = Buffer.from(`${headerB64}.${payloadB64}`, 'ascii');
  const classicSigBytes = Buffer.from(classicJwk.n, 'base64url').length;

  let combined;
  try {
    combined = Buffer.from(sigB64, 'base64url');
  } catch {
    return { valid: false, reason: 'signature segment is not valid base64url' };
  }
  if (combined.length <= classicSigBytes) {
    return { valid: false, reason: `combined signature too short (${combined.length} bytes)` };
  }
  const sigma1 = combined.subarray(0, classicSigBytes);
  const sigma2 = combined.subarray(classicSigBytes);

  const classicOk = cryptoVerify(
    'sha256', message,
    { key: createPublicKey({ key: classicJwk, format: 'jwk' }), padding: constants.RSA_PKCS1_PSS_PADDING, saltLength: constants.RSA_PSS_SALTLEN_DIGEST },
    sigma1,
  );
  if (!classicOk) {
    return { valid: false, reason: 'sigma1 (PS256) verification failed' };
  }

  const pqcKey = await importJWK(pqcJwk, 'ML-DSA-65');
  const messagePlusSigma1 = Buffer.concat([message, sigma1]);
  const pqcOk = await webcrypto.subtle.verify({ name: 'ML-DSA-65' }, pqcKey, sigma2, messagePlusSigma1);
  if (!pqcOk) {
    return { valid: false, reason: 'sigma2 (ML-DSA-65) verification failed' };
  }

  const claims = JSON.parse(Buffer.from(payloadB64, 'base64url').toString('utf8'));
  return { valid: true, reason: 'both sigma1 and sigma2 verified', claims };
}

// Payload-extension verification (RS256 + ML-DSA-65 via a `pqc` claim) --
// mirrors mock-service-os/mock_as/utils/opin/payloadExtensionVerification.js's
// own verifyPayloadExtension() exactly (same RFC 8785/JCS canonicalization,
// same claim-stripping order, same AND-gate), duplicated here for the same
// separate-deployable-package reason as verifyStrongNesting() above. Used
// for the RS's own hybrid-signed response bodies (insurance-server-lambdas'
// ResponseSigningService.java implements this scheme independently of the
// AS's rehybridizeJwt(), per Decision 13 -- "every hybrid artifact EXCEPT
// the id_token and JARM").
async function verifyPayloadExtension(compactJws, classicJwk, pqcJwk) {
  const parts = compactJws.split('.');
  if (parts.length !== 3) {
    return { valid: false, reason: `not a 3-segment compact JWS (${parts.length})` };
  }
  const [headerB64, payloadB64, sigB64] = parts;
  const message = Buffer.from(`${headerB64}.${payloadB64}`, 'ascii');

  let sig;
  try {
    sig = Buffer.from(sigB64, 'base64url');
  } catch {
    return { valid: false, reason: 'signature segment is not valid base64url' };
  }

  const rs256Ok = cryptoVerify(
    'sha256', message,
    { key: createPublicKey({ key: classicJwk, format: 'jwk' }), padding: constants.RSA_PKCS1_PADDING },
    sig,
  );
  if (!rs256Ok) {
    return { valid: false, reason: 'RS256 verification failed' };
  }

  let payload;
  try {
    payload = JSON.parse(Buffer.from(payloadB64, 'base64url').toString('utf8'));
  } catch {
    return { valid: false, reason: 'payload is not valid JSON' };
  }

  const pqcClaim = payload.pqc;
  if (!pqcClaim || typeof pqcClaim.signature !== 'string') {
    return { valid: false, reason: 'missing payload.pqc.signature -- not hybrid-shaped' };
  }

  let pqcSig;
  try {
    pqcSig = Buffer.from(pqcClaim.signature, 'base64url');
  } catch {
    return { valid: false, reason: 'payload.pqc.signature is not valid base64url' };
  }

  const { pqc: _pqc, ...claimsWithoutPqc } = payload;
  const canonicalBytes = Buffer.from(canonicalize(claimsWithoutPqc), 'utf8');

  const pqcKey = await importJWK(pqcJwk, 'ML-DSA-65');
  const pqcOk = await webcrypto.subtle.verify({ name: 'ML-DSA-65' }, pqcKey, pqcSig, canonicalBytes);
  if (!pqcOk) {
    return { valid: false, reason: 'ML-DSA-65 (payload.pqc.signature) verification failed' };
  }

  return { valid: true, reason: 'both RS256 and ML-DSA-65 verified', claims: payload };
}

// Single-key verification (classic PS256 or pure pqc ML-DSA-65) -- one
// jose call covers both, since jose's own algorithm registry is what
// signer_core.mjs's own SignJWT branch above already relies on for
// ML-DSA-65 signing; verification reuses the identical registry. The
// expected algorithm is passed explicitly by the CALLER (never inferred
// from the token's own header) specifically so a token whose header
// claims a different algorithm than the caller expected is rejected,
// not silently accepted under whatever alg it happens to name.
async function verifySingleKey(compactJwt, jwk, expectedAlg) {
  try {
    const key = await importJWK(jwk, expectedAlg);
    const { payload } = await jwtVerify(compactJwt, key, { algorithms: [expectedAlg] });
    return { valid: true, reason: `${expectedAlg} verified`, claims: payload };
  } catch (err) {
    return { valid: false, reason: `${expectedAlg} verification failed: ${err.message}` };
  }
}

// id_token's own header.alg is NOT a reliable signal (mock-service-os/
// mock_as/utils/opin/idTokenExternalSigningKey.js: oidc-provider only
// accepts "PS256" into its own alg table, so the id_token's header says
// "PS256" even when its signature is genuinely Strong Nesting underneath
// -- the same header-looks-ordinary asymmetry already documented for
// client_assertion/the PAR request object, Decision 9). JARM, signed via
// the ordinary outbound rehybridizeJwt() middleware, DOES get its header
// rewritten to STRONG_NESTING_ALG for real. Dispatching on signature
// LENGTH instead (mirrors hybridVerification.js's own truncateIfHybrid()
// detection) works for both: Strong Nesting's sigma1||sigma2 blob is
// always longer than one classical signature's worth of bytes; Payload
// Extension's RS256 signature is always ordinary-length, decodable
// separately as JSON with its own `pqc` claim confirming which case
// applies before either verifier is run for real.
// Returns null (not a boolean) when classicJwk isn't a usable RSA JWK at
// all (e.g. a key-confusion attempt handing this an AKP/ML-DSA JWK in the
// classic_jwk slot) -- a real, tested case (test_hybrid_scheme_confusion_
// rejected), not just a defensive guard: this must fail CLOSED (caught by
// the caller, treated as "not Strong-Nesting-shaped", which then runs
// verifyPayloadExtension() -- itself guaranteed to reject a key of the
// wrong kty too, since createPublicKey({kty:'AKP',...}, format:'jwk')
// throws rather than silently producing a usable RSA key), never crash
// the request with an uncaught TypeError.
function isStrongNestingShaped(compactJwt, classicJwk) {
  const parts = compactJwt.split('.');
  if (parts.length !== 3) return false;
  let sigLen;
  try {
    sigLen = Buffer.from(parts[2], 'base64url').length;
  } catch {
    return false;
  }
  if (!classicJwk || typeof classicJwk.n !== 'string') return null;
  const classicSigBytes = Buffer.from(classicJwk.n, 'base64url').length;
  return sigLen > classicSigBytes;
}

async function verifyJwt(input) {
  const { verify_jwt: token, classic_jwk: classicJwk, pqc_jwk: pqcJwk, expected_alg: expectedAlg } = input;
  if (classicJwk && pqcJwk) {
    const shaped = isStrongNestingShaped(token, classicJwk);
    if (shaped === null) {
      return { valid: false, reason: 'classic_jwk is not a usable RSA key (missing or non-string "n")' };
    }
    if (shaped) {
      return verifyStrongNesting(token, classicJwk, pqcJwk);
    }
    try {
      return await verifyPayloadExtension(token, classicJwk, pqcJwk);
    } catch (err) {
      return { valid: false, reason: `payload-extension verification failed: ${err.message}` };
    }
  }
  if (pqcJwk) {
    return verifySingleKey(token, pqcJwk, expectedAlg || 'ML-DSA-65');
  }
  return verifySingleKey(token, classicJwk, expectedAlg || 'PS256');
}

// id_token only (thesis/results/v8/DECISIONS.md): client_one is
// registered with id_token_encrypted_response_alg=RSA-OAEP/enc=A256GCM
// (mock-service-os/mock_as/mongo-seed/init_clients.json) -- sign-then-
// encrypt, identically across all 3 profiles (the encryption key
// exchange itself is NOT part of this project's PQC migration scope;
// only the INNER signature varies by profile). jose.compactDecrypt()
// does the full JWE unwrap (RSA-OAEP key unwrap + A256GCM content
// decrypt); the resulting plaintext is itself a compact JWS string,
// verified the same way as every other artifact right after.
async function decryptAndVerifyJwt(input) {
  const { decrypt_and_verify_jwt: jwe, enc_jwk: encJwk, classic_jwk: classicJwk, pqc_jwk: pqcJwk, expected_alg: expectedAlg } = input;
  let plaintext;
  try {
    const encKey = await importJWK(encJwk, encJwk.alg || 'RSA-OAEP');
    const result = await compactDecrypt(jwe, encKey);
    plaintext = Buffer.from(result.plaintext).toString('utf8');
  } catch (err) {
    return { valid: false, reason: `JWE decryption failed: ${err.message}` };
  }
  return verifyJwt({ verify_jwt: plaintext, classic_jwk: classicJwk, pqc_jwk: pqcJwk, expected_alg: expectedAlg });
}

export async function handleRequest(input) {
  // Both verify paths always resolve to a clean {valid, reason, claims?}
  // JSON response, even on a malformed/wrong-shaped key (a real, tested
  // case -- key-confusion attempts must fail closed, not crash the
  // request into a 500 the Python side would then see as an unrelated
  // RuntimeError instead of the actual SignatureVerificationError it is).
  if (input.verify_jwt !== undefined) {
    try {
      return JSON.stringify(await verifyJwt(input));
    } catch (err) {
      return JSON.stringify({ valid: false, reason: `verification crashed: ${err.message}` });
    }
  }
  if (input.decrypt_and_verify_jwt !== undefined) {
    try {
      return JSON.stringify(await decryptAndVerifyJwt(input));
    } catch (err) {
      return JSON.stringify({ valid: false, reason: `verification crashed: ${err.message}` });
    }
  }
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
