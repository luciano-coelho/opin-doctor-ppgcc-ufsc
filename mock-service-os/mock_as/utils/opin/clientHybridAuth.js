// Decision 9 (thesis/results/v4/DECISIONS.md) originally, now Decision 13:
// accepts client-signed hybrid client_assertion / PAR request objects
// (client -> AS direction). Only client_one is handled -- the only client
// opin_flow.py drives in hybrid mode.
//
// As of Decision 13, the client signs these via the payload-extension
// scheme (PS256 last, over claims carrying a `pqc` extension -- see
// payloadExtensionVerification.js), an entirely ordinary PS256 JWT that
// oidc-provider's own native verification already accepts unmodified --
// unlike Decision 9's Strong Nesting, there is nothing to truncate here
// anymore. PS256 since 2026-11-10 (was RS256 before -- see the dated
// note on Decision 13, thesis/results/v4/DECISIONS.md). This middleware's
// job is the ADDITIONAL check oidc-provider has no way to perform on its
// own: reject the request outright if `pqc` is either present-but-invalid
// or absent (oidc-provider's own PS256-only check would otherwise still
// accept a classical-only assertion, silently downgrading the AND gate to
// an OR gate -- Decision 115, 2026-11-10: the original Decision 13 text
// already named "invalid or absent" as the same risk, but the code only
// ever implemented the "invalid" half until now). This module supplies
// client_one's own classical and ML-DSA-65 public keys -- read from
// static files, not oidc-provider's client registry, since only the
// classical key is registered there (unchanged from classic/pqc mode) and
// oidc-provider has no notion of a second, PQC key for a client at all.
import { readFileSync } from 'node:fs';
import { verifyPayloadExtension } from './payloadExtensionVerification.js';

// client_one_hybrid_pub.jwks, not client_one_pub.jwks -- same RSA key/kid
// (see mongo-seed/start.sh's own comment on this same file for why: a real
// JWKS consumer doing ordinary kid+alg discovery needs the published alg
// to match what's actually in the token header). Since 2026-11-10 both
// files publish "alg": "PS256" -- identical content, in fact -- because
// the payload-extension scheme no longer uses a different alg than
// classic mode (was "alg": "RS256" here, distinct from classic's "PS256",
// through 2026-11-09; see the dated note on Decision 13). Doesn't change
// what THIS module verifies with (only n/e are used, alg is never
// inspected here), but keeps every place that reads client_one's
// hybrid-mode public key pointed at the one file that's actually correct
// to publish.
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
        // Decision 115 (v9 DECISIONS.md): reject BOTH an invalid pqc claim
        // AND a missing one. This middleware only ever runs when
        // CRYPTO_PROFILE=hybrid (see express.js's isHybridProfile gate),
        // which is identical for Hibrido dual=false (control) and Hibrido
        // dual=true (AND) -- there is no signal here to distinguish them,
        // and Decision 115 deliberately did not add one, so this applies
        // uniformly to both. PS256-only validity (oidc-provider's own
        // subsequent check) is necessary but no longer sufficient on its
        // own: a classical-only assertion with no pqc claim at all used to
        // fall through unchanged (Decision 13's original text already
        // named "invalid or absent" as the same downgrade risk; the code
        // only ever implemented "invalid" until now).
        if (!result.hybridShaped || !result.valid) {
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
