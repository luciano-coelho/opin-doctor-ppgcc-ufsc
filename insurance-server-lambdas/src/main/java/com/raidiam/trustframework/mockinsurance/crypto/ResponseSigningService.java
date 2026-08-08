package com.raidiam.trustframework.mockinsurance.crypto;

import com.fasterxml.jackson.databind.ObjectMapper;
import com.nimbusds.jose.JOSEException;
import com.nimbusds.jose.JWSAlgorithm;
import com.nimbusds.jose.JWSHeader;
import com.nimbusds.jose.crypto.RSASSASigner;
import com.nimbusds.jose.jwk.RSAKey;
import io.micronaut.context.annotation.Value;
import jakarta.annotation.PostConstruct;
import jakarta.inject.Inject;
import jakarta.inject.Singleton;
import org.bouncycastle.asn1.x509.SubjectPublicKeyInfo;
import org.bouncycastle.jce.provider.BouncyCastleProvider;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;

import java.io.InputStream;
import java.nio.charset.StandardCharsets;
import java.security.KeyFactory;
import java.security.PrivateKey;
import java.security.PublicKey;
import java.security.Security;
import java.security.Signature;
import java.security.spec.PKCS8EncodedKeySpec;
import java.security.spec.X509EncodedKeySpec;
import java.util.Base64;
import java.util.LinkedHashMap;
import java.util.Map;

/**
 * Signs Consents/Person API response bodies as a compact JWS, per the Open
 * Finance Brasil FAPI response-signing requirement (which the MockOPIN
 * Resource Server never actually implemented -- see thesis/results/experiment2
 * - PQC/DECISIONS.md).
 * <p>
 * The signing algorithm is picked once at boot from {@code CRYPTO_PROFILE}
 * (classic -> PS256/RSA via Nimbus, pqc -> ML-DSA-65 via BouncyCastle 1.79's
 * JCA provider -- Nimbus JOSE+JWT has no ML-DSA support in any released
 * version as of 2026-08, so that path is hand-rolled), mirroring the same
 * externalized-profile architecture used for mock_as (mock-service-os/mock_as/
 * crypto-profiles/). Both modes sign for real (rather than classic being a
 * no-op) so that a byte/latency comparison between Experiment 1 and
 * Experiment 2 isolates the signing algorithm as the only variable.
 */
@Singleton
public class ResponseSigningService {

    private static final Logger LOG = LoggerFactory.getLogger(ResponseSigningService.class);

    @Value("${mockinsurance.crypto-profile:classic}")
    private String cryptoProfile;

    @Inject
    private ObjectMapper objectMapper;

    private JwsSigner signer;

    private interface JwsSigner {
        String alg();

        String kid();

        String signToBase64Url(byte[] signingInput) throws Exception;

        Map<String, Object> publicJwk();
    }

    @PostConstruct
    void init() throws Exception {
        if (Security.getProvider("BC") == null) {
            Security.addProvider(new BouncyCastleProvider());
        }
        this.signer = switch (cryptoProfile) {
            case "classic" -> loadPs256Signer();
            case "pqc" -> loadMlDsa65Signer();
            default -> throw new IllegalStateException(
                    "Unknown mockinsurance.crypto-profile '" + cryptoProfile + "', expected classic or pqc");
        };
        LOG.info("Response signing profile: {} (alg: {}, kid: {})", cryptoProfile, signer.alg(), signer.kid());
    }

    public String sign(byte[] jsonPayload) throws Exception {
        Map<String, Object> header = new LinkedHashMap<>();
        header.put("alg", signer.alg());
        header.put("kid", signer.kid());
        header.put("typ", "JWT");
        String headerB64 = base64Url(objectMapper.writeValueAsBytes(header));
        String payloadB64 = base64Url(jsonPayload);
        byte[] signingInput = (headerB64 + "." + payloadB64).getBytes(StandardCharsets.US_ASCII);
        String sigB64 = signer.signToBase64Url(signingInput);
        return headerB64 + "." + payloadB64 + "." + sigB64;
    }

    public Map<String, Object> getPublicJwk() {
        return signer.publicJwk();
    }

    private static String base64Url(byte[] bytes) {
        return Base64.getUrlEncoder().withoutPadding().encodeToString(bytes);
    }

    private JwsSigner loadPs256Signer() throws Exception {
        RSAKey rsaKey = RSAKey.parse(readResource("classic.json"));
        RSASSASigner rsaSigner = new RSASSASigner(rsaKey);
        JWSHeader nimbusHeader = new JWSHeader.Builder(JWSAlgorithm.PS256).build();

        return new JwsSigner() {
            public String alg() {
                return "PS256";
            }

            public String kid() {
                return rsaKey.getKeyID();
            }

            public String signToBase64Url(byte[] signingInput) throws JOSEException {
                return rsaSigner.sign(nimbusHeader, signingInput).toString();
            }

            public Map<String, Object> publicJwk() {
                return rsaKey.toPublicJWK().toJSONObject();
            }
        };
    }

    private JwsSigner loadMlDsa65Signer() throws Exception {
        Map<?, ?> json = objectMapper.readValue(readResource("pqc.json"), Map.class);
        String kid = (String) json.get("kid");
        byte[] pkcs8 = Base64.getDecoder().decode((String) json.get("pkcs8PrivateKeyBase64"));
        byte[] x509 = Base64.getDecoder().decode((String) json.get("x509PublicKeyBase64"));

        KeyFactory keyFactory = KeyFactory.getInstance("ML-DSA", "BC");
        PrivateKey privateKey = keyFactory.generatePrivate(new PKCS8EncodedKeySpec(pkcs8));
        PublicKey publicKey = keyFactory.generatePublic(new X509EncodedKeySpec(x509));
        byte[] rawPub = SubjectPublicKeyInfo.getInstance(publicKey.getEncoded()).getPublicKeyData().getBytes();

        return new JwsSigner() {
            public String alg() {
                return "ML-DSA-65";
            }

            public String kid() {
                return kid;
            }

            public String signToBase64Url(byte[] signingInput) throws Exception {
                Signature signature = Signature.getInstance("ML-DSA", "BC");
                signature.initSign(privateKey);
                signature.update(signingInput);
                return base64Url(signature.sign());
            }

            public Map<String, Object> publicJwk() {
                Map<String, Object> jwk = new LinkedHashMap<>();
                jwk.put("kty", "AKP");
                jwk.put("alg", "ML-DSA-65");
                jwk.put("use", "sig");
                jwk.put("kid", kid);
                jwk.put("pub", base64Url(rawPub));
                return jwk;
            }
        };
    }

    private String readResource(String name) throws Exception {
        try (InputStream in = getClass().getResourceAsStream("/crypto-profiles/" + name)) {
            if (in == null) {
                throw new IllegalStateException("Missing classpath resource /crypto-profiles/" + name);
            }
            return new String(in.readAllBytes(), StandardCharsets.UTF_8);
        }
    }
}
