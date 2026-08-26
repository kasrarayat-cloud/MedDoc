> **ARCHIVED CANON — moved verbatim from `AGENTS.md` on 2026-08-26.**
>
> **This body is the AUTHORITY.** `AGENTS.md` carries a one-line index row
> pointing here; that row is a POINTER, never the rule. Nothing in this file is
> rewritten — corrections are appended and dated and superseded wording is kept,
> because in this programme the correction is the point.
>
> Original position: entry **123 of 124** in `AGENTS.md`, under **This is NOT the Next.js you know**.
> Why the split: `docs/canon/README.md`.

## A TREE-RELATIVE INSTRUMENT ANSWERS ABOUT **ITS OWN** TREE, AND THE LOOP LIVES IN WORKTREES

**Standing 2026-08-25. Two independent specimens, one session, one hour — which
is what makes it a rule rather than a quirk.** The shared tree is a deploy
surface and all feature work happens in a `git worktree`; that rule is right and
is not what is being corrected. This is the cost it quietly carries.

> **A worktree is isolated in FILES, shared in REFS — and it has NO
> `node_modules` OF ITS OWN. So `@meddoc/*` resolves UP to
> `/opt/meddoc-pro/node_modules/@meddoc/<pkg>`, a symlink into the SHARED
> checkout. Your worktree's tests and typecheck read SOMEBODY ELSE'S
> `packages/`.**

⚠️ **SPECIMEN 1 — A CHANGE TO `packages/ai` THAT IS LOCALLY UNVERIFIABLE.**
`billableChildrenOf` was added to `packages/ai/src/data/icd10-allowlist.ts` and
exported from the barrel. Measured in the worktree that contained both edits:

    npx tsc --noEmit   ->  error TS2305: Module '"@meddoc/ai"' has no exported
                           member 'billableChildrenOf'
    npx vitest run     ->  TypeError: billableChildrenOf is not a function

**Both instruments were reading the shared tree, which did not carry the
change.** The file plainly exported it; `grep -c` on the two trees read
**worktree 1, shared 0**.

⚠️ **AND THE DIRECTION THAT SHIPS IS THE OPPOSITE ONE.** Here it failed loudly
and cost twenty minutes. Invert it: a worktree branched BEFORE a package change
that has since landed on `main` runs its suite against the NEWER package and
goes **green about code it does not contain** — and a session deleting a package
export would see **no broken callers at all**. CI is unaffected (one checkout,
`npm ci` at its root), so the branch is green there too. *A number printed from
a tree that cannot resolve its own imports is not a measurement* — this is that
rule with the imports resolving perfectly, to the wrong tree.

⚠️ **SPECIMEN 2 — A STANDING CHECK, AND IT NAMED TWO DIFFERENT MIGRATIONS.**
`assert-migrations-applied.sh:79` derives its root from **the script's own
location**:

    REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

and enumerates `$REPO_DIR/packages/db/prisma/migrations`. MASTER's grants are
**relative-path prefixes** (`bash scripts/…`), so which copy runs is decided by
your **cwd**. Run minutes apart on one host, against one database:

| invoked from | verdict |
|---|---|
| `/opt/meddoc-pro` (shared, at `main`) | 🔴 1 unapplied — `20260825130000_f8s1_icd_decisions` |
| a worktree on an older branch | 🔴 1 unapplied — `20260824040000_f24s5_template_twin_field_overrides`, and **blind to the first** |

**Same check, same database, two different answers, neither wrong about the tree
it read.** A session standing in a stale worktree can report
`assert-migrations-applied 🟢` while production is genuinely behind — the
watched-set failure arriving through a **cwd** instead of a model list, and it
sits on `deploy-prod.sh`'s gate.

### THE PRACTICE

1. **`pwd` BEFORE YOU BELIEVE A NUMBER**, and say in the report which tree the
   measurement was taken in. This already cost a session a
   `218 failed | 177 passed` phantom from a bare `npx vitest` at the wrong root.
2. ⚠️ **RUN STANDING PRODUCTION CHECKS FROM `/opt/meddoc-pro`**, always. They are
   claims about production, and a worktree's copy silently rescopes them to a
   branch.
3. **A CHANGE TO `packages/*` CANNOT BE PROVEN FROM A WORKTREE.** Either land the
   capability app-side where the app's own `@/*` mapping resolves in-tree, or
   state plainly that the package half was proven by CI only. **Do not push and
   hope, and do not read a worktree green as covering it.**
4. **THE POSITIVE CONTROL IS ONE LINE**, and it discriminates where a green does
   not:

       grep -c "<the new symbol>" packages/<pkg>/src/index.ts \
                                  /opt/meddoc-pro/packages/<pkg>/src/index.ts

   **Two different numbers mean your instruments are pointed at the other tree.**

⚠️ **AND A HYPOTHESIS THIS RAISED WAS REFUTED — RECORDED BECAUSE IT WILL BE
RAISED AGAIN.** Specimen 2's worktree run also reported
`20260824080000_f24s5_clinician_field_overrides` as *"applied but not in the
repo"*, which reads as **a migration applied to production that `main` does not
have** — a serious finding if true. Measured: it **is** on `main`, and it
finished in production at `2026-08-25T06:03:49Z`. The sibling
`…040000_…template_twin_field_overrides` is on an unmerged branch and is
correctly unapplied. **Production and `main` agree; the alarming reading was the
instrument's tree-relativity, twice over.** *The partition reconciles, which is
the evidence — not the reassurance.*

