import { errors } from 'oidc-provider';
import axios from 'axios';
import { randomUUID } from 'crypto';
import https from 'https';
import NodeCache from 'node-cache';
import crypto from 'crypto';
import Debug from 'debug';

const log = Debug('raidiam:server:info');
const nodeCash = new NodeCache();

// Since Etapa 2 (RS response signing, see thesis/results/experiment2 -
// PQC/DECISIONS.md, Decision 4), every RS response body is a JWS Compact
// Serialization (Content-Type: application/jwt) in both classic and pqc
// CRYPTO_PROFILE, not plain JSON -- axios's default transformResponse only
// parses a string as JSON when JSON.parse succeeds, so a JWT body silently
// falls through as a raw string instead. Mirrors
// thesis/scripts/opin_flow.py's parse_rs_body(): the signature isn't
// verified here either (the RS may be signing with ML-DSA-65, which this
// runtime has no verifier for -- same Nimbus gap that motivated the RS's
// own BouncyCastle workaround), this just needs the claims to keep the
// interaction flow moving, not a security proof.
function parseRsBody(response) {
  const body = response.data;
  const contentType = response.headers?.['content-type'] || '';
  if (typeof body === 'string' && (contentType.startsWith('application/jwt') || body.split('.').length === 3)) {
    const payload = body.split('.')[1];
    return JSON.parse(Buffer.from(payload, 'base64url').toString('utf-8'));
  }
  return body;
}

export class InsurerAdapter {
  oidcProvider;
  httpClient;
  nodeCash;
  clientId;

  constructor(httpClient, oidcProvider, clientId) {
    this.httpClient = httpClient;
    this.oidcProvider = oidcProvider;
    this.nodeCash = nodeCash;
    this.clientId = clientId;
  }

  async getConsent(consentId) {
    const config = await this.getRequestConfig('consents op:consent');
    let response;
    try {
      response = await this.httpClient.get(`/open-insurance/consents/v2/consents/${consentId}`, config);
    } catch (error) {
      log(`error fetching the consent ${consentId} - ${error} - ${error.response?.data}`);
      throw new errors.InvalidGrant(`consent ${consentId} not found`);
    }
    return parseRsBody(response);
  }

  async updateConsent(consentId, data) {
    const config = await this.getRequestConfig('consents op:consent');
    let response;
    try {
      response = await this.httpClient.put(`/open-insurance/consents/v2/consents/${consentId}`, { data: data }, config);
      log(`consent ${consentId} updated`);
    } catch (error) {
      log(`error updating the consent ${consentId} - ${error}`);
      throw new errors.InvalidGrant(`consent ${consentId} not updated`);
    }
    return parseRsBody(response);
  }

  async getUserInformation(userId, consentRecord) {
    var result = [];

    var capitalizationTilePermissions = [
      'CAPITALIZATION_TITLE_READ',
      'CAPITALIZATION_TITLE_PLANINFO_READ',
      'CAPITALIZATION_TITLE_EVENTS_READ',
      'CAPITALIZATION_TITLE_SETTLEMENTS_READ',
    ];
    var hasPermission = consentRecord.permissions.some((i) => capitalizationTilePermissions.includes(i));
    if (hasPermission) {
      const userAccounts = await this.getUserCapitalizationTitlePlansInformation(userId);
      result.push({ scope: 'capitalization-title', accounts: parseRsBody(userAccounts).data });
    }

    var financialRiskPermissions = [
      'DAMAGES_AND_PEOPLE_FINANCIAL_RISKS_READ',
      'DAMAGES_AND_PEOPLE_FINANCIAL_RISKS_POLICYINFO_READ',
      'DAMAGES_AND_PEOPLE_FINANCIAL_RISKS_CLAIM_READ',
      'DAMAGES_AND_PEOPLE_FINANCIAL_RISKS_PREMIUM_READ',
    ];
    hasPermission = consentRecord.permissions.some((i) => financialRiskPermissions.includes(i));
    if (hasPermission) {
      const userAccounts = await this.getUserFinancialRiskPoliciesInformation(userId);
      result.push({ scope: 'financial-risk', accounts: parseRsBody(userAccounts).data });
    }

    var housingPermissions = [
      'DAMAGES_AND_PEOPLE_HOUSING_READ',
      'DAMAGES_AND_PEOPLE_HOUSING_POLICYINFO_READ',
      'DAMAGES_AND_PEOPLE_HOUSING_CLAIM_READ',
      'DAMAGES_AND_PEOPLE_HOUSING_PREMIUM_READ',
    ];
    hasPermission = consentRecord.permissions.some((i) => housingPermissions.includes(i));
    if (hasPermission) {
      const userAccounts = await this.getUserHousingPoliciesInformation(userId);
      result.push({ scope: 'housing', accounts: parseRsBody(userAccounts).data });
    }

    var responsibilityPermissions = [
      'DAMAGES_AND_PEOPLE_RESPONSIBILITY_READ',
      'DAMAGES_AND_PEOPLE_RESPONSIBILITY_POLICYINFO_READ',
      'DAMAGES_AND_PEOPLE_RESPONSIBILITY_CLAIM_READ',
      'DAMAGES_AND_PEOPLE_RESPONSIBILITY_PREMIUM_READ',
    ];
    hasPermission = consentRecord.permissions.some((i) => responsibilityPermissions.includes(i));
    if (hasPermission) {
      const userAccounts = await this.getUserResponsibilityPoliciesInformation(userId);
      result.push({ scope: 'responsibility', accounts: parseRsBody(userAccounts).data });
    }

    var personPermissions = [
      'DAMAGES_AND_PEOPLE_PERSON_READ',
      'DAMAGES_AND_PEOPLE_PERSON_POLICYINFO_READ',
      'DAMAGES_AND_PEOPLE_PERSON_CLAIM_READ',
      'DAMAGES_AND_PEOPLE_PERSON_PREMIUM_READ',
    ];
    hasPermission = consentRecord.permissions.some((i) => personPermissions.includes(i));
    if (hasPermission) {
      const userAccounts = await this.getUserPersonPoliciesInformation(userId);
      result.push({ scope: 'person', accounts: parseRsBody(userAccounts).data });
    }

    var lifePensionPermissions = [
      'LIFE_PENSION_READ',
      'LIFE_PENSION_CONTRACTINFO_READ',
      'LIFE_PENSION_MOVEMENTS_READ',
      'LIFE_PENSION_PORTABILITIES_READ',
      'LIFE_PENSION_WITHDRAWALS_READ',
      'LIFE_PENSION_CLAIM',
    ];
    hasPermission = consentRecord.permissions.some((i) => lifePensionPermissions.includes(i));
    if (hasPermission) {
      const userAccounts = await this.getUserLifePensionContractsInformation(userId);
      result.push({ scope: 'life-pension', accounts: parseRsBody(userAccounts).data });
    }

    var pensionPlanPermissions = [
      'PENSION_PLAN_READ',
      'PENSION_PLAN_CONTRACTINFO_READ',
      'PENSION_PLAN_MOVEMENTS_READ',
      'PENSION_PLAN_PORTABILITIES_READ',
      'PENSION_PLAN_WITHDRAWALS_READ',
      'PENSION_PLAN_CLAIM',
    ];
    hasPermission = consentRecord.permissions.some((i) => pensionPlanPermissions.includes(i));
    if (hasPermission) {
      const userAccounts = await this.getUserPensionPlanContractsInformation(userId);
      result.push({ scope: 'pension-plan', accounts: parseRsBody(userAccounts).data });
    }

    var acceptanceAndBranchesAbroadPermissions = [
      'DAMAGES_AND_PEOPLE_ACCEPTANCE_AND_BRANCHES_ABROAD_READ',
      'DAMAGES_AND_PEOPLE_ACCEPTANCE_AND_BRANCHES_ABROAD_POLICYINFO_READ',
      'DAMAGES_AND_PEOPLE_ACCEPTANCE_AND_BRANCHES_ABROAD_PREMIUM_READ',
      'DAMAGES_AND_PEOPLE_ACCEPTANCE_AND_BRANCHES_ABROAD_CLAIM_READ',
    ];
    hasPermission = consentRecord.permissions.some((i) => acceptanceAndBranchesAbroadPermissions.includes(i));
    if (hasPermission) {
      const userAccounts = await this.getUserAcceptanceAndBranchesAbroadPoliciesInformation(userId);
      result.push({ scope: 'insurance-acceptance-and-branches-abroad', accounts: parseRsBody(userAccounts).data });
    }

    var financialAssistancePermissions = [
      'FINANCIAL_ASSISTANCE_READ',
      'FINANCIAL_ASSISTANCE_CONTRACTINFO_READ',
      'FINANCIAL_ASSISTANCE_MOVEMENTS_READ',
    ];
    hasPermission = consentRecord.permissions.some((i) => financialAssistancePermissions.includes(i));
    if (hasPermission) {
      const userAccounts = await this.getUserFinancialAssistanceContractsInformation(userId);
      result.push({ scope: 'financial-assistance', accounts: parseRsBody(userAccounts).data });
    }

    var patrimonialPermissions = [
      'DAMAGES_AND_PEOPLE_PATRIMONIAL_READ',
      'DAMAGES_AND_PEOPLE_PATRIMONIAL_POLICYINFO_READ',
      'DAMAGES_AND_PEOPLE_PATRIMONIAL_PREMIUM_READ',
      'DAMAGES_AND_PEOPLE_PATRIMONIAL_CLAIM_READ',
    ];
    hasPermission = consentRecord.permissions.some((i) => patrimonialPermissions.includes(i));
    if (hasPermission) {
      const userAccounts = await this.getUserPatrimonialPoliciesInformation(userId);
      result.push({ scope: 'patrimonial', accounts: parseRsBody(userAccounts).data });
    }

    var ruralPermissions = [
      'DAMAGES_AND_PEOPLE_RURAL_READ',
      'DAMAGES_AND_PEOPLE_RURAL_POLICYINFO_READ',
      'DAMAGES_AND_PEOPLE_RURAL_PREMIUM_READ',
      'DAMAGES_AND_PEOPLE_RURAL_CLAIM_READ',
    ];
    hasPermission = consentRecord.permissions.some((i) => ruralPermissions.includes(i));
    if (hasPermission) {
      const userAccounts = await this.getUserRuralPoliciesInformation(userId);
      result.push({ scope: 'rural', accounts: parseRsBody(userAccounts).data });
    }

    var autoPermissions = [
      'DAMAGES_AND_PEOPLE_AUTO_READ',
      'DAMAGES_AND_PEOPLE_AUTO_POLICYINFO_READ',
      'DAMAGES_AND_PEOPLE_AUTO_PREMIUM_READ',
      'DAMAGES_AND_PEOPLE_AUTO_CLAIM_READ',
    ];
    hasPermission = consentRecord.permissions.some((i) => autoPermissions.includes(i));
    if (hasPermission) {
      const userAccounts = await this.getUserAutoPoliciesInformation(userId);
      result.push({ scope: 'auto', accounts: parseRsBody(userAccounts).data });
    }

    var transportPermissions = [
      'DAMAGES_AND_PEOPLE_TRANSPORT_READ',
      'DAMAGES_AND_PEOPLE_TRANSPORT_POLICYINFO_READ',
      'DAMAGES_AND_PEOPLE_TRANSPORT_PREMIUM_READ',
      'DAMAGES_AND_PEOPLE_TRANSPORT_CLAIM_READ',
    ];
    hasPermission = consentRecord.permissions.some((i) => transportPermissions.includes(i));
    if (hasPermission) {
      const userAccounts = await this.getUserTransportPoliciesInformation(userId);
      result.push({ scope: 'transport', accounts: parseRsBody(userAccounts).data });
    }

    return result;
  }

  async getUserCapitalizationTitlePlansInformation(userId) {
    const config = await this.getRequestConfig('op:admin');
    try {
      return await this.httpClient.get(`/user/${userId}/capitalization-title-plans`, config);
    } catch (error) {
      log(`error getting the user capitalization title plans ${userId} - ${error}`);
      throw new errors.InvalidGrant(`user capitalization title plans ${userId} not found`);
    }
  }

  async getUserFinancialRiskPoliciesInformation(userId) {
    const config = await this.getRequestConfig('op:admin');
    try {
      return await this.httpClient.get(`/user/${userId}/financial-risk-policies`, config);
    } catch (error) {
      log(`error getting the user financial risk policies ${userId} - ${error}`);
      throw new errors.InvalidGrant(`user financial risk policies ${userId} not found`);
    }
  }

  async getUserHousingPoliciesInformation(userId) {
    const config = await this.getRequestConfig('op:admin');
    try {
      return await this.httpClient.get(`/user/${userId}/housing-policies`, config);
    } catch (error) {
      log(`error getting the user housing policies ${userId} - ${error}`);
      throw new errors.InvalidGrant(`user housing policies ${userId} not found`);
    }
  }

  async getUserResponsibilityPoliciesInformation(userId) {
    const config = await this.getRequestConfig('op:admin');
    try {
      return await this.httpClient.get(`/user/${userId}/responsibility-policies`, config);
    } catch (error) {
      log(`error getting the user responsibility policies ${userId} - ${error}`);
      throw new errors.InvalidGrant(`user responsibility policies ${userId} not found`);
    }
  }

  async getUserPersonPoliciesInformation(userId) {
    const config = await this.getRequestConfig('op:admin');
    try {
      return await this.httpClient.get(`/user/${userId}/person-policies`, config);
    } catch (error) {
      log(`error getting the user person policies ${userId} - ${error}`);
      throw new errors.InvalidGrant(`user person policies ${userId} not found`);
    }
  }

  async getUserLifePensionContractsInformation(userId) {
    const config = await this.getRequestConfig('op:admin');
    try {
      return await this.httpClient.get(`/user/${userId}/life-pension-contracts`, config);
    } catch (error) {
      log(`error getting the user life-pension-contracts ${userId} - ${error}`);
      throw new errors.InvalidGrant(`user life-pension-contracts ${userId} not found`);
    }
  }

  async getUserPensionPlanContractsInformation(userId) {
    const config = await this.getRequestConfig('op:admin');
    try {
      return await this.httpClient.get(`/user/${userId}/pension-plan-contracts`, config);
    } catch (error) {
      log(`error getting the user pension-plan-contracts ${userId} - ${error}`);
      throw new errors.InvalidGrant(`user pension-plan-contracts ${userId} not found`);
    }
  }

  async getUserAcceptanceAndBranchesAbroadPoliciesInformation(userId) {
    const config = await this.getRequestConfig('op:admin');
    try {
      return await this.httpClient.get(`/user/${userId}/acceptance-and-branches-abroad-policies`, config);
    } catch (error) {
      log(`error getting the user acceptance-and-branches-abroad-policies ${userId} - ${error}`);
      throw new errors.InvalidGrant(`user acceptance-and-branches-abroad-policies ${userId} not found`);
    }
  }

  async getUserFinancialAssistanceContractsInformation(userId) {
    const config = await this.getRequestConfig('op:admin');
    try {
      return await this.httpClient.get(`/user/${userId}/financial-assistance-contracts`, config);
    } catch (error) {
      log(`error getting the user financial-assistance-contracts ${userId} - ${error}`);
      throw new errors.InvalidGrant(`user financial-assistance-contracts ${userId} not found`);
    }
  }

  async getUserPatrimonialPoliciesInformation(userId) {
    const config = await this.getRequestConfig('op:admin');
    try {
      return await this.httpClient.get(`/user/${userId}/patrimonial-policies`, config);
    } catch (error) {
      log(`error getting the user patrimonial policies ${userId} - ${error}`);
      throw new errors.InvalidGrant(`user patrimonial policies ${userId} not found`);
    }
  }

  async getUserRuralPoliciesInformation(userId) {
    const config = await this.getRequestConfig('op:admin');
    try {
      return await this.httpClient.get(`/user/${userId}/rural-policies`, config);
    } catch (error) {
      log(`error getting the user rural policies ${userId} - ${error}`);
      throw new errors.InvalidGrant(`user rural policies ${userId} not found`);
    }
  }

  async getUserAutoPoliciesInformation(userId) {
    const config = await this.getRequestConfig('op:admin');
    try {
      return await this.httpClient.get(`/user/${userId}/auto-policies`, config);
    } catch (error) {
      log(`error getting the user auto policies ${userId} - ${error}`);
      throw new errors.InvalidGrant(`user auto policies ${userId} not found`);
    }
  }

  async getUserTransportPoliciesInformation(userId) {
    const config = await this.getRequestConfig('op:admin');
    try {
      return await this.httpClient.get(`/user/${userId}/transport-policies`, config);
    } catch (error) {
      log(`error getting the user transport policies ${userId} - ${error}`);
      throw new errors.InvalidGrant(`user auto policies ${userId} not found`);
    }
  }

  async updateWebhook(clientId, webhookUri) {
    const config = await this.getRequestConfig('op:admin');
    let response;
    try {
      response = await this.httpClient.put(`/admin/webhook/${clientId}`, { webhookUri }, config);
    } catch (error) {
      log(`Error updating the client ${clientId} webhook - ${error}`);
      return;
    }

    if (response.status < 200 || response.status >= 300) {
      log(`Error updating the client ${clientId} webhook - ${JSON.stringify(response)}`);
      return;
    }
    log(`Client ${clientId} webhook URI updated`);
  }

  async deleteWebhook(clientId) {
    log(`Deleting client ${clientId} webhook URI`);
    this.updateWebhook(clientId, null);
  }

  async getRequestConfig(scopes) {
    if (!scopes) {
      scopes = '';
    }

    const token = await this.getToken(scopes);
    return {
      headers: {
        Authorization: `Bearer ${token}`,
        'x-fapi-interaction-id': randomUUID(),
      },
    };
  }

  async getToken(scope) {
    log('Retrieving token');
    const hash = crypto.createHash('md5').update(scope).digest('hex');
    let token = this.nodeCash.get(hash);
    if (token) {
      log('Using token from cache');
      return token;
    } else {
      log('Obtaining new token');
      token = await this.makeToken(scope);
      this.nodeCash.set(hash, this.token, 2000);
    }

    return token;
  }

  async makeToken(scope) {
    const token = new this.oidcProvider.ClientCredentials({
      client: {
        clientId: this.clientId,
        responseTypeAllowed: (type) => false,
        responseModeAllowed: (type, responseType, fapiProfile) => false,
        grantTypeAllowed: (type) => false,
        redirectUriAllowed: (redirectUri) => false,
        requestUriAllowed: (requestUri) => false,
        postLogoutRedirectUriAllowed: (postLogoutRedirectUri) => false,
        includeSid: () => false,
        compareClientSecret: (actual) => false,
        metadata: () => {
          return { client_id: this.clientId };
        },
        backchannelPing: async (request) => {},
      },
      scope: scope,
    });

    return await token.save();
  }
}

export let insurerAdapter = undefined;

export function init(baseUrl, oidcProvider, clientId, clientCert, clientCertKey) {
  const httpsAgent = new https.Agent({
    key: clientCertKey,
    cert: clientCert,
    rejectUnauthorized: false,
  });

  const instance = axios.create({ baseURL: baseUrl, httpsAgent: httpsAgent });
  insurerAdapter = new InsurerAdapter(instance, oidcProvider, clientId);

  return insurerAdapter;
}
