#!/bin/bash
# Decisao 57, item 5. Passo de handshake do ensaio de infraestrutura
# (INFRA_REHEARSAL.md) -- script de verdade, testado localmente em
# loopback antes de ser entregue pro ensaio real. Para CADA um dos 4
# perfis: remove o gateway anterior, sobe com o CRYPTO_PROFILE certo,
# espera ficar pronto (com limite de tentativas), roda o cliente
# (negtest -scenario matrix), extrai a linha "connection OK" com grep
# (nunca tail -1 -- outras linhas podem aparecer antes dela), compara
# handshakeBytesIn/Out contra BASELINE_HANDSHAKE_BYTES.
#
# Uso local (loopback, testado nesta sessao -- ver saida real abaixo
# no relatorio): GATEWAY_SSH="" CLIENT_SSH="" ./rehearsal_handshake.sh
# Uso no ensaio real (AWS): GATEWAY_SSH="ssh -i <chave> ec2-user@<EIP-servidor>" \
#   CLIENT_SSH="ssh -i <chave> ec2-user@<IP-cliente-L0>" \
#   GATEWAY_HOST=<EIP-servidor> ./rehearsal_handshake.sh
set -euo pipefail

GATEWAY_SSH="${GATEWAY_SSH-}"   # vazio = roda local (sem SSH); setado = "ssh -i <chave> ec2-user@<host>"
CLIENT_SSH="${CLIENT_SSH-}"
GATEWAY_HOST="${GATEWAY_HOST:-mtls}"   # alias de rede local (loopback) ou EIP real (ensaio)
GATEWAY_CONTAINER="${GATEWAY_CONTAINER:-v9-mtls-ensaio}"
NETWORK="${NETWORK:-insurance-server-lambdas_default}"
# Decisao 72 (achado real, ao vivo, retomando a Fase A real, Passo
# 10): o default antigo (sempre `$(dirname "$0")/../../...`) so faz
# sentido rodando LOCAL (script no repo real, no laptop do operador)
# -- a copia que `deliver_source.py` entrega pro CONTROLE nunca tem
# `certs/generated` do lado dela (CLIENT_ONLY_FILES so entrega isso
# pro CLIENTE) e, mesmo que tivesse, o mount `-v $CERTS_DIR:/certs:ro`
# precisa existir no HOST que de fato roda o `docker run` (cliente/
# servidor), nunca no controle que so dispara o comando via SSH --
# mesmo raciocinio que ja corrigiu `_launch_gateway.real_certs_mount`
# na Decisao 58. Em modo remoto (CLIENT_SSH/GATEWAY_SSH setados), usa
# o caminho ABSOLUTO real (`/home/ec2-user/...` -- usuario de login
# fixo em toda instancia deste projeto, confirmado em todo outro
# lugar que faz SSH aqui) que `deliver_source.py` de fato entrega,
# NUNCA `~` -- achado real, ao vivo (retomando esta MESMA Decisao):
# `~` dentro de `-v "$VAR:..."` (as aspas duplas ja existiam no
# script, pra proteger caminhos LOCAIS do Windows com espaco) nunca e
# expandido pelo shell remoto (aspas duplas suprimem expansao de
# til), entao o Docker recebia o til LITERAL e reprovava como "nome
# de volume local invalido". Caminho absoluto elimina a ambiguidade
# de aspas por completo -- nao precisa expandir nada.
if [ -z "${CERTS_DIR-}" ]; then
  if [ -n "$CLIENT_SSH" ]; then
    CERTS_DIR="/home/ec2-user/thesis/results/v9/certs/generated"
  else
    CERTS_DIR="$(cd "$(dirname "$0")/../../certs/generated" && pwd)"
  fi
fi
if [ -z "${REAL_CERTS_DIR-}" ]; then
  if [ -n "$GATEWAY_SSH" ]; then
    REAL_CERTS_DIR="/home/ec2-user/mock-service-os/certs"
  else
    REAL_CERTS_DIR="$(cd "$(dirname "$0")/../../../../../mock-service-os/certs" && pwd)"
  fi
fi

# Decisao 73 (achado real, ao vivo, retomando AINDA a mesma Decisao
# 72/Passo 10 -- o fix de caminho acima era necessario mas nao
# suficiente): `--network $NETWORK` + os `--network-alias` do gateway
# SO existem no stack local de validacao, exatamente a mesma causa
# raiz ja corrigida em `orchestrator._launch_gateway` (Decisao 70) --
# este script tinha a MESMA logica duplicada, nunca recebeu o mesmo
# tratamento. Em modo remoto, o gateway so precisa publicar a porta
# no host (`GATEWAY_HOST` ja e um IP real, nunca um alias Docker); o
# cliente negtest disca esse IP diretamente, nunca precisando de rede
# Docker nenhuma (a rede default basta pra alcancar qualquer IP
# externo).
if [ -n "$GATEWAY_SSH" ]; then
  GATEWAY_NETWORK_FLAGS="-p 443:443"
else
  GATEWAY_NETWORK_FLAGS="--network $NETWORK --network-alias mtls --network-alias matls-auth.local --network-alias auth.local --network-alias matls-api.local --network-alias api.local --network-alias directory"
fi
if [ -n "$CLIENT_SSH" ]; then
  CLIENT_NETWORK_FLAGS=""
else
  CLIENT_NETWORK_FLAGS="--network $NETWORK"
fi

on_gateway() { if [ -n "$GATEWAY_SSH" ]; then $GATEWAY_SSH "$1"; else bash -c "$1"; fi; }
on_client()  { if [ -n "$CLIENT_SSH"  ]; then $CLIENT_SSH  "$1"; else bash -c "$1"; fi; }

# BASELINE_HANDSHAKE_BYTES, Decisao 14 (DECISIONS.md L1511-1519/1750-1751)
# -- literal aqui so pra este script shell nao depender de importar
# Python; evaluate_criteria.py continua a fonte real, nunca duplicada
# como logica, so os 8 numeros re-citados.
declare -A BASELINE_IN=( [classico]=1513 [pqc]=10728 [hibrido-v8]=8397 [hibrido-and]=11902 )
declare -A BASELINE_OUT=([classico]=1640 [pqc]=10878 [hibrido-v8]=8552 [hibrido-and]=12177 )

PASS=1
for PERFIL in classico pqc hibrido-v8 hibrido-and; do
  echo "=== [$PERFIL] removendo gateway anterior (se houver) ==="
  on_gateway "docker rm -f $GATEWAY_CONTAINER >/dev/null 2>&1 || true"
  # Decisao 74 (achado real, ao vivo, mesmo retomada -- o fix de rede
  # da Decisao 73 era necessario mas ainda nao suficiente): em modo
  # remoto, este passo (Passo 10) roda DEPOIS do Passo 9
  # (--exercise-start-stop), que deixa o container `v9-mtls`
  # (nome fixo em orchestrator.py) rodando de proposito -- `stop_
  # block` nunca o remove, so ele ocupa a porta 443 do HOST com `-p
  # 443:443` (Decisao 70). O container deste script tem OUTRO nome
  # (`$GATEWAY_CONTAINER`, default `v9-mtls-ensaio`) mas disputa a
  # MESMA porta 443 do mesmo host -- "Bind for 0.0.0.0:443 failed:
  # port is already allocated". So remove o de orchestrator.py
  # defensivamente em modo remoto (nome conhecido, nunca em modo
  # local, onde nem ele nem a disputa de porta existem).
  if [ -n "$GATEWAY_SSH" ]; then
    on_gateway "docker rm -f v9-mtls >/dev/null 2>&1 || true"
  fi

  echo "=== [$PERFIL] subindo gateway com CRYPTO_PROFILE=$PERFIL ==="
  on_gateway "export MSYS_NO_PATHCONV=1; docker run -d --name $GATEWAY_CONTAINER \
    $GATEWAY_NETWORK_FLAGS \
    -e HTTP_MODE=business -e TICKETS_DISABLED=true -e CRYPTO_PROFILE=$PERFIL \
    -v \"$REAL_CERTS_DIR:/real-certs:ro\" mockopin-v9-gateway"

  echo "=== [$PERFIL] esperando o gateway ficar pronto (limite: 30 tentativas, 1s cada) ==="
  READY=0
  for i in $(seq 1 30); do
    if on_gateway "docker logs $GATEWAY_CONTAINER 2>&1 | grep -q 'listening on'"; then
      READY=1
      break
    fi
    sleep 1
  done
  if [ "$READY" -ne 1 ]; then
    echo "FALHA [$PERFIL]: gateway nao ficou pronto em 30s"
    PASS=0
    continue
  fi

  echo "=== [$PERFIL] disparando a conexao real (negtest -scenario matrix) ==="
  CLIENT_MODE="$PERFIL"
  if [ "$PERFIL" = "hibrido-and" ]; then CLIENT_MODE="hibrido-and-strict"; fi
  on_client "export MSYS_NO_PATHCONV=1; docker run --rm $CLIENT_NETWORK_FLAGS \
    -v \"$CERTS_DIR:/certs:ro\" mockopin-v9-negtest \
    -scenario matrix -client-mode $CLIENT_MODE -server-mode $PERFIL \
    -target $GATEWAY_HOST:443 -cert-dir /certs"

  echo "=== [$PERFIL] extraindo a linha 'connection OK' (grep, nunca tail -1) ==="
  LOG_LINE=$(on_gateway "docker logs $GATEWAY_CONTAINER 2>&1 | grep 'connection OK' | grep \"sni=\\\"mtls\\\"\" | tail -1")
  echo "$LOG_LINE"

  BYTES_IN=$(echo "$LOG_LINE" | grep -oE 'handshakeBytesIn=[0-9]+' | grep -oE '[0-9]+')
  BYTES_OUT=$(echo "$LOG_LINE" | grep -oE 'handshakeBytesOut=[0-9]+' | grep -oE '[0-9]+')
  EXP_IN="${BASELINE_IN[$PERFIL]}"
  EXP_OUT="${BASELINE_OUT[$PERFIL]}"
  DELTA_IN=$((BYTES_IN - EXP_IN))
  DELTA_OUT=$((BYTES_OUT - EXP_OUT))

  echo "=== [$PERFIL] handshakeBytesIn=$BYTES_IN (esperado $EXP_IN, delta $DELTA_IN) | handshakeBytesOut=$BYTES_OUT (esperado $EXP_OUT, delta $DELTA_OUT) ==="
  if [ "$DELTA_IN" -ne 0 ] || [ "$DELTA_OUT" -ne 0 ]; then
    echo "FALHA [$PERFIL]: delta != 0B contra o baseline"
    PASS=0
  else
    echo "OK [$PERFIL]: delta 0B nos dois sentidos"
  fi
  echo ""
done

on_gateway "docker rm -f $GATEWAY_CONTAINER >/dev/null 2>&1 || true"

if [ "$PASS" -eq 1 ]; then
  echo "RESULTADO FINAL: PASS -- 4/4 perfis, delta 0B nos dois sentidos"
  exit 0
else
  echo "RESULTADO FINAL: FAIL -- ver perfis marcados FALHA acima"
  exit 1
fi
