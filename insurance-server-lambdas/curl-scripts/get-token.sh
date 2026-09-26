# Script to obtain the authentication token
# Adjust the client_assertion values as needed

curl -X POST \
  http://localhost:3000/token \
  -H "Accept: application/json" \
  -H "Content-Type: application/x-www-form-urlencoded;charset=UTF-8" \
  -d "grant_type=client_credentials" \
  -d "scope=quote-patrimonial-lead" \
  -d "client_assertion=<PASTE_YOUR_JWT_HERE>" \
  -d "client_assertion_type=urn:ietf:params:oauth:client-assertion-type:jwt-bearer"
