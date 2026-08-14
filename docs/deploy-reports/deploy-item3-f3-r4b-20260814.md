# Deploy report — item 3 + F3 + R4b + the .qm-rdoc-gate census

**Commit deployed:** `133f55c1924be9b5cf4a30090ad177ac657f0850`
**Citation:** 4 of 4 on the merge commit — `CI`, `e2e`, `a11y-ci`, `secrets-scan`
**Declaration:** `docs/foundation/deploys/20260814-133f55c1.md` (committed before
the act as `docs/deploy-declarations/item3-f3-r4b-20260814.md` in `4cdf7fb1`)
**Rollback image:** `:pre-item3-20260814`
**Log:** `docs/deploy-logs/deploy-20260814T173629Z.log` (gitignored; on the host)

## Judgement against the declaration

| quantity | declared | before (17:35:30Z) | after (17:46:52Z) | verdict |
|---|---|---|---|---|
| visits | 40 → **re-baselined 42** | 42 | 42 | ✅ |
| signed | 25 | 25 | 25 | ✅ |
| patients | 29 | 29 | 29 | ✅ |
| templates | 9 | 9 | 9 | ✅ |
| `audit_logs` | monotonic | 11382 | 11382 | ✅ |
| migrations | **102 → 103** | 102 | 103 | ✅ MUST CHANGE |
| allergy-conflict reasons | 0 | 0 | 0 | ✅ declared row |
| retired-vocabulary reasons | 4, not rewritten | 4 | 4 | ✅ |

**No difference the declaration does not name.**

### ⚠️ The re-baseline, stated before the act and repeated here

The declaration was authored hours earlier and said `visits 40` /
`audit_logs from 11360`. Measured immediately before the deploy: **42** and
**11382**. Both extra visits belong to `kasra.rayat@gmail.com` / "Solo — kasra
rayat" / gastroenterology, created 15:46:50Z and 15:46:58Z — **the owner's own
session, the one that produced the cream-panel screenshot this deploy fixes.**
No pilot doctor's record is involved, and nothing here was a smoke target.

The comparison judges against the measured-now column, because the
MUST-NOT-CHANGE claim is *"this deploy does not move them"*, not *"they equal
the numbers from four hours ago"*. That substitution was written into the
declaration **before** the deploy ran, not discovered afterwards.

## Structural verification (no clinical record touched)

Per the standing law: container health, migrations, and the shipped bundle —
never a doctor's visit.

**Worker** (runs from `src`, has no `.next` — the first grep was aimed at a
path that does not exist and returned a zero for both the needle *and* the
positive control, which is how it was caught):

| claim | evidence |
|---|---|
| positive control | `buildUltrasoundSystemPrompt` — 6 files |
| the never-editorialize clause ships | present in `system-default-template.ts` |
| the mismatch banner ships | `structure-mismatch-reason.ts` present |
| F3 — L4 on the additive writer | `applyAdditiveReviewState` ×3 in `04-generate-soap.ts` |

**App bundle:**

| claim | evidence |
|---|---|
| positive control | `review-doc-em-level` in 2 chunks |
| hosted gate roots ship | `qm-rounds-host qm-rdoc-gate qm-rdoc-gate-em` **and** `…-quiet` |
| **no unhosted gate root survives** | `"qm-rdoc-gate qm-rdoc-gate-(quiet\|em)` — **0 matches** |

**Containers:** `transcribe-md`, `transcribe-md-worker`, `gotenberg` all healthy.

**Standing invariant checks, all exit 0:**
`check-imaging-em-artifacts` (0 of 17 imaging visits carry an E/M artifact) ·
`assert-migrations-applied` (103/103) · `check-composite-fk` (present and
correctly shaped) · `check-ingress-tls` (every SNI completes a fresh handshake) ·
`check-bind-mount-agreement` · `check-hooks-installed`.

⚠️ Re-measured after the first pass captured `tail`'s exit status instead of
each script's — six exit codes that meant nothing and looked like six passes.

## What shipped

1. **Item 3** — the never-editorialize clause, the survival gate over all three
   note-writing prompts, and a mismatch banner that names what was measured.
2. **F3** — L4 migrated to `applyAdditiveReviewState`, the same mechanism L6
   uses, so an allergy-conflict reason can no longer be overwritten by a later
   structure banner. Plus the two named residues: the banner is bounded (five
   names then "and K more") and L6 stopped appending retired vocabulary.
3. **R4b + the census** — all four `.qm-rdoc-gate` panels now carry the Rounds
   bridge. Three were unhosted: the medication list (owner screenshot) and the
   two inline E/M gates in `review-document-view`, which were reported by
   nobody and found by enumerating the family from the CSS rather than from the
   class names.
4. **`scripts/gh-runs.sh`** — refuses any `--commit` sha under 40 characters.

## Open items carried forward

- **Drafted prescriptions have no edit/remove surface post-R5.** Deliberate;
  re-opens on first doctor contact.
- **Export-block disposition** — whether `MEDICATIONS` should print at all is an
  OWNER QUESTION, recorded open. Exports unchanged.
- ⚠️ **`gh-runs.sh` cannot catch a WRONG full sha.** It refuses anything under
  40 characters, which is the trap it was built for — but a mistyped 40-hex
  string is accepted and returns `[]` exactly like the short-sha false
  all-clear. Encountered live this session. The two-view check (`--branch`
  alongside `--commit`) is what covers it.
