#!/usr/bin/env bash
# v9, piloto: higiene de reprodutibilidade (Etapa 1, adendo, item 3d).
#
# Achado real de processo (rodada de verificacao independente pos-Etapa
# 1): `docker compose down`, SEM `--profile main`, NAO remove containers
# que foram subidos COM esse profile (auth/mongo_seed/mockapi/psql/
# localstack/mongodb, docker-compose.yml do insurance-server-lambdas e
# do mock-service-os) -- o comando sai com codigo 0, reporta sucesso, e
# nao faz nada. Confirmado ao vivo: um teardown manual com o comando
# "nu" deixou tudo rodando; so `--profile main down` removeu de verdade.
#
# Uso: teardown_backend_main.sh <diretorio-do-compose>
# Ex.:  teardown_backend_main.sh ../../../../insurance-server-lambdas
#       teardown_backend_main.sh ../../../../mock-service-os
set -euo pipefail

if [ "$#" -ne 1 ]; then
  echo "uso: $0 <diretorio-do-compose>" >&2
  exit 2
fi

COMPOSE_DIR="$1"
if [ ! -f "$COMPOSE_DIR/docker-compose.yml" ]; then
  echo "FATAL: $COMPOSE_DIR/docker-compose.yml nao existe" >&2
  exit 2
fi

cd "$COMPOSE_DIR"
echo "== teardown_backend_main: docker compose --profile main down em $(pwd) =="
docker compose --profile main down
