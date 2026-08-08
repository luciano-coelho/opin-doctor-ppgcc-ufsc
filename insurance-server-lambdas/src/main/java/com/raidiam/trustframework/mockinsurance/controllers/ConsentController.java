package com.raidiam.trustframework.mockinsurance.controllers;

import com.raidiam.trustframework.mockinsurance.auth.AuthenticationGrant;
import com.raidiam.trustframework.mockinsurance.auth.RequiredAuthenticationGrant;
import com.raidiam.trustframework.mockinsurance.fapi.Idempotent;
import com.raidiam.trustframework.mockinsurance.fapi.ResponseErrorWithRequestDateTime;
import com.raidiam.trustframework.mockinsurance.fapi.SignedResponse;
import com.raidiam.trustframework.mockinsurance.models.generated.CreateConsent;
import com.raidiam.trustframework.mockinsurance.models.generated.CreateConsentV3;
import com.raidiam.trustframework.mockinsurance.models.generated.ResponseConsent;
import com.raidiam.trustframework.mockinsurance.models.generated.ResponseConsentV3;
import com.raidiam.trustframework.mockinsurance.models.generated.UpdateConsent;
import com.raidiam.trustframework.mockinsurance.services.ConsentService;
import com.raidiam.trustframework.mockinsurance.utils.InsuranceLambdaUtils;
import io.micronaut.http.HttpRequest;
import io.micronaut.http.HttpResponse;
import io.micronaut.http.HttpStatus;
import io.micronaut.http.annotation.*;
import io.micronaut.scheduling.TaskExecutors;
import io.micronaut.scheduling.annotation.ExecuteOn;
import io.micronaut.security.annotation.Secured;
import jakarta.inject.Inject;
import jakarta.validation.constraints.Max;
import jakarta.validation.constraints.Min;

import org.slf4j.Logger;
import org.slf4j.LoggerFactory;

import java.util.List;

@ExecuteOn(TaskExecutors.BLOCKING)
@Secured({"CONSENTS_MANAGE", "CONSENTS_FULL_MANAGE"})
@Controller("/open-insurance/consents")
public class ConsentController extends BaseInsuranceController {

    private static final Logger LOG = LoggerFactory.getLogger(ConsentController.class);

    @Inject
    private ConsentService service;

    @Post("/v2/consents")
    @Status(HttpStatus.CREATED)
    @ResponseErrorWithRequestDateTime
    @SignedResponse
    @Idempotent
    @RequiredAuthenticationGrant(AuthenticationGrant.CLIENT_CREDENTIALS)
    public ResponseConsent createConsent(@Body CreateConsent body, HttpRequest<?> request) {
        var callerInfo = InsuranceLambdaUtils.getRequestMeta(request);
        String clientId = callerInfo.getClientId();
        LOG.info("Creating new consent for client {} v2", clientId);
        InsuranceLambdaUtils.logObject(mapper, body);
        ResponseConsent response = service.createConsent(body, clientId).toResponse();
        InsuranceLambdaUtils.decorateResponse(response::setLinks, appBaseUrl + request.getPath() + "/" + response.getData().getConsentId());
        return response;
    }

    @Post("/v3/consents")
    @Status(HttpStatus.CREATED)
    @ResponseErrorWithRequestDateTime
    @SignedResponse
    @Idempotent
    @RequiredAuthenticationGrant(AuthenticationGrant.CLIENT_CREDENTIALS)
    public ResponseConsentV3 createConsentV3(@Body CreateConsentV3 body, HttpRequest<?> request) {
        var callerInfo = InsuranceLambdaUtils.getRequestMeta(request);
        String clientId = callerInfo.getClientId();
        LOG.info("Creating new consent for client {} v3", clientId);
        InsuranceLambdaUtils.logObject(mapper, body);
        ResponseConsentV3 response = service.createConsentV3(body, clientId).toResponseV3();
        InsuranceLambdaUtils.decorateResponseSimpleLinkMeta(response::setLinks, response::setMeta, appBaseUrl + request.getPath() + "/" + response.getData().getConsentId());
        InsuranceLambdaUtils.logObject(mapper, response);
        return response;
    }

    @Put("/v2/consents/{consentId}")
    @Secured({"CONSENTS_FULL_MANAGE"})
    @ResponseErrorWithRequestDateTime
    @SignedResponse
    @RequiredAuthenticationGrant(AuthenticationGrant.CLIENT_CREDENTIALS)
    public ResponseConsent putConsentV2(@PathVariable("consentId") String consentId, @Body UpdateConsent request) {
        LOG.info("Updating consent {} v2", consentId);
        InsuranceLambdaUtils.logObject(mapper, request);
        var resp = service.updateConsent(consentId, request);
        InsuranceLambdaUtils.logObject(mapper, resp);
        return resp;
    }

    @Put("/v3/consents/{consentId}")
    @Secured({"CONSENTS_FULL_MANAGE"})
    @ResponseErrorWithRequestDateTime
    @SignedResponse
    @RequiredAuthenticationGrant(AuthenticationGrant.CLIENT_CREDENTIALS)
    public ResponseConsentV3 putConsentV3(@PathVariable("consentId") String consentId, @Body UpdateConsent request) {
        LOG.info("Updating consent {} v3", consentId);
        InsuranceLambdaUtils.logObject(mapper, request);
        var resp = service.updateConsentV3(consentId, request);
        InsuranceLambdaUtils.logObject(mapper, resp);
        return resp;
    }

    @Get("/v2/consents/{consentId}")
    @ResponseErrorWithRequestDateTime
    @SignedResponse
    @RequiredAuthenticationGrant(AuthenticationGrant.CLIENT_CREDENTIALS)
    public ResponseConsent getConsent(@PathVariable("consentId") String consentId, HttpRequest<?> request) {
        LOG.info("Looking up consent {} v2", consentId);
        var callerInfo = InsuranceLambdaUtils.getRequestMeta(request);
        List<String> roles = callerInfo.getRoles();
        if (roles.contains("CONSENTS_FULL_MANAGE")) {
            LOG.info("OP making call - return full response");
            var response = service.getFullConsent(consentId);
            InsuranceLambdaUtils.decorateResponse(response::setLinks, appBaseUrl + request.getPath());
            InsuranceLambdaUtils.logObject(mapper, response);
            return response;
        }

        var response = service.getConsent(consentId, callerInfo.getClientId());
        InsuranceLambdaUtils.decorateResponse(response::setLinks, appBaseUrl + request.getPath());
        LOG.info("External client making call - return partial response");
        InsuranceLambdaUtils.logObject(mapper, response);
        return response;
    }

    @Get("/v3/consents/{consentId}")
    @ResponseErrorWithRequestDateTime
    @SignedResponse
    @RequiredAuthenticationGrant(AuthenticationGrant.CLIENT_CREDENTIALS)
    public ResponseConsentV3 getConsentV3(@PathVariable("consentId") String consentId, HttpRequest<?> request) {
        LOG.info("Looking up consent {} v3", consentId);
        var callerInfo = InsuranceLambdaUtils.getRequestMeta(request);
        List<String> roles = callerInfo.getRoles();
        if (roles.contains("CONSENTS_FULL_MANAGE")) {
            LOG.info("OP making call - return full response");
            var response = service.getFullConsentV3(consentId);
            InsuranceLambdaUtils.decorateResponseSimpleLinkMeta(response::setLinks, response::setMeta, appBaseUrl + request.getPath());
            InsuranceLambdaUtils.logObject(mapper, response);
            return response;
        }

        var response = service.getConsentV3(consentId, callerInfo.getClientId());
        InsuranceLambdaUtils.decorateResponseSimpleLinkMeta(response::setLinks, response::setMeta, appBaseUrl + request.getPath());
        LOG.info("External client making call - return partial response");
        InsuranceLambdaUtils.logObject(mapper, response);
        return response;
    }

    @Delete("/v{version}/consents/{consentId}")
    @Status(HttpStatus.NO_CONTENT)
    @RequiredAuthenticationGrant(AuthenticationGrant.CLIENT_CREDENTIALS)
    public HttpResponse<Object> delete(@PathVariable("version") @Min(1) @Max(3) int version, @PathVariable("consentId") String consentId, HttpRequest<?> request) {
        LOG.info("Deleting consent v{} {}", version, consentId);
        InsuranceLambdaUtils.RequestMeta requestMeta = InsuranceLambdaUtils.getRequestMeta(request);
        service.deleteConsent(consentId, requestMeta.getClientId());
        LOG.info("Returning 204 No Content");
        return HttpResponse.noContent();
    }
}
