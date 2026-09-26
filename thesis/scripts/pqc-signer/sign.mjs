// One-shot CLI entry point: reads one JSON request from stdin, writes one
// result to stdout, exits. Unchanged behavior since v2 -- see
// signer_core.mjs's own header comment for the three input/output shapes
// and for why this file still exists alongside server.mjs. Kept as
// the Docker image's default CMD specifically so every caller that isn't
// opin_flow.py's hot statistical loop (hybrid_verify.py, the artifacts/
// capture scripts run standalone, or a human running `docker run --rm -i
// mockopin-pqc-signer` by hand to check one signature) keeps working
// exactly as before, with no dependency on a persistent service being up.
import { handleRequest } from './signer_core.mjs';

const input = JSON.parse(await new Promise((resolve, reject) => {
  let data = '';
  process.stdin.on('data', (chunk) => { data += chunk; });
  process.stdin.on('end', () => resolve(data));
  process.stdin.on('error', reject);
}));

process.stdout.write(await handleRequest(input));
