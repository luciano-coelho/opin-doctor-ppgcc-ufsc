# Script to simulate a request to the protected API
# Replace <YOUR_TOKEN> with the token obtained in the previous step

curl -X POST \
  http://localhost:8080/open-insurance/quote-patrimonial/v1/lead/request \
  -H "Authorization: Bearer <YOUR_TOKEN>" \
  -H "x-fapi-interaction-id: f3f14ffe-b573-46ee-8e8c-5a04991d5a0f" \
  -H "x-idempotency-key: f3f14ffe-b573-46ee-8e8c-5a04991d5a0f" \
  -H "Content-Type: application/json" \
  -d @request-body.json
