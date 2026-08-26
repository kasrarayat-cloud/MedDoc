> **ARCHIVED CANON — moved verbatim from `AGENTS.md` on 2026-08-26.**
>
> **This body is the AUTHORITY.** `AGENTS.md` carries a one-line index row
> pointing here; that row is a POINTER, never the rule. Nothing in this file is
> rewritten — corrections are appended and dated and superseded wording is kept,
> because in this programme the correction is the point.
>
> Original position: entry **21 of 124** in `AGENTS.md`, under **This is NOT the Next.js you know**.
> Why the split: `docs/canon/README.md`.

## GATE ON THE OBJECT THE GATE READS

**Standing 2026-08-23. A merge was blocked for ninety minutes while every
instrument I owned said it was cited.**

> **`gh run list` reports the WORKFLOW RUN. Branch protection reads the CHECK
> RUN. They are different objects, they can disagree, and a citation taken from
> the wrong one is true about what you measured and false about what gates you.**

Measured: `e2e` workflow run `32619113910` read `completed / success` on the PR
head, and `4 of 4` by the usual citation check. Simultaneously its check-run
`Playwright E2E (transcribe-md)` sat **`in_progress` forever**, and
`mergeStateStatus` read **`BLOCKED`** with `mergeable: MERGEABLE` — no conflict,
a required context that never reported. Re-running the workflow produced a fresh
check-run that completed; all seven then read success and the state went `CLEAN`.

**The rule generalises past `gh`.** Whenever a decision is enforced by one
system and observed through another, confirm they name the same object. Ask what
the ENFORCER reads, and measure that:

    can this merge?   ->  /commits/<sha>/check-runs   (what protection reads)
    did CI pass?      ->  gh run list                 (what a human means)

### ⚠️ AND A DOCUMENTED-UNRELIABLE INSTRUMENT IS NOT A PERMANENTLY-WRONG ONE

This file records `gh pr checks` reporting `pending` for a run already
`completed/success`. So when it said **`Playwright E2E: pending`**, I discounted
it as the known lie — **and it was telling the truth.** It was reporting the
check-run, accurately, while I was reading the workflow run.

> **A precedent about an instrument is a prior, not a verdict. Reaching for the
> precedent INSTEAD of the data is how a true report gets discarded** — and the
> failure is invisible, because dismissing an instrument you have documented as
> unreliable feels like rigour.

⚠️ **AND THE FIRST REFLEX WAS `gh pr merge --admin`** — denied by the permission
layer, correctly. That would have forced past a gate not yet diagnosed. The deny
caught what judgement should have: **an override is never the response to a
blocker you cannot yet explain.**

