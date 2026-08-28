// Decision 9 (thesis/results/v4/DECISIONS.md) originally, now Decision 13:
// accepts client-signed hybrid client_assertion / PAR request objects
// (client -> AS direction). Only client_one is handled -- the only client
// opin_flow.py drives in hybrid mode.
//
// As of Decision 13, the client signs these via the payload-extension
// scheme (RS256 last, over claims carrying a `pqc` extension -- see
// payloadExtensionVerification.js), an entirely ordinary RS256 JWT that
// oidc-provider's own native verification already accepts unmodified --
// unlike Decision 9's Strong Nesting, there is nothing to truncate here
// anymore. This middleware's only remaining job is the ADDITIONAL check
// oidc-provider has no way to perform on its own: if `pqc` is present but
// its ML-DSA-65 signature doesn't verify, reject the request outright
// (oidc-provider's own RS256-only check would otherwise still accept it,
// silently downgrading the AND gate to an OR gate). This module supplies
// client_one's own classical and ML-DSA-65 public keys -- read from
// static files, not oidc-provider's client registry, since only the
// classical key is registered there (unchanged from classic/pqc mode) and
// oidc-provider has no notion of a second, PQC key for a client at all.
import { readFileSync } from 'node:fs';
import { verifyPayloadExtension } from './payloadExtensionVerification.js';

// client_one_hybrid_pub.jwks, not client_one_pub.jwks -- same RSA key/kid,
// but "alg": "RS256" instead of "PS256" (see mongo-seed/start.sh's own
// comment on this same file for why: a real JWKS consumer doing ordinary
// kid+alg discovery needs the published alg to match what's actually in
// the token header). Doesn't change what THIS module verifies with (only
// n/e are used, alg is never inspected here), but keeps every place that
// reads client_one's hybrid-mode public key pointed at the one file
// that's actually correct to publish.
const CLASSIC_JWKS_PATH = '/certs/client_one_hybrid_pub.jwks';
const PQC_JWKS_PATH = '/certs/client_one_pqc_pub.jwks';

const classicJwks = JSON.parse(readFileSync(CLASSIC_JWKS_PATH, 'utf8'));
const pqcJwks = JSON.parse(readFileSync(PQC_JWKS_PATH, 'utf8'));

const classicPublicJwk = classicJwks.keys.find((k) => k.kty === 'RSA' && k.use === 'sig');
const pqcPublicJwk = pqcJwks.keys.find((k) => k.kty === 'AKP');
if (!classicPublicJwk) {
  throw new Error(`clientHybridAuth: no RSA sig key found in ${CLASSIC_JWKS_PATH}`);
}
if (!pqcPublicJwk) {
  throw new Error(`clientHybridAuth: no AKP key found in ${PQC_JWKS_PATH}`);
}

const COMPACT_JWS_RE = /^[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+$/;

function readRawBody(req) {
  return new Promise((resolve, reject) => {
    let data = '';
    req.setEncoding('utf8');
    req.on('data', (chunk) => {
      data += chunk;
    });
    req.on('end', () => resolve(data));
    req.on('error', reject);
  });
}

// Inbound Koa middleware, registered via provider.use() before
// app.use(provider.callback()) -- same registration pattern as
// express.js's existing OUTBOUND rehybridization middleware, but this one
// must run BEFORE await next() (it needs to touch the request, not the
// response). Only acts on POST /token and POST /request
// (application/x-www-form-urlencoded) -- the only two endpoints that ever
// carry a client_assertion or a request object. Consuming ctx.req here
// makes it non-readable, which is exactly the fallback path
// oidc-provider's own body-parsing (lib/shared/selective_body.js) is
// coded to handle: it reads ctx.req.body || ctx.request.body instead of
// re-reading the (now-consumed) stream itself.
export async function inboundHybridClientAuthMiddleware(ctx, next) {
  const isRelevantEndpoint = ctx.method === 'POST' && (ctx.path === '/token' || ctx.path === '/request');
  const contentType = ctx.get('content-type') || '';
  if (isRelevantEndpoint && contentType.includes('application/x-www-form-urlencoded')) {
    const raw = await readRawBody(ctx.req);
    const params = new URLSearchParams(raw);
    const parsed = Object.fromEntries(params.entries());

    for (const field of ['client_assertion', 'request']) {
      const value = parsed[field];
      if (typeof value === 'string' && COMPACT_JWS_RE.test(value)) {
        const result = await verifyPayloadExtension(value, classicPublicJwk, pqcPublicJwk);
        // hybridShaped is only ever set once RS256 has already verified
        // (see payloadExtensionVerification.js) -- so this specifically
        // catches "RS256 is valid, a pqc claim is present, but it doesn't
        // verify", the one case oidc-provider's own subsequent RS256-only
        // check cannot catch on its own. No pqc claim at all, or RS256
        // itself invalid, both fall through unchanged: oidc-provider's
        // normal alg/signature check already does the right thing either
        // way (accept a legitimately classical-only assertion, or reject
        // an invalid one with its own standard error).
        if (result.hybridShaped && !result.valid) {
          ctx.status = 400;
          ctx.body = {
            error: 'invalid_request',
            error_description: `hybrid AND-gate failed for ${field}: ${result.reason}`,
          };
          return;
        }
      }
    }

    ctx.request.body = parsed;
  }
  await next();
}
