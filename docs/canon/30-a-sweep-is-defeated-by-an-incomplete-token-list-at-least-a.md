> **ARCHIVED CANON — moved verbatim from `AGENTS.md` on 2026-08-26.**
>
> **This body is the AUTHORITY.** `AGENTS.md` carries a one-line index row
> pointing here; that row is a POINTER, never the rule. Nothing in this file is
> rewritten — corrections are appended and dated and superseded wording is kept,
> because in this programme the correction is the point.
>
> Original position: entry **55 of 124** in `AGENTS.md`, under **This is NOT the Next.js you know**.
> Why the split: `docs/canon/README.md`.

## A SWEEP IS DEFEATED BY AN INCOMPLETE **TOKEN LIST** AT LEAST AS OFTEN AS BY A MISSING **FORM**

**Standing 2026-08-14, and it corrects an earlier version of itself — which is
the reason it is worth reading.**

The first draft of this entry said the R5 sweep "enumerated two of four naming
forms" and missed a file that reached the deleted surface by role name and
element id. **That diagnosis was wrong about its own file.** The missed file,
`rounds-a11y.spec.ts`, reaches the gate by the TEST ID `rounds-gate-host-rx` at
line 214 — one line BEFORE the role-name reach at :215. The sweep DID search
test ids. Completing a form checklist would not have found it.

> **The token was absent because it is INTERPOLATED AT ITS DEFINITION SITE.**
>
>     data-testid={`rounds-gate-host-${active.id}`}
>
> **No grep of the application source can produce the literal
> `rounds-gate-host-rx`. It exists only in the code that CONSUMES it.**

The same failure recurred inside a form the sweep had already "covered": it
found the `qm-lin-rx-*` class family and missed `qm-warn-*` — 78 rules, a second
family belonging to the same surface.

### THE DISCIPLINE, AND THE FIRST ITEM IS THE ONE USUALLY SKIPPED

1. **ENUMERATE TOKENS FROM THE CONSUMERS, NOT ONLY THE DEFINITION.** A composed
   identifier has no literal in source. The only place it appears is in the code
   reaching for it — so grep the TESTS and the callers, not just the component.
2. **TREAT EVERY FORM AS A SET TO EXHAUST, NOT A BOX TO TICK.** *"I searched test
   ids"* is not a coverage statement; `qm-lin-rx-*` found and `qm-warn-*` missed
   is the proof.
3. **ENUMERATE THE FORMS ANYWAY — necessary, not sufficient.** R5 actually had to
   touch: test id · CSS class family · ARIA/accessible name · element id · free
   text content · `data-*` attribute · URL query-param VALUE (`?filter=critical`)
   · enum/union string constants spanning schema + prompt + resolver (`rx_gate`)
   · derived field names (`criticalCount`) · seeder/fixture option names
   (`hasRxGate`, `withCriticalOverride`) · helper module and import paths ·
   Playwright project names and env fixtures (`rx-safety`, `MOCK_RX_WARNINGS`) ·
   audit-action enum values. **A four-item checklist reads as complete and is
   not.**

### ⚠️ FRESH SELF-APPLICATION, 2026-08-20 — I SEARCHED FOR THE FIX I IMAGINED

A supervised session checked whether a filed residual had landed by grepping
`PIPESTATUS|hash-of-empty|e3b0c442` — **the three forms its own proposed fix
would have taken.** The shipped fix said `set -o pipefail`. Zero hits, concluded
"not landed", and re-broke a working guard by landing the declined version on
top of it.

> **The token list was drawn from the fix I had in mind, not from the space of
> fixes.** A grep for your own solution is a test of your memory, not of the
> file.

**When checking whether something is DONE, search for the PROBLEM, not for your
solution to it** — here, the function name and the pipe, which would have found
`pipefail` on the first try. Full record in the two-way-review entry below.

⚠️ **AND NOTE WHAT ACTUALLY FOUND THE MISSED FILE: the E2E gate, by running the
pack.** Not the sweep that was supposed to precede it. Positive-control the
sweep's own pattern before believing any zero, and drive the fixing pass from
the list — but do not mistake a sweep for the thing that proves coverage.

---


---

## ⚠️ AND THE SAME SHAPE WHILE VERIFYING A DEPLOY, 2026-08-27 — A `NOT FOUND` THAT WAS MY SEARCH

**Appended.** This entry's own rule — *a composed identifier has no literal in
source* — met while doing structural production verification, and it produced a
scare rather than a defect.

Confirming the newly deployed coding surface was actually in the shipped bundle,
four tokens were grepped against `.next` inside the running container:

| token | result |
|---|---|
| `icd-summary-chip` | found |
| `icd-frozen-notice` | found |
| `rounds-ink-muted` | found |
| **`visit-view-tab-coding`** | **NOT FOUND** |

**Three surfaces present and the fourth missing** reads exactly like a partial
deploy — the shape this house treats as more dangerous than a total failure.

**It was the search.** The id is built as `` `visit-view-tab-${view}` ``, so the
full string exists nowhere: not in the source, not in the bundle. Grepping the
**prefix** `visit-view-tab-` found it in *both* the SSR chunk and the client
chunk, which is a stronger result than the literal would have been.

> **A `NOT FOUND` IS A MEASUREMENT OF YOUR PATTERN BEFORE IT IS A FACT ABOUT THE
> ARTIFACT.** And the tell was available without any thought: **three of four
> tokens from the same component resolved.** A deploy does not ship three
> quarters of one file. *Arithmetic that does not reconcile is a finding* —
> here it was a finding about the instrument.

**THE HABIT, and it costs nothing:** when a bundle grep comes back empty, before
believing it, **open the source and check whether the string is assembled.** If
it is, search the longest literal prefix. And when some tokens from one component
resolve and others do not, suspect the pattern first — the artifact is a single
file and does not have opinions about which of its strings to include.
