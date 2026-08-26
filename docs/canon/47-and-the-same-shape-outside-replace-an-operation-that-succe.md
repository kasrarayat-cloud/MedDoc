> **ARCHIVED CANON — moved verbatim from `AGENTS.md` on 2026-08-26.**
>
> **This body is the AUTHORITY.** `AGENTS.md` carries a one-line index row
> pointing here; that row is a POINTER, never the rule. Nothing in this file is
> rewritten — corrections are appended and dated and superseded wording is kept,
> because in this programme the correction is the point.
>
> Original position: entry **102 of 124** in `AGENTS.md`, under **This is NOT the Next.js you know ▸ A scripted edit PROVES ITS OWN APPLICATION**.
> Why the split: `docs/canon/README.md`.

### ⚠️ AND THE SAME SHAPE OUTSIDE `.replace()`: AN OPERATION THAT SUCCEEDS AND DOES NOT LAND

**`core.fileMode` is `false` in this repository**, so git ignores the on-disk
executable bit entirely. `chmod +x` **succeeds**, `ls -l` shows `rwxrwxr-x`, and
the file still enters the index as **`100644`** — which git will not exec as a
hook. Every instrument agreed with the intention and none measured the effect.

⚠️ **REFERENCE CASE, 2026-08-12: `scripts/hooks/pre-push` was committed INERT** —
the mechanization built that same day to stop a recurring class, shipped as a
file git would never run. **The only tell was `create mode 100644` in one line of
commit output**, and it was legible solely because the sibling `pre-commit` reads
`100755`. Nothing else would have said so until a clone failed to run it.

    git update-index --chmod=+x scripts/hooks/<hook>
    git ls-files -s scripts/hooks/          # 100755, or it does not run

⚠️ **The repo's `.sh` scripts are deliberately `100644`** — invoked as
`bash scripts/x.sh`, they never need the bit. **Hooks are the exception, because
git execs them directly.** So "make everything executable" is the wrong repair;
the rule is *set the bit where the executor is git itself.*

*Corollary, earned in the same pass:* **a rename does not protect when the types
are identical.** `loadVisitExportData(visitId, userId)` had its second parameter
renamed to `practiceId`; **nine call sites kept passing a user id** and `tsc`
accepted all nine, because both are `string`. It failed closed — a user id
matches no practice — but the compiler should have caught it and could not.
Contrast, same commit: `captureEditPattern({ … practiceId })` broke **loudly at
every call site**, because a required NAMED property cannot be confused with a
same-typed neighbour. **When changing what a positional parameter MEANS, change
its shape (named property, branded type), not only its name.**

