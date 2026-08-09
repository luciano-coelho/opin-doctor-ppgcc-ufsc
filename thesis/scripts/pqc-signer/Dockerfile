# Node >=24.7 has native ML-DSA support in node:crypto, which jose v6
# delegates to -- see sign.mjs. Built once, run once per signature (docker
# run --rm -i mockopin-pqc-signer), invoked from opin_flow.py.
FROM node:24-alpine
WORKDIR /app
COPY package.json .
RUN npm install --omit=dev
COPY sign.mjs .
ENTRYPOINT ["node", "sign.mjs"]
