# THREE REPORTS OF ONE FIXTURE IS ONE REPORT

**Canon 2026-09-06, from an adversarial pass over PR #1018 whose verification
stage caught its own finder stage inflating a count.**

## THE RULE

> **INDEPENDENT LENSES THAT ALL READ THE SAME FIXTURE ARE NOT INDEPENDENT
> WITNESSES. Before treating convergence as evidence, ask what each report
> actually READ — and if the answer is the same artifact, the count is one.**

## THE CASE

A six-lens refutation pass reported the offer/door divergence **three times**,
from three lenses given deliberately distinct angles. Three independent reports of
one defect reads as strong corroboration, and it was used that way in the
dedup: severity was set from the highest of the three, and the finding was
promoted on the strength of the fan-out.

An adversarial verifier then measured what each lens had actually stood on. **All
three cited the same test fixture** — `gate-review-defaults-omit-door.test.ts:720-732`,
whose `refused = {...base, unmentionedPolicy:'omit', sourceType:'manual'}` is a row
that `certification-lifecycle.ts:464`, **added in the same commit**, refuses to
persist.

> **A GREEN ARM STANDING ON AN IMPOSSIBLE ROW READS AS EVIDENCE THAT THE STATE IS
> LIVE.** Three lenses derived the same non-finding from it, independently and
> correctly, because the fixture asserted a world the writer forbids.

Verified over the whole input space: the writer accepts an `omit` on exactly four
shapes, and on **0 of 4** is the predicate false. The divergence was real
arithmetic on an unreachable input.

## ⚠️ THE HALF THAT GENERALISES

**Fan-out buys independence only where the lenses read different things.** Given
one shared fixture, a shared brief, or a shared summary, N lenses produce N copies
of one observation — and the redundancy that was supposed to be a check becomes a
multiplier on whatever that artifact got wrong.

Two consequences worth acting on:

- **DEDUPE BY WHAT WAS READ, NOT BY WHAT WAS CONCLUDED.** Two findings with
  different titles, files and severities can still be one report. The question is
  which artifact each one stands on.
- **A COUNT IS NOT A CONFIDENCE.** "Five lenses found it" is a strong signal only
  after the five are shown to have looked at five things. Otherwise it is one
  signal, amplified — and amplification is exactly what a verification stage is
  supposed to strip out.

⚠️ **THIS IS CANON 114's SIBLING, POINTED AT THE READER RATHER THAN THE ARM.**
114 says a control whose fixture cannot reach its subject proves nothing. This
says a *finding* whose fixture cannot reach its subject does not become true by
being reported three times.
