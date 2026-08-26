> **ARCHIVED CANON — moved verbatim from `AGENTS.md` on 2026-08-26.**
>
> **This body is the AUTHORITY.** `AGENTS.md` carries a one-line index row
> pointing here; that row is a POINTER, never the rule. Nothing in this file is
> rewritten — corrections are appended and dated and superseded wording is kept,
> because in this programme the correction is the point.
>
> Original position: entry **86 of 124** in `AGENTS.md`, under **This is NOT the Next.js you know ▸ THE SHARED TREE IS A DEPLOY SURFACE, NOT A WORKSPACE**.
> Why the split: `docs/canon/README.md`.

### ⚠️ AND THE DISCRIMINATOR IS **DARK vs LIVE**, NOT THE SIZE OF THE FIX

**Standing 2026-08-15.** The rule above — *ask, never fix it yourself* — is about
acting **under another actor**. It is not a prohibition on touching the shared
tree; it is a prohibition on touching it **while somebody else is standing in
it.**

> **LOOP LIVE → the shared tree is theirs. Ask, or wait.**
> **LOOP DARK → an obstruction there is nobody's, and clearing it is ordinary
> maintenance.**

⚠️ **REFERENCE CASE, AND IT IS THE DARK ONE.** The loop had died and **could not
restart**: its launch guard refuses a dirty tree, and a dead session had left
`?? docs/preflight-reports/preflight-<ts>.md` behind. Waiting for the owner
would have kept the loop down for no benefit — **there was no other actor to
collide with, which is the entire content of the hazard.** The report was moved
onto an open branch and committed (never deleted — it is the audit trail for the
run it describes) and the loop restarted ~40 minutes sooner.

#### ⚠️ AND THE SECOND REFERENCE CASE IS THE LIVE ONE — ROUTINE SYNCING COUNTS

> **`git merge --ff-only` on the shared tree is an act on a deploy surface, not
> housekeeping.**

**Standing 2026-08-16.** The author ran `tmux ls`, **saw the loop alive, and
ff-merged anyway** — not by overriding the rule but by never reaching for it,
because fast-forwarding a clean tree to a commit it already contains feels like
tidying. No harm followed, by about two minutes of timing.

⚠️ **THE NEAR-MISS AND THE REFLEX THAT ALMOST DOCUMENTED IT LIVE ARE ONE
LESSON.** The same session then began writing this very entry into the shared
tree while the loop still held it. **A rule about not touching a live deploy
surface, being written onto a live deploy surface**, is the clearest available
proof that the hazard is a reflex rather than a decision — and reflexes are not
fixed by knowing the rule.

**So the test is not "is this a change?" but "is anyone standing there?"** If
the loop is live, the tree is theirs — including for operations that modify
nothing anyone would notice.

**What makes this safe is checkable in one command, not a judgement call:**
`tmux ls` / `pgrep -af foundation-loop.sh`. If either answers, the tree is not
yours.

⚠️ **AND FLAG IT ANYWAY.** The act was correct and it is still worth naming in
the report, because *"I resolved a shared-tree obstruction"* reads as routine
once nobody records which side of the line it was on. **The boundary is what
keeps the ratification from becoming a precedent for the LIVE case** — which is
the one that costs a deploy.

