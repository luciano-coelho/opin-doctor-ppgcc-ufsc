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
import java.security.MessageDigest;
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
            case "hybrid" -> loadHybridSigner();
            default -> throw new IllegalStateException(
                    "Unknown mockinsurance.crypto-profile '" + cryptoProfile + "', expected classic, pqc, or hybrid");
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

    // Strong Nesting (PS256 + ML-DSA-65), per thesis/results/v4/
    // Arquitetura_Tecnica_Experimento3_Strong_Nesting.docx:
    //   sigma1 = PS256_sign(message)
    //   sigma2 = ML-DSA-65_sign(message || sigma1)   -- raw byte
    //            concatenation, not base64 (same convention as the AS's
    //            mock_as/utils/opin/hybridSigning.js, confirmed with the
    //            user to be identical across Etapas 2/3/6)
    //   signature = base64url(sigma1 || sigma2)
    //
    // Unlike the AS (oidc-provider/jose can't be told to produce this alg,
    // forcing an intercept-and-replace approach after the fact -- see
    // DECISIONS.md), this service already builds the JWS header/signing
    // input itself (see sign() above) before calling out to a JwsSigner,
    // so there's no library alg-name validation to work around here: the
    // header this produces says "MLDSA65-RSA2048-PSS-SHA256" from the
    // start, no replacement step needed.
    private JwsSigner loadHybridSigner() throws Exception {
        Map<?, ?> hybridJson = objectMapper.readValue(readResource("hybrid.json"), Map.class);
        Map<?, ?> classicJwk = (Map<?, ?>) hybridJson.get("classicSigningKey");
        Map<?, ?> pqcJwk = (Map<?, ?>) hybridJson.get("pqcSigningKey");

        RSAKey rsaKey = RSAKey.parse(objectMapper.writeValueAsString(classicJwk));
        RSASSASigner rsaSigner = new RSASSASigner(rsaKey);
        JWSHeader nimbusHeader = new JWSHeader.Builder(JWSAlgorithm.PS256).build();
        // Decoded directly from the JWK's own "n" field (not
        // rsaKey.toRSAPublicKey().getModulus().toByteArray()) -- BigInteger's
        // two's-complement encoding adds a leading zero byte whenever the
        // modulus's high bit is set (true for almost every real RSA-2048
        // key), which would silently give 257 bytes instead of 256 and a
        // hybrid kid that can never match what mock_as computes from the
        // same key's "n" field. JWK's own encoding is already the minimal
        // unsigned form at the key's natural size.
        byte[] classicPkBytes = Base64.getUrlDecoder().decode((String) classicJwk.get("n"));

        byte[] pkcs8 = Base64.getDecoder().decode((String) pqcJwk.get("pkcs8PrivateKeyBase64"));
        byte[] x509 = Base64.getDecoder().decode((String) pqcJwk.get("x509PublicKeyBase64"));
        KeyFactory keyFactory = KeyFactory.getInstance("ML-DSA", "BC");
        PrivateKey pqcPrivateKey = keyFactory.generatePrivate(new PKCS8EncodedKeySpec(pkcs8));
        PublicKey pqcPublicKey = keyFactory.generatePublic(new X509EncodedKeySpec(x509));
        byte[] pqcPkBytes = SubjectPublicKeyInfo.getInstance(pqcPublicKey.getEncoded()).getPublicKeyData().getBytes();

        if (classicPkBytes.length != 256) {
            throw new IllegalStateException("hybrid: expected 256-byte classic public key, got " + classicPkBytes.length);
        }
        if (pqcPkBytes.length != 1952) {
            throw new IllegalStateException("hybrid: expected 1952-byte ML-DSA-65 public key, got " + pqcPkBytes.length);
        }

        // pk_hybrid = classicPk || pqcPk (Etapa 5's exact composition),
        // single kid derived from it -- same scheme as the AS's
        // HYBRID_KID, computed independently here from the RS's own two
        // keys (a different identity from the AS's, correctly: kid
        // identifies *this participant's* composed public key, not a
        // value shared across participants).
        byte[] hybridPk = new byte[classicPkBytes.length + pqcPkBytes.length];
        System.arraycopy(classicPkBytes, 0, hybridPk, 0, classicPkBytes.length);
        System.arraycopy(pqcPkBytes, 0, hybridPk, classicPkBytes.length, pqcPkBytes.length);
        MessageDigest sha256 = MessageDigest.getInstance("SHA-256");
        String hybridKid = base64Url(sha256.digest(hybridPk));

        return new JwsSigner() {
            public String alg() {
                return "MLDSA65-RSA2048-PSS-SHA256";
            }

            public String kid() {
                return hybridKid;
            }

            public String signToBase64Url(byte[] signingInput) throws Exception {
                byte[] sigma1 = rsaSigner.sign(nimbusHeader, signingInput).decode();

                byte[] messagePlusSigma1 = new byte[signingInput.length + sigma1.length];
                System.arraycopy(signingInput, 0, messagePlusSigma1, 0, signingInput.length);
                System.arraycopy(sigma1, 0, messagePlusSigma1, signingInput.length, sigma1.length);

                Signature signature = Signature.getInstance("ML-DSA", "BC");
                signature.initSign(pqcPrivateKey);
                signature.update(messagePlusSigma1);
                byte[] sigma2 = signature.sign();

                byte[] combined = new byte[sigma1.length + sigma2.length];
                System.arraycopy(sigma1, 0, combined, 0, sigma1.length);
                System.arraycopy(sigma2, 0, combined, sigma1.length, sigma2.length);
                return base64Url(combined);
            }

            public Map<String, Object> publicJwk() {
                Map<String, Object> jwk = new LinkedHashMap<>();
                jwk.put("kty", "HYBRID");
                jwk.put("alg", "MLDSA65-RSA2048-PSS-SHA256");
                jwk.put("use", "sig");
                jwk.put("kid", hybridKid);
                jwk.put("pk_hybrid", base64Url(hybridPk));
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
