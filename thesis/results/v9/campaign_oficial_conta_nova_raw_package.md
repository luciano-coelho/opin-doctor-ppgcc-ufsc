# Pacote offline dos dados brutos da campanha oficial

Os dados brutos (pcaps, logs, `.keylog` de sessão TLS) de
`thesis/results/v9/campaign_oficial_conta_nova_raw/` **não entram no git**
(ver `.gitignore`) -- ficam compactados em um único pacote, fora do
repositório, em um diretório privado local. Este arquivo registra onde
esse pacote está e seu sha256, para que a integridade do pacote possa
ser conferida sem precisar do pacote em si estar versionado.

- **Caminho completo:** `C:\Users\lucia_csx8nlz\mockopin-offline-data\campaign_oficial_conta_nova_raw.tar.gz`
  (fora de `MockOPIN\`, nunca rastreado pelo git).
- **Formato:** `.tar.gz` (zstd não disponível neste ambiente no momento da
  geração -- `tar -czf`, gzip padrão).
- **Tamanho:** 100.340.836 bytes (~96 MiB / ~100 MB).
- **sha256 do pacote:** `cdd10999aa19512c06cfdcd2b6fd825dc75b7bea325b4a31f57a532e55bf1228`
- **Conteúdo:** a árvore completa de `campaign_oficial_conta_nova_raw/`,
  incluindo os 78 arquivos `.keylog` (segredos de sessão TLS) junto com
  os `.pcap` correspondentes -- os dois precisam estar juntos para
  decifração/depuração offline, que é exatamente o propósito deste
  pacote local.
- **Verificação de integridade feita:** o pacote foi extraído para um
  diretório temporário e os 725 arquivos resultantes foram conferidos,
  um a um, por sha256 contra `campaign_oficial_conta_nova_sha256_manifest.txt`
  (a mesma lista versionada no git) -- **0 divergências, 725/725
  arquivos idênticos**. Diretório temporário removido depois da
  verificação.

A cópia de trabalho local em `thesis/results/v9/campaign_oficial_conta_nova_raw/`
não foi alterada nem removida por este empacotamento -- este pacote é uma
cópia adicional, não uma migração.
