# Artefatos reais (v8) -- capturados de uma frota viva, não gerados localmente

Mesmo papel dos artefatos da v7 (`thesis/results/v7/artifacts/`): evidência
real por perfil (certificado do cliente, log de handshake), não um
recálculo local -- capturados depois das 3 janelas oficiais, antes do
destroy final.

## Proveniência

- **`client_one_<perfil>.crt`**: capturado AGORA, em tempo real, via SSH
  relay operador -> control -> servidor (`sa-east-1`), lendo o arquivo de
  certificado estático de cada perfil (`~/mock-service-os/certs/`) --
  os 3 arquivos coexistem no disco do servidor independente de qual
  perfil o gateway está servindo no momento, então não precisou trocar
  o perfil ativo para capturar os 3.
- **`handshake_log_w03_run21.log`**: **não** foi re-capturado ao vivo --
  o gateway já estava fixo em `hybrid` (último perfil da ordem da
  janela 3 em todas as instalações) no momento desta captura, então um
  `docker logs` ao vivo teria retornado o MESMO conteúdo (hybrid) nos
  3 diretórios de perfil, rotulado errado para classic/pqc. Em vez
  disso, cada log aqui é o log real do gateway **já coletado durante a
  própria execução 21 da janela 3** (sa-east-1/L0, a primeira execução
  daquela janela, uma por perfil), já commitado em
  `thesis/results/v8/janela3/experiment{1,2,3} - */sa-east-1/L0/server/
  w03_run21_gateway.log` -- genuinamente real, da frota viva, só que
  coletado no momento certo (durante a execução) em vez de agora.

Correção registrada em Decision -- o script original
(`capture_real_artifacts.sh`) assumia poder capturar o log de handshake
ao vivo para qualquer perfil a qualquer momento; isso só é verdade se o
gateway estiver, de fato, rodando aquele perfil no momento da captura.
