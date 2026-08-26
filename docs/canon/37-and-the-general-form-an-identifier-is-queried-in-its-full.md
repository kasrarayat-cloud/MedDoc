> **ARCHIVED CANON — moved verbatim from `AGENTS.md` on 2026-08-26.**
>
> **This body is the AUTHORITY.** `AGENTS.md` carries a one-line index row
> pointing here; that row is a POINTER, never the rule. Nothing in this file is
> rewritten — corrections are appended and dated and superseded wording is kept,
> because in this programme the correction is the point.
>
> Original position: entry **73 of 124** in `AGENTS.md`, under **This is NOT the Next.js you know ▸ A PUSH IS CHECKED FOR IN-FLIGHT RUNS **BY COMMIT *AND* BY BRANCH**, BEFORE IT HAPPENS**.
> Why the split: `docs/canon/README.md`.

### ⚠️ AND THE GENERAL FORM: AN IDENTIFIER IS QUERIED IN ITS **FULL** FORM, EVERYWHERE

**Standing 2026-08-14. This entry began as a `gh` quirk and it is not one.**

> **A lookup keyed on an ABBREVIATED identifier can return "no matches" instead
> of "ambiguous", with exit 0. Abbreviation is a display convenience; it is
> never a query key.**

`gh run list --commit` is the instance this repo has paid for, and the table
above records it. The generalisation is the addition: **any** interface that
accepts a shortened id — a SHA prefix, a truncated container id, a partial
image digest, a name without its namespace — may resolve it, or may silently
resolve nothing, and the two outcomes are indistinguishable from the exit code.

⚠️ **REPRODUCED LIVE BY BOTH SESSIONS ON THE SAME NIGHT, and mine sat directly
on a deploy gate.** Waiting for `main`'s merge-commit citation before deploying
R5, I polled `gh run list --commit 636e69a3` — the short form. It returned `[]`,
my `until` loop read that as "nothing in flight", and **it exited while three
required checks were still running.** Measured seconds apart on the same commit:

    --commit SHORT : 0 runs
    --commit FULL  : 4 runs
    --branch main  : 4 runs

All three commands exit 0. **What caught it was the two-view rule above** — the
`--branch` view disagreed, in the same output, and the disagreement was the only
signal. A single-view check would have deployed a commit whose gate had not
finished looking at it.

**So the two rules compose, and neither is sufficient alone:** take two views,
AND query with the full 40 characters. The two-view habit catches a lying
instrument; the full identifier stops you creating one.

#### ⚠️ AND THE THIRD: **FULL-LOOKING IS NOT FULL**

**Standing 2026-08-16. Second occurrence in this programme, and the first was
caught by a different script.**

> **A 40-character hex string is not a commit. Read the identifier
> (`git rev-parse HEAD`); never BUILD one by padding, completing or
> remembering a short sha.**

⚠️ **THE REASON IT SURVIVES A LENGTH CHECK IS THE WHOLE PROBLEM.**
`gh-runs.sh` refused short shas from the day it was written — and a fabricated
sha sails through, because it is exactly 40 hex characters. Measured: a batch
citation polled `cc6d9ee8ceff34c14eafcdf22ea59923eec4facf` while `origin/main`
was `cc6d9ee81287036bbf1e97ef8cbf88eaae719cef`. **Same eight characters,
different commit.**

⚠️ **AND THE TWO FAILURES ARE INDISTINGUISHABLE TO THE CALLER, WHICH IS WHAT
MAKES IT WAIT FOREVER:**

    fabricated sha             -> no rows -> exit 1
    real sha, runs not started -> no rows -> exit 1

So an `until … cited "$SHA"` loop — the shape the wrapper exists to serve —
polls a commit that does not exist, and its log is indistinguishable from
patient, correct waiting.

**What caught it was the two-view rule**, one section up: `--commit` returned
empty while `--branch main` showed four runs on a *different* sha. **The
disagreement was the only signal**, exactly as that rule promises.

**Mechanized** — `gh-runs.sh` now exist-checks and fails **`2` = CANNOT TELL**
rather than `1` = not cited, because those are different claims. It fetches once
first, so a real-but-not-yet-local sha is not called fake. *(`check-citation.sh`
already had this guard and caught the programme's first fabricated sha with
"NO SUCH COMMIT — cannot tell". **A guard on one door is not a guard on the
other** — the same lesson as the push-side hook versus `merge-pr.sh`.)*

> **THE RULE, TIGHTENED TWICE, AND THE SECOND TIGHTENING IS THE LOAD-BEARING
> ONE: TAKE TWO VIEWS.** `--branch` is the view that is right first. A citation
> is still taken from `--commit`, because that is what binds evidence to a SHA —
> but **a zero from `--commit` is not a fact until `--branch` agrees.**

⚠️ **AND IT APPLIES TO A PR BRANCH EXACTLY AS IT APPLIES TO `main` — INCLUDING
WHEN THE ONLY RUNS YOU CAN CANCEL ARE YOUR OWN.** The third and fourth rows above
are the same shape nineteen hours apart — #557 on `feat/b1a-vendor-request-id`,
then #568 — and that is the argument: **the class recurred within a day of the
rule being written down.**

**Reference case, 2026-08-09 — PR #568.** The PR opened at `20:28:09Z` and four
runs were created at `20:28:12Z`. The docs commit was pushed at `20:30:54Z` —
**2m45s after the PR opened** — and cancelled three of them: `CI` at 2m58s,
`a11y-ci` at 3m04s, `e2e` at 3m07s. Only `secrets-scan` survived, and only
because it had already succeeded at `20:28:42Z`.

⚠️ **AND "JUST BATCH IT" WAS NOT AVAILABLE HERE — WHICH IS THE PART WORTH
LEARNING.** The docs commit **did not exist** when the PR was pushed: it was
authored at `20:30:22Z`, two minutes *into* the run it went on to cancel. So the
habit that would have prevented this is not *combine two commits already sitting
there*; it is **hold the first push until the session's remaining commits are
written**. That is the harder rule, and it is the one this case actually teaches.

⚠️ **THE BLAST RADIUS IS YOUR OWN RUNS, WHICH IS EXACTLY WHY IT FEELS HARMLESS.**
Every workflow groups per-ref under its own prefix (`ci-`, `e2e-`, `a11y-`,
`secrets-scan-`) with `cancel-in-progress: true`, so one push cancels your
in-flight run of **each** of them — and only yours. Nobody else is inconvenienced,
nothing turns red, and the habit therefore never gets corrected by consequence.

**The recovery was CORRECT and is not what is being corrected.** The citation was
taken on the descendant, which contains everything the parent did, so nothing was
certified that no gate had seen. **The cancellation was avoidable; the response
to it was right.**

**Price the class by its worst instance, not its cheapest.** #568 discarded
**~9 runner-minutes across three concurrent runs** (2m58s + 3m04s + 3m07s) and
re-ran four jobs that had already passed, because the second commit landed about
three minutes of wall clock into the run. The identical mistake at minute forty
discards the whole gate — the 2026-08-07 row above, at ~45 minutes of wall clock.
**The cost is set by HOW LATE the second push lands; the habit is identical
either way, so do not read the cheap instances as evidence that the class is
cheap.**

**The cheap habit that avoids all of it: BATCH.** Most of these cost a cycle
because two pushes were made minutes apart where one would have done. And when a
second push genuinely must happen, it is gated by the **two-view check at the top
of this section** — both views, the full 40-character SHA, and a zero believed
only when both are empty.

