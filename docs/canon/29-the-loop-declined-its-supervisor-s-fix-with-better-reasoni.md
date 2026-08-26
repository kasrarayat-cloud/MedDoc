> **ARCHIVED CANON — moved verbatim from `AGENTS.md` on 2026-08-26.**
>
> **This body is the AUTHORITY.** `AGENTS.md` carries a one-line index row
> pointing here; that row is a POINTER, never the rule. Nothing in this file is
> rewritten — corrections are appended and dated and superseded wording is kept,
> because in this programme the correction is the point.
>
> Original position: entry **52 of 124** in `AGENTS.md`, under **This is NOT the Next.js you know**.
> Why the split: `docs/canon/README.md`.

## THE LOOP DECLINED ITS SUPERVISOR'S FIX WITH BETTER REASONING, AND CI ENFORCED IT

**Standing 2026-08-20. The two-way-review reference. SUPERVISION RUNS IN BOTH
DIRECTIONS NOW.**

A supervised session filed a residual against loop-owned library code
(`scripts/lib/ledger-progress.sh`): compare the hash against the empty-stdin
digest `e3b0c442…855` and return CANNOT-TELL. The loop implemented the fix
differently — `$(set -o pipefail; git show … | sha256sum …)`, with `pipefail`
set INSIDE the substitution so a sourced library neither mutates its caller's
shell options nor depends on them — and **declined the filed version in its own
gate**, at `gate-f20-ledger-progress-universe.test.ts:522`:

> *"it cannot tell 'we hashed nothing' from 'the file is genuinely zero bytes',
> and the existence check exists precisely so those stay distinguishable.
> `pipefail` is also STRICTLY STRONGER: it catches a truncated read that emitted
> bytes before failing, which yields a WRONG hash that no constant comparison
> could ever see."*

Both points are correct and the supervisor's were not: a legitimately empty
ledger hashes to that constant, so the filed check would turn a valid
measurement into CANNOT-TELL.

⚠️ **THE SUPERVISOR THEN LANDED THE DECLINED VERSION ON TOP OF THE SHIPPED
ONE**, believing the residual still open. CI caught it in a single run — the arm
`a LEGITIMATELY EMPTY ledger still MEASURES` went red, which is exactly the arm
written to catch that proposal. **The gate was waiting for him.**

**Two rules come out of it, and the second is the one that bites:**

1. **A supervised session landing into LOOP-OWNED code gets the same
   sync-and-read-the-shipped-fix discipline the loop is held to.** Read what is
   there now, not what you remember filing. The loop's tests are not decoration
   for someone else's work — they are the contract on that file.
2. ⚠️ **"I FILED IT" IS NOT "IT IS STILL OPEN."** A residual, an INBOX entry, a
   queue item — each is a claim about a PAST state. Between filing and returning,
   someone competent may have done it, done it better, or considered and
   rejected your version *for a reason recorded in a test you did not read*.
   **Re-establish the state before acting on your own memory of it.**

**Authority does not run one way here.** The loop is not a junior that receives
rulings; on its own code, with its own gate, it was right and the supervisor was
wrong. The record says so because that is the only way the next reader learns
which version won and why.


