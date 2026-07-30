#!/bin/bash
echo "Starting import"
sleep 15

echo "Update the JWKS of client one and two"
jq --argjson jwks1 "$(jq . < $2/certs/client_one_pub.jwks)" \
   --argjson jwks2 "$(jq . < $2/certs/client_two_pub.jwks)" \
   '.[0].payload.jwks = $jwks1 | .[1].payload.jwks = $jwks2' \
   $2/init_clients.json > $2/init_clients.json.tmp && mv $2/init_clients.json.tmp $2/init_clients.json

# mongosh and the mongoimport/database-tools binaries use different flag
# names for the exact same thing (--tls/--tlsCAFile vs. the legacy
# --ssl/--sslCAFile) even though they ship in the same mongo:latest image.
MONGOSH_TLS_OPTS="--tls --tlsCAFile /certs/ca.crt"
MONGOIMPORT_TLS_OPTS="--ssl --sslCAFile /certs/ca.crt"

mongosh --host "$1" $MONGOSH_TLS_OPTS --eval "db = db.getSiblingDB('openid-server'); db.client.drop()"
mongoimport --host $1 $MONGOIMPORT_TLS_OPTS --db openid-server --collection client --type json --file $2/init_clients.json --jsonArray
mongoimport --host $1 $MONGOIMPORT_TLS_OPTS --db accounts --collection accounts --type json --file $2/init_accounts.json --jsonArray
mongoimport --host $1 $MONGOIMPORT_TLS_OPTS --db accounts --collection credentials --type json --file $2/init_credentials.json --jsonArray

echo "Stopping Import"
