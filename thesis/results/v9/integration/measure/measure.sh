#!/bin/bash
# v9, T6, Fase 1: roda gateway+proxy dentro do MESMO conteiner (localhost,
# sem travessia de rede entre containers), captura tudo com tcpdump,
# decifra com tshark usando o keylog que os dois binarios escrevem no
# mesmo filesystem -- evita qualquer necessidade de bind mount ou
# compartilhamento de arquivo entre containers (nao funciona neste
# ambiente -- ver DECISIONS.md da v9, Decisao 11).
set -euo pipefail

PROFILE="$1"
TICKETS_DISABLED="${2:-true}"
OUTDIR=/out
mkdir -p "$OUTDIR"

KEYLOG=/tmp/keylog.txt
PCAP=/tmp/cap.pcap
: > "$KEYLOG"

tcpdump -i lo -s 0 -w "$PCAP" 'tcp port 8443' >/tmp/tcpdump.log 2>&1 &
TCPDUMP_PID=$!
sleep 1

CRYPTO_PROFILE="$PROFILE" LISTEN=127.0.0.1:8443 CERT_DIR=/certs TICKETS_DISABLED="$TICKETS_DISABLED" KEYLOG_PATH="$KEYLOG" \
  /usr/local/bin/gateway > "$OUTDIR/gateway_${PROFILE}_${TICKETS_DISABLED}.json" 2>&1 &
GATEWAY_PID=$!
sleep 1

set +e
/usr/local/bin/proxy -profile "$PROFILE" -target 127.0.0.1:8443 -cert-dir /certs \
  -tickets-disabled="$TICKETS_DISABLED" -keylog-path "$KEYLOG" \
  > "$OUTDIR/proxy_${PROFILE}_${TICKETS_DISABLED}.json" 2>"$OUTDIR/proxy_${PROFILE}_${TICKETS_DISABLED}.log"
PROXY_STATUS=$?
set -e

sleep 1
kill "$GATEWAY_PID" >/dev/null 2>&1 || true
kill "$TCPDUMP_PID" >/dev/null 2>&1 || true
wait "$TCPDUMP_PID" 2>/dev/null || true
sleep 0.5

echo "== gateway (profile=$PROFILE tickets_disabled=$TICKETS_DISABLED) =="
grep '^{' "$OUTDIR/gateway_${PROFILE}_${TICKETS_DISABLED}.json" || true

echo "== proxy (profile=$PROFILE tickets_disabled=$TICKETS_DISABLED) =="
cat "$OUTDIR/proxy_${PROFILE}_${TICKETS_DISABLED}.json" || true

echo "== tshark: registros TLS decifrados via keylog (frame, direcao, tamanho, tipo) =="
tshark -r "$PCAP" -o "tls.keylog_file: $KEYLOG" -Y tls \
  -T fields -e frame.number -e ip.src -e tcp.len -e tls.record.content_type -e tls.handshake.type \
  2>/dev/null || echo "(tshark nao produziu linhas decifradas)"

echo "== tshark: bytes brutos por direcao, pcap inteiro (independente de decifragem, cross-check) =="
tshark -r "$PCAP" -T fields -e ip.src -e ip.dst -e tcp.len 2>/dev/null \
  | awk 'NF==3 {sum[$1" -> "$2]+=$3} END {for (k in sum) printf "%-32s %8d B\n", k, sum[k]}'

exit "$PROXY_STATUS"
