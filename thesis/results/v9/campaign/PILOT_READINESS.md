# v9 pilot readiness dossier — PQC/hybrid/AND, AWS

Standalone document (Decision 54, revised in Decision 55). Does not
require having followed the previous decisions. Covers: actual status
of the pilot's 7 criteria, the binary/image pins and how they are
delivered, the tolerance derived from handshake bytes, the restricted
IAM policy and the verification script, the emergency stop independent
of Terraform, the cost ceiling (including the worst case), and what
remains on Luciano's side.

Scope: a 60-execution pilot (4 profiles × 3 routes × N=5), never the
official 960-execution campaign. Branch `v9/fase1-local`. No AWS
action was taken to produce this document.

---

## a) The 7 go/no-go criteria — actual status

| # | Criterion (threshold) | Status | Evidence / what's missing |
|---|---|---|---|
| 1 | Per-message sizes — 0B in the ClientHello, ±4B in the Certificate, 0B in the rest, across the 12 captures (4 profiles × 3 routes) | **Validated locally (complete mechanics)** | Actual pcap decrypted per profile, flight extracted via tshark, matches the baselines exactly across the 4 profiles. `SSHExecutor.dedicated_capture` implemented and tested. **Only AWS confirms:** the real interface (`ens5`), traffic crossing 2 real instances, tolerance with a real SAN (EIP). |
| 2 | Actual initcwnd ≥ 10 segments | **Only verifiable on AWS** | Method written and mechanically tested, only meaningful with RTT > 0. |
| 3 | Zero errors in 20/20 executions on the most distant route (`sa-east-1/L325`) | **Only verifiable on AWS** | Depends on the real L325 route. |
| 4 | 44 HTTP / 6 mTLS / 28 JWT / 4 jwks / 4 CA, exact, across 60/60 | **Partially validated locally** | Exact count confirmed across hundreds of real local executions, 4 profiles, 0 errors. The 60/60 cardinality under a real network can only be closed by AWS. |
| 5 | Zero errors across the 60/60 combined executions | **Partially validated locally** | Same evidence as item 4. |
| 6 | CurveID + DualAuthenticated in 100% of executions, keylog+capture+sizes extracted | **Validated locally (mechanics)** | Confirmed across the 4 profiles, hundreds of real connections, 0 failures. |
| 7 | Each route's RTT within ±10% of nominal, two channels agreeing | **Not validated** | Method defined, depends on real routes. |

**Honest reading:** none of the 7 criteria is 100% closed without AWS — expected, as they are criteria about a real network. This document ensures that the MECHANICS of each one is implemented and tested with real data wherever that is possible locally.

---

## b) Handshake baselines — the 4 values, with their source

**Correction in this round:** an earlier round classified the Classic and PQC values as "never cited before" — false. All 4 were already in the pre-registration, Decision 14 (T6, instrumentation), `DECISIONS.md` lines 1511-1519 and 1750-1751 (the consolidated "Total measured at the Handshake() boundary" table).

| Profile | handshakeBytesIn (client→server) | handshakeBytesOut (server→client) | Source |
|---|---|---|---|
| Classic | 1.513 | 1.640 | Decision 14, `DECISIONS.md` L1517/L1750-1751 |
| PQC | 10.728 | 10.878 | Decision 14, `DECISIONS.md` L1518/L1750-1751 |
| Hybrid-v8 | 8.397 | 8.552 | Decision 14, `DECISIONS.md` L1519/L1750-1751 |
| Hybrid-AND | 11.902 | 12.177 | Decision 14, `DECISIONS.md` L1520/L1750-1751 |

All 4 were reconfirmed with 0B of deviation across 480 real local connections in this session (Decision 54) and again across 20 certificate rebuilds with 4 SAN variations (Decision 55, item 3, below).

---

## c) Binary/image pins and how they are delivered

### What is pinned, and why
`thesis/results/v9/campaign/PINS.json` (version-controlled) freezes, for the 4 images: the `.tar`'s sha256 (`tar_sha256`), the `RootFS.Layers`, a subset of the `.Config` (`Entrypoint`/`Cmd`/`Env`/`ExposedPorts`), and — only for `gateway`/`proxy`, which have their own Go binary — the sha256 of the extracted binary and the output of `go version -m`. All from **a single built image**, never recomputed automatically. Changing the file requires a numbered Amendment in `DECISIONS.md`.

**Reproducibility, actually tested:** the gateway and proxy binary was built twice, from scratch (`--no-cache`), with explicit `-trimpath` + `GOARCH=amd64` — **identical** sha256 both times, for both binaries. The `.tar` from `docker save` of the same local image (never rebuilt) is also byte-for-byte reproducible across independent invocations (confirmed, Decision 68).

### Image ID — Decision 68 (Amendment): dropped as a verification criterion
**Real finding, live, during the pilot's actual execution (Decision 67):** `docker image inspect .Id` **diverges between different Docker versions**, even when loading the SAME `.tar`, with provably identical content — confirmed by running a `docker:25-dind` (a local proxy for the server's real version, Docker 25.0.16) alongside the operator's Docker (29.9.1): for the 4 images, `RootFS.Layers` and the `.Config` subset come out **identical** in both versions; only the final `.Id` diverges. This broke the Decision 55 mechanism on the first real execution (the gateway aborted on a divergent Image ID, with the binary confirmed identical underneath).

**Fixed:** the delivery fail-closed no longer checks Image ID. Image ID is still recorded in PINS.json, only as an **informational** field — never compared, never a cause for abort. No pre-registered pilot criterion (the 7 evaluation criteria/thresholds) changes — this is only the MECHANISM for verifying that the delivered image is the expected one, never what is measured.

### How the image reaches each instance — never via `docker build`, 2 real hops, identity by content (Decision 68)
v8's real model (`deliver_images.sh`) restored in Decision 59 — two hops, each on the right machine:
1. `deliver_images.py`, on the OPERATOR's machine (which has Docker): `docker save -o <image>.tar <image>`, the `.tar`'s sha256 **checked against the pinned `tar_sha256`** (Decision 68, BEFORE any scp — catches a wrong/rebuilt local image, never just transport corruption), disk-space check on the control host, scp to the control host (`~/images/`). For the gateway, it also extracts the binary and checks its sha256 against PINS.json here.
2. `SSHExecutor._deliver_image(image_key, host)`, running FROM THE CONTROL HOST: scp of the already-staged `.tar` (a LOCAL file, never `docker save`) to the host, `ssh host docker load`. Fail-closed, in this order: (a) the host's `RootFS.Layers` identical to the pinned ones; (b) the host's `.Config` subset identical to the pinned one; (c) for `gateway`/`proxy`, the sha256 of the binary INSIDE the loaded container, matching the pinned one. Image ID is read/recorded, informational only.

Tested (a tampered tar fails — before any scp; a tampered layer fails; tampered config fails; a tampered binary inside the image fails; everything correct passes; a second `SSHExecutor` instance, simulating a future official campaign, passes with the same pins; no call invokes `docker` locally on the control host).

### Architecture of each instance — who runs what
**Correction to Decision 56(a) (a real finding from Decision 59):** "the orchestrator and the build run on the operator's machine... NEVER on an AWS instance" was **wrong** for the "orchestrator" part. The *build* (docker build/save) indeed remains only on the operator's machine — but `orchestrator.py` (`SSHExecutor`, the actual remote execution) only reaches the server/clients from inside the **control** host (the server/clients' Security Group only accepts SSH from the control host's own EIP, `main.tf`) — `deliver_to_control()` (`deliver_source.py`, Decision 59) delivers `orchestrator.py` + dependencies to the control host, from where it actually runs. `pki_relay.py`/`collect_artifacts.py`/`cleanup.py`/`emergency_stop.py`/`iam_dryrun_check.py` keep running **on the operator** (never on the control host) — they talk to the control host via SSH (`pki_relay.py`/`collect_artifacts.py`) or not even that (`cleanup.py`/`emergency_stop.py`/`iam_dryrun_check.py`, direct AWS API only).

| Instance | Type | Architecture | Runs gateway/proxy/measure/pqc-signer? | Runs `docker` locally? |
|---|---|---|---|---|
| Control | `t4g.micro` | **ARM64** | **No.** The 4 images (linux/amd64) never get loaded/run on the control host — only relayed (`.tar` staged by `deliver_images.py`, scp to the host, `docker load` running ON THE HOST via ssh). `orchestrator.py` actually runs HERE (Decision 59), but never invokes `docker` as a local process (confirmed by test, `test_deliver_image_nunca_invoca_docker_localmente`). | **No — never.** |
| Server (L0, sa-east-1) | `m7i-flex.large` | x86_64 | gateway + measure (both amd64, matching the real architecture) |
| Client L0 (co-located) | `m7i-flex.large` | x86_64 | proxy (amd64) |
| Client L219 (eu-north-1) | `m7i-flex.large` | x86_64 | proxy |
| Client L325 (ap-southeast-1) | `m7i-flex.large` | x86_64 | proxy |

No ARM variant of the 3 images exists or is needed.

### `check_capture_prerequisites` — now checks layers+config, no longer Image ID
Fixed in Decision 53 (it only checked presence — an image from a different origin/build would pass without being caught) and again in Decision 68 (Image ID dropped as a criterion, for the same reason as the rest of this document): `check_capture_prerequisites(host, expected_measure_layers=..., expected_measure_config=...)` explicitly fails if `mockopin-v9-measure`'s `RootFS.Layers`/`.Config` subset on the instance do not match PINS.json. Tested with wrong layers (fails), wrong config (fails), and both correct (passes).

---

## d) Handshake-byte tolerance — derived, validated across 20 rebuilds

**Corrections in this round:** (1) the earlier proposal was asymmetric without justification — the certificate's serial number affects BOTH `In` AND `Out`, across all 4 profiles, not just Hybrid-AND's `In`. (2) the previous 480 samples came from a single certificate build, never sampling variation across builds. Both are resolved by the mechanism below, which replaces the earlier proposal entirely.

### `expected_handshake_bytes(profile, certs_dir)`
`thesis/results/v9/integration/evaluate_criteria.py`: `expected = measured_baseline + (sum_DER_of_deployed_certificates − sum_DER_of_baseline_certificates)`, per direction (`in` = client chain, `out` = server chain). Never re-estimates from scratch — it only propagates the certificate difference, the only legitimate source of variation identified (Decision 54, item 3) outside of SNI/tickets/MinVersion (all already controlled or verified by another mechanism, including the binary pin from item c above).

### Real validation: 20 rebuilds, 4 SAN variations, 4 profiles
`make certs` run 20 times (loopback, private IP, EIP-style public IP, DNS name — 5 builds each), covering the 4 profiles, with the gateway actually rebuilt and measured on every rebuild (never simulated):

| SAN variant | Builds | Deviation (predicted − measured), all profiles/directions |
|---|---|---|
| Loopback (default) | 5 | **0B, all** |
| Private IP (10.0.1.50) | 5 | **0B, all** |
| EIP-style public IP (203.0.113.50) | 5 | **0B, all** |
| Additional DNS name | 5 | **0B, all** |

**20/20 builds, 0B of deviation across ALL.** Real example (Classic, SAN changed from loopback to a private IP): the server certificate drops from 900B to 880B DER (-20B) — predicted `out=1620`, measured `out=1620`. Exact.

### Finding in this round (Decision 56, item 2): the deviation against the BASELINE can also be zeroed out, not just predicted
The technique above correctly predicts any deviation, but we discovered it is possible to **eliminate the deviation at the source**: `make certs SERVER_IPS="<real IP>,::1"` — keeping the comma and the `::1` (an IPv6 placeholder, decorative, never contacted — the same role the IP itself already has in the SAN, Decision 30: only DNS matters for verification) — preserves EXACTLY the same SAN entry count and type as the baseline (`127.0.0.1,::1`), since an IPv4 entry always takes up 4 bytes and an IPv6 entry always 16 bytes in ASN.1 DER, **regardless of the value**. Validated across 20 real builds (10 private-style IPs, 10 public EIP-style, varying the value on every build): **0B delta against the BASELINE (not just against the prediction) across the 4 profiles, in both directions, in 20/20 builds, 80/80 profile×direction combinations.** An alternative using DNS-name padding was tested and discarded — the exact length needed does not scale linearly with the name's size (ASN.1 encoding edge effects observed, never calibrated to an exact 0B in 3 attempts) — the IP+`::1` technique is simpler and provably exact, and is preferred. No Amendment needed (the technique is viable and does not change any code, only the `SERVER_IPS` value passed to `make certs` on pilot day).

### Final proposed rule (pre-pilot, for approval — not applied retroactively)
- **The pre-registered thresholds remain the official gate** for criterion 1: 0B in the ClientHello, ±4B in the Certificate, 0B in the other messages (Decision 20/29/30, never changed).
- **`expected_handshake_bytes` enters as an additional diagnostic**, never replacing the gate above. Implemented (`orchestrator._bytes_diagnostic_for_profile`, called by the smoke gate): a predicted-vs-measured deviation ≠ 0 sets `bytes_diagnostic_needs_decision=True` in the manifest — **PAUSES and asks for Luciano's decision, exactly like the smoke gate** (never aborts nor ignores on its own). Tested (zero deviation passes; a detected deviation flags the pending decision without blocking `smoke_ok`, which continues to be decided only by the already-official criteria; mutant confirmed).

---

## e) IAM policy and dry-run verification

### Every EC2 call Terraform makes (plan/apply/destroy), for the `main.tf` resources
| Resource | plan (refresh) | apply (create/modify) | destroy |
|---|---|---|---|
| `aws_instance` | `DescribeInstances`, `DescribeInstanceAttribute`, `DescribeVolumes`, `DescribeTags` | `RunInstances`, `CreateTags`, `ModifyInstanceMetadataOptions` (IMDSv2), `ModifyInstanceAttribute` (shutdown behavior) | `TerminateInstances` |
| `aws_eip` | `DescribeAddresses` | `AllocateAddress`, `AssociateAddress`, `CreateTags` | `DisassociateAddress`, `ReleaseAddress` |
| `aws_key_pair` | `DescribeKeyPairs` | `ImportKeyPair` (the key is supplied via `tls_private_key`, never generated by AWS — hence `ImportKeyPair`, not `CreateKeyPair`) | `DeleteKeyPair` |
| `aws_security_group` | `DescribeSecurityGroups` | `CreateSecurityGroup`, `CreateTags` (includes the egress rule, inline in the resource) | `DeleteSecurityGroup` |
| `aws_vpc_security_group_ingress_rule` (SSH + gateway) | `DescribeSecurityGroupRules` | `AuthorizeSecurityGroupIngress`, `CreateTags` | `RevokeSecurityGroupIngress` |
| `data.aws_vpc`/`data.aws_subnets` | `DescribeVpcs`, `DescribeSubnets` | — | — |
| Provider (every operation) | `sts:GetCallerIdentity` | — | — |

### Restricted policy (3 regions + tag conditions where IAM allows)
```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Sid": "LeituraGeralTresRegioes",
      "Effect": "Allow",
      "Action": [
        "ec2:Describe*", "sts:GetCallerIdentity",
        "servicequotas:GetServiceQuota", "budgets:ViewBudget", "budgets:DescribeBudgets"
      ],
      "Resource": "*",
      "Condition": { "StringEquals": { "aws:RequestedRegion": ["sa-east-1", "eu-north-1", "ap-southeast-1"] } }
    },
    {
      "Sid": "CriarSemCondicaoDeTagPossivel",
      "Effect": "Allow",
      "Action": ["ec2:RunInstances", "ec2:AllocateAddress", "ec2:ImportKeyPair", "ec2:CreateSecurityGroup"],
      "Resource": "*",
      "Condition": {
        "StringEquals": {
          "aws:RequestedRegion": ["sa-east-1", "eu-north-1", "ap-southeast-1"],
          "aws:RequestTag/Project": "mockopin-pqc-v9-piloto"
        }
      }
    },
    {
      "Sid": "CreateTagsSoNaCriacaoDesteProjeto",
      "Effect": "Allow",
      "Action": "ec2:CreateTags",
      "Resource": "*",
      "Condition": {
        "StringEquals": {
          "aws:RequestedRegion": ["sa-east-1", "eu-north-1", "ap-southeast-1"],
          "ec2:CreateAction": ["RunInstances", "AllocateAddress", "ImportKeyPair", "CreateSecurityGroup"]
        }
      }
    },
    {
      "Sid": "ModificarSoRecursoJaTagueado",
      "Effect": "Allow",
      "Action": [
        "ec2:ModifyInstanceMetadataOptions", "ec2:ModifyInstanceAttribute", "ec2:TerminateInstances",
        "ec2:AssociateAddress", "ec2:DisassociateAddress", "ec2:ReleaseAddress", "ec2:DeleteKeyPair",
        "ec2:AuthorizeSecurityGroupIngress", "ec2:RevokeSecurityGroupIngress", "ec2:DeleteSecurityGroup"
      ],
      "Resource": "*",
      "Condition": {
        "StringEquals": {
          "aws:RequestedRegion": ["sa-east-1", "eu-north-1", "ap-southeast-1"],
          "aws:ResourceTag/Project": "mockopin-pqc-v9-piloto"
        }
      }
    }
  ]
}
```

**Honest limitation, with no possible change:** `RunInstances`/`AllocateAddress`/`ImportKeyPair`/`CreateSecurityGroup` do not support an `aws:ResourceTag` condition at creation time (the resource does not exist yet) — they use `aws:RequestTag` (what WOULD be applied), which is the most IAM allows at that point. `ec2:CreateTags` is restricted by `ec2:CreateAction` (it only tags what was just created by one of the project's 4 actions) instead of by resource, for the same reason.

### `iam_dryrun_check.py` — tested with a mock, never run by this process
Calls each action above with `--dry-run`, per region, using real parameters (pinned AMIs, instance type) for the actions with no pre-existing resource; for the ones that require a real resource (`TerminateInstances`, `ModifyInstanceAttribute`, `ReleaseAddress`, `DeleteKeyPair`, `RevokeSecurityGroupIngress`), it accepts the ID as an optional argument and explicitly marks `"nao testado"` without it — never fabricating a PASS. Tested (7 tests, `DryRunOperation`→authorized, `UnauthorizedOperation`→rejected, aggregation per region). **Luciano runs it, with real credentials, before the pilot** (`python iam_dryrun_check.py --profile mockopin-pqc [--instance-id ... --key-name ... --sg-id ... --allocation-id ... --rule-id ...]`).

---

## f) Emergency stop — two layers

### Layer 1 (normal): `cleanup.py`, depends on Terraform state
```
python cleanup.py --tf-dir ../../terraform --profile mockopin-pqc --release-eips --force
```
See detail in section g. Depends on `terraform destroy` working (intact and accessible state).

### Layer 2 (independent of state): `emergency_stop.py`, new
For the case where Terraform's state is lost, corrupted, or inaccessible, but the resources still exist in the account. Acts via the **`Project=mockopin-pqc-v9-piloto` tag**, directly through the API, across the 3 regions — every destructive action checks the tag (via a filtered `describe-*` call) immediately before acting, never on a loose ID.

```
python emergency_stop.py --profile mockopin-pqc --execute
```
Without `--execute`, it only lists what would be done (the default mode, never accidentally destructive). Order: instances (terminate, wait up to 2 min before proceeding) → EIPs (disassociate, then release) → security groups (only after the instances have actually terminated) → key pairs. Tested with a mock (6 tests: dry mode never calls anything mutable; each action only runs on the ID that came from the tag; disassociates before releasing an EIP; mutant confirmed).

### Worst-case cost if nothing is done beyond the self-shutdown
Self-shutdown (`terminate`, not `stop`) always caps COMPUTE — but **never releases the EIP** (Decision 45, confirmed directly in v8's actual code: no self-shutdown path releases an Elastic IP).

- **Compute, capped by the self-shutdown:** 4× `m7i-flex.large` for 4h + 1× `t4g.micro` for 5h ≈ (4 × US$0,0958 × 4h) + (US$0,0084 × 5h) ≈ **US$1,575**, and then it stops (instances terminated).
- **EBS:** `delete_on_termination` is the provider's default (never set to `false` in `main.tf`) — deleted along with the instance, no residual cost.
- **5 orphaned EIPs, WITH NO TIME LIMIT AT ALL:** US$0,005/h each × 5 = **US$0,025/hour, indefinitely**, until someone runs `emergency_stop.py`/`cleanup.py --release-eips` or releases them manually. Over a forgotten month: ≈ **US$18**. Small, but non-zero and uncapped — exactly the scenario `emergency_stop.py` (layer 2) exists to cover even without Terraform.

---

## g) Budget alert — reclassified

**Correction in this round:** an AWS budget alert is a **notification with billing delay** (AWS Budgets are recalculated ~every 8-24h, never in real time) — never an automatic limit that stops spending. Treating it as "protection" would be overly optimistic; it is an alarm that warns after the fact, not a brake.

A general alert already exists on the account (inherited from v8, value never read by this project, by policy — Decision 27; historical reference in `DECISIONS.md`: US$27,72). **Revised suggestion: US$3** (below the earlier suggestion of US$5) — still ~2.6× the pilot's normal estimate (US$1,15 with margin), low enough to sound the alarm quickly even against the orphaned-EIP scenario (US$0,60/day) before it accumulates much, but far enough from the normal estimate to avoid triggering from price fluctuation. The final decision on the value is Luciano's.

---

## h) Residual risks — updated

| # | Risk | Status | Pending decision |
|---|---|---|---|
| 1 | The `mockopin-v9-measure` image needs to exist on each instance | **RESOLVED** (Decision 55, item 2; verification mechanism fixed in Decision 68) — delivered via `docker save`/`docker load`, identity checked by `RootFS.Layers`+`.Config` against PINS.json, never `docker build` on the instance | None |
| 2 | Proxy and measure lacked the same verification mechanism as the gateway | **RESOLVED** (Decision 55, items 1-2; Decision 68) — all 4 now have a `tar_sha256`+`RootFS.Layers`+`.Config` pin (gateway/proxy also have a binary+`go version -m` pin, checked inside the loaded image) | None |
| 3 | Control host with no separate per-tag/project self-shutdown | Accepted and mitigated (`self_terminate_hours=5`, `terminate`) | None |
| 4 | General budget alert, not pilot-specific | Reclassified (item g) — still pending creation | Decide the value (US$3 suggested) and create the alert |
| 5 | AND covers only TLS 1.3 | Design limitation accepted since the pre-registration | None |
| 6 | `handshakeBytesIn/Out` with no formal pre-registered tolerance | **RESOLVED regarding the mechanism** (Decision 55, item 3) — `expected_handshake_bytes` validated across 20 real rebuilds, 0B deviation; becomes a pausing diagnostic, never the official gate | Approve the mechanism as a permanent diagnostic (not a criterion change, just a new layer) |
| 7 | IAM policy broader than ideal on some creation actions | **Documented with precise technical justification** (item e) — it is a real IAM limit, not an avoidable slack | Accept as is (there is no more restrictive alternative within IAM) |
| 8 (new) | `emergency_stop.py` was never run against real AWS (only tested with a mock) | Honestly recorded | Luciano tests it in dry mode (`without --execute`) against the real account before relying on it in a real emergency |

---

## i) Does the runbook cover the 3-4h window with Luciano present?

Yes — the sequence is unchanged from this revision (apply → PKI → capture preflight → smoke gate, now with the bytes diagnostic → 60 executions → collection → cleanup), ~45min-1h20 of active execution within the 4h/5h self-shutdown window, with 3 explicit pause/decision points (capture preflight, smoke gate including the new bytes diagnostic, final cleanup verification) — all always Luciano's decision, never automatic.

---

## j) What remains, on Luciano's side (short list)

1. Confirm vCPU Service Quotas in the 3 regions and Elastic IP quotas in `sa-east-1` (item b of the original dossier — unchanged).
2. Generate a personal SSH key pair and export `TF_VAR_operator_ssh_public_key` before `terraform apply`.
3. Review and apply the proposed IAM policy (section e) to the orchestrator's user/role — accept the documented slack in `RunInstances`/`AllocateAddress`/`ImportKeyPair`/`CreateSecurityGroup`, or adjust it on your own.
4. Run `iam_dryrun_check.py` with real credentials before the pilot, and separately test `emergency_stop.py` in dry mode (without `--execute`) against the real account.
5. Decide the value of the pilot-specific budget alert (US$3 suggested) and create it.
6. Approve (or request adjustment of) the bytes-diagnostic mechanism (`expected_handshake_bytes`, section d) as an additional pause-and-ask layer on the smoke gate — it never replaces the pre-registered thresholds.
7. Set the pilot date.
