# Secao (a) -- Parametros criptograficos por perfil (extraidos de artefatos reais)

Certificados: parser DER generico proprio sobre os bytes DECIFRADOS reais da mensagem TLS Certificate (`tshark -x` com keylog, bloco "Decrypted TLS"), nunca o exportador `x509af` (que falhava em reassemblar o 2o certificado do hibrido-and -- Decisao 105). Handshake (grupo/cipher/SignatureScheme): `tshark -T fields`. Cada perfil foi extraido das 3 rotas pilotadas (L0/L219/L325); os resultados foram comparados -- ver `cross_route_consistent`.

## Perfil: classico
- TLS (ServerHello.legacy_record_version): `0x0303` (TLS 1.3 negociado via extensao supported_versions)
- Cipher suite: `0x1301` (TLS_AES_128_GCM_SHA256 se 0x1301)
- Grupo negociado: `0x0018` / dec 24 -- secp384r1 (classico)
- SignatureScheme(s) em CertificateVerify: ['0x0804'] -- ['rsa_pss_rsae_sha256']
- Consistente nas 3 rotas pilotadas (L0/L219/L325)? **True**
- CertificateRequest presentes na captura (mTLS): 6

CertificateEntry real, lado **server** (frame 6, 1 entrada(s), lista totalmente consumida: True):
  - serial=2 `CN=classico_server` emitido por `CN=classico_ca` -- assinatura: sha256WithRSAEncryption (256B raw) -- chave: rsaEncryption (270B raw, 2048 bits (lib cryptography)) -- DER total=900B -- sha256=3fcd60adeda39407...
CertificateEntry real, lado **client** (frame 9, 1 entrada(s), lista totalmente consumida: True):
  - serial=3 `CN=classico_client` emitido por `CN=classico_ca` -- assinatura: sha256WithRSAEncryption (256B raw) -- chave: rsaEncryption (270B raw, 2048 bits (lib cryptography)) -- DER total=787B -- sha256=5095d5fee97f012a...

## Perfil: pqc
- TLS (ServerHello.legacy_record_version): `0x0303` (TLS 1.3 negociado via extensao supported_versions)
- Cipher suite: `0x1301` (TLS_AES_128_GCM_SHA256 se 0x1301)
- Grupo negociado: `0x0202` / dec 514 -- MLKEM1024 puro (IANA 0x0202) -- sem componente classico
- SignatureScheme(s) em CertificateVerify: ['0x0905'] -- ['PQC puro (ML-DSA, codepoint 0x0905 -- ver nota)']
- Consistente nas 3 rotas pilotadas (L0/L219/L325)? **True**
- CertificateRequest presentes na captura (mTLS): 6

CertificateEntry real, lado **server** (frame 11, 1 entrada(s), lista totalmente consumida: True):
  - serial=15 `CN=pqc_server` emitido por `CN=pqc_ca` -- assinatura: ML-DSA-65 (FIPS 204, OID NIST) (3309B raw) -- chave: ML-DSA-65 (FIPS 204, OID NIST) (1952B raw) -- DER total=5619B -- sha256=1a63b339beb9972f...
CertificateEntry real, lado **client** (frame 16, 1 entrada(s), lista totalmente consumida: True):
  - serial=16 `CN=pqc_client` emitido por `CN=pqc_ca` -- assinatura: ML-DSA-65 (FIPS 204, OID NIST) (3309B raw) -- chave: ML-DSA-65 (FIPS 204, OID NIST) (1952B raw) -- DER total=5506B -- sha256=a48b3ea711d8ee44...

## Perfil: hibrido-v8
- TLS (ServerHello.legacy_record_version): `0x0303` (TLS 1.3 negociado via extensao supported_versions)
- Cipher suite: `0x1301` (TLS_AES_128_GCM_SHA256 se 0x1301)
- Grupo negociado: `0x11ed` / dec 4589 -- SecP384r1MLKEM1024 (IANA 0x11ED, hibrido)
- SignatureScheme(s) em CertificateVerify: ['0x0804'] -- ['rsa_pss_rsae_sha256']
- Consistente nas 3 rotas pilotadas (L0/L219/L325)? **True**
- CertificateRequest presentes na captura (mTLS): 6

CertificateEntry real, lado **server** (frame 11, 1 entrada(s), lista totalmente consumida: True):
  - serial=6 `CN=hibrido_v8_server` emitido por `CN=hibrido_v8_ca` -- assinatura: sha256WithRSAEncryption (256B raw) -- chave: rsaEncryption (270B raw, 2048 bits (lib cryptography)) -- DER total=6242B -- sha256=b3ec3fdd388ae58c...
CertificateEntry real, lado **client** (frame 14, 1 entrada(s), lista totalmente consumida: True):
  - serial=7 `CN=hibrido_v8_client` emitido por `CN=hibrido_v8_ca` -- assinatura: sha256WithRSAEncryption (256B raw) -- chave: rsaEncryption (270B raw, 2048 bits (lib cryptography)) -- DER total=6131B -- sha256=f4ae36e6c96d25f9...

## Perfil: hibrido-and
- TLS (ServerHello.legacy_record_version): `0x0303` (TLS 1.3 negociado via extensao supported_versions)
- Cipher suite: `0x1301` (TLS_AES_128_GCM_SHA256 se 0x1301)
- Grupo negociado: `0x11ed` / dec 4589 -- SecP384r1MLKEM1024 (IANA 0x11ED, hibrido)
- SignatureScheme(s) em CertificateVerify: ['0xfe65'] -- ['composto/dual classico+PQC (faixa experimental 0xFE00-0xFEFF -- "o AND")']
- Consistente nas 3 rotas pilotadas (L0/L219/L325)? **True**
- CertificateRequest presentes na captura (mTLS): 6

CertificateEntry real, lado **server** (frame 11, 2 entrada(s), lista totalmente consumida: True):
  - serial=10 `CN=hibrido_and_rsa_server` emitido por `CN=hibrido_and_rsa_ca` -- assinatura: sha256WithRSAEncryption (256B raw) -- chave: rsaEncryption (270B raw, 2048 bits (lib cryptography)) -- DER total=914B -- sha256=11fc683e8ffb6719...
  - serial=12 `CN=hibrido_and_mldsa_server` emitido por `CN=hibrido_and_mldsa_ca` -- assinatura: ML-DSA-65 (FIPS 204, OID NIST) (3309B raw) -- chave: ML-DSA-65 (FIPS 204, OID NIST) (1952B raw) -- DER total=5647B -- sha256=ad8ccd2bb9c8b0c8...
CertificateEntry real, lado **client** (frame 17, 2 entrada(s), lista totalmente consumida: True):
  - serial=11 `CN=hibrido_and_rsa_client` emitido por `CN=hibrido_and_rsa_ca` -- assinatura: sha256WithRSAEncryption (256B raw) -- chave: rsaEncryption (270B raw, 2048 bits (lib cryptography)) -- DER total=801B -- sha256=e4942918c44139b9...
  - serial=13 `CN=hibrido_and_mldsa_client` emitido por `CN=hibrido_and_mldsa_ca` -- assinatura: ML-DSA-65 (FIPS 204, OID NIST) (3309B raw) -- chave: ML-DSA-65 (FIPS 204, OID NIST) (1952B raw) -- DER total=5534B -- sha256=021f4d0acea4bb88...

## Checagem automatizada obrigatoria (BLOCO B item 3)
**Resultado: PASS**
- classico/hibrido-v8: exatamente 1 entrada RSA-2048 em cada lado (servidor e cliente).
- pqc: toda entrada e ML-DSA-65 puro (OID 2.16.840.1.101.3.4.3.18, chave 1952B, assinatura 3309B), nenhum componente classico.
- hibrido-and: AMBOS RSA-2048 E ML-DSA-65 presentes em cada lado (AND verdadeiro), e o componente ML-DSA bate EXATAMENTE com o parametro do perfil pqc standalone.

## Achado real: a dupla assinatura do hibrido-and ("o AND") -- BLOCO B item 1
A mensagem Certificate real do hibrido-and (servidor E cliente, nas 3 rotas) contem DUAS CertificateEntry na MESMA mensagem de handshake: uma RSA-2048 e uma ML-DSA-65 -- extraidas diretamente dos bytes decifrados reais (nunca do codigo-fonte). Entre as duas entradas ha 3 bytes de padding zero NAO previstos pela RFC 8446 (um bug de encoding do stack experimental, nao um erro de parsing deste script -- o parser so avanca aceitando um `cert_data` que comeca com a tag SEQUENCE 0x30; quando o campo declarado nao bate, ele busca ate 8 bytes adiante por um inicio valido).

Confirmacao cruzada contra os arquivos .crt reais em disco (`C:\Users\lucia_csx8nlz\MockOPIN\thesis\results\v9\certs\generated`):
  - `hibrido_and_rsa_server`: sha256 do pcap == sha256 do disco (`hibrido_and_rsa_server.crt`)? **True**
  - `hibrido_and_mldsa_server`: sha256 do pcap == sha256 do disco (`hibrido_and_mldsa_server.crt`)? **True**
  - `hibrido_and_rsa_client`: sha256 do pcap == sha256 do disco (`hibrido_and_rsa_client.crt`)? **True**
  - `hibrido_and_mldsa_client`: sha256 do pcap == sha256 do disco (`hibrido_and_mldsa_client.crt`)? **True**

Prova de que o handshake validou AMBOS os certificados (nunca so "o codigo diz que confere os dois"): evidencia do log real do gateway (`raw/full_container_logs/v9-mtls.log`):
  - `dualAuthenticated=true` em 6/6 conexoes reais do hibrido-and (as demais, dualAuthenticated=false, sao um canal interno nao relacionado -- `clientCert="op"`, curve=CurveP256 -- nunca o cliente instrumentado do piloto)
  - `handshakeBytesIn`/`handshakeBytesOut` reais observados: hibrido-and connection OK remoteAddr=54.151.227.69:54652 sni="mtls" curve=SecP384r1MLKEM1024 dualAuthenticated=true clientCert="hibrido_and_rsa_client" handshakeBytesIn=11902 handshakeBytesOut=12177
  - a conexao so chega a "connection OK" se o stack TLS (Go crypto/tls, que rejeita handshakes com cadeia de certificado invalida) ja tiver processado a mensagem Certificate completa (ambas as entradas) sem erro -- nao ha como chegar a esse log com so uma das duas cadeias validada.
  - limitacao honesta: o log em nivel INFO do gateway nao imprime uma linha separada "verifiquei RSA" + "verifiquei ML-DSA" -- a evidencia disponivel e o resultado agregado (`dualAuthenticated=true` + conexao aceita), nunca um trace de verificacao por certificado individual.
