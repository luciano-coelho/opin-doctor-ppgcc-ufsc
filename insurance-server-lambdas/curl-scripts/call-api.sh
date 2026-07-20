# Script para simular requisição à API protegida
# Substitua <SEU_TOKEN> pelo token obtido no passo anterior

curl -X POST \
  http://localhost:8080/open-insurance/quote-patrimonial/v1/lead/request \
  -H "Authorization: Bearer <SEU_TOKEN>" \
  -H "x-fapi-interaction-id: f3f14ffe-b573-46ee-8e8c-5a04991d5a0f" \
  -H "x-idempotency-key: f3f14ffe-b573-46ee-8e8c-5a04991d5a0f" \
  -H "Content-Type: application/json" \
  -d @request-body.json
