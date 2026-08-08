package com.raidiam.trustframework.mockinsurance.fapi;

import com.fasterxml.jackson.databind.ObjectMapper;
import com.nimbusds.jose.util.Pair;
import com.raidiam.trustframework.mockinsurance.crypto.ResponseSigningService;
import com.raidiam.trustframework.mockinsurance.utils.AnnotationsUtil;
import io.micronaut.context.ApplicationContext;
import io.micronaut.http.HttpMethod;
import io.micronaut.http.HttpRequest;
import io.micronaut.http.MediaType;
import io.micronaut.http.MutableHttpResponse;
import io.micronaut.http.annotation.Filter;
import io.micronaut.http.filter.HttpServerFilter;
import io.micronaut.http.filter.ServerFilterChain;
import io.micronaut.http.filter.ServerFilterPhase;
import jakarta.annotation.PostConstruct;
import jakarta.inject.Inject;
import org.reactivestreams.Publisher;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import reactor.core.publisher.Mono;

import java.util.ArrayList;
import java.util.LinkedHashMap;
import java.util.LinkedList;
import java.util.List;
import java.util.Map;

/**
 * Wraps the response body of endpoints annotated {@link SignedResponse} as a
 * compact JWS, per the Open Finance Brasil FAPI response-signing requirement.
 * Only applies to successful (2xx) responses that actually have a body --
 * errors and 204 No Content pass through unsigned, same as the real API
 * (error payloads aren't part of the signed-response requirement).
 */
@Filter("/**")
public class ResponseSigningFilter implements HttpServerFilter {

    private static final Logger LOG = LoggerFactory.getLogger(ResponseSigningFilter.class);

    private final ApplicationContext applicationContext;
    private final List<Pair<HttpMethod, String>> signedResponseRegexes = new LinkedList<>();

    @Inject
    private ResponseSigningService responseSigningService;

    @Inject
    private ObjectMapper objectMapper;

    @Inject
    public ResponseSigningFilter(ApplicationContext applicationContext) {
        this.applicationContext = applicationContext;
    }

    @PostConstruct
    private void init() {
        AnnotationsUtil.performActionsOnControllerMethodByAnnotation(applicationContext, SignedResponse.class, (fullPath, httpMethod, extractedAnnotation) -> {
            signedResponseRegexes.add(Pair.of(httpMethod, fullPath));
            LOG.info("Added signed-response path {} - {}", httpMethod, fullPath);
        });
    }

    private boolean isRequired(HttpRequest<?> request) {
        for (Pair<HttpMethod, String> rule : signedResponseRegexes) {
            if (request.getMethod() == rule.getLeft() && request.getPath().matches(rule.getRight())) {
                return true;
            }
        }
        return false;
    }

    @Override
    public Publisher<MutableHttpResponse<?>> doFilter(HttpRequest<?> request, ServerFilterChain chain) {
        if (!isRequired(request)) {
            return chain.proceed(request);
        }

        return Mono.from(chain.proceed(request)).map(response -> signIfEligible(request, response));
    }

    private MutableHttpResponse<?> signIfEligible(HttpRequest<?> request, MutableHttpResponse<?> response) {
        int status = response.getStatus().getCode();
        if (status < 200 || status >= 300) {
            return response;
        }

        var body = response.getBody(Object.class);
        if (body.isEmpty()) {
            return response;
        }

        try {
            byte[] jsonBytes = objectMapper.writeValueAsBytes(body.get());
            String jws = responseSigningService.sign(jsonBytes);
            // A fresh response, not response.body(jws): Micronaut resolves the
            // message body writer from the original (POJO-typed) response, and
            // mutating that same instance's body in place makes it try to
            // re-run the POJO codec against the JWS string and fail. Same
            // pattern IdempotencyFilter uses for its cache-replay path.
            MutableHttpResponse<Object> signed = io.micronaut.http.HttpResponse.status(response.getStatus());
            // Snapshot into a plain map first: copying while iterating the
            // live (possibly lazily-populated) response headers directly
            // throws ConcurrentModificationException.
            Map<String, List<String>> headerSnapshot = new LinkedHashMap<>();
            response.getHeaders().forEach(entry -> headerSnapshot.put(entry.getKey(), new ArrayList<>(entry.getValue())));
            headerSnapshot.forEach((name, values) -> values.forEach(value -> signed.getHeaders().add(name, value)));
            // application/jwt has no registered MessageBodyWriter, so Micronaut
            // falls back to the default JSON writer and fails trying to encode
            // the JWS string/bytes as JSON. text/plain does have a writer that
            // emits the body as-is; the actual Content-Type header is then
            // overwritten to the correct value afterwards.
            signed.body(jws.getBytes(java.nio.charset.StandardCharsets.UTF_8)).contentType(MediaType.TEXT_PLAIN_TYPE);
            signed.getHeaders().set(io.micronaut.http.HttpHeaders.CONTENT_TYPE, "application/jwt");
            return signed;
        } catch (Exception e) {
            LOG.error("Failed to sign response body for {} {}", request.getMethod(), request.getPath(), e);
            throw new RuntimeException(e);
        }
    }

    @Override
    public int getOrder() {
        return ServerFilterPhase.RENDERING.before();
    }
}
