# Secoes (g)(h) -- Ambiente/protocolo e limitacoes

## (g) Ambiente e protocolo
- Instancia (real, de `criterio2_initcwnd.json`): `m7i-flex.large`
- Topologia: 1 regiao AWS (`sa-east-1`) -- controle + servidor + 1 cliente
- Go (binarios gateway/proxy, real de `PINS.json`): `go1.27.3`
- tcpdump/tshark (imagem measure, reconstruida com equivalencia provada, Decisao 103): `tcpdump 4.99.6` (libpcap 1.10.7), `TShark (Wireshark) 4.6.9`, base `Alpine 3.24.3`
- Docker: proxy do AMI real = Docker 25.0.16 (testado com `docker:25-dind` 25.0.5 como aproximacao), operador = Docker 29.9.1 (ver Decisao 68 para a divergencia de Image ID entre versoes e por que isso NAO afeta a verificacao de entrega)
- Pins: `campaign/PINS.json` -- 7 entradas de imagem pinadas
- Execucoes reais: 60/60 -- capturas dedicadas: 12
- Protocolo de coleta: `orchestrator.py run_pilot` (execucao real) -> `collect_artifacts.py` (coleta + verificacao sha256) -> `consolidate_v9_pilot.py` (7 criterios + RELATORIO_PILOTO.md) -> este script (`build_consolidated_report_v9.py`, consolidacao final, SOMENTE leitura de `raw/`+`criteria_evaluation.json`, nunca tocando AWS)
- Custo real do piloto: ver `campaign/REQUISITOS_CAMPANHA_OFICIAL.md`, secao de custo/duracao (item 5 da diretoria vigente) para a aritmetica completa com as 4 taxas reais medidas desta rodada.

## (h) Limitacoes e itens abertos
- N=5 execucoes/celula -- apenas descritivo (median/p95/min/max/n), NUNCA teste de significancia estatistica. Qualquer leitura causal sobre diferencas entre perfis exigiria a escala N=30 da campanha oficial.
- Criterio 2 (initcwnd/MSS real) so cobre 1 das 12 combinacoes perfil x rota (classico/L219) -- as outras 11 permanecem nao verificadas por esta metrica especifica.
- hibrido-and: o componente PQC da assinatura dupla/composta (SignatureScheme 0xfe65) foi confirmado no handshake real mas NAO foi isolado como certificado X.509 separado nesta extracao -- mecanismo exato nao investigado.
- ML-DSA-65 (perfil pqc): a lib `cryptography` 46.x nao sabe extrair o objeto de chave publica desse OID -- o tamanho foi inferido via `openssl asn1parse` (comprimento bruto da BIT STRING da SubjectPublicKeyInfo), consistente com os parametros publicados do FIPS 204, mas NAO confirmado por uma biblioteca que entenda nativamente o formato da chave.
- 1 unica regiao AWS pilotada (sa-east-1) e 3 das 8 rotas da campanha oficial (L0/L219/L325) -- us-east-1/ap-northeast-1 e as rotas L14/L30/L123 nunca foram tocadas por este piloto. Ver `REQUISITOS_CAMPANHA_OFICIAL.md` para os riscos concretos de cada gap.
- Sampler de steal de CPU/memoria (achado 10, Decisao 58) NAO implementado neste piloto por desenho -- item bloqueante de alta prioridade antes da campanha oficial, ver `REQUISITOS_CAMPANHA_OFICIAL.md`.
- Nenhum checkpoint/resume existe em `orchestrator.py run_pilot` -- uma interrupcao a meio da campanha oficial (960 execucoes) perderia TODO o progresso nao salvo (so grava arquivos finais ao fim).
