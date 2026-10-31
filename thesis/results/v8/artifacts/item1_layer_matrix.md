# Item 1 (Luciano, 2026-10-31) -- matriz de camadas por perfil

Verificação ao vivo, frota de pé, servidor `sa-east-1` (certs/chaves
reais já em disco, não regenerados). "Verificado criptograficamente"
significa: assinatura/chave checada de verdade (desafio assinado e
verificado, ou campo de assinatura decodificado e validado), não
apenas um campo do tamanho/OID esperado.

| Camada | Classic | PQC | Hybrid | Verificado cripto? | Evidência (arquivo:linha) |
|---|---|---|---|---|---|
| **Troca de chaves TLS** | ECDH secp384r1 | ML-KEM-1024 (MLKEM1024) | SecP384r1MLKEM1024 | **Sim** (Classic/Hybrid via sonda `openssl s_client` independente, ao vivo; PQC via log real do gateway, OpenSSL puro não interopera com esse grupo -- ver item 1 anterior) | `artifacts/classic/openssl_s_client_probe.txt`; `artifacts/hybrid/openssl_s_client_probe.txt`; `janela3/experiment2 - PQC/sa-east-1/L0/server/w03_run21_gateway.log` (`curveID:"MLKEM1024"`) |
| **Autenticação TLS -- certificado do SERVIDOR** | RSA-4096, `sha256WithRSAEncryption` (`mtls.crt`) | **ML-DSA-65 puro** (`mtls_pqc.crt`) | RSA-4096 base + extensão `X509v3 Alternative Signature Algorithm` (ML-DSA-65) (`mtls_hybrid.crt`) | Sim (campo de assinatura/chave lido direto via `openssl x509 -text` no servidor) | `mock_mtls/main.go:72-149` (seleção do arquivo por perfil); confirmado ao vivo: `openssl x509 -in mtls_pqc.crt -noout -text` → `Public Key Algorithm: ML-DSA-65`; `mtls_hybrid.crt` → `Public Key Algorithm: rsaEncryption` + extensão alternativa |
| **Autenticação TLS -- certificado do CLIENTE** | RSA-4096 | ML-DSA-65 puro | RSA-4096 + AltSignatureValue (ML-DSA-65) | **Sim, com desafio assinado de verdade** (não só o tamanho do campo) | `artifacts/pqc/verify_pqc_cert_output.txt` (RESULT: verificado); `artifacts/hybrid/verify_hybrid_cert_output.txt` (RESULT: verificado) -- rodados agora, ao vivo, via `mock-service-os/certs/main.go -verify-pqc-cert`/`-verify-hybrid` |
| **Cadeia de certificados** (real do handshake mTLS é **2 níveis, folha→raiz direto**, não 3 -- `DECISIONS.md:7939-7943`) | raiz RSA (`ca.crt`) → folha RSA | raiz **ML-DSA-65** (`root_ca_pqc.crt`/`issuer_ca_pqc.crt`) → folha ML-DSA-65 -- cadeia PQC ponta a ponta | raiz RSA clássica (`ca.crt`) → folha RSA+extensão ML-DSA-65 | Parcial -- algoritmo da raiz PQC confirmado agora ao vivo (`openssl x509 -text`); verificação formal folha→raiz (assinatura da CA sobre a folha) NÃO rodada nesta auditoria para PQC puro, só para hybrid (via `-verify-hybrid`) | Confirmado agora: `openssl x509 -in root_ca_pqc.crt -noout -text` → `Signature Algorithm: ML-DSA-65`; idem `issuer_ca_pqc.crt`. **Achado real**: isso resolve a assimetria do parecer (item 4.3/Rec.2) -- a cadeia PQC da v8 NÃO é mais classicamente assinada no nível de CA (era na v7) |
| **Assinatura JWT (client_assertion, request_object, id_token, JARM)** | PS256 (RSA-PSS) | ML-DSA-65 puro | **Composta**: Strong Nesting (PS256+ML-DSA-65, server-issued) OU extensão de payload (RS256+ML-DSA-65 via claim `pqc`, client-issued) dependendo do artefato | Sim, verificação dupla real (ambas as camadas da assinatura checadas, não só uma) | `thesis/scripts/pqc-signer/signer_core.mjs:36-91` (as duas construções); `artifacts/pqc/verify_jwt_output.txt` (v7, reaproveitável -- ver nota abaixo) |
| **⚠️ Rótulo pode confundir**: o cabeçalho (`alg`) de um id_token Hybrid **lê "PS256"** mesmo quando a assinatura real é Strong Nesting (PS256+ML-DSA-65) -- quem olhar só o header vê "clássico". Não é um bug, é documentado no próprio código, mas é exatamente uma célula que não é o que o rótulo sugere à primeira vista. | | | | | `thesis/scripts/pqc-signer/signer_core.mjs:175-176` |
| **JWE (id_token encryption)** | RSA-OAEP + A256GCM | **RSA-OAEP + A256GCM, idêntico** | **RSA-OAEP + A256GCM, idêntico** | N/A -- não migrado, por decisão de escopo já declarada | `thesis/scripts/opin_flow.py:798-802`: "a troca de chaves de criptografia em si NÃO está no escopo desta migração PQC" -- **LIMITAÇÃO DECLARADA, não um gap silencioso**: os 3 perfis usam a MESMA criptografia clássica aqui |
| **Conexão interna entre participantes (AS→RS)** | CurveP256 (carve-out clássico, SNI `matls-api.local`) -- **idêntico nos 3 perfis** | idêntico | idêntico | Sim, verificado por correlação de log (`verify_negotiated_groups()`) em todas as 720 execuções oficiais, 0 violações | `campaign_run.py:823-831` (`_INTERNAL_CARVEOUT_EXPECTED_CURVE = "CurveP256"`); Decision 108's `check_artifact_health` |
| **Diretório/PKI** (`root_ca_pqc.crt`/`issuer_ca_pqc.crt`, termo PKI_bytes do OPINsize -- **SEPARADOS da cadeia real do handshake mTLS, nunca usados para verificar uma conexão real**, `DECISIONS.md:7939-7943`) | RSA (`ca.crt`, cadeia clássica, 2 níveis folha→raiz) | **ML-DSA-65** (confirmado ao vivo agora, ambos os níveis) | RSA clássica (`ca.crt`) -- hybrid usa a mesma raiz clássica do Classic para o termo PKI_bytes | Sim (campo de assinatura lido direto, ao vivo) | Confirmado agora: `openssl x509 -in root_ca_pqc.crt -noout -text` e `issuer_ca_pqc.crt` → `Signature Algorithm: ML-DSA-65` nos dois |

## Resumo das células que NÃO são o que o rótulo sugere

1. **JWE do id_token**: igual nos 3 perfis (RSA-OAEP/A256GCM) -- decisão de
   escopo já declarada no código, não um gap silencioso.
2. **Header `alg` do JWT Hybrid**: lê "PS256" (parece clássico) mesmo
   quando a assinatura real é dupla (PS256+ML-DSA-65) -- documentado,
   mas visualmente enganoso para quem não lê o `pqc`/segunda assinatura.
3. **Certificado do servidor sob Hybrid**: a chave pública continua
   RSA-4096 (só ganha uma EXTENSÃO ML-DSA-65) -- "Hybrid" no servidor
   não troca a chave base, soma uma segunda assinatura. Consistente com
   o design documentado (Bindel et al. 2019), mas vale deixar explícito
   no texto da tese para não sugerir troca de chave onde não há.
4. **Diretório/PKI**: pendência não verificada nesta auditoria (ver acima).
