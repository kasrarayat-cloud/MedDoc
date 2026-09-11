# JUDGEMENT — the #313 O5 IR backfill of `d2120cdd` (ruled act)

**Judged against `docs/foundation/mutations/20260911-backfill-sole-paragraph-control.md`,
every row of it.** The declaration was committed at `a36d7c10`, 2026-09-11T02:25:18Z.
The dry run ran 04:24:51–04:24:58Z. The act started at 04:25:3xZ and printed its
END STATE 🟢 shortly after. Its process was terminated at 04:36:22Z (see "the exit
code").

## VERDICT — 🟢 every declared row holds. Exactly three rows moved, and all three were declared.

The act was bracketed by the same read-only snapshot, run before (04:25:30Z) and
after (04:36:22Z).

| row | declared | before | after | |
|---|---|---|---|---|
| `d2120cdd.compiledDocumentIr` | gains `soleParagraphControl: true` on exactly 27 fields | md5 `ef92ff7e…`, property absent | md5 `816219b9…`, **property present** | 🟢 |
| the 27 flagged fields | HPI ×4, PMH ×3, PSH ×3, Allergies ×2, Medications ×2, Family History ×3, Impression ×4, Plan ×5, Telehealth consent | — | display orders 6–9, 18–20, 22–24, 26–27, 30–31, 39–41, 56, 58–61, 63–67 | 🟢 |
| bullet groups under the current mappings | 7 groups / 24 members; Allergies ×2 refused (G7) | 0 | **7 / 24**: d6–d9, d18–d20, d22–d24, d30–d31, d39–d41, d58–d61, d63–d67 | 🟢 |
| `audit_logs` | +1 `TEMPLATE_TWIN_COMPILED` | 12518 (8 of that action) | **12519 (9)** | 🟢 |
| IRs carrying the property | — | 0 | **1** (`d2120cdd` only) | 🟢 |

**MUST NOT change:**

| row | before | after | |
|---|---|---|---|
| `d2120cdd` `structureSha256` / `staticContentSha256` | `2b7384fa` / `542a938a` | `2b7384fa` / `542a938a` | 🟢 |
| **the certified, ACTIVE `18a7ae19`** | IR md5 `ef92ff7e…` | **`ef92ff7e…`: not one byte** | 🟢 |
| the four other compiled versions' IRs | `f92e992c…`, `906c6c83…` ×3 | identical | 🟢 |
| `d2120cdd` mapping rows (all columns, 53) | md5 `5b1c7db8…` | `5b1c7db8…` | 🟢 |
| `d2120cdd` field-definition rows (53) | md5 `8ef53ebc…` | `8ef53ebc…` | 🟢 |
| fill manifests · certifications · note templates · active | 5 · 4 · 17 · `939aa9ea` | 5 · 4 · 17 · `939aa9ea`; `3877d5cf` still `draft` | 🟢 |
| **clinical: visits · patients · signatures** | **58 · 46 · 40** | **58 · 46 · 40** | 🟢 |

The door's own END STATE agreed independently: read-back IR == written IR, both
sha columns unchanged, and a re-plan refuses ONLY on "already present".

## ⚠️ THE EXIT CODE IS 143, AND IT IS NOT THE ACT FAILING

The script printed its END STATE and "🟢 backfill complete", and then **did not
exit**. Its node process stayed alive inside the worker for about 10 minutes. The
database showed no open transaction, no idle-in-transaction session and no
blocked lock, so the write was committed.

The script ends with `.finally(() => prisma.$disconnect())`, so the handle that
held the event loop open is not Prisma. It is likely a client opened at import
time (for example Redis, behind the fill cache). The same shape is in the confirm
and certify doors. Filed as `RULED-ACT-SCRIPTS-DO-NOT-EXIT`.

**The orchestrator terminated ONLY that script's process.** It checked the
arguments of in-container pid 280 (`scripts/backfill-sole-paragraph-control.ts`)
and sent SIGTERM. The worker's own process was untouched. The door printed
`FINISHED … exit 143` with its "do not re-run until you know what landed"
warning. **What landed is established above by the before/after snapshot, not by
the exit code.**

## ⚠️ THE ROLLBACK FLOOR IS NOW CROSSED FOR THE OWNER'S PRACTICE

`SELECT count(*) … LIKE '%soleParagraphControl%'` went from **0 to 1**, as
declared. Code below #313 cannot parse `d2120cdd`'s IR. While the template is a
draft, a rollback costs only the draft. After activation it would break the
owner's active form. **From this act onward, #313's deploy is the rollback floor
for the owner's practice.** A rollback below it first needs a declared mutation
that strips the key.
