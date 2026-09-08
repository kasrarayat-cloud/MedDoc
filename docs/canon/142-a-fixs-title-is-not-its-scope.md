# A FIX'S TITLE IS NOT ITS SCOPE

**Standing 2026-09-08. Found by writing a commit and discovering the sentence
was already in the log — for a different defect.**

> **Two defects can share one true sentence. The second one is not fixed by the
> first one's commit, and the title will not tell you.**

## THE INSTANCE

`b69b29ac` (2026-09-07) landed under:

> *fix(lens): a sealed sandbox pointed at the wrong tree, and every guard said
> fine*

It fixed a **node_modules / import-resolution** failure: a lens reported ~24
test files failing with *"Failed to resolve import react/jsx-dev-runtime"* and
*"@meddoc/auth resolves to …"*, because the sandbox's dependency tree pointed
outside itself.

One day later, on the #274 refutation pass, a lens was provisioned at
`bc544641` — **main's HEAD, not the subject branch** — because
`make-lens-sandbox.sh` resolved its ref in `$SHARED`, the script's own repo
root. The file under review did not exist in that tree. Every guard passed:
created, write-locked, hook-refused, credential-free, marked.

**The sentence is exactly as true of the second defect as of the first.** A
sealed sandbox, pointed at the wrong tree, with every guard saying fine.

⚠️ **AND THE TITLE IS WHY IT NEARLY WENT UNFIXED.** Meeting `b69b29ac` in
`git log -1 -- scripts/make-lens-sandbox.sh` reads as *"this is already
handled"*. Only opening the diff shows that line 52 —
`git -C "$SHARED" worktree add --detach "$DIR" "$REF"` — was never touched.

## WHY IT IS A CLASS AND NOT A COINCIDENCE

A good commit title names the **failure mode**, because that is what the next
reader is searching for. A failure mode is a shape, and a shape has instances.
So the better the title, the more likely it already describes a defect somebody
else will meet later — and the more authoritative it looks when they find it.

> **The generalisation that makes a title useful is the same generalisation
> that makes it over-claim.**

This is the sibling of *"naming a class is not enumerating it"*: there, a
lesson was written down and then violated by its own author days later. Here, a
lesson was written down and its title was mistaken for coverage.

## THE HABIT

1. **Meeting a commit whose title matches your symptom, read the DIFF, not the
   subject.** The question is never *"has this sentence been written?"* but
   *"does the code do the thing the sentence promises, at the line I am looking
   at?"*
2. **Landing a fix whose title already exists, say so in the body and name what
   the earlier one did NOT touch.** One line. It converts a confusing duplicate
   into a pair a future reader can tell apart.
3. **Prefer titles that name the MECHANISM when a class already has an entry** —
   *"the ref was resolved in the SHARED tree"* beats a second copy of
   *"pointed at the wrong tree"*, precisely because the class sentence is
   already taken.

## THE COST, HONESTLY

Here it cost nothing: the fix was written before the collision was noticed, and
noticing it improved the record rather than the code. **The cost it prevents is
the other order** — a session searching the log, finding the class sentence,
concluding it is handled, and leaving a live defect in a tool that seals
sandboxes for adversarial review.

⚠️ **AND THE BLAST RADIUS OF THIS PARTICULAR ONE IS WHY IT IS WORTH AN ENTRY.**
A lens in the wrong tree sees an EMPTY diff, which reads as *"nothing to
review"* rather than *"you are in the wrong tree"*. Round one of the #274 pass
found a BLOCKING clinical defect — a certified disposition mis-paired onto the
wrong control — and one of its four lenses was in the wrong tree while doing so.
**The finding survived because a different lens caught it.**
