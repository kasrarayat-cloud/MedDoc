# ⚠️ NOTHING READS THIS DIRECTORY

**Measured 2026-09-09.** `grep -rn "deploy-declarations"` over `*.sh`, `*.ts` and
`*.yml` finds **no reader**. The §2.5 deploy gate reads
**`docs/foundation/deploys/`** and nothing else — `scripts/deploy-prod.sh:140`,
`DECL_DIR="docs/foundation/deploys"`, resolved by
`declaration_resolve` in `scripts/lib/declaration.sh`.

Ten declaration-shaped files had accumulated here. They are correct in content,
tracked, committed, and **invisible to the gate they were written for.** That is
the hazard canon names precisely:

> **NOTHING READS A DECLARATION UNTIL THE ACT DOES.** A declaration in the wrong
> directory is not a warning and not a lint — it is a file that looks completely
> correct, reviews clean, and is discovered only by the gate it was written for,
> at the moment you are trying to use it.

## If you are about to write one

Write it at `docs/foundation/deploys/<UTC-date>-<short-sha>.md`, where the sha is
**the commit that will deploy**. Do not add files here.

## If yours is already here

`git mv` it to that name, keep the body **byte-identical** (verify by hashing the
body before and after, not by reading it), and say so in the commit message. A
declaration re-pathed after the fact is trustworthy only if its **original**
commit timestamp still provably precedes the act.

## Why these ten are not being moved en masse

Each names a different deploy and a different commit, most of them long shipped.
Re-pathing a declaration for an act that already happened does not recover the
**gate** — only the **evidence** — and inventing filenames for past deploys would
put ten unverifiable entries into the directory the gate reads, where **one
malformed name refuses every deploy from every lane**
(`gate-declaration-filenames`). Adjudicating them is an owner call. This file
exists so the next session finds the measurement instead of re-deriving it.
