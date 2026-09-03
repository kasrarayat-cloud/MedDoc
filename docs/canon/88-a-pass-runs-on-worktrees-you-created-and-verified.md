# AN ADVERSARIAL PASS RUNS ON WORKTREES YOU CREATED AND VERIFIED YOURSELF

**Standing 2026-09-02, owner ruling #165. This is the pass harness, not advice.**

## The rule

> **Before a single lens launches: create each worktree yourself, at the exact
> commit under review, and ASSERT that it contains the change — by content, not
> by ref. Print the table. Launch nothing until every row is right.**

    for i in 1..N:
      git worktree add --detach <path-i> <commit>
      ln -s <shared>/node_modules <path-i>/node_modules
      assert grep -c '<symbol the change introduces>' <path-i>/<changed file>  >= 1
      assert <the new test file> exists

The output is four lines and it is the difference between a pass and a pantomime.

## Why it is mechanism and not a habit

Two attempts at one pass, two different failures, neither visible from inside a
lens:

| attempt | what the worktrees held | how it surfaced |
|---|---|---|
| 1 | the right FILES under a stale HEAD ref | misread as stale code; pass killed for nothing — [canon 87](87-a-ref-is-not-a-tree.md) |
| 2 | genuinely the wrong code — the change absent entirely | caught only because the first failure had made me look |

An automatic isolation facility builds worktrees from the **primary checkout**,
not from the feature branch the work lives on. That is reasonable behaviour and
it is not what an adversarial pass needs, and nothing announces the difference.

⚠️ **A LENS CANNOT CATCH THIS FOR YOU, AND ITS FAILURE IS SILENT IN THE WORST
DIRECTION.** A lens on the wrong tree does not error. It reports `NOTHING FOUND`
— the most reassuring sentence available — about code that does not exist. The
pass then certifies a change nobody examined, and the transcript shows five
lenses agreeing.

## The two rules that fall out

1. **The harness is the caller's job.** Isolation is what makes lenses safe to
   let loose (they mutate freely, and one has already written into a live working
   tree). Isolation you did not construct is isolation you cannot vouch for.
2. **Every lens positive-controls its own universe anyway**, and reports
   `wrong universe` rather than attacking what it finds. Belt and braces,
   because the caller's check and the lens's check fail for different reasons.

## The honest limit

This costs one command per lens and it does not make a pass correct — it only
makes it a pass *of the right thing*. Everything else that makes a pass worth
running (distinct lenses, refute-don't-review, FILE:LINE plus a concrete
input → wrong output, and verifying every finding yourself before believing it)
is unchanged and still does the actual work.
