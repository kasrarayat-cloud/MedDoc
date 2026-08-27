# GREEN MUST NOT OUTRUN TRUTH

**Ratified 2026-08-27.** A fix that would turn a PR green while its siblings'
promises stay false is **withheld**, not landed.

> **The question is not "does this fix work?" It is "what will the green mean
> once this lands?"**

⚠️ **REFERENCE CASE, AND THE FIX WAS CORRECT — THAT IS THE POINT.** PR #877, the
ledger split, was red on exactly one thing: `gate-f30-retirement-conditions`,
**a file the PR did not touch**, failing because the split had moved the closure
headings out from under `check-retirement-conditions.sh`. The fix was small,
proven, mutation-backed, and CI-verified after the fact.

**It was committed and deliberately NOT pushed.**

The F30 gate was **the single failure in 5,302 tests.** Pushing that one fix
would have taken the PR from red to green — while:

| still true, still unwatched |
|---|
| `rotate-ledger.sh` FATAL'd on **every** rotation (3 phantom manifest anchors) |
| `--apply` printed *"rotation applied"* with the head **byte-identical** and the content **duplicated** |
| `grep 'OWNER RULING' docs/foundation/RULINGS.md` returned **0**, where the pre-split file returned 23 |
| `MASTER.md` told every session the ledger was 371,533 chars and grep-only, when it was 44,935 and readable |
| 2 of 25 archive spans resolved **past end-of-file** |

**Not one of those was watched by any gate.** The PR's own new gate asserted the
census across the file pair and passed, correctly, the whole time.

> **A citation certifies a TREE, not the defect you happened to fix.** Green
> bought by fixing the only thing that was watched is the most expensive
> artifact this repository can produce: it certifies a tree whose rotation
> refuses, whose rulings cannot be grepped, and whose standing prompt describes
> a file that no longer exists at that size — and it certifies it *correctly*,
> by every rule we have.

**THE HABIT, and it is one sentence before you push:** *if this push makes the
branch green, what will a reader believe that is not true?* If you can name
anything, the fix is staged and the PR is marked a **draft** — one command,
reversible, and it makes the branch unmergeable by anyone, including a future
you at 03:00 with the findings half-read.

⚠️ **AND THE COMPANION IS NOT "FIX EVERYTHING FIRST".** Two of the five defects
were unambiguous bugs in new code; two were design calls on somebody else's
ratified artifact. The withheld fix was reported **with the list**, and the list
said which were mine and which were not. *Withholding is a routing decision, not
a refusal to work.*
