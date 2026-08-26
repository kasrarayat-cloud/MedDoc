> **ARCHIVED CANON — moved verbatim from `AGENTS.md` on 2026-08-26.**
>
> **This body is the AUTHORITY.** `AGENTS.md` carries a one-line index row
> pointing here; that row is a POINTER, never the rule. Nothing in this file is
> rewritten — corrections are appended and dated and superseded wording is kept,
> because in this programme the correction is the point.
>
> Original position: entry **19 of 124** in `AGENTS.md`, under **This is NOT the Next.js you know**.
> Why the split: `docs/canon/README.md`.

## A WELL-CHOSEN FIXTURE DISGUISES A WRONG UNIVERSE

**Third cousin of the two sections below, and the nastiest of the family.**
Those describe a check that measures the wrong QUANTITY, and a check that
measures the right quantity over the wrong SET. This one is a check that is
correct in both respects **and runs in a configuration production does not
use** — while *looking* like it runs in the right one, because its fixture was
chosen from the right domain.

> **A pipeline proof runs in the PRODUCTION UNIVERSE: production's FLAG SET and
> production's ROUTES. Anything else is a proof about a system nobody ships.**

⚠️ **REFERENCE CASE, 2026-08-14 — RC-1, one command from merge.** The branch
carried a unit suite (3790 green), four mutation proofs, and a QA walk that read
**15 of 15** on the live stack. Every one of them was wrong about the universe,
in two independent ways:

| the proof used | production uses |
|---|---|
| `specialty: 'primary-care'` → `buildSoapSystemPrompt` | **`ultrasound`** → `buildUltrasoundSystemPrompt`, a DIFFERENT builder |
| `TRANSCRIBE_MD_EVIDENCE_ANCHORS` unset | **`true`** |

Measured: **all 7** production visits bound to the templates the change targets
carry `specialty='ultrasound'`. The proof covered **0%** of the affected rows.
The consequence was not cosmetic — the model wrote the section correctly and had
its answer overwritten with an unfilled form, deleting the side of exam and the
study indication from a signed imaging report, silently, with both structure
gates passing.

⚠️ **AND THE FIXTURE IS WHAT MADE IT INVISIBLE.** The QA walk's template was
imaging-SHAPED — `## EXAM`, `SIDE OF EXAM: —`, a `500 milliseconds` tripwire —
so fifteen green arms *read* as an imaging proof to their own author. A wrong
universe announces itself when the fixture looks foreign. **When the fixture
looks native, nothing announces anything.**

The discipline is mechanical:

1. **ENUMERATE THE ROUTES.** If a value selects between implementations — a
   report type, a specialty, a builder, a renderer — **proving one proves ONE.**
   Run the matrix. `describe.each` over the routes costs a line.
2. **ENUMERATE THE FLAGS, FROM THE RUNNING CONTAINER.** Not from `.env`, not
   from the compose file, not from memory: `docker exec … printenv`. A test that
   defaults a flag OFF while production runs it ON is testing the rollback.
3. **ASK WHICH PRODUCTION ROWS THE PROOF COVERS, AND COUNT THEM.** "It passes"
   and "it passes for anybody" are different claims. A `GROUP BY` on the
   affected population answers it in one query, and the answer here was zero.
4. **A FIXTURE FROM THE RIGHT DOMAIN IS NOT A ROUTE.** Shape is not routing.

