# CLOSED ON ARRIVAL — THE LEDGER UNIQUENESS GATE ALREADY EXISTS, AND IT CAUGHT ME

**Filed 2026-09-06 from the #188 double-claim. Closed the same hour, twice
corrected. Nothing to build.**

## THE ASK, AND WHY IT WAS ALREADY SATISFIED

One base row per ruling number on `main`, amendments distinguished from
duplicates by suffix.

**`gate-ledger-reachability.test.ts` has enforced exactly that since
`cbe5a5ad` (2026-08-28)** — *"two rulings claim the same number — an amendment
carries a part marker, a collision does not"* — landed with canon 73's
merge-invariant filing. It runs on `main`, keys on the full identifier, and
adjudicates suffixes correctly. **I filed a build request for a working gate**
because I never checked whether one existed before proposing it.

## ⚠️ TWO CORRECTIONS, BOTH TO CLAIMS I MADE

**1 · "Five more collisions" was wrong — all five are AMENDMENTS.** `#106(g)`,
`#109(a)`, `#115 b`, `#116 b`/`(c)-CORRECTED`, `#131 (b)`/`(c)`. My probe
extracted `#([0-9]+)`, **stripping the very suffix that distinguishes an
amendment from a duplicate**, so every amendment read as a collision — a 5×
overstatement of something I reported before measuring. The existing gate never
made that mistake; it is green on `main` with all five present.

**2 · THE RENUMBER ITSELF COLLIDED — and that is the finding worth keeping.**
Repairing #188 by renumbering to **#196**, I collided with ADMIN-2's subdomain
ruling, which had claimed #196 concurrently and merged to `main` first.

> **The identical mechanism, one number down, hours later — because a number
> picked from the newest view one lane can see is still a guess about a shared
> namespace.**

⚠️ **AND I CHECKED AGAINST A STALE `main`.** My first query said zero #196 rows;
`origin/main` was 26 commits ahead and carried it. *Evidence is only evidence on
the tree it describes* — I read a local ref and believed it about a shared one.

**The gate caught it. #188's own collision was caught by a citation resolving to
the wrong ruling, which is luck.** That difference is the whole argument for
having the gate, and it arrived as a demonstration rather than a proposal.

## WHAT IS ACTUALLY LEFT — one adjudication, not a build

`main` carries `(g)`, `(a)`, `(b)`, `(c)`, `(c)-CORRECTED` **and bare `b`** —
#115 and #116 use no parentheses. The gate accepts all of them today. If the
suffix format is ever narrowed, that inconsistency becomes a false accusation
against two legitimate amendments, so it is recorded here rather than left to be
rediscovered.

## THE HABIT THIS EARNS

**Claim a ruling number against a freshly fetched `origin/main`, in the same
breath that writes the row** — never against a local ref, and never against a
number remembered from earlier in the session. The gate is the backstop, not the
method.
