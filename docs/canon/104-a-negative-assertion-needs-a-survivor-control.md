# A NEGATIVE ASSERTION NEEDS A SURVIVOR CONTROL

**Ratified 2026-09-04.** Any check whose success condition is *"X does not
appear"* is satisfied perfectly by an instrument that produces **nothing at
all** — and an instrument that produces nothing is the most common way for one
to break.

> **Every "X must be ABSENT" arm ships with a "Y must be PRESENT" arm beside
> it, over the same run of the same instrument.**

## THE REFERENCE CASE, AND IT WAS CAUGHT ONLY BY THE SURVIVOR ARM

`scripts/dc.sh` gained a redacting `config` door, because
`docker compose config` resolves every variable and prints the plaintext of
`MINIO_ROOT_PASSWORD`, `POSTGRES_PASSWORD`, `ANTHROPIC_API_KEY` and the rest.
It had burned credentials in this programme **twice**, and was reached for a
third time by a session that had just written about the first two.

The redactor was proved with planted secrets:

    POSITIVE CONTROL  planted secrets surviving: 0   (must be 0)   ✅

**That zero was a lie.** The awk program had been written inline inside a bash
function inside a heredoc, and the nested quoting broke it:

    awk: cmd. line:1: unterminated string

It emitted **zero bytes**. No secret survived because *nothing* survived.

What caught it was the arm on the other side:

    NEGATIVE  non-secret lines surviving: 0   (must be 3)   ❌
    NEGATIVE  output is non-empty:        0   (must be 10)  ❌

**A redactor that eats everything is not a redactor.** Only a survivor control
can tell "it masked the secrets" from "it produced no output".

## WHY THIS IS NOT ALREADY COVERED BY THE POSITIVE-CONTROL RULE

The standing rule — *a zero is your instrument until proven otherwise* — asks
whether the instrument **works**. This instrument ran, exited, and printed a
zero for the thing being watched. The question a survivor arm asks is
different and narrower:

> **Did anything at all come through?**

That is a question about the DENOMINATOR, and a negative assertion never has
one by construction: *absence* has no natural count. So the count has to be
supplied from the other side of the same run.

## THE SHAPE

For any filter, redactor, sanitiser, stripper or sweep:

| arm | asserts | catches |
|---|---|---|
| **positive** | the target is absent | the filter not filtering |
| **survivor** | a NAMED non-target is present, verbatim | the filter eating everything |
| **arithmetic** | lines in == lines out (or a stated delta) | partial destruction |

The redactor now carries all three: 7 planted secrets masked, 3 named
non-secret lines intact, **10 lines in and 10 lines out**.

## AND IT GENERALISES BEYOND FILTERS

Any of these is a negative assertion wearing different clothes:

- *"no PHI appears in this export"* — and the export is empty
- *"no `console.log` remains in the bundle"* — and the grep pattern was wrong
- *"no offender is left in the watched directory"* — and the scan looked at the
  wrong directory ([canon 96](96-a-control-that-never-touches-a-file-cannot-guard-files.md))
- *"the diff removes nothing"* — and the diff is empty because the tree is wrong

⚠️ **The tell is grammatical, and it is available before you measure: if your
success condition is a zero, ask what the NON-zero half of the same run is, and
assert that too.** If you cannot name one, the arm cannot distinguish success
from silence.
