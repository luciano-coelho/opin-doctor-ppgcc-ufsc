# Secao (b) -- Tamanhos

Fonte: `criteria_evaluation.json`, criterio 1 (bytes por mensagem de handshake, extraidos do pcap decifrado real, com baseline do RFC 8446 Secao 4.4.2) + `raw/piloto_calls.json` (jwt_sizes/jwk_sizes reais por chamada).

## Bytes por mensagem de handshake, por perfil x rota (real vs baseline)
| Perfil | Rota | ClientHello | Certificate | OK? |
|---|---|---|---|---|
| classico | L0 | 336 (baseline 336) | 913 (baseline 913, tol. 4) | OK |
| classico | L219 | 336 (baseline 336) | 913 (baseline 913, tol. 4) | OK |
| classico | L325 | 336 (baseline 336) | 913 (baseline 913, tol. 4) | OK |
| pqc | L0 | 1779 (baseline 1779) | 5632 (baseline 5632, tol. 4) | OK |
| pqc | L219 | 1779 (baseline 1779) | 5632 (baseline 5632, tol. 4) | OK |
| pqc | L325 | 1779 (baseline 1779) | 5632 (baseline 5632, tol. 4) | OK |
| hibrido-v8 | L0 | 1876 (baseline 1876) | 6255 (baseline 6255, tol. 4) | OK |
| hibrido-v8 | L219 | 1876 (baseline 1876) | 6255 (baseline 6255, tol. 4) | OK |
| hibrido-v8 | L325 | 1876 (baseline 1876) | 6255 (baseline 6255, tol. 4) | OK |
| hibrido-and | L0 | 1858 (baseline 1858) | 6582 (baseline 6582, tol. 4) | OK |
| hibrido-and | L219 | 1858 (baseline 1858) | 6582 (baseline 6582, tol. 4) | OK |
| hibrido-and | L325 | 1858 (baseline 1858) | 6582 (baseline 6582, tol. 4) | OK |

Demais mensagens (ServerHello/EncryptedExtensions/CertificateRequest/Certificate_cliente/CertificateVerify/Finished) por perfil x rota -- ver `consolidated.json -> sizes.message_sizes_by_profile_route[*].other_messages` (omitido aqui por repeticao -- os valores sao IDENTICOS nas 3 rotas de cada perfil, como esperado: o conteudo do handshake nao depende da rota/latencia, so o cipher suite do perfil).

## JWT (bytes, real, por perfil)
| Perfil | median | p95 | min | max | n |
|---|---|---|---|---|---|
| hibrido-v8 | 7156.0 | 9093 | 5061 | 9093 | 420 |
| classico | 1208.0 | 3146 | 621 | 3146 | 420 |
| pqc | 5283.5 | 7246 | 4696 | 7246 | 420 |
| hibrido-and | 7156.0 | 9093 | 5061 | 9093 | 420 |

## JWKS (kty/use/bytes, real, por perfil -- entradas unicas observadas)
- **hibrido-v8**: [{'kid': 'I4SZA4ycHOiCgSV7jKQEwgGmhsX3aV0KnTEF372by2A', 'kty': 'HYBRID', 'use': 'sig', 'size_bytes': 2208}, {'kid': 'AsnNSC2ubVrgn8NjhuQgItg7nTpgjuieL1G8R3HsG4k', 'kty': 'RSA', 'use': 'enc', 'size_bytes': 256}, {'kid': 'mZi6awCMmw-lTxi5N3k9d6i_Wa5veP2IZyMvNolkcvQ', 'kty': 'HYBRID', 'use': 'sig', 'size_bytes': 2208}, {'kid': 'mZi6awCMmw-lTxi5N3k9d6i_Wa5veP2IZyMvNolkcvQ', 'kty': 'RSA', 'use': 'sig', 'size_bytes': 256}]
- **classico**: [{'kid': 'xQLs45xYyJr1omHs4qnB2rhes9qNFHIHQ5YPQKVJliM', 'kty': 'RSA', 'use': 'sig', 'size_bytes': 256}, {'kid': 'AsnNSC2ubVrgn8NjhuQgItg7nTpgjuieL1G8R3HsG4k', 'kty': 'RSA', 'use': 'enc', 'size_bytes': 256}, {'kid': '041486ea-f7b8-4b36-9dfb-fadf2966d0e8', 'kty': 'RSA', 'use': 'sig', 'size_bytes': 256}]
- **pqc**: [{'kid': 'QiYeUNBZXaKsrgR_BfvZfQJHxyPo9mez54AgoBeB9VU', 'kty': 'AKP', 'use': 'sig', 'size_bytes': 1952}, {'kid': 'AsnNSC2ubVrgn8NjhuQgItg7nTpgjuieL1G8R3HsG4k', 'kty': 'RSA', 'use': 'enc', 'size_bytes': 256}, {'kid': '5226750c-4adb-4d00-be74-c6a38845622d', 'kty': 'AKP', 'use': 'sig', 'size_bytes': 1952}]
- **hibrido-and**: [{'kid': 'I4SZA4ycHOiCgSV7jKQEwgGmhsX3aV0KnTEF372by2A', 'kty': 'HYBRID', 'use': 'sig', 'size_bytes': 2208}, {'kid': 'AsnNSC2ubVrgn8NjhuQgItg7nTpgjuieL1G8R3HsG4k', 'kty': 'RSA', 'use': 'enc', 'size_bytes': 256}, {'kid': 'mZi6awCMmw-lTxi5N3k9d6i_Wa5veP2IZyMvNolkcvQ', 'kty': 'HYBRID', 'use': 'sig', 'size_bytes': 2208}, {'kid': 'mZi6awCMmw-lTxi5N3k9d6i_Wa5veP2IZyMvNolkcvQ', 'kty': 'RSA', 'use': 'sig', 'size_bytes': 256}]

## OPINsize
Nao computado. `OPINsize` e uma metrica agregada especifica da v7/v8 (soma de bytes de todo o fluxo OIDC-FAPI PAR/JARM/mTLS de uma execucao OPIN completa). O piloto v9 mede um protocolo e um conjunto de criterios pre-registrados DIFERENTES (handshake TLS/mTLS direto, sem fluxo OIDC-FAPI) -- nao existe um equivalente direto de `OPINsize` nos 7 criterios pre-registrados de v9, entao nenhum numero e inventado aqui.
