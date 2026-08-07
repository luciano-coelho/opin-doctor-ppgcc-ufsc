/* eslint-disable no-console */

import * as path from 'node:path';
import * as url from 'node:url';
import { dirname } from 'desm';
import express from 'express'; // eslint-disable-line import/no-unresolved
import helmet from 'helmet';
import got from 'got';
import Provider from 'oidc-provider';
import { randomUUID, randomBytes } from 'node:crypto';
import Debug from 'debug';
import { SSMClient, GetParameterCommand } from '@aws-sdk/client-ssm';
import bodyParser from 'body-parser';

import Account from './utils/account.js';
import BRAND_NAME from './utils/brandHelper.js';
import { supportDynamicScopes, ensureTokenEndpointAsAudience } from './utils/oidc.js';

const log = Debug('raidiam:server:info');

const __dirname = dirname(import.meta.url);
const {
  BRAND = 'NO_BRAND',
  AWS_SSM_REGION = 'us-east-1',
  AWS_LOCAL = false,
  LOCAL_STACK_ENDPOINT,
  TRUSTFRAMEWORK_SSA_KEYSET,
  SSM_PARAMETER_PREFIX = '/local/op_fapi_client_config',
} = process.env;

const ssmClient = new SSMClient({
  ...(AWS_LOCAL && { endpoint: LOCAL_STACK_ENDPOINT }),
  maxAttempts: 3,
  region: AWS_SSM_REGION,
});

const brandConfig = {
  [BRAND_NAME.OPIN]: {
    brand: 'opin',
    clientId: 'QZY-zq89jUAnkOgBhRp19',
    dynamicScopesSupported: ['consent:'],
  },
  [BRAND_NAME.OPIN_LOCAL]: {
    brand: 'opin',
    clientId: 'client',
    dynamicScopesSupported: ['consent:'],
  },
  default: {
    brand: 'opin',
    clientId: 'client',
    dynamicScopesSupported: ['consent:'],
  },
};

async function getSsmParameter(name) {
  const command = new GetParameterCommand({
    Name: name,
    WithDecryption: true,
  });

  try {
    const result = await ssmClient.send(command);
    return result.Parameter.Value;
  } catch (error) {
    console.error('Error fetching parameter:', error);
    throw error;
  }
}

async function loadSsmParameters() {
  let issuer = await getSsmParameter(`${SSM_PARAMETER_PREFIX}/issuer`);
  issuer = issuer.startsWith('https://') ? issuer : `https://${issuer}`;
  const clientCert = await getSsmParameter(`${SSM_PARAMETER_PREFIX}/transport_certificate`);
  const clientCertKey = await getSsmParameter(`${SSM_PARAMETER_PREFIX}/transport_key`);

  return { issuer, clientCert, clientCertKey };
}

async function loadSupportFunctions(provider, dynamicScopes) {
  log(`Configure support dynamic scopes function - ${dynamicScopes}`);
  supportDynamicScopes(provider, ...dynamicScopes);
  log(`Configure token endpoint as audience function`);
  ensureTokenEndpointAsAudience(provider);
}

async function loadOidcConfiguration(brand, mtlsIssuer) {
  let configPath = `./utils/${brand}/configuration.js`;
  log(`Loading configuration from ${configPath}`);
  // Import the module
  const configFunc = await import(configPath);

  log(`Load Directory Key Set: ${TRUSTFRAMEWORK_SSA_KEYSET}`);
  const ssaJwksResponse = await got(TRUSTFRAMEWORK_SSA_KEYSET);
  // Passed through as plain JWKS JSON, not a jose KeyStore: its only consumer
  // (verifySsaJwt in utils/opin/configuration.js) verifies synchronously with
  // node:crypto, since oidc-provider's validator hook can't await jose's
  // Promise-based jwtVerify. See thesis/results/experiment2 - PQC/DECISIONS.md.
  const ssaJwks = JSON.parse(ssaJwksResponse.body);

  let configuration = configFunc.default(mtlsIssuer, ssaJwks);
  // Add the findAccount property
  configuration.findAccount = Account.findAccount;
  return configuration;
}

async function main() {
  const app = express();

  app.use((req, res, next) => {
    res.locals.nonce = randomBytes(16).toString('base64');
    next();
  });
  const directives = helmet.contentSecurityPolicy.getDefaultDirectives();
  delete directives['form-action'];
  directives['script-src'] = ["'self'", (req, res) => `'nonce-${res.locals.nonce}'`];
  app.use(
    helmet({
      contentSecurityPolicy: {
        useDefaults: false,
        directives,
      },
    }),
  );

  app.set('views', path.join(__dirname, 'views'));
  app.set('view engine', 'ejs');
  app.use(express.static(path.join(__dirname, 'public')));

  app.use(bodyParser.json());

  log(`Load configuration for ${BRAND}`);
  const config = brandConfig[BRAND] || brandConfig.default;
  const { issuer, clientCert, clientCertKey } = await loadSsmParameters();

  let mtlsIssuer = new URL(issuer);
  mtlsIssuer.host = `matls-${mtlsIssuer.host}`;
  mtlsIssuer = mtlsIssuer.toString().replace(/\/$/, ''); // Remove trailing slash.
  let apiUrl = new URL(issuer);
  apiUrl.host = apiUrl.host.replace('auth', 'matls-api');
  apiUrl = apiUrl.toString().replace(/\/$/, ''); // Remove trailing slash.
  log(`Issuer: ${issuer}, mTLS Issuer: ${mtlsIssuer}, API Host: ${apiUrl}`);

  let oidcConfig = await loadOidcConfiguration(config.brand, mtlsIssuer);

  let adapter;
  if (process.env.MONGODB_URI) {
    ({ default: adapter } = await import('./utils/mongodb.js'));
    await adapter.connect('openid-server');
  }

  let provider = new Provider(issuer, { adapter, ...oidcConfig });
  log(`Create Account adapter`);
  await Account.initialiseAdapter('accounts');

  log(`Init Adapter for ${BRAND || 'Default'}`);
  const { init } = await import(`./utils/${config.brand}/adapter.js`);
  init(apiUrl, provider, config.clientId, clientCert, clientCertKey);

  loadSupportFunctions(provider, config.dynamicScopesSupported);

  const routes = await import(`./utils/${config.brand}/routes.js`);
  routes.default(app, provider);

  provider.use(async (ctx, next) => {
    await next(); // Ensure the next middleware

    if (!ctx.get('x-fapi-interaction-id')) {
      ctx.set('x-fapi-interaction-id', randomUUID());
    } else {
      ctx.set('x-fapi-interaction-id', ctx.get('x-fapi-interaction-id'));
    }
  });

  // Trust the proxy
  app.enable('trust proxy');
  provider.proxy = true;

  const prod = process.env.NODE_ENV === 'production';
  if (prod) {
    app.use((req, res, next) => {
      if (req.secure) {
        next();
      } else if (req.method === 'GET' || req.method === 'HEAD') {
        res.redirect(
          url.format({
            protocol: 'https',
            host: req.get('host'),
            pathname: req.originalUrl,
          }),
        );
      } else {
        res.status(400).json({
          error: 'invalid_request',
          error_description: 'do yourself a favor and only use https',
        });
      }
    });
  }

  // Serve static files
  app.use('/assets', express.static(path.join(__dirname, 'assets')));
  app.use(provider.callback());

  return {
    app,
  };
}

async function run() {
  const app = await main();
  const port = process.env.PORT ? process.env.PORT : 9000;

  const server = app.app.listen(port, () => {
    log(`Listening on port ${port}`);
  });

  return {
    app,
    server,
  };
}

export { run };
