# Script para obter o token de autenticação
# Ajuste os valores de client_assertion conforme necessário

curl -X POST \
  http://localhost:3000/token \
  -H "Accept: application/json" \
  -H "Content-Type: application/x-www-form-urlencoded;charset=UTF-8" \
  -d "grant_type=client_credentials" \
  -d "scope=quote-patrimonial-lead" \
  -d "client_assertion=<COLE_AQUI_SEU_JWT>" \
  -d "client_assertion_type=urn:ietf:params:oauth:client-assertion-type:jwt-bearer"
