# A REF IS NOT A TREE — READ THE FILES BEFORE CONCLUDING ANYTHING ABOUT THEM

**Recorded 2026-09-02, from a mistake that cost an adversarial pass mid-flight.**

## What happened

Five lenses were running against a change under review. A `git worktree list`
showed each of their worktrees at `HEAD=6220e0ea` — an old commit, from before
any of the work. The obvious reading: they are attacking stale code, so the pass
proves nothing about the change.

**The pass was killed on that reading. It was wrong.** The worktrees' HEAD *ref*
was stale; their *files* were byte-identical to the target:

    renderer.ts          lens=2125374a19814a70  r165=2125374a19814a70  IDENTICAL
    roundtrip-verify.ts  lens=891fd5df4e06207e  r165=891fd5df4e06207e  IDENTICAL
    blank-proof-count.ts lens=884992ce9b3f0e27  r165=884992ce9b3f0e27  IDENTICAL

The harness had populated the trees from the working directory while basing the
ref elsewhere. Five lenses' work was destroyed; the journal showed all five
`started` and none `completed`, so nothing was even cached to resume from.

> **A REF NAMES A COMMIT. A WORKING TREE HOLDS FILES. Nothing guarantees they
> agree, and the tools report them separately.**

## ⚠️ AND THE SECOND ATTEMPT PROVED THE CONCERN WAS REAL, WHICH IS THE TRAP

The re-launched pass got worktrees that genuinely lacked the code — all zeros,
the new test file absent. So the underlying worry was legitimate; only the
*evidence for it* was wrong the first time.

**That is the shape worth remembering.** Being right about the risk is not the
same as being right about the instance, and a correct conclusion reached from a
misread is still a misread — it just does not bill you for it that time.

## The check, and it is one line

Do not ask what commit a tree is on. Ask whether the tree contains the thing
under review, by a property only the real code has:

    grep -c '<a symbol the change introduces>' <path to the file it changed>

Zero means wrong universe. Non-zero means right universe, whatever `HEAD` says.
For a stronger form, compare `sha256sum` against the tree you know is correct.

## The generalisation

This is [canon 36](36-evidence-is-only-evidence-on-the-tree-it-describes.md)'s
sibling. That entry says evidence is only evidence on the tree it describes.
This one says: **the tree is not the ref, so identify the tree by its
CONTENTS.** The same confusion appears wherever a name is mistaken for the thing
named — a tag that has moved, a symlink, a container image id versus its tag, a
branch pointer versus the checkout.
