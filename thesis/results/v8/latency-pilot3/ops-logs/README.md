# Piloto 3 (ensaio geral, topologia completa) -- logs operacionais, rodada pausada em 2026-10-28

Nenhuma execução de medição chegou a rodar nesta rodada -- por isso não
há `experiment* - <perfil>/` aqui, só os logs operacionais das etapas de
infraestrutura/entrega/pré-flight, na ordem em que aconteceram de
verdade (numeração dos arquivos = ordem cronológica, não um protocolo
fixo). IP do operador, ID de conta e ARNs mascarados em todos os
arquivos (`OPERADOR`/`<REDACTED>`), conferido por `scan_secrets.sh`
antes do commit.

- `01`/`02`: plano e apply da topologia completa (65 recursos, 12
  instâncias, 7 regiões), aprovados por Luciano.
- `03`: saída parcial do incidente real (Decision 93) -- apply
  destrutivo que derrubou 38 recursos por uma variável de escopo antiga.
- `04`-`06`: plano e apply de restauração (38 recursos, via plano salvo
  em arquivo).
- `07`-`12`: etapa 4 do runbook (pré-flight de alcance/SSH), incluindo o
  teste real que confirmou ICMP bloqueado por desenho (grupos de
  segurança só liberam TCP 22/443).
- `13`: etapa 4b -- 9/9 trocas de perfil (`switch_crypto_profile.py`
  reusado remotamente) bem-sucedidas nos 3 servidores.
- `14`-`15`: pré-flight por TCP/443 (sem ICMP) -- 8/8 clientes, 20/20
  amostras, 0 falhas; checagem de handshake TLS do cliente remoto real
  **inconclusiva** (ver `15`), não um PASS/FAIL confirmado.
- `16`-`17`: etapa 5 -- entrega de imagens e código-fonte, sha256
  conferido em todas as partes.
- `18`-`20`: teardown final (pausa pedida por Luciano) -- plano de
  destroy salvo (65 a destruir, 0/0), apply do mesmo plano, verificação
  das 7 regiões confirmando zero recursos remanescentes.

Ver `thesis/results/v8/DECISIONS.md` (Decision 93, addendum final) e
`thesis/results/v8/campaign/PILOT_RUNBOOK.md` ("Status: piloto 3") para
o relato completo e o ponto de retomada.
