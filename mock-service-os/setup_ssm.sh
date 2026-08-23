#!/usr/bin/env bash

CONFIG_FILE_PATH="/init/config/config.txt"
# Create or replace the config file.
: > "$CONFIG_FILE_PATH"

printf "Configuring localstack components..."

set -x
REGION=us-east-1

awslocal ssm put-parameter \
    --name "/local/op_fapi_client_config/issuer" \
    --value "auth.local" \
    --type "SecureString" \
    --overwrite \
    --region "${REGION}"
# classic (RSA-4096, Experiment 1), pqc (ML-DSA-65, Experiment 2), or hybrid
# (Experiment 3) -- picks which cert pair mock_as's InsurerAdapter presents
# for its own AS->RS backend calls (rendering the consent screen, updating
# consent status). Previously always classical regardless of CRYPTO_PROFILE
# -- see thesis/results/v2/experiment2 - PQC/DECISIONS.md, Decision 10. The
# hybrid case was discovered mid-Etapa-7, not planned in Etapa 6: this
# backend leg turned out not to be optional plumbing -- getConsent() is on
# the critical path for rendering the login/consent screen, so the
# gateway's hybrid AND gate (thesis/results/v4/DECISIONS.md, Etapa 6)
# rejected the AS's own classical-only op.crt with a TLS "bad certificate"
# alert the moment a real hybrid-mode flow exercised it.
TRANSPORT_CERT_DIR="/init/certs/client_classic"
if [ "${CRYPTO_PROFILE:-classic}" = "pqc" ]; then
  TRANSPORT_CERT_DIR="/init/certs/client_pqc"
elif [ "${CRYPTO_PROFILE:-classic}" = "hybrid" ]; then
  TRANSPORT_CERT_DIR="/init/certs/client_hybrid"
fi
echo "Setting AS transport_certificate/transport_key from ${TRANSPORT_CERT_DIR}.* (CRYPTO_PROFILE=${CRYPTO_PROFILE:-classic})"
awslocal ssm put-parameter \
    --name "/local/op_fapi_client_config/transport_certificate" \
    --value "$(cat ${TRANSPORT_CERT_DIR}.crt)" \
    --type "SecureString" \
    --overwrite \
    --region "${REGION}"
awslocal ssm put-parameter \
    --name "/local/op_fapi_client_config/transport_key" \
    --value "$(cat ${TRANSPORT_CERT_DIR}.key)" \
    --type "SecureString" \
    --overwrite \
    --region "${REGION}"

 awslocal s3 mb s3://keystore
 awslocal s3 website s3://keystore --index-document jwks.json
 awslocal s3 cp /init/ssa/jwks.json s3://keystore/jwks.json --content-type application/json
 awslocal s3api put-object-acl --bucket keystore --key jwks.json --acl public-read

 awslocal s3 cp /init/ssa/private_jwk.json s3://keystore/private_jwk.json --content-type application/json
 awslocal s3api put-object-acl --bucket keystore --key private_jwk.json --acl public-read

echo "ready" > $CONFIG_FILE_PATH
