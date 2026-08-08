package com.raidiam.trustframework.mockinsurance.fapi;

import java.lang.annotation.ElementType;
import java.lang.annotation.Retention;
import java.lang.annotation.Target;

import static java.lang.annotation.RetentionPolicy.RUNTIME;

/**
 * Marks a controller method whose successful JSON response must be wrapped as a
 * compact JWS (Content-Type: application/jwt), per the Open Finance Brasil FAPI
 * response-signing requirement -- see ResponseSigningFilter.
 */
@Retention(RUNTIME)
@Target(ElementType.METHOD)
public @interface SignedResponse {
}
