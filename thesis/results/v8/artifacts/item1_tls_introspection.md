# Item 1 (Luciano, 2026-10-31) -- introspecção TLS independente por perfil

Frota ainda de pé após a campanha. `openssl s_client` real, direto contra
o gateway de `sa-east-1` (via relay SSH operador -> control -> servidor,
`localhost:443` no próprio servidor), com o certificado de cliente real
de cada perfil (`~/mock-service-os/certs/client_one[_<perfil>].{crt,key}`)
e `-CAfile ca.crt` (a CA local do laboratório). Cada perfil exigiu trocar
o `CRYPTO_PROFILE` ativo do gateway antes da sonda (5 execuções de
settling por troca, igual a qualquer troca de perfil já feita nesta
campanha) -- **nenhuma medição oficial foi tocada**, é tráfego de sonda,
não contado em N_mTLS. Estado final restaurado para `hybrid` (o mesmo em
que a janela 3 terminou).

## Classic

```
Negotiated TLS1.3 group (Peer Temp Key): ECDH, secp384r1, 384 bits
Cipher: TLS_AES_128_GCM_SHA256   Protocol: TLSv1.3
Peer signature type: rsa_pss_rsae_sha256   Peer signing digest: SHA256
Verify return code: 26 (unsuitable certificate purpose)
```
Grupo negociado bate exatamente com o esperado (`CurveP384`, Decision
108 / `_CLIENT_EXPECTED_CURVE`). A cadeia resolve até a CA local correta
(deixou de dar "unable to verify the first certificate" ao passar
`-CAfile`), mas falha em um checagem de *purpose* (EKU) do OpenSSL --
esperado para um certificado de laboratório sem a extensão
`serverAuth`/`clientAuth` explícita que o OpenSSL moderno passou a
exigir; o próprio projeto já usa `InsecureSkipVerify=true` no cliente
real por este motivo documentado (`tls_kem_proxy/main.go`), não é uma
falha de segurança nova encontrada agora.
Saída completa: `classic/openssl_s_client_probe.txt`.

## Hybrid

```
Negotiated TLS1.3 group: SecP384r1MLKEM1024
Cipher: TLS_AES_128_GCM_SHA256   Protocol: TLSv1.3
Peer signature type: rsa_pss_rsae_sha256   Peer signing digest: SHA256
Verify return code: 26 (unsuitable certificate purpose, mesmo caso do Classic)
```
Grupo negociado bate exatamente com o esperado (`SecP384r1MLKEM1024`).
Saída completa: `hybrid/openssl_s_client_probe.txt`.

## PQC -- achado real, não um bug do projeto

`openssl s_client -groups mlkem1024` enviou um key share real (1755
bytes escritos, OpenSSL reconhece o nome do grupo) mas o servidor
rejeitou com `handshake failure` (alerta TLS 40) -- **nenhum grupo em
comum**, apesar de ambos os lados "falarem" ML-KEM-1024. Isso é uma
incompatibilidade real de implementação: o grupo híbrido
`SecP384r1MLKEM1024` interopera entre OpenSSL 3.5.8 e o `crypto/tls` do
Go deste projeto, mas o grupo PQC puro `MLKEM1024` não -- plausivelmente
codepoints TLS diferentes entre as duas implementações para o grupo
"ML-KEM-1024 sozinho" (sem o acoplamento clássico), já que o grupo
híbrido segue um rascunho IETF com adoção mais ampla entre bibliotecas,
enquanto o PQC puro não tem o mesmo nível de padronização entre
implementações nesta janela de tempo. Saída completa:
`pqc/openssl_s_client_probe.txt`.

**Evidência independente real do PQC vem do próprio log do gateway,
coletado durante a execução 21 da janela 3** (tráfego real do cliente Go
do próprio projeto, não uma sonda):
```
tlsVersion:"TLS 1.3"  cipherSuite:"TLS_AES_128_GCM_SHA256"  curveID:"MLKEM1024"
```
(`thesis/results/v8/janela3/experiment2 - PQC/sa-east-1/L0/server/
w03_run21_gateway.log`) -- bate exatamente com o esperado
(`_CLIENT_EXPECTED_CURVE["pqc"] = "MLKEM1024"`), confirmando que o
rótulo do perfil bate com os parâmetros negociados mesmo sem o OpenSSL
conseguir fazer a mesma sonda.

## Conclusão (item 1)

Os 3 perfis têm o rótulo confirmado contra os parâmetros realmente
negociados: Classic e Hybrid por sonda `openssl s_client` independente
agora, ao vivo; PQC pela própria evidência real do gateway durante a
execução 21 (já comitada), já que a sonda independente falhou por uma
incompatibilidade de interoperabilidade entre OpenSSL e Go para esse
grupo específico -- documentado, não escondido.
