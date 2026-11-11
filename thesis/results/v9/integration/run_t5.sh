#!/usr/bin/env bash
# v9, Fase 1, T5: builda o toolchain corrigido, o gateway e o proxy desta
# pasta, gera certificados efemeros (make certs), e roda os 4 perfis
# (classico, pqc, hibrido-v8, hibrido-and) ponta a ponta, localmente, em
# conteineres. Sem bind mount em lugar nenhum (nao funciona neste
# ambiente -- ver DECISIONS.md da v9, Decisao 11); certificados entram
# nas imagens via COPY, copiados antes do build por este script.
set -euo pipefail
cd "$(dirname "$0")"

ALPINE_IMAGE="alpine:3.24@sha256:be2656061b536c1883c4034790e21d0a09c5aaaf51968b89368a3c0371ea2c9a"
NETWORK=mockopin-v9-net
IMAGE_GATEWAY=mockopin-v9-gateway
IMAGE_PROXY=mockopin-v9-proxy
PROFILES=(classico pqc hibrido-v8 hibrido-and)
# Decisao 125 (pre-voo local, achado real -- Decisao 122): um container
# "mtls"/"v9-mtls" ou a rede "mockopin-v9-net" de uma rodada ANTERIOR
# (deste script ou de outro driver local) deixados de pe fazem a
# resolucao de nome ficar nao-deterministica e corrompem silenciosamente
# esta rodada -- aborta ANTES de buildar qualquer coisa, nunca limpa
# sozinho. Mesmos padroes de nome que preflight.check_no_orphan_docker_
# resources() usa pro lado Python.
ORPHAN_CONTAINERS=$(docker ps -a --format '{{.Names}}' | grep -xE 'v9-mtls|mtls|auth|mongo_seed|mongo[123]|mockapi|tls_kem_proxy_run|pqc_signer_service_run' || true)
ORPHAN_NETWORKS=$(docker network ls --format '{{.Name}}' | grep -xF "$NETWORK" || true)
if [ -n "$ORPHAN_CONTAINERS" ] || [ -n "$ORPHAN_NETWORKS" ]; then
  echo "FATAL (pre-voo, Decisao 125): residuo de rodada anterior encontrado -- limpe antes de repetir:" >&2
  [ -n "$ORPHAN_CONTAINERS" ] && echo "  containers: $ORPHAN_CONTAINERS" >&2
  [ -n "$ORPHAN_NETWORKS" ] && echo "  redes: $ORPHAN_NETWORKS" >&2
  exit 1
fi

echo "== T5: gerando certificados efemeros (make certs em ../certs) =="
( cd ../certs && make certs )

echo "== Copiando certificados para os contextos de build (COPY, nunca bind mount) =="
rm -rf gateway/certs proxy/certs
cp -r ../certs/generated gateway/certs
cp -r ../certs/generated proxy/certs

echo "== Buildando o toolchain Go corrigido (mecanismo AND) =="
docker build -q -t mockopin-v9-toolchain -f ../toolchain/Dockerfile ../toolchain >/dev/null

echo "== Buildando gateway e proxy =="
docker build -q -t "$IMAGE_GATEWAY" gateway >/dev/null
docker build -q -t "$IMAGE_PROXY" proxy >/dev/null

docker network inspect "$NETWORK" >/dev/null 2>&1 || docker network create "$NETWORK" >/dev/null

declare -A RESULTS

for profile in "${PROFILES[@]}"; do
  echo ""
  echo "== Perfil: $profile =="
  docker rm -f mtls >/dev/null 2>&1 || true
  docker run -d --rm --name mtls --network "$NETWORK" -e CRYPTO_PROFILE="$profile" "$IMAGE_GATEWAY" >/dev/null

  ready=0
  for _ in $(seq 1 20); do
    if docker run --rm --network "$NETWORK" "$ALPINE_IMAGE" sh -c "nc -z mtls 443" >/dev/null 2>&1; then
      ready=1
      break
    fi
    sleep 0.5
  done
  if [ "$ready" -ne 1 ]; then
    echo "FATAL: gateway (perfil $profile) nao ficou pronto para aceitar conexoes"
    docker logs mtls 2>&1 || true
    docker rm -f mtls >/dev/null 2>&1 || true
    RESULTS[$profile]="FALHA (gateway nao respondeu)"
    continue
  fi

  set +e
  OUTPUT=$(docker run --rm --network "$NETWORK" "$IMAGE_PROXY" -profile "$profile" -target mtls:443 2>&1)
  STATUS=$?
  set -e

  echo "$OUTPUT"
  if [ "$STATUS" -eq 0 ] && echo "$OUTPUT" | grep -q "^RESULT profile=$profile"; then
    RESULTS[$profile]=$(echo "$OUTPUT" | grep "^RESULT profile=$profile")
  else
    RESULTS[$profile]="FALHA (status=$STATUS)"
  fi

  echo "---- log do gateway ($profile) ----"
  docker logs mtls 2>&1 | tail -5
  docker rm -f mtls >/dev/null 2>&1 || true
done

echo ""
echo "== Relatorio final T5 =="
for profile in "${PROFILES[@]}"; do
  echo "$profile: ${RESULTS[$profile]}"
done

echo ""
echo "== Limpeza =="
docker network rm "$NETWORK" >/dev/null 2>&1 || true
rm -rf gateway/certs proxy/certs
( cd ../certs && make clean )
echo "done."
