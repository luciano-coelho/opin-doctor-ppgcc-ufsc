import { insurerAdapter } from './adapter.js';
import { getConsentId } from './helpers.js';

import { errors } from 'oidc-provider';
import { createPublicKey, verify as cryptoVerify, constants } from 'node:crypto';
import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import path from 'node:path';
import { calculateJwkThumbprint } from 'jose';

import Debug from 'debug';
const log = Debug('raidiam:server:info');
const err = Debug('raidiam:server:error');

// CRYPTO_PROFILE picks which mock_as/crypto-profiles/<name>.json to load --
// classic (PS256/RSA, Experiment 1) or pqc (ML-DSA-65, Experiment 2). One
// switch, read once at boot, instead of branching classic/PQC logic through
// the file. Defaults to classic so an unset env var reproduces Experiment 1.
// See thesis/results/experiment2 - PQC/DECISIONS.md.
const CRYPTO_PROFILE = process.env.CRYPTO_PROFILE || 'classic';
const __dirname = path.dirname(fileURLToPath(import.meta.url));
const cryptoProfile = JSON.parse(
  readFileSync(path.join(__dirname, '..', '..', 'crypto-profiles', `${CRYPTO_PROFILE}.json`), 'utf8'),
);
log(`Crypto profile: ${CRYPTO_PROFILE} (signingAlgs: ${cryptoProfile.signingAlgs.join(', ')})`);

// hybrid mode: oidc-provider/jose cannot be configured to produce or
// validate "MLDSA65-RSA2048-PSS-SHA256" -- it isn't a real JOSE algorithm,
// so it's absent from every library's algorithm dispatch table (see
// DECISIONS.md for the full reasoning). oidc-provider is therefore kept
// completely unaware of hybrid mode and configured exactly like classic
// internally (PS256, hybrid.json's classic-half key) -- it produces a
// normal, fully valid PS256 token. The hybrid re-signing middleware
// (express.js, using utils/opin/hybridSigning.js) then discards that
// signature and replaces it with the real Strong Nesting composite before
// the response leaves the process. `internalSigningAlgs`/`internalSigningKey`
// are what oidc-provider itself is configured with; `cryptoProfile.signingAlgs`
// (the composite alg string) is only ever used for the boot log above and
// is never handed to oidc-provider/jose.
const isHybrid = CRYPTO_PROFILE === 'hybrid';
const internalSigningAlgs = isHybrid ? ['PS256'] : cryptoProfile.signingAlgs;
const internalSigningKey = isHybrid ? cryptoProfile.classicSigningKey : cryptoProfile.signingKey;

// The AS's encryption key -- unaffected by CRYPTO_PROFILE (see enabledJWA
// below: encryption stays classical regardless of profile).
const AS_ENC_JWK = {
  p: '_aSA0u5saMEl1hc9-Sglp9LDOeZcgs_Gw7Olxefs77bIjMQpFwrFsIWR4HH6K9nscTIAKNM9AVq30Y1TTB0idebzPbjECB90KgYa3hm2g4A6pHkaOuHs0RGTWbWavDUkQka-CSB8hE7sTNSrmDpG8FbLihuSzDFWCdLGsDqXeuk',
  kty: 'RSA',
  q: 'gvBSWfBZtjHBqhwxXdO5k9J0nNqPta-sBuKc7PNhODbr0UWNkHcailKWs3f0ViXaSRAEW-EB9Ty4plgMBjy-ycc4va1Rfg-6Pn_tnVYbB5-4nmHO8vAFZR4EP4MHipyizJfNPuSlawLNc71Eo5lAUWzPRpTBZ1XvQ9AZgx-wA2M',
  d: 'et4yFr71HRMW2epVzYPNcNfqGJqTU7NsbVMCSH-ZDJ_ysPn5CgTmAK-NZh2hJvra4RCBgpOQiEYqEqX5jc3xPZyTUtCTJwRpgVNLnhylk031hy22qA2QqWRsWGLBxRvgP8gb9intIs6MkrIiPkO2t5o3J9OYpF7aO40mXH5CM2EJm-FxqGuKMVb_zWVqImmh3mqC2GlPBsiZLcHeFIbtGopsel07nngBBSmCOf7XAmtqYvZAGiJQkd1poI7p_c5n7x3aj1jPGShVLzfLBWqNipoZk0GfbY7qTlkY6dT2x098V_MSpSip9tkQ__whdHOlR5GE_HT0vlmhfwixZKaTEQ',
  e: 'AQAB',
  use: 'enc',
  qi: 'eiD4hKfSwXUVN8q14yL2JK4rUt0heIZ93CHVtkonsA8VasPOI1E6D51WaFRHaJxgvn7CiY16h2qg9xjP1uMBNcuscSKRnyqAeGJuyPh576-FWxJlZSqh9PoSxj4eHQMCWmBBi7TL820hrgA2mhc0KLekCRT36-89-Va7G74N5A8',
  dp: 'n1NJNLZd1MOXD8-Tt0HXvX6v8VvZurXnhiD_vbw84isv-PRzVy0GFycgBhuyaP8__a7J2NswE_y3QOOEcmhOsD79hkTcprmTT558HA2MzzeqHoyPxHMMPhvLMmvYIedDunoTf0ovzTCCUJS6oSniS7BJtJwzbx6CjDMhaau0YZk',
  alg: 'RSA-OAEP',
  dq: 'G1DXXTvu-ztWE47eHZzV0ijNewt9f4GueaE865G6bmfGulmwNrsiJkkkdzxHFNHAwA0_W4uNRQPt4YXsvEBf7OhKxgcqQQo26GL3xyL3cJe5hBETg0rfVUD10eob4Kbcr6Hbh4tblv92rPaHIzoNWO9CLo9J6azbxWHccKZjqdE',
  n: 'gbulO7BqCAKwVy3ZqrR033OM1Mp-SqOViwD1manyHjhDSB5dPLL8AG9zdl8hoQwQO8TVR4Ske2oYLkr9zxtWROTYKvF6Ssp0W5Df-sE6lEnMRqPr0GNrIubA0i2I0-uuK26N-x2_KJZbrMviH8qAdQGKopJ1-9DTvgXbOZmzQDuP3s0V8BB7pSroOaBpE7wtKAr5akPElbw_XR7m5ocmbd2TIHu8kdLU4W60Aha7x427KaYhetbtVkkS3h6j7FP9Wm2iMSkneo2ZA0WP4N4jqv3wqA2c7d_IeQNWmUxFrIoApmhy4MoMMDXjmWM_7JwH1UK6RsaknAfT7C0YJjVDGw',
};

// pqc mode, JWKS_SHADOW=1 only: the AS signs tokens with ML-DSA-65
// (cryptoProfile.signingKey, kty AKP), but the Conformance Suite's
// ValidateServerJWKs condition uses Nimbus JOSE+JWT, which throws on ANY
// kty: AKP key in a JWKS regardless of what else is present (confirmed
// empirically -- see thesis/results/v2/experiment2 - PQC/DECISIONS.md,
// Decision 6). To get the suite past that check for diagnostic purposes,
// /jwks can publish the classic RSA signing key instead (public-only
// projection -- it never signs anything in this mode) alongside the real
// encryption key. This is a published decoy, not a lie about what's used
// to sign: real token signatures still use the AKP key, unaffected by this
// (see express.js, where this is served by a route that shadows
// oidc-provider's own /jwks -- the internal signing keystore below is
// untouched). See Decision 7 for the exact limitation this accepts.
//
// Gated behind JWKS_SHADOW=1, off by default: this was purely a Conformance
// Suite diagnostic (Decision 6/7 concluded the suite can't drive Experiment
// 2 regardless -- Layer 3 is unfixable from our side), and opin_flow.py
// (the tool that actually drives Experiment 2 now) doesn't hit the Nimbus
// wall this decoy exists for. Left always-on, it would silently corrupt
// opin_flow.py's own JWK-size measurements -- reporting the classical RSA
// key's size instead of the real ML-DSA-65 key actually signing tokens.
let publishedJwksOverride = null;
if (CRYPTO_PROFILE === 'pqc' && process.env.JWKS_SHADOW === '1') {
  const classicProfile = JSON.parse(
    readFileSync(path.join(__dirname, '..', '..', 'crypto-profiles', 'classic.json'), 'utf8'),
  );
  const decoySigJwk = {
    kty: classicProfile.signingKey.kty,
    use: classicProfile.signingKey.use,
    alg: classicProfile.signingKey.alg,
    n: classicProfile.signingKey.n,
    e: classicProfile.signingKey.e,
  };
  decoySigJwk.kid = await calculateJwkThumbprint(decoySigJwk);
  const encJwkPublic = {
    kty: AS_ENC_JWK.kty,
    use: AS_ENC_JWK.use,
    alg: AS_ENC_JWK.alg,
    n: AS_ENC_JWK.n,
    e: AS_ENC_JWK.e,
  };
  encJwkPublic.kid = await calculateJwkThumbprint(encJwkPublic);
  publishedJwksOverride = { keys: [decoySigJwk, encJwkPublic] };
  log(`Published /jwks override active (pqc mode): publishing classic RSA sig key (kid ${decoySigJwk.kid}) instead of the real ML-DSA-65 signing key`);
}

// extraClientMetadata.validator (see below) must be synchronous -- confirmed
// in oidc-provider's own docs ("async validators or functions returning
// Promise shall be rejected during runtime"). jose v6's verification API
// (jwtVerify and everything built on it) is Promise-based with no sync
// escape hatch, so it can't be used inside that hook. This verifies the
// software_statement JWS by hand with node:crypto instead, which does have
// a synchronous verify(). Kept at PS256: the SSA is signed by the Trust
// Framework/Directory (TRUSTFRAMEWORK_SSA_KEYSET), a different actor from
// the AS's own signing key below -- migrating it to ML-DSA-65 is a separate,
// not-yet-scoped change to the Directory/localstack keystore fixture.
function verifySsaJwt(jws, jwks, { issuer, maxTokenAgeSeconds }) {
  const [headerB64, payloadB64, signatureB64] = jws.split('.');
  if (!headerB64 || !payloadB64 || !signatureB64) {
    throw new errors.InvalidSoftwareStatement('malformed software_statement JWT');
  }

  const header = JSON.parse(Buffer.from(headerB64, 'base64url').toString('utf8'));
  if (header.typ && header.typ.toLowerCase() !== 'jwt') {
    throw new errors.InvalidSoftwareStatement(`unexpected software_statement typ: ${header.typ}`);
  }
  if (header.alg !== 'PS256') {
    throw new errors.InvalidSoftwareStatement(`unexpected software_statement alg: ${header.alg}`);
  }

  const jwk = jwks.keys.find((key) => key.kid === header.kid && key.use !== 'enc');
  if (!jwk) {
    throw new errors.InvalidSoftwareStatement(`no matching software_statement signing key for kid ${header.kid}`);
  }

  const verified = cryptoVerify(
    'sha256',
    Buffer.from(`${headerB64}.${payloadB64}`),
    {
      key: createPublicKey({ key: jwk, format: 'jwk' }),
      padding: constants.RSA_PKCS1_PSS_PADDING,
      saltLength: constants.RSA_PSS_SALTLEN_DIGEST,
    },
    Buffer.from(signatureB64, 'base64url'),
  );
  if (!verified) {
    throw new errors.InvalidSoftwareStatement('software_statement signature verification failed');
  }

  const payload = JSON.parse(Buffer.from(payloadB64, 'base64url').toString('utf8'));
  const now = Math.floor(Date.now() / 1000);
  if (payload.iss !== issuer) {
    throw new errors.InvalidSoftwareStatement(`unexpected software_statement issuer: ${payload.iss}`);
  }
  if (typeof payload.iat !== 'number' || now - payload.iat > maxTokenAgeSeconds) {
    throw new errors.InvalidSoftwareStatement('software_statement is too old');
  }
  if (typeof payload.exp === 'number' && payload.exp < now) {
    throw new errors.InvalidSoftwareStatement('software_statement has expired');
  }
  if (typeof payload.nbf === 'number' && payload.nbf > now) {
    throw new errors.InvalidSoftwareStatement('software_statement is not yet valid');
  }

  return payload;
}

// Validate that the consent ID sent in the token request is authorized before
// issuing an access token.
// If there's no consent ID in the request, the validation is skipped.
async function validateConsent(token) {
  let consentId = getConsentId(token.scope);
  if (!consentId) {
    return;
  }

  console.log(`validating consent ${consentId}`);
  let consent = await insurerAdapter.getConsent(consentId);
  const status = consent.data?.status;
  if (['REJECTED', 'REVOKED', 'CONSUMED'].includes(status)) {
    throw new errors.InvalidGrant(`consent ${consentId} status is ${status}`);
  }

  console.log('consent is authorised');
}

export { publishedJwksOverride };
export const isHybridProfile = isHybrid;

export default function (mtlsIssuer, ssaJwks) {
  return {
    scopes: [
      'openid',
      'profile',
      'email',
      'address',
      'phone',
      'consents',
      'claim-notification',
      'resources',
      'customers',
      'insurance-acceptance-and-branches-abroad',
      'insurance-auto',
      'insurance-financial-risk',
      'insurance-housing',
      'insurance-person',
      'insurance-patrimonial',
      'insurance-rural',
      'insurance-responsibility',
      'insurance-transport',
      'claim-notification',
      'endorsement',
      'quote-patrimonial-lead',
      'quote-patrimonial-home',
      'quote-patrimonial-condominium',
      'quote-patrimonial-business',
      'quote-patrimonial-diverse-risks',
      'contract-life-pension',
      'contract-life-pension-lead',
      'quote-financial-risk-lead',
      'quote-acceptance-and-branches-abroad-lead',
      'quote-housing-lead',
      'quote-responsibility-lead',
      'quote-transport-lead',
      'quote-rural-lead',
      'quote-auto-lead',
      'quote-auto',
      'quote-person-lead',
      'quote-person-life',
      'quote-person-travel',
      'quote-capitalization-title-lead',
      'quote-capitalization-title',
      'quote-capitalization-title-raffle',
      'capitalization-title-raffle',
      'capitalization-title',
      'insurance-life-pension',
      'insurance-pension-plan',
      'insurance-financial-assistance',
      'dynamic-fields',
      'op:admin',
      'override',
    ],
    interactions: {
      url(ctx, interaction) {
        // eslint-disable-line no-unused-vars
        return `/interaction/${interaction.uid}`;
      },
    },
    cookies: {
      keys: ['some secret key', 'and also the old rotated away some time ago', 'and one more'],
    },
    claims: {
      address: ['address'],
      email: ['email', 'email_verified'],
      phone: ['phone_number', 'phone_number_verified'],
      profile: [
        'birthdate',
        'family_name',
        'gender',
        'given_name',
        'locale',
        'middle_name',
        'name',
        'nickname',
        'picture',
        'preferred_username',
        'profile',
        'updated_at',
        'website',
        'zoneinfo',
      ],
      openid: ['sub', 'acr'],
    },
    acrValues: ['urn:brasil:openbanking:loa2', 'urn:brasil:openbanking:loa3'],
    enabledJWA: {
      authorizationSigningAlgValues: internalSigningAlgs,
      introspectionSigningAlgValues: internalSigningAlgs,
      requestObjectSigningAlgValues: internalSigningAlgs,
      clientAuthSigningAlgValues: internalSigningAlgs,
      userinfoSigningAlgValues: internalSigningAlgs,
      idTokenSigningAlgValues: internalSigningAlgs,
      // Encryption stays classical regardless of profile: jose has no
      // ML-KEM support (no active JOSE/COSE draft for it either -- withdrawn
      // from the JOSE WG at IETF 126), and ML-KEM-768 migration for the AS
      // is not in scope (only the RS's JWE is, per Etapa 2.3).
      requestObjectEncryptionAlgValues: ['RSA-OAEP'],
      requestObjectEncryptionEncValues: ['A256GCM'],
      idTokenEncryptionAlgValues: ['RSA-OAEP'],
      idTokenEncryptionEncValues: ['A256GCM'],
    },
    clientDefaults: {
      grant_types: ['authorization_code', 'client_credentials', 'refresh_token', 'implicit'],
      id_token_signed_response_alg: internalSigningAlgs[0],
      request_object_signed_response_alg: internalSigningAlgs[0],
      request_object_signing_alg: internalSigningAlgs[0],
      authorization_signed_response_alg: internalSigningAlgs[0],
      response_types: ['code', 'code id_token'],
      tls_client_certificate_bound_access_tokens: true,
    },
    ttl: {
      AccessToken: function AccessTokenTTL(ctx, token, client) {
        if (token.resourceServer) {
          return token.resourceServer.accessTokenTTL || 60 * 15; // 15 minutes in seconds
        }
        return 60 * 15; // 15 minutes in seconds
      },
      AuthorizationCode: 900 /* 15 minutes in seconds */,
      ClientCredentials: function ClientCredentialsTTL(ctx, token, client) {
        if (token.resourceServer) {
          return token.resourceServer.accessTokenTTL || 15 * 60; // 15 minutes in seconds
        }
        return 15 * 60; // 15 minutes in seconds
      },
      DeviceCode: 900 /* 15 minutes in seconds */,
      Grant: function GrantTTL(ctx, token, client) {
        if (token.grantTtl) {
          return token.grantTtl;
        }
        return 157680000; /* 5 years in seconds */
      },
      IdToken: 3600 /* 1 hour in seconds */,
      Interaction: 600 /* 1 hour in seconds */,
      RefreshToken: function RefreshTokenTTL(ctx, token, client) {
        if (
          ctx &&
          ctx.oidc.entities.RotatedRefreshToken &&
          client.applicationType === 'web' &&
          client.tokenEndpointAuthMethod === 'none' &&
          !token.isSenderConstrained()
        ) {
          // Non-Sender Constrained SPA RefreshTokens do not have infinite expiration through rotation
          return ctx.oidc.entities.RotatedRefreshToken.remainingTTL;
        }

        return 365 * 24 * 60 * 60; // 1 Year In seconds
      },
      Session: 2 * 60 * 60 /* 2 Hours in seconds */,
    },
    features: {
      devInteractions: { enabled: false }, // defaults to true
      fapi: {
        enabled: true,
        profile: '1.0 Final',
      },
      encryption: {
        enabled: true,
      },
      pushedAuthorizationRequests: {
        allowUnregisteredRedirectUris: false,
        enabled: true,
        requirePushedAuthorizationRequests: false,
      },
      introspection: { enabled: true }, // defaults to false
      jwtResponseModes: { enabled: true },
      clientCredentials: { enabled: true },
      requestObjects: {
        enabled: true,
      },
      registration: {
        enabled: true,
      },
      registrationManagement: {
        enabled: true,
        rotateRegistrationAccessToken: false,
      },
      deviceFlow: { enabled: true }, // defaults to false
      revocation: { enabled: true }, // defaults to false
      mTLS: {
        enabled: true,
        tlsClientAuth: true,
        certificateBoundAccessTokens: true,
        selfSignedTlsClientAuth: false,
        getCertificate(ctx) {
          const cert = ctx.get('BANK-TLS-Certificate');
          return cert;
        },
        certificateAuthorized(ctx) {
          return ctx.get('X-BANK-Certificate-Verify') === 'SUCCESS' || ctx.get('x-forwarded-client-cert');
        },
        certificateSubjectMatches(ctx, property, expected) {
          if (property !== 'tls_client_auth_subject_dn') {
            throw new Error(`${property} is not supported by this deployment`);
          }
          const subject = ctx.get('X-BANK-Certificate-DN');
          if (subject === expected) {
            return true;
          }
          var decoded = decodeURI(subject);
          if (decoded === expected) {
            return true;
          } else {
            log(
              'Certifcate Subject does not match the registered one, transforming. Expected: %O Actual: %O',
              expected,
              subject,
            );
          }
          // const transformedSubject = reformatDNforBRCAC(subject, expected);
          // if (transformedSubject === expected) {
          //   return true;
          // } else {
          //   log(
          //     'Transformed Certifcate Subject does not match the registered one. Expected: %O Actual: %O',
          //     expected,
          //     transformedSubject,
          //   );
          // }

          // const softwareId = ctx.oidc.client.software_id;
          // const orgId = ctx.oidc.client.org_id;
          // if (validateSubjectFields(subject, expected, softwareId, orgId)) {
          //   log('Constituent parts of the DN Match the certificate presented');
          //   return true;
          // } else {
          //   log('Could not match any part of a certificate validation process');
          //   return false;
          // }
        },
      },
    },
    issueRefreshToken: async (ctx, client, code) => {
      if (!client.grantTypeAllowed('refresh_token')) {
        return false;
      }
      return true;
    },
    jwks: {
      keys: [
        // AS's own signing key -- comes from crypto-profiles/<CRYPTO_PROFILE>.json
        // (PS256/RSA for classic, ML-DSA-65/AKP for pqc). No `kid` set on
        // purpose in either profile: oidc-provider computes one via the JWK
        // thumbprint (jose's calculateJwkThumbprint supports AKP JWKs since
        // v6.1.0, same code path as RSA). See thesis/results/experiment2 -
        // PQC/DECISIONS.md.
        internalSigningKey,
        AS_ENC_JWK,
      ],
    },
    extraClientMetadata: {
      properties: [
        'software_statement',
        'software_id',
        'client_description',
        'org_id',
        'org_name',
        'org_number',
        'webhook_uris',
      ],
      validator(ctx, key, value, metadata) {
        if (key === 'software_statement') {
          if (value === undefined && ctx === undefined) return;
          // software_statement is not stored, but used to convey client metadata

          if (metadata.jwks) {
            throw new errors.InvalidClientMetadata('jwks by value not permitted');
          }
          let payload;
          try {
            // extraClientMetadata.validator must be sync -- see verifySsaJwt above.
            payload = verifySsaJwt(value, ssaJwks, {
              issuer: process.env.TRUSTFRAMEWORK_SSA_ISS,
              maxTokenAgeSeconds: 5 * 24 * 60 * 60,
            });

            // This has the double benefit of also ensuring that the DCR is presented over a mtls link
            const subject = ctx.get('X-BANK-Certificate-DN');
            if (
              !subject ||
              !payload.software_id ||
              (!subject.includes(`CN=${payload.software_id}`) && !subject.includes(`UID=${payload.software_id}`))
            ) {
              throw new errors.UnapprovedSoftwareStatement(
                `software_statement not approved for use with presented client tls certificate or no client tls certificate presented. expected x509 CN or UID: ${
                  payload.software_id
                }, actual x509: ${ctx.get('X-BANK-Certificate-DN')}`,
              );
            }

            if (payload.org_status != 'Active') {
              throw new errors.UnapprovedSoftwareStatement(
                'software_statement not approved for use, organisation inactive',
              );
            }

            if (!payload.software_roles || payload.software_roles.length == 0) {
              throw new errors.UnapprovedSoftwareStatement(
                'software_statement not approved for use, no regulatory roles defined',
              );
            }

            if (!payload.software_redirect_uris || payload.software_redirect_uris.length == 0) {
              throw new errors.UnapprovedSoftwareStatement(
                'software_statement not approved for use, no redirect uris defined',
              );
            }

            if (metadata.software_id && metadata.software_id != payload.software_id) {
              throw new errors.InvalidSoftwareStatement('software statement does not blelong to this client');
            }

            if (metadata.jwks_uri && metadata.jwks_uri != payload.software_jwks_uri) {
              throw new errors.InvalidClientMetadata('jwks uri is invalid');
            }

            if (metadata.org_id && metadata.org_id != payload.org_id) {
              throw new errors.InvalidSoftwareStatement('software statement does not blelong to this client');
            }

            if (!metadata.redirect_uris || metadata.redirect_uris.length == 0) {
              throw new errors.InvalidClientMetadata('no redirect uris defined');
            }

            metadata.redirect_uris = metadata.redirect_uris.filter((item) =>
              payload.software_redirect_uris.includes(item),
            );

            if (!metadata.redirect_uris || metadata.redirect_uris.length == 0) {
              throw new errors.InvalidClientMetadata('no valid redirect uris defined');
            }

            // Validate the webhook URIs if requested by the client.
            if (metadata.webhook_uris && metadata.webhook_uris.length != 0) {
              // Deny the request if the client sent webhook_uris, but the field software_api_webhook_uris in the ssa is empty.
              if (!payload.software_api_webhook_uris || payload.software_api_webhook_uris == 0) {
                throw new errors.InvalidClientMetadata('no webhooks uris defined in the software statement');
              }

              // Deny the request if an invalid webhook_uri was requested.
              let valid_webhook_uris = metadata.webhook_uris.filter((item) =>
                payload.software_api_webhook_uris.includes(item),
              );
              if (metadata.webhook_uris.length != valid_webhook_uris.length) {
                throw new errors.InvalidClientMetadata('invalid webhook uri');
              }
            }

            const scopes = ['openid'];
            scopes.push(
              'consents',
              'resources',
              'claim-notification',
              'customers',
              'insurance-acceptance-and-branches-abroad',
              'insurance-auto',
              'insurance-financial-risk',
              'insurance-housing',
              'insurance-person',
              'insurance-patrimonial',
              'insurance-rural',
              'insurance-responsibility',
              'insurance-transport',
              'claim-notification',
              'endorsement',
              'quote-patrimonial-lead',
              'quote-patrimonial-home',
              'quote-patrimonial-condominium',
              'quote-patrimonial-business',
              'quote-patrimonial-diverse-risks',
              'contract-life-pension',
              'contract-life-pension-lead',
              'quote-financial-risk-lead',
              'quote-acceptance-and-branches-abroad-lead',
              'quote-housing-lead',
              'quote-responsibility-lead',
              'quote-transport-lead',
              'quote-rural-lead',
              'quote-auto-lead',
              'quote-auto',
              'quote-person-lead',
              'quote-person-life',
              'quote-person-travel',
              'quote-capitalization-title-lead',
              'quote-capitalization-title',
              'quote-capitalization-title-raffle',
              'capitalization-title',
              'insurance-life-pension',
              'insurance-pension-plan',
              'insurance-financial-assistance',
              'dynamic-fields',
            );

            let requestedArray;
            if (metadata.scope) {
              requestedArray = metadata.scope.split(' ');
            }

            const {
              software_jwks_uri,
              org_id,
              software_client_name,
              software_client_uri,
              software_tos_uri,
              software_logo_uri,
              software_policy_uri,
              software_id,
              software_client_description,
              org_name,
              org_number,
            } = payload;
            Object.assign(metadata, {
              software_id,
              org_id,
              org_name,
              org_number,
              client_description: software_client_description,
              jwks_uri: software_jwks_uri,
              application_type: 'web',
              client_name: software_client_name,
              id_token_signed_response_alg: internalSigningAlgs[0],
              request_object_signing_alg: internalSigningAlgs[0],
              authorization_signed_response_alg: internalSigningAlgs[0],
              tos_uri: software_tos_uri,
              logo_uri: software_logo_uri,
              request_object_encryption_alg: 'RSA-OAEP',
              request_object_encryption_enc: 'A256GCM',
              policy_uri: software_policy_uri,
              default_max_age: 0,
              require_signed_request_object: true,
              subject_type: 'public',
              ...(requestedArray && { scope: requestedArray.join(' ') }),
              ...(!requestedArray && { scope: scopes.join(' ') }),
              response_types: ['code id_token', 'code'],
              grant_types: ['client_credentials', 'authorization_code', 'refresh_token', 'implicit'],
              client_uri: software_client_uri,
              tls_client_certificate_bound_access_tokens: true,
            });

            // software_statement is not stored, but used to convey client metadata
            delete metadata.software_statement;
          } catch (error) {
            err(`${error.message}: ${JSON.stringify(metadata)}`);
            if (error instanceof errors.InvalidClientMetadata) {
              throw error;
            } else if (error instanceof errors.InvalidSoftwareStatement) {
              throw error;
            } else console.log(error);
            throw new errors.InvalidClientMetadata(
              `unknown processing error, have you entered invalid client metadata: ${error.message}`,
            );
          }
        }
      },
    },
    extraTokenClaims: async (ctx, token) => {
      let claims = {
        org_id: token.client.org_id,
        org_name: token.client.org_name,
        org_number: token.client.org_number,
        software_id: token.client.software_id,
      };

      let oidcProvider = ctx?.oidc?.provider;
      if (!oidcProvider) {
        // When the bank adapter creates a token, this function is called with
        // ctx as undefined.
        return;
      }

      await validateConsent(token);

      return claims;
    },
    discovery: {
      mtls_endpoint_aliases: {
        token_endpoint: `${mtlsIssuer}/token`,
        revocation_endpoint: `${mtlsIssuer}/token/revocation`,
        introspection_endpoint: `${mtlsIssuer}/token/introspection`,
        device_authorization_endpoint: `${mtlsIssuer}/device/auth`,
        registration_endpoint: `${mtlsIssuer}/reg`,
        userinfo_endpoint: `${mtlsIssuer}/me`,
        pushed_authorization_request_endpoint: `${mtlsIssuer}/request`,
      },
    },
  };
}
