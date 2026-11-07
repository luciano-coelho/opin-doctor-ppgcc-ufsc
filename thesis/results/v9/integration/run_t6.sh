#!/usr/bin/env bash
# v9, Fase 1, T6: instrumentacao completa -- keylog+pcap decifrado,
# contagem de bytes na fronteira exata do Handshake() (dentro do
# processo), bytes pos-handshake separados (tickets, quando ligados,
# via rodada diagnostica -tickets-disabled=false), microbenchmarks de
# CPU por operacao, CurveID/DualAuthenticated por execucao. 4 perfis,
# cada um em modo normal (tickets desligados, Decisao 13) e modo
# diagnostico (tickets ligados, so para quantificar o efeito).
set -euo pipefail
cd "$(dirname "$0")"

PROFILES=(classico pqc hibrido-v8 hibrido-and)
OUT=t6_out
rm -rf "$OUT"
mkdir -p "$OUT"

echo "== T6: gerando certificados efemeros (make certs em ../certs) =="
( cd ../certs && make certs )

echo "== Copiando certificados para o contexto de build do measure (COPY, nunca bind mount) =="
rm -rf measure/certs
cp -r ../certs/generated measure/certs

echo "== Buildando o toolchain Go corrigido (mecanismo AND) =="
docker build -q -t mockopin-v9-toolchain -f ../toolchain/Dockerfile ../toolchain >/dev/null

echo "== Buildando measure e bench =="
docker build -q -t mockopin-v9-measure -f measure/Dockerfile . >/dev/null
docker build -q -t mockopin-v9-bench bench >/dev/null

echo "== Microbenchmarks de CPU (4 primitivas, independentes de perfil) =="
docker run --rm mockopin-v9-bench -n 2000 | tee "$OUT/bench.log"

for profile in "${PROFILES[@]}"; do
  echo ""
  echo "== Perfil: $profile, modo normal (tickets desligados) =="
  docker run --rm --cap-add=NET_ADMIN --cap-add=NET_RAW mockopin-v9-measure "$profile" true \
    | tee "$OUT/${profile}_normal.log"

  echo ""
  echo "== Perfil: $profile, modo diagnostico (tickets LIGADOS, so para medir o efeito) =="
  docker run --rm --cap-add=NET_ADMIN --cap-add=NET_RAW mockopin-v9-measure "$profile" false \
    | tee "$OUT/${profile}_diag.log"
done

echo ""
echo "== Resumo (extraido dos JSONs de proxy, normal vs diagnostico) =="
printf "%-12s %8s %8s %10s %10s %10s\n" "perfil" "curve" "dualOK" "hsBytesN" "hsBytesD" "deltaTicket"
for profile in "${PROFILES[@]}"; do
  n_json=$(grep -o '{"side":"proxy".*}' "$OUT/${profile}_normal.log" | tail -1)
  d_json=$(grep -o '{"side":"proxy".*}' "$OUT/${profile}_diag.log" | tail -1)
  curve=$(echo "$n_json" | sed -E 's/.*"curveID":"([^"]+)".*/\1/')
  dual=$(echo "$n_json" | sed -E 's/.*"dualAuthenticated":([a-z]+).*/\1/')
  hsn=$(echo "$n_json" | sed -E 's/.*"handshakeBytesOut":([0-9]+).*/\1/')
  hsd=$(echo "$d_json" | sed -E 's/.*"handshakeBytesOut":([0-9]+).*/\1/')
  delta=$((hsd - hsn))
  printf "%-12s %8s %8s %10s %10s %10s\n" "$profile" "$curve" "$dual" "$hsn" "$hsd" "$delta"
done

echo ""
echo "== Limpeza =="
rm -rf measure/certs
( cd ../certs && make clean )
echo "done. Logs completos em $OUT/ (nao commitado -- ver .gitignore)."
