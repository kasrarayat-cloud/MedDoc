# JUDGEMENT — code-only deploy of `a8ead1cb`

**Judged against `docs/foundation/deploys/20260901-a8ead1cb.md`.** Baseline
`2026-09-01T01:13:43Z`; deployed `02:24:56Z`; captured `02:29:22Z`.

⚠️ **PROVENANCE, STATED HONESTLY.** The declaration was written and placed before
the act and printed in full into the deploy transcript, but it was **not
committed** when the deploy ran — the gate said so out loud, and a deploy is
`present`, not `strict`, because it is reversible (#96(b)). The baseline
timestamp precedes the act by 71 minutes and the declaration's content is fixed
in the transcript. Weaker than a commit timestamp, stronger than memory.

## ⚠️ THE FIRST ATTEMPT REFUSED, AND IT WAS RIGHT

`deploy-prod.sh` was run once at `01:14:14Z` and **REFUSED**: the citation gate
read **0 of 4** on `a8ead1cb`. The PR head `412b2a40` was cited 4 of 4 — but a
**merge commit is a different commit and needs its own evidence**. Nothing was
built, migrated or recreated, and production was verified untouched by image id
(`a736745fdaa8`, unmoved). The deploy proceeded only after the merge commit was
independently cited 4 of 4.

## Verdict: 17 of 17

### MUST CHANGE — both moved

| quantity | declared | measured | verdict |
|---|---|---|---|
| image `transcribe-md` | `a736745fdaa8` → must move | **`0d519d709038`** | ✓ |
| image `transcribe-md-worker` | `69561f6f6963` → must move | **`53d0642c31af`** | ✓ |

### MUST NOT CHANGE — all fifteen held

| quantity | declared | measured | verdict |
|---|---|---|---|
| migrations applied | 111 | 111 | ✓ |
| `AuditAction` enum labels | 153 | 153 | ✓ |
| visits | 54 | 54 | ✓ |
| signed visits | 36 | 36 | ✓ |
| patients | 42 | 42 | ✓ |
| note templates | 14 | 14 | ✓ |
| twin compiled versions | 3 | 3 | ✓ |
| twin certifications | 1 | 1 | ✓ |
| twin fill manifests | 2 | 2 | ✓ |
| twin mappings total | 150 | 150 | ✓ |
| **twin mappings `CERTIFIED`** | **115** | **115** | ✓ |
| **twin mappings with an approver** | **86** | **86** | ✓ |
| containers | 9, identical membership | 9, identical | ✓ |
| co-tenants | `307 · 410 · 404 · 200` | `307 · 410 · 404 · 200` | ✓ |
| audit rows (may only GROW) | 12105 | **12119** (+14) | ✓ |

⚠️ **THE TWO BOLD ROWS ARE THE POINT.** **(c) has not run** — it is the next
ruled act. Had either moved, something would have written to clinical mappings
that nobody authorised. Both held exactly.

**The audit +14 is within the declared "may only GROW"** and is ordinary
application traffic across the window; no clinical count moved beside it.

## Structural verification — worker source, both controls

| token | before | after | verdict |
|---|---|---|---|
| `REGISTRY_SUBCONCEPTS` | 0 | **2** | ✓ |
| `isSubConcept` (registry) | 0 | **1** | ✓ |
| `allergy.substance` in the accumulating set | 0 | **1** | ✓ |
| `isSubConcept` filter at the proposer seam | 0 | **2** | ✓ |
| POSITIVE CONTROL `past_medical_history` | 1 | **1** | ✓ |
| NEGATIVE CONTROL `zzz_not_a_real_token` | 0 | **0** | ✓ |
| ⛔ `family_history.condition` in the accumulating set | — | **0** | ✓ |

The last row is the **S1 fix confirmed in production**: the adversarial pass
measured that joining family-history conditions destroys the RELATION
(`"Diabetes; Hypertension"` with no indication of whose, `valid:true`, zero
blocking). It is absent from the shipped accumulating set.

⚠️ **THE WEB `.next` BUNDLE IS NOT VERIFIED, AS DECLARED IN ADVANCE.** Two
candidate discriminators were rejected **before** the act: `allergy.substance`
already resolved in 7 chunks (it lives in the proposer's prompt list — a check
on it passes before the deploy runs), and `REGISTRY_SUBCONCEPTS` reads 0 there
only because identifiers are minified — the control `REGISTRY_SYNONYMS`, in this
code for weeks, also reads 0. That check would have been **unpassable by
construction**. An unverified surface named honestly beats a green bought with a
token that cannot discriminate.

## What this deploy did NOT do

**It certified nothing and wrote no clinical row.** `MIN_CERTIFIED_FILLED_FIELDS`
remains **10**. **(c)** — ruling #158's 35 live-template confirmations — is a
separate ruled mutation, and **(d)** is behind it. No clinical walk: that is
owed by (d), on QA, against a byte-identical build.
