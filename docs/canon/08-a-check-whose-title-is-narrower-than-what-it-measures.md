> **ARCHIVED CANON — moved verbatim from `AGENTS.md` on 2026-08-26.**
>
> **This body is the AUTHORITY.** `AGENTS.md` carries a one-line index row
> pointing here; that row is a POINTER, never the rule. Nothing in this file is
> rewritten — corrections are appended and dated and superseded wording is kept,
> because in this programme the correction is the point.
>
> Original position: entry **18 of 124** in `AGENTS.md`, under **This is NOT the Next.js you know**.
> Why the split: `docs/canon/README.md`.

## A check whose TITLE is narrower than what it MEASURES

**Standing rule. Read a check's name as a claim, then go and confirm the
implementation makes exactly that claim — no wider, no narrower.** The failure is
not a bug in the logic; the logic is usually correct about something. It is
correct about the *wrong quantity*, and the name is what stops anyone noticing.

Both reference cases are T5's own ratchet, found within an hour of each other,
and both would have made the item's CLOSE CONDITION UNREACHABLE:

| The name said | It actually measured | What that cost |
|---|---|---|
| "**unscoped** request-context reads" | *every* clinical read, scoped or not | routing a call through the accessor left the number unchanged — **adoption could never lower it** |
| a count of reads **in code** | reads in code *and in comments* | the accessor's own doc-comment example counted, putting a permanent **floor of 1** under a ratchet whose whole purpose is to reach 0 |

Note what neither one was: neither ever produced a wrong answer *to the question
it was actually computing*. A test that passes and a test that measures the
wrong thing look identical from the outside, and a green ratchet that cannot
move looks exactly like a codebase with nothing left to fix.

⚠️ **FRESH REFERENCE CASE, 2026-08-21 — `notMentionedCount`, AND IT BLOCKED AN
ATTRIBUTION IN REAL TIME.** `picks-bridge.ts:254-286` routes **FIVE** distinct
exits into one bucket named *not mentioned*:

| exit | what it actually means |
|---|---|
| `!pick` | the dictation genuinely did not mention it — **benign** |
| `pick.value == null \|\| ''` | empty value |
| `set_aside_not_adopted` | the verifier DEMOTED it, awaiting the clinician |
| `not_an_enumerated_option` | an off-list value |
| `!built` | **the derivation REFUSED it** |

**A REFUSAL AND AN ABSENCE ARE THE SAME NUMBER.** On the owner's acceptance
visit the fill read 25 → 20, and a deploy carrying a new refusing derivation
had landed 53 minutes earlier — so *"the new code refused five cells"* was
live, plausible, and **unanswerable from the count**.

**The worker LOG discriminated where the COUNT could not**: 9 ×
`laterality_mismatch`, 0 × `not_an_enumerated_option`, 0 ×
`set_aside_not_adopted`, **0 derivation refusals** — not a regression. The
`console.info` lines at each non-benign exit are the only reason that question
was answerable at all.

> **A bucket that absorbs a REFUSAL and an ABSENCE cannot answer "did my change
> break this?" — which is the one question a count like that gets asked.**

Filed, not fixed: the exits want counting separately.

Three questions that catch it, and they are cheap:

1. **If the work this check guards SUCCEEDED completely, what number would it
   print?** If the answer is "the same one", the check is not watching the work.
   (T5's non-vacuity floor did worse than not move — it went RED for the
   migration's success, because it summed only the buckets adoption was
   draining. **A check that fails when the thing it guards starts working is a
   check nobody keeps.**)
2. **Name every bucket the scan can sort an item into, and assert the total.**
   T5 ended with five — unscoped / scoped / personal / system / comment — and
   the total reconciles against the pre-adoption figure. Anything that doesn't
   fit a named bucket is the finding.
3. **Mutate toward SUCCESS, not just toward failure.** Everyone remembers to
   prove a guard can go red on a regression. Prove it also MOVES when the fix
   lands — otherwise the ratchet is a decoration.

   ⚠️ **REFERENCE CASE, 2026-08-12 — AND IT WAS FOUND BY THE HAPPY-PATH CONTROL,
   WHICH IS THE HALF EVERYBODY SKIPS.** `scripts/retire-branch.sh` passed **9 of
   9** refusal tests — trunk refs, rollback shapes, wildcards, an unmerged branch
   left provably untouched. Then the positive control ran: on a branch that was
   checked out it printed *"left in place"* and then **`🟢 retired`, exit 0**. A
   false success, in the script written to stop exactly that, **invisible to
   every refusal test because refusals were never the broken half.** Fixed to
   exit `2` and to earn the green line.

   **A guard proven only in the RED direction is half-proven, and it is the
   cheaper half.**

