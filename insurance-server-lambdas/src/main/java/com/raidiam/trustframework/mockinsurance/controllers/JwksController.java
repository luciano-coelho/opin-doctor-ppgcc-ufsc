package com.raidiam.trustframework.mockinsurance.controllers;

import com.raidiam.trustframework.mockinsurance.crypto.ResponseSigningService;
import io.micronaut.http.annotation.Controller;
import io.micronaut.http.annotation.Get;
import io.micronaut.security.annotation.Secured;
import io.micronaut.security.rules.SecurityRule;
import jakarta.inject.Inject;

import java.util.Map;

/**
 * Publishes the Resource Server's own signing public key -- needed to verify
 * the JWS-signed Consents/Person responses (see ResponseSigningFilter). The
 * RS never exposed this before Experiment 2, since it never signed anything.
 */
@Controller("/jwks")
@Secured(SecurityRule.IS_ANONYMOUS)
public class JwksController {

    @Inject
    private ResponseSigningService responseSigningService;

    @Get
    public Map<String, Object> jwks() {
        return Map.of("keys", responseSigningService.getPublicJwks());
    }
}
