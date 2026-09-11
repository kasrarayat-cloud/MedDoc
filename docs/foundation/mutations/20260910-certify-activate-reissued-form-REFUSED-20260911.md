# JUDGEMENT — certify and activate the re-issued 53-control form (ruled act): REFUSED BY ITS OWN PRIVACY GATE

**Judged against `docs/foundation/mutations/20260910-certify-activate-reissued-form.md`.**
The declaration was committed at `a36d7c10`, 2026-09-11T02:25:18Z. The
preconditions were met before the act: the deploy judgement is committed at
`f4e9c77c`, 04:42:30Z, and the backfill and confirm are both judged 🟢. The
report-only run ended at 04:41:46Z with exit 0. The commit run finished at
04:44:16Z with **exit 1**.

## VERDICT — ⛔ THE ACT DID NOT HAPPEN. Its synthetic-evidence privacy gate refused the certification encounter, and it wrote nothing but the scan's own usage row.

### What landed (the same snapshot, before 04:4x and after 04:44:17)

| row | declared if it had run | before | after | |
|---|---|---|---|---|
| `d2120cdd.certificationStatus` | → CERTIFIED | NEEDS_CONFIRMATION | **NEEDS_CONFIRMATION** | not run |
| certifications | 4 → 5 | 4 | **4** | not run |
| `3877d5cf` / `939aa9ea` | → active / inactive | draft / active | **draft / active** | not run |
| field detection | → CERTIFIED ×53 | RECOGNIZED ×53 | **RECOGNIZED ×53** | not run |
| pinned note / latest test / output object | → set | NULL | **NULL** (no MinIO object) | not run |
| `audit_logs` (SYNTHETIC_TESTED / CERTIFIED / ACTIVATED) | +3 named | 12531 (9/5/5) | **12531 (9/5/5)** | 🟢 nothing written |
| `api_usage_events` | +j ≥ 1 | 1867 | **1868**: one `tm_template_synthetic_phi_scan` row at 04:44:06Z | the gate's own scan |
| `ai_calls` | +k ≥ 1 | 1686 | **1686** | — |
| **clinical: visits · patients · signatures** | 58 · 46 · 40 | 58 · 46 · 40 | **58 · 46 · 40**. No fixture straggler | 🟢 |
| the active `18a7ae19` (IR, mappings, certification row) | not one row | as before | **identical** | 🟢 |
| `d2120cdd` mappings (53 CERTIFIED) | unchanged | md5 `cd6ac2bd…` | **`cd6ac2bd…`** | 🟢 |

### Why it refused, measured rather than guessed

A read-only diagnostic ran inside the worker. It derived the encounter through
the same `deriveVerificationEncounter` call and called the real gate through a
client that captures the model's verdict. The diagnostic's own scan added a
second usage row, and its scratch file was removed as root, with the removal
verified. It showed:

- The derived encounter (2154 chars, synthetic by construction) **ends with
  "The patient was referred by Dr. Alan Whitfield for further evaluation."**
- The deterministic checks passed: the explicit synthetic marker is present,
  and there are 0 structured-PHI hits.
- The model scan returned `{"directIdentifierClasses":["referring provider name"],
  "appearsExplicitlySynthetic":true,"anyUncertain":true}`. That is
  `TemplateTwinSyntheticEvidenceRejectedError`.

**Two correct rules collided.** #312 confirmed Referring MD as dictated
evidence (`visit_metadata.referring_physician`), because acceptance row 7 wants
the referrer filled. So the generator now dictates a referrer, and it invents a
plausible physician NAME. The certification gate (since #375, 2026-07-22)
refuses any name in synthetic evidence. `18a7ae19` passed the same gate on
2026-09-07, because its referrer row was manual and its encounter had no name.

### The remedy, and why it is not improvised here

The generator must name a ROLE, not a person, for example "referred by their
primary care physician". That still fills the Referring MD control and carries
no identifier. **It is a code change on the certification path, so it needs a
PR, its checks and a deploy.** It cannot be patched into a running act. The
act is re-run under this same committed declaration once that change is
deployed.

⚠️ **A second defect found on the way.** `synthetic-test.ts` catches EVERY
error from the gate with a bare `catch {}` and reports "use clearly labeled
synthetic evidence". So a scan that is merely UNAVAILABLE (an outage, credits
exhausted) reads as an accusation that the evidence contains PHI. Here the
diagnostic separated the two cases; the product does not. Filed.
