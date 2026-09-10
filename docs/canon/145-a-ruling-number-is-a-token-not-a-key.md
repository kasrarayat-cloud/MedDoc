# `#NNN` IS A TOKEN, NOT A KEY

**Standing 2026-09-07, from a renumber that corrupted five unrelated files while
its author was quoting the canon against exactly that.**

## THE REFERENCE CASE

Two lanes claimed the same ruling numbers 47 minutes apart. The later lane
renumbered — the cheap move, since neither had landed — and did it in two passes:

1. **`RULINGS.md`, by LINE INDEX.** Only the author's own five rows were
   rewritten, chosen by position, so no other lane's row could move. Verified by
   `git diff --numstat`: 5 added, 5 removed.
2. **The source tree, by BLANKET SUBSTITUTION.** Every `#246`…`#250` became
   `#251`…`#255`.

The first pass was careful because a canon entry warned about it. **The second
pass rewrote five files that had nothing to do with any ruling:**

    apps/transcribe-md/src/lib/confused-drug-names.ts        cites #248
    apps/transcribe-md/tests/lib/confused-drug-names.test.ts cites #248
    apps/transcribe-md/scripts/keyterm-regression/README.md  cites #246, #247
    apps/transcribe-md/scripts/keyterm-regression/synthesize.ts  cites #247
    apps/transcribe-md/src/worker/layers/__tests__/low-conf-l1.test.ts

None of them is a ruling citation. They are ordinary prose that happens to
contain a hash and three digits.

Caught before commit, reverted by name. **Nothing shipped, and that was one
`git diff --name-only` away from being untrue.**

## THE LESSON, AND IT IS NARROWER THAN THE ONE THAT PRECEDED IT

The prior warning was about the shared LEDGER: a blanket substitution there
silently rewrites other lanes' rows. The author read it, believed it, protected
the ledger — and then repeated it one directory over.

> **The ledger is not the only shared namespace. `#NNN` is not a key: it is a
> token that recurs in prose about anything — a PR, an issue, a line number, a
> CPT code, a footnote.**

⚠️ **AND THE TELL IS THAT THE PROTECTION WAS ASYMMETRIC.** A renumber that
guards one file by line index and every other file by regex is not a careful
renumber with one gap; it is a renumber whose author located the danger in a
FILE rather than in the OPERATION. The file was never the hazard.

## THE RULE

- **Rewrite ruling numbers by POSITION or by an explicit ALLOWLIST of files.**
  Never by pattern across a tree.
- **Diff by NAME before committing** — `git diff --name-only` — and require every
  path to be one you intended. A count is not a check: five unrelated files and
  five intended ones both read as "ten files changed".
- **A citation is a claim about a ledger, and it can be checked.** If a rewrite
  must be automated, resolve each hit against the ledger first and skip the ones
  that resolve to nothing — that is what distinguishes a citation from a token.

## ⚠️ ITS COMPANION FAILURE, SAME SESSION, OPPOSITE DIRECTION

A peer's message cited **canon 137** as the entry recording the earlier
incident. Acting on it, this session repeated that number in three commit
messages that are now on `origin`.

**Canon 137 does not exist.** The highest entry anywhere in the repository at
that moment was **134**, and the entry the peer meant is almost certainly
**132 — "a scripted correction prints its applied count"**.

> **A number that does not resolve is worse than a description that does.** The
> peer's prose was accurate and its citation was not, and the citation is the
> half that got repeated.

Both halves of this entry are the same mistake wearing different clothes:
treating `#NNN` as an identifier that can be trusted without being looked up.
