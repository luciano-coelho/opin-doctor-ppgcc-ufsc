# Secao (a) -- Parametros criptograficos por perfil (extraidos de artefatos reais)

Extraido via `tshark --export-objects x509af` + `tshark -T fields` sobre os pares pcap+keylog reais preservados em `raw/criterio1_capturas/` (decifragem TLS por keylog, nunca assumido do codigo-fonte). Cada perfil foi extraido das 3 rotas pilotadas (L0/L219/L325) e os resultados foram comparados -- ver `cross_route_consistent`.

## Perfil: classico
- TLS (ServerHello.legacy_record_version): `0x0303` (TLS 1.3 negociado via extensao supported_versions)
- Cipher suite: `0x1301` (TLS_AES_128_GCM_SHA256 se 0x1301)
- Grupo negociado: `0x0018` / dec 24 -- secp384r1 (classico)
- SignatureScheme(s) em CertificateVerify: ['0x0804'] -- ['rsa_pss_rsae_sha256']
- Consistente nas 3 rotas pilotadas (L0/L219/L325)? **True**
- CertificateRequest presentes na captura (mTLS): 6

Certificados X.509 reais (DER extraido do handshake decifrado):
  - `CN=classico_server` emitido por `CN=classico_ca` -- sha256WithRSAEncryption -- chave: RSAPublicKey 2048 -- SAN: ['mtls', 'auth.local', 'matls-auth.local', 'api.local', 'matls-api.local', 'directory', 'directory.local', 'keystore', '127.0.0.1', '::1'] -- sha256(DER)=3fcd60adeda39407... -- 6 instancia(s) identica(s) na captura
  - `CN=classico_client` emitido por `CN=classico_ca` -- sha256WithRSAEncryption -- chave: RSAPublicKey 2048 -- SAN: ['opin-client-one'] -- sha256(DER)=5095d5fee97f012a... -- 6 instancia(s) identica(s) na captura

## Perfil: pqc
- TLS (ServerHello.legacy_record_version): `0x0303` (TLS 1.3 negociado via extensao supported_versions)
- Cipher suite: `0x1301` (TLS_AES_128_GCM_SHA256 se 0x1301)
- Grupo negociado: `0x0202` / dec 514 -- MLKEM1024 puro (IANA 0x0202) -- sem componente classico
- SignatureScheme(s) em CertificateVerify: ['0x0905'] -- ['PQC puro (ML-DSA, codepoint 0x0905 -- ver nota)']
- Consistente nas 3 rotas pilotadas (L0/L219/L325)? **True**
- CertificateRequest presentes na captura (mTLS): 6

Certificados X.509 reais (DER extraido do handshake decifrado):
  - `CN=pqc_server` emitido por `CN=pqc_ca` -- ML-DSA-65 (FIPS 204 -- OID NIST; nao resolvido pela lib cryptography, confirmado por tamanho de chave/assinatura, ver extract_pqc_asn1_sizes) -- chave: nao suportado pela lib cryptography 46.x (PQC) [1953, 3310] -- SAN: ['mtls', 'auth.local', 'matls-auth.local', 'api.local', 'matls-api.local', 'directory', 'directory.local', 'keystore', '127.0.0.1', '::1'] -- sha256(DER)=1a63b339beb9972f... -- 6 instancia(s) identica(s) na captura
  - `CN=pqc_client` emitido por `CN=pqc_ca` -- ML-DSA-65 (FIPS 204 -- OID NIST; nao resolvido pela lib cryptography, confirmado por tamanho de chave/assinatura, ver extract_pqc_asn1_sizes) -- chave: nao suportado pela lib cryptography 46.x (PQC) [1953, 3310] -- SAN: ['opin-client-one'] -- sha256(DER)=a48b3ea711d8ee44... -- 6 instancia(s) identica(s) na captura

## Perfil: hibrido-v8
- TLS (ServerHello.legacy_record_version): `0x0303` (TLS 1.3 negociado via extensao supported_versions)
- Cipher suite: `0x1301` (TLS_AES_128_GCM_SHA256 se 0x1301)
- Grupo negociado: `0x11ed` / dec 4589 -- SecP384r1MLKEM1024 (IANA 0x11ED, hibrido)
- SignatureScheme(s) em CertificateVerify: ['0x0804'] -- ['rsa_pss_rsae_sha256']
- Consistente nas 3 rotas pilotadas (L0/L219/L325)? **True**
- CertificateRequest presentes na captura (mTLS): 6

Certificados X.509 reais (DER extraido do handshake decifrado):
  - `CN=hibrido_v8_server` emitido por `CN=hibrido_v8_ca` -- sha256WithRSAEncryption -- chave: RSAPublicKey 2048 -- SAN: ['mtls', 'auth.local', 'matls-auth.local', 'api.local', 'matls-api.local', 'directory', 'directory.local', 'keystore', '127.0.0.1', '::1'] -- sha256(DER)=b3ec3fdd388ae58c... -- 6 instancia(s) identica(s) na captura
  - `CN=hibrido_v8_client` emitido por `CN=hibrido_v8_ca` -- sha256WithRSAEncryption -- chave: RSAPublicKey 2048 -- SAN: ['opin-client-one'] -- sha256(DER)=f4ae36e6c96d25f9... -- 6 instancia(s) identica(s) na captura

## Perfil: hibrido-and
- TLS (ServerHello.legacy_record_version): `0x0303` (TLS 1.3 negociado via extensao supported_versions)
- Cipher suite: `0x1301` (TLS_AES_128_GCM_SHA256 se 0x1301)
- Grupo negociado: `0x11ed` / dec 4589 -- SecP384r1MLKEM1024 (IANA 0x11ED, hibrido)
- SignatureScheme(s) em CertificateVerify: ['0xfe65'] -- ['composto/dual classico+PQC (faixa experimental 0xFE00-0xFEFF -- "o AND")']
- Consistente nas 3 rotas pilotadas (L0/L219/L325)? **True**
- CertificateRequest presentes na captura (mTLS): 6

Certificados X.509 reais (DER extraido do handshake decifrado):
  - `CN=hibrido_and_rsa_server` emitido por `CN=hibrido_and_rsa_ca` -- sha256WithRSAEncryption -- chave: RSAPublicKey 2048 -- SAN: ['mtls', 'auth.local', 'matls-auth.local', 'api.local', 'matls-api.local', 'directory', 'directory.local', 'keystore', '127.0.0.1', '::1'] -- sha256(DER)=11fc683e8ffb6719... -- 6 instancia(s) identica(s) na captura
  - `CN=hibrido_and_rsa_client` emitido por `CN=hibrido_and_rsa_ca` -- sha256WithRSAEncryption -- chave: RSAPublicKey 2048 -- SAN: ['opin-client-one'] -- sha256(DER)=e4942918c44139b9... -- 6 instancia(s) identica(s) na captura
  - 12 objeto(s) pequeno(s) exportado(s) pelo x509af NAO sao certificados X.509 validos (tamanho < 100 bytes, openssl nao decodifica) -- NAO usados como evidencia: [23, 24, 23, 24, 23, 24, 23, 24, 23, 24, 23, 24] bytes

## Checagem automatizada obrigatoria (item 4a)
**Resultado: PASS**
- Todo RSA em classico/hibrido-v8/hibrido-and == 2048 bits exatos.
- pqc nao mostra nenhum componente classico impropio (grupo MLKEM1024 puro, certificado ML-DSA-65 puro).

## Nota honesta sobre hibrido-and ("o AND")
O SignatureScheme 0xfe65 (composto/dual) foi confirmado REAL na mensagem CertificateVerify do handshake decifrado desse perfil. O certificado X.509 da cadeia permanece puramente RSA-2048 nas 3 rotas -- o componente PQC da assinatura dupla NAO foi isolado como um certificado X.509 separado por esta extracao (os objetos extras exportados pelo x509af sao fragmentos de ~23-24 bytes, nao certificados validos). A natureza exata de como o lado PQC da assinatura composta e transportado (certificado adicional fora da cadeia padrao, extensao TLS propria, ou outro mecanismo) permanece um item aberto -- nao investigado mais a fundo aqui.
