# Offline package of the official campaign's raw data

The raw data (pcaps, logs, TLS session `.keylog` files) from
`thesis/results/v9/campaign_oficial_conta_nova_raw/` **does not go into git**
(see `.gitignore`) -- it is kept compressed in a single package, outside the
repository, in a local private directory. This file records where
that package is and its sha256, so the package's integrity can
be checked without the package itself being version-controlled.

- **Full path:** `C:\Users\lucia_csx8nlz\mockopin-offline-data\campaign_oficial_conta_nova_raw.tar.gz`
  (outside `MockOPIN\`, never tracked by git).
- **Format:** `.tar.gz` (zstd not available in this environment at the time of
  generation -- `tar -czf`, standard gzip).
- **Size:** 100.340.836 bytes (~96 MiB / ~100 MB).
- **Package sha256:** `cdd10999aa19512c06cfdcd2b6fd825dc75b7bea325b4a31f57a532e55bf1228`
- **Contents:** the complete tree of `campaign_oficial_conta_nova_raw/`,
  including the 78 `.keylog` files (TLS session secrets) together with
  their corresponding `.pcap` files -- the two need to be together for
  offline decryption/debugging, which is exactly this local package's
  purpose.
- **Integrity check performed:** the package was extracted to a
  temporary directory and the resulting 725 files were checked,
  one by one, by sha256 against `campaign_oficial_conta_nova_sha256_manifest.txt`
  (the same list version-controlled in git) -- **0 divergences, 725/725
  files identical**. The temporary directory was removed after
  verification.

The local working copy at `thesis/results/v9/campaign_oficial_conta_nova_raw/`
was neither altered nor removed by this packaging -- this package is an
additional copy, not a migration.
