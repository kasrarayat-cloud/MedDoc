# A TWO-VIEW CHECK AGAINST A NEVER-PUSHED BRANCH QUERIES AN EMPTY SHA

> ⚠️ **NUMBERED 143, NOT 142 — A CROSS-BRANCH COLLISION, CAUGHT BY THE GATE.**
> This was written as 142 against `main`, where 141 was the highest. An unmerged
> lane already held `142-a-ruling-number-is-a-token-not-a-key.md`, so two bodies
> claimed one number the moment the two branches met. Neither had landed, so
> #219's "the number belongs to whoever merges first" does not settle it — the
> discovering side renumbers and moves on, which is cheaper than a race. Both
> index rows survived; nothing was lost.

**Standing 2026-09-08.** The in-flight check before a push is
`gh run list --commit <FULL sha>` **and** `--branch <name>`, and both must be
empty before you believe the branch is quiet. That rule assumes there IS a
remote head to name.

> **When the branch has never been pushed, `git ls-remote` returns the empty
> string — and the check is then performed against nothing.**

⚠️ **AND `gh run list --commit ""` DOES NOT REFUSE.** It answers. In the
measured case it printed four rows with a blank status column, which reads at a
glance exactly like "four completed runs, nothing in flight" — the same shape a
genuine clean check produces. Nothing said *"you gave me no SHA."*

**MEASURED, 2026-09-08.** Pushing the rebased `docs/rulings-297-300`:

    RH=$(git ls-remote origin "refs/heads/$B" | cut -f1)   # -> "" (never pushed)
    gh run list --commit "$RH"                             # -> 4 rows, status blank
    git push --force-with-lease="$B:$RH" origin "HEAD:$B"  # -> * [new branch]

The push was safe. **It was not safe BECAUSE of the check** — the check was
vacuous. It was safe because the branch did not exist, and the only artifact
that says so is the push's own `* [new branch]` line.

> **THE `[new branch]` RESULT IS THE PROOF. THE CHECK IS NOT.**

**AND THE LEASE IS VACUOUS TOO, IN THE SAME BREATH.**
`--force-with-lease=<ref>:""` degenerates: there is no expected value to
protect, so the guard that exists to refuse a clobber cannot refuse anything.
Two independent protections, both empty, both silent — which is why this is a
canon entry rather than a note. A protection that quietly does nothing is worse
than one that is absent, because its presence is read as evidence.

**THE HABIT:** before the two-view check, assert the remote head is a real
40-character SHA — the pre-push hook already fails closed on exactly that, for
exactly this reason. If it is empty, say **"new branch, nothing to destroy"**
and let the push's own result be the record. Do not report a two-view check you
did not perform.

⚠️ **THIS IS THE WATCHED-SET FAILURE, NOT THE BROKEN-INSTRUMENT ONE.** `gh` is
working perfectly; it is answering correctly about a universe with no commit in
it. That distinction is already recorded for the propagation window, where the
same command under-reports on a SHA that DOES exist. Same tool, same output
shape, two different empty answers — and neither is a quiet branch.
