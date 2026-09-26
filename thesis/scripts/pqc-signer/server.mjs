// A persistent HTTP server wrapping the exact same signer_core.js dispatch
// sign.mjs uses, so opin_flow.py's hot statistical loop (8 ML-DSA-65 calls
// per full flow execution) pays one Node process start per profile run,
// not one `docker run --rm -i` container spawn per signature. Measured:
// each spawn cost ~0.79s and accounted for ~94% of the PQC/Híbrido
// latency delta over Clássico -- a cost of *how the signer is invoked*,
// not of the ML-DSA-65 algorithm itself, which this change leaves
// untouched (same signer_core.mjs, same jose/node:crypto call).
//
// Mirrors tls_kem_proxy's own lifecycle exactly (opin_flow.py's
// start_pqc_signer_service()/stop_pqc_signer_service()): started once
// per profile (or per single-run process), reused for every signature in
// that run, torn down afterwards -- see thesis/scripts/tls_kem_proxy/
// main.go's own header comment for the analogous "delegate to a
// long-lived Go/Node helper" pattern this now shares.
//
// POST / with one of signer_core.mjs's three JSON request shapes on the
// body -> the corresponding plain-text result, exactly matching what the
// one-shot sign.mjs would have written to stdout for the same input.
// GET /healthz -> "ok", once the process is actually accepting
// connections -- used by opin_flow.py's readiness poll (same pattern as
// tls_kem_proxy's own HTTP-based readiness check, not a bare TCP connect,
// since a bound port doesn't yet mean the request handler is wired up).
import http from 'node:http';
import { handleRequest } from './signer_core.mjs';

const port = Number(process.env.PORT || '8901');

const server = http.createServer((req, res) => {
  if (req.method === 'GET' && req.url === '/healthz') {
    res.writeHead(200, { 'Content-Type': 'text/plain' });
    res.end('ok');
    return;
  }
  if (req.method !== 'POST') {
    res.writeHead(405, { 'Content-Type': 'text/plain' });
    res.end('method not allowed');
    return;
  }
  let body = '';
  req.on('data', (chunk) => { body += chunk; });
  req.on('end', async () => {
    try {
      const input = JSON.parse(body);
      const output = await handleRequest(input);
      res.writeHead(200, { 'Content-Type': 'text/plain' });
      res.end(output);
    } catch (err) {
      res.writeHead(500, { 'Content-Type': 'text/plain' });
      res.end(`pqc-signer server error: ${err && err.stack ? err.stack : err}`);
    }
  });
  req.on('error', (err) => {
    res.writeHead(400, { 'Content-Type': 'text/plain' });
    res.end(`pqc-signer server request error: ${err}`);
  });
});

server.listen(port, '0.0.0.0', () => {
  console.log(`pqc-signer: persistent server listening on :${port}`);
});
