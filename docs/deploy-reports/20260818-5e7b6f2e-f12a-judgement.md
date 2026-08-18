# F12-a IS LIVE — deploy `5e7b6f2e`, 2026-08-18T13:38:52Z — **21 of 21 JUDGED**

Judged against `docs/foundation/deploys/20260818-1d48d7cd.md`, which was
committed **before** the act and whose numbers were never revised.

| | |
|---|---|
| deployed | `5e7b6f2eec6490a7c67be60ccabafb87d2cb42d7` |
| the item's merge commit | `daf2b13d74f164393151decd1d5f805f969883e4` |
| citation on the DEPLOYED commit | **4 of 4, every line `a1`** — `CI` 32139865606 · `e2e` 32139865522 · `a11y-ci` 32139865562 · `secrets-scan` 32139865464 |
| citation on the item's merge commit | **4 of 4** — `e2e` at `a2`, explained in the ledger (issue #631) |
| declaration | `20260818-1d48d7cd.md`, committed `fd6ea2d2` |
| rollback | `:pre-5e7b6f2e-20260818` on both service images |
| migration | **none** — code only |

⚠️ **THE DEPLOYED COMMIT IS NOT THE ITEM'S MERGE COMMIT, AND BOTH ARE CITED
SEPARATELY.** `daf2b13d..5e7b6f2e` is **two markdown files** — the ledger and the
declaration rename — and nothing else. Rather than lean on that, the exact
commit that shipped was gated in its own right. *"I deployed `main`"* and *"I
judged what I deployed"* are different claims, and this row is the second one.

---

## MUST CHANGE — 4 of 4

| # | declared | observed |
|---|---|---|
| 1 | visits whose export prints an office E/M code **10 → 5** | **10 → 5** ✔ |
| 2 | of the five, **3 SIGNED** | **3** ✔ |
| 3 | **1** attributable to the TEMPLATE arm | **1** ✔ |
| 4 | **4** attributable to ruling #126a's NOTE-TEXT fallback | **4** ✔ |

⚠️ **ROW 4 IS THE ITEM.** Without the fallback the adversarial pass forced, this
deploy would have moved **one** production row. Four operative notes were
keeping an office E/M level purely because they carry no bound template.

## MUST NOT CHANGE — 12 of 12

| # | declared | observed |
|---|---|---|
| A1 | visits NEWLY printing a level | **0** ✔ |
| A2 | office visits that STOP printing one | **0** ✔ |
| A3 | untemplated visits with no operative markers keeping their level | **21** ✔ |
| A4 | `transcribe_visits` | **46** ✔ |
| A5 | `transcribe_md_patients` | **34** ✔ |
| A6 | `status='SIGNED'` | **29** ✔ |
| A7 | `emScoredCode` non-null | **17** ✔ |
| A8 | `cptCodes.em` blobs | **27** ✔ |
| A9 | `cptCodes.em.signedCode` | **6** ✔ |
| A10 | `note_templates` | **10** ✔ |
| A11 | applied migrations | **104** ✔ |
| A12 | co-tenants `307 · 404 · 200 · 200 · 410` | exact ✔ |

⚠️ **A7, A8 AND A9 HOLDING IS A PASS, NOT AN OMISSION.** The declaration says so
in advance: this deploy suppresses a PROJECTION and deliberately does **not**
clean up the five existing stored artifacts. **A comparison showing those counts
FALLING would have been a finding.** Removing them is an irreversible production
mutation and belongs behind `run-ruled-mutation.sh` with its own declaration.

## STRUCTURAL — 5 of 5

| declared | observed |
|---|---|
| 9 of 9 containers healthy, only the two app images moved | ✔ — `transcribe-md` and `transcribe-md-worker` `Up 45 seconds (healthy)`; the other seven still `Up 10–11 days` |
| `assert-migrations-applied` 104 of 104 | ✔ |
| `check-imaging-em-artifacts` 0 of 18 | ✔ — **and it is still blind to the operative class by construction**, exactly as the declaration warned. Its green is not coverage for this item |
| `check-cotenants` | ✔ |
| rollback tag cut against the RUNNING image ids before any step | ✔ — `:pre-5e7b6f2e-20260818` |

---

## HOW THE PROJECTION ROWS WERE VERIFIED — and what was deliberately NOT done

⚠️ **NO REAL DOCTOR'S VISIT WAS EXPORTED, SIGNED OR RENDERED.** Rows 1-4 and
A1-A3 describe what an EXPORT prints, and the only way to read that directly
from production is to export somebody's actual clinical note. Standing law
forbids it, so they are verified two ways that do not touch a record:

1. **THE SHIPPED IMAGE CARRIES THE PREDICATE**, read from the running container
   with a traversal control (91 files found, so the probe is measuring):

       note-shape.ts                  present
       templateIsSilent                  4 occurrences
       OFFICE_SKELETON_SECTIONS          5
       isProcedureNoteShapeFromText      2
       "emBlob && emApplies"             1
       "READY && emApplies"              1
       NEGATIVE CONTROL "if (emBlob) {"  0   ← the pre-fix shape is GONE

2. **THE PREDICATE RE-DERIVED OVER THE POST-DEPLOY DATABASE** reproduces every
   declared number exactly (10 → 5 · 5 · 3 · 1 · 4 · 0 · 21). The data did not
   move — A4-A11 prove that independently — so the arithmetic and the shipped
   code agree.

**What this does NOT claim:** that a PDF or DOCX was produced and read. That
proof is the E2E arm asserting the exported BYTES of both artifacts carry no
`992\d\d` for the operative class, which ran green in the citation above.

---

## STILL OPEN, NAMED RATHER THAN IMPLIED

- **`worker.ts:963-967`** still COMPUTES a `cptCodes.em` blob for an operative
  note; the naive fix would delete the procedure CPT code from a colonoscopy.
- **Editing a SUPERSEDED template mutates `sections` in place** on a row a signed
  visit still points at — worse than the hole #126a closed, because the fallback
  is suppressed by design when labels survive.
- **`GET /api/visits/[id]`** returns the raw `cptCodes` blob unprojected.
- **`check-imaging-em-artifacts.sh`** cannot see the operative artifact class.
- Two `codes-tab` reversions of this change's own discipline.
