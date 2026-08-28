# AN EXONERATION IS A CLAIM TOO

**Ratified 2026-08-27, verbatim, and it stands beside its accusatory twin.**

> **Clearing your own deploy needs the same scoped instruments as indicting it.**

This file already says *a destruction list is a CLAIM* — verify before you
execute. **This is the mirror: a CLEAN BILL is a claim, and nobody verifies those,
because a clean result feels like the absence of a result.**

⚠️ **REFERENCE CASE, AND IT RAN IN BOTH DIRECTIONS INSIDE ONE MINUTE.** Judging a
production deploy, the question was whether either migration could have touched
note text. The check:

    cat packages/db/prisma/migrations/2026082*/migration.sql | grep -icE "UPDATE |DELETE |…"
    -> 5

**Five write verbs, in my own just-shipped deploy.** For a moment that was a
finding against the act I had just performed.

**It was the glob.** `2026082*` matched every migration from the whole of that
August, not the two the deploy applied. Scoped to the two files **by name**, the
answer was **0** — and the zero was positive-controlled by an `ALTER` grep
returning 7, so it was a measurement rather than a broken pattern.

**BOTH readings were wrong, from the same defect, in opposite directions:**

| the sloppy instrument said | the correct instrument said |
|---|---|
| **5** — an accusation against my own deploy | **0** — with a control proving the pattern fires |

Had the glob happened to match nothing, the same carelessness would have
produced a **false exoneration** — and *nobody would have questioned it*, because
it agreed with what everyone wanted the answer to be.

## WHY THE EXONERATING DIRECTION IS THE DANGEROUS ONE

An accusation gets scrutinised: it stops work, it costs someone something, and
the first thing anyone does is re-run it. **A clean result ends the enquiry.** It
is checked by nobody, it is written into the judgement as a tick, and it is
indistinguishable from a check that was never capable of failing.

> This is the same family as *every zero you produce is your instrument until
> proven otherwise* — pointed at the moment you are most motivated not to look:
> **when the zero is the answer you were hoping for, about work that is yours.**

## THE PRACTICE

1. **Scope by NAME, never by glob, when the set is knowable.** Two migrations
   were applied; both were named in the deploy log. There was no reason to
   pattern-match at all.
2. **Positive-control the exoneration exactly as you would the accusation** —
   demonstrate the pattern *can* fire against this input before believing that it
   did not.
3. **State the instrument in the judgement, not just the verdict.** *"0 write
   verbs across the two named files, positive control 7"* is auditable.
   *"No note text was touched"* is a conclusion nobody can re-check.
