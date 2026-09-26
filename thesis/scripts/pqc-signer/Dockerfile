# Node >=24.7 has native ML-DSA support in node:crypto, which jose v6
# delegates to -- see signer_core.mjs. Two entry points share that same
# dispatch: sign.mjs (default CMD, one-shot -- `docker run --rm -i
# mockopin-pqc-signer`, unchanged since v2) and server.mjs (a persistent
# HTTP service for opin_flow.py's hot statistical loop --
# `docker run -d ... mockopin-pqc-signer node server.mjs`, overriding
# CMD).
# Pinned by digest (same reproducibility concern as mock_mtls's golang
# pin) -- lower risk than the golang RC tag (Node 24 is a stable
# LTS-track release, not a release candidate), pinned anyway for the same
# guarantee across the whole multi-day data-collection protocol.
FROM node:24-alpine@sha256:d32cdf619f63fe0471182d08996dd516c6275bb5fd31ae06e55a570bd9e1ad43
WORKDIR /app
COPY package.json .
RUN npm install --omit=dev
COPY signer_core.mjs sign.mjs server.mjs ./
CMD ["node", "sign.mjs"]
