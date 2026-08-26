> **ARCHIVED CANON — moved verbatim from `AGENTS.md` on 2026-08-26.**
>
> **This body is the AUTHORITY.** `AGENTS.md` carries a one-line index row
> pointing here; that row is a POINTER, never the rule. Nothing in this file is
> rewritten — corrections are appended and dated and superseded wording is kept,
> because in this programme the correction is the point.
>
> Original position: entry **39 of 124** in `AGENTS.md`, under **This is NOT the Next.js you know**.
> Why the split: `docs/canon/README.md`.

## A CHECK'S REMEDIATION ADVICE IS WRITTEN FOR ITS COMMON STATE

**Standing 2026-08-24.**

> **In a HELD or STAGED state, following a check's printed advice can bypass the
> very gate the state exists to protect.**

A check that goes red prints what to do about it, and that text is written for
the case that usually causes the red. It cannot know that this time the red is
deliberate.

⚠️ **REFERENCE CASE.** With the F24-S5 deploy deliberately HELD,
`assert-migrations-applied` reads 🔴 `1 unapplied` on production at every STEP 0
— correctly: the migration is on `main` and production has not been deployed.
Its advice reads *"rebuild db-migrate and re-run"*, and following it would
**apply a production migration outside the §2.5 declaration gate** — the one act
that gate exists to prevent.

**The check is right, the number is right, and the sentence under it is wrong for
this state.**

**The practice:** before acting on remediation text, establish WHY the check is
red. A red that reconciles exactly with a known deliberate state is a
confirmation, not an instruction. And when a hold is declared, say in the ledger
which standing checks will read red because of it — otherwise the next session
reads a real alarm and helpfully clears it.

