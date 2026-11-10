#!/usr/bin/env node
// Gera as 6 chaves de assinatura do AS (mock_as) e do RS (insurance-server-
// lambdas) para os perfis classic/hybrid/pqc -- Fase B da higiene de chaves
// privadas (2026-11-10, Decisao 114 e nota de fechamento). Antes desta
// rodada, essas 6 chaves foram geradas por um comando `node -e` ad-hoc
// dentro do container `node:24-alpine`, nunca versionado -- este script
// substitui aquele comando por algo reproduzivel.
//
// Precisa do Node >=24 com suporte experimental a ML-DSA no Web Crypto
// (`crypto.webcrypto.subtle`) -- o Node do host (22.x) nao suporta e falha
// com ERR_OSSL_UNSUPPORTED. Rode sempre dentro do container, nunca no host:
//
//   docker run --rm -v "$(pwd):/work" -w /work node:24-alpine \
//     node mock-service-os/certs/generate-crypto-profiles.mjs
//
// So escreve dentro de mock-service-os/mock_as/crypto-profiles/ e
// insurance-server-lambdas/src/main/resources/crypto-profiles/ -- os dois
// diretorios tem .gitignore (*.json) cobrindo essas chaves desde a Fase B;
// nunca commite o conteudo gerado por este script.
//
// Dentro de cada lado (AS, RS), o perfil hibrido REAPROVEITA a mesma chave
// RSA do classico e a mesma chave ML-DSA-65 do pqc (mesmo kid quando
// aplicavel) -- nao sao chaves hibridas separadas. Confirmado comparando
// hash das chaves reais pre-existentes antes de escrever este script.
import { webcrypto } from 'node:crypto';
import { writeFileSync, mkdirSync } from 'node:fs';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';

const { subtle } = webcrypto;
const __dirname = dirname(fileURLToPath(import.meta.url));
const REPO_ROOT = join(__dirname, '..', '..');

const AS_DIR = join(REPO_ROOT, 'mock-service-os', 'mock_as', 'crypto-profiles');
const RS_DIR = join(
  REPO_ROOT, 'insurance-server-lambdas', 'src', 'main', 'resources', 'crypto-profiles',
);

async function genRsaJwk() {
  const { privateKey } = await subtle.generateKey(
    { name: 'RSA-PSS', modulusLength: 2048, publicExponent: new Uint8Array([1, 0, 1]), hash: 'SHA-256' },
    true, ['sign', 'verify'],
  );
  const jwk = await subtle.exportKey('jwk', privateKey);
  // subtle inclui key_ops/ext que nenhum arquivo real carrega -- descartados.
  const { kty, n, e, d, p, q, dp, dq, qi } = jwk;
  return { kty, n, e, d, p, q, dp, dq, qi, use: 'sig', alg: 'PS256' };
}

async function genMlDsaKeyPair() {
  return subtle.generateKey({ name: 'ML-DSA-65' }, true, ['sign', 'verify']);
}

async function mlDsaToAkpJwk(privateKey) {
  // formato nativo do Node/jose para AKP: kty, alg, pub, priv (seed de 32
  // bytes, 43 chars base64url) -- confirmado contra as chaves reais ja
  // rotacionadas antes de escrever este script.
  const { kty, alg, pub, priv } = await subtle.exportKey('jwk', privateKey);
  return { kty, alg, use: 'sig', pub, priv };
}

async function mlDsaToPkcs8Spki(privateKey, publicKey, kid) {
  // subtle (nao o KeyObject.export sincrono) -- unico caminho que produz a
  // forma compacta baseada em seed (72/2632 chars base64 padrao) que o
  // BouncyCastle do RS (KeyFactory "ML-DSA", "BC") ja consome com sucesso.
  const pkcs8 = Buffer.from(await subtle.exportKey('pkcs8', privateKey)).toString('base64');
  const x509 = Buffer.from(await subtle.exportKey('spki', publicKey)).toString('base64');
  return { kty: 'AKP', alg: 'ML-DSA-65', kid, pkcs8PrivateKeyBase64: pkcs8, x509PublicKeyBase64: x509 };
}

async function main() {
  mkdirSync(AS_DIR, { recursive: true });
  mkdirSync(RS_DIR, { recursive: true });

  // --- AS (mock_as) ---
  const asRsaJwk = await genRsaJwk();
  const asMlDsaPair = await genMlDsaKeyPair();
  const asMlDsaJwk = await mlDsaToAkpJwk(asMlDsaPair.privateKey);

  writeFileSync(join(AS_DIR, 'classic.json'), JSON.stringify({
    signingAlgs: ['PS256'],
    signingKey: asRsaJwk,
  }, null, 2));

  writeFileSync(join(AS_DIR, 'hybrid.json'), JSON.stringify({
    signingAlgs: ['MLDSA65-RSA2048-PSS-SHA256'],
    classicSigningKey: asRsaJwk,
    pqcSigningKey: asMlDsaJwk,
  }, null, 2));

  writeFileSync(join(AS_DIR, 'pqc.json'), JSON.stringify({
    signingAlgs: ['ML-DSA-65'],
    signingKey: asMlDsaJwk,
  }, null, 2));

  // --- RS (insurance-server-lambdas) ---
  const rsRsaJwkBase = await genRsaJwk();
  const rsaKid = crypto.randomUUID();
  const rsRsaJwk = { ...rsRsaJwkBase, kid: rsaKid };

  const rsMlDsaPair = await genMlDsaKeyPair();
  const mlDsaKid = crypto.randomUUID();
  const rsMlDsaKey = await mlDsaToPkcs8Spki(rsMlDsaPair.privateKey, rsMlDsaPair.publicKey, mlDsaKid);

  writeFileSync(join(RS_DIR, 'classic.json'), JSON.stringify(rsRsaJwk, null, 2));

  writeFileSync(join(RS_DIR, 'hybrid.json'), JSON.stringify({
    alg: 'MLDSA65-RSA2048-PSS-SHA256',
    classicSigningKey: rsRsaJwk,
    pqcSigningKey: rsMlDsaKey,
  }, null, 2));

  writeFileSync(join(RS_DIR, 'pqc.json'), JSON.stringify(rsMlDsaKey, null, 2));

  console.log('OK: 6 arquivos escritos em', AS_DIR, 'e', RS_DIR);
  console.log('AS  classic/pqc RSA n len=%d priv(seed) len=%d', asRsaJwk.n.length, asMlDsaJwk.priv.length);
  console.log('RS  classic/pqc RSA n len=%d pkcs8 b64 len=%d spki b64 len=%d',
    rsRsaJwk.n.length, rsMlDsaKey.pkcs8PrivateKeyBase64.length, rsMlDsaKey.x509PublicKeyBase64.length);
}

main().catch((err) => { console.error(err); process.exit(1); });
