# Pre-flight TCP + TLS handshake report (item F3, etapa 4 repetida por TCP/443)

## Entrega (etapa 5): OK
- deliver_images.sh: 01:44:07Z-02:00:45Z, 0 erros, 8/8 "identical image ID", 26/26 sha256 OK (incl. partes do tarball dividido).
- deliver_source.sh: 02:01:22Z-02:03:15Z, 0 erros, cryptography-50.0.2 confirmada via pip em todos os hosts.

## TCP connect timing (20 amostras/cliente, porta 443, SYN->SYN-ACK), 0 falhas em 160/160 amostras

| client              | colocated | median_ms | esperado   |
|---------------------|-----------|-----------|------------|
| L0@sa-east-1         | sim       | 0.193     | ~0.4ms     |
| L0@us-east-1         | sim       | 0.315     | ~0.4ms     |
| L0@ap-northeast-1    | sim       | 0.138     | ~0.4ms     |
| L14@us-east-1        | nao       | 15.156    | -          |
| L30@ap-northeast-1   | nao       | 32.070    | -          |
| L123@sa-east-1       | nao       | 122.899   | -          |
| L219@sa-east-1       | nao       | 220.012   | -          |
| L325@sa-east-1       | nao       | 330.490   | ~330ms     |

Todos os valores batem com a ordem de grandeza esperada. Nenhuma falha de conexao.

## TLS handshake check -- INCONCLUSIVO (nao corrigido em silencio, reportado como esta)

Metodologia usada: subi tls_kem_proxy no cliente (perfil hybrid, unico perfil testado
desta forma) e fiz urllib.request.urlopen('https://127.0.0.1:8443/jwks') sem Host
header e sem apresentar certificado de cliente.

Resultado: 8/8 clientes -> HTTPError 404 Not Found.

Diagnostico (lido no codigo real, nao suposto): opin_flow.py's do_call() SEMPRE
define host_header=AUTH_HOST ("auth.local") e SEMPRE passa cert=cert (mTLS) na
chamada real a /jwks (linhas 1928-1929). Meu script de teste nao fez nenhuma das
duas coisas. Um 404 (resposta HTTP real, nao erro de TLS) e consistente com o
gateway tendo completado o handshake TLS mas roteado a requisicao pelo Host
header padrao (sem match) em vez de para o servico AS -- ou seja, a causa mais
provavel e uma limitacao do MEU script de diagnostico, nao um defeito real do
fluxo de campanha.

NAO CONFIRMADO ainda que o handshake TLS realmente fecha, do ponto de vista do
cliente remoto real, em nenhum dos 3 perfis. A unica evidencia de fluxo completo
bem-sucedido ate agora e switch_crypto_profile.py (9/9 switches, 3 servidores x
3 perfis), mas essa evidencia roda DO PROPRIO SERVIDOR contra localhost -- nao
prova o caminho de rede real cliente remoto -> servidor.

## Decisao necessaria
Para fechar este item com evidencia real (nao inferida), preciso de uma v3 do
script de teste que corrija host_header + certificado de cliente, repetindo o
teste nos 3 perfis a partir de cada cliente real (implica religar os servidores
nos 3 perfis novamente, custo/tempo adicional). Aguardando autorizacao antes de
prosseguir, conforme instrucao de nao iniciar proxima etapa sem aval.
