// Decision 9 (thesis/results/v4/DECISIONS.md): accepts client-signed
// hybrid client_assertion / PAR request objects (client -> AS direction),
// closing the Decision 7 gap. Only client_one is handled -- the only
// client opin_flow.py drives in hybrid mode.
//
// The client signs these with an ordinary `alg: "PS256"` header from the
// start (see hybridVerification.js's truncateIfHybrid() for why this
// direction can't use the combined alg header the AS/RS's own outbound
// artifacts use); this module supplies client_one's own classical and
// ML-DSA-65 public keys -- read from static files, not oidc-provider's
// client registry, since only the classical key is registered there
// (unchanged from classic/pqc mode) and oidc-provider has no notion of a
// second, PQC key for a client at all.
import { readFileSync } from 'node:fs';
import { truncateIfHybrid } from './hybridVerification.js';

const CLASSIC_JWKS_PATH = '/certs/client_one_pub.jwks';
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
        const result = await truncateIfHybrid(value, classicPublicJwk, pqcPublicJwk);
        if (result.truncated) {
          parsed[field] = result.truncated;
        }
        // Not hybrid-shaped, or hybrid verification failed: leave the
        // field exactly as received. A genuinely invalid assertion still
        // gets rejected -- just by oidc-provider's own normal alg-
        // whitelist/signature check, with its own standard error, rather
        // than by this middleware pre-emptively guessing at intent.
      }
    }

    ctx.request.body = parsed;
  }
  await next();
}
