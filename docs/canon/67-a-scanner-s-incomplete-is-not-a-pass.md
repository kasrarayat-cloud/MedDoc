# A SCANNER'S `incomplete` IS NOT A PASS — IT IS THE SET IT ADMITS IT COULD NOT JUDGE

**Ratified 2026-08-27.**

> **`violations: 0` answers "of what I could judge, nothing failed." The
> question you asked was "is this surface accessible."** Those differ by exactly
> the `incomplete` bucket, and a scanner that reports both is being honest — the
> reader who quotes only the first is not.

⚠️ **REFERENCE CASE, AND THE WORST DEFECTS WERE IN THE BUCKET.** F8-S2's coding
panel was swept with axe, panel open, scoped to the panel. It returned:

    violations: 1 (color-contrast, 5 nodes)   incomplete: 1   passes: 11

The five were real and were fixed. **But an independent ratio audit of the same
panel — computing WCAG contrast per text node against its resolved ancestor
background — found EIGHT failures, and the three worst were not among axe's
five:**

| node | ratio | in axe's violations? |
|---|---|---|
| the count digits — *"**2** suggested · **1** accepted"* | **1.16** | **NO — `incomplete`** |
| the frozen notice | 2.46 | yes |
| the summary chip | 2.51 | yes |

**1.16:1 is invisible text.** axe did not fail it; axe declined to judge it,
because the element's background was `rgba(0,0,0,0)` and the rule cannot resolve
a ground through an arbitrary ancestor chain. **The most severe defect on the
surface was in the bucket labelled "I could not tell."**

## WHY THE HONEST TOOL PRODUCES THE DISHONEST REPORT

Nothing about axe misbehaved. It has a violations list, an incomplete list, and
a passes list, and it filled all three correctly. **The failure is entirely in
the reading**: `violations.length === 0` is the number that looks like the
answer, reads like a gate, and fits in a CI assertion — and it silently excludes
whatever the scanner declined to judge.

> **This is the WATCHED-SET failure with the scanner's own consent.** Elsewhere
> in this file a gate watches a narrower set than its name implies and nobody
> notices. Here the tool *tells you* the set is narrower, in a field right next
> to the one you quoted.

## THE RULE

**An accessibility claim on a new clinical surface requires the `incomplete`
bucket RESOLVED TO ZERO, or independently measured.** Either is acceptable;
ignoring it is not.

- **Resolved to zero** is the better outcome and often free — here the same
  eight-line fix took `incomplete` from **1 → 0**, because giving the text a
  ground-appropriate colour also let the rule resolve the ground.
- **Independently measured** means a second instrument that does not share the
  first's blind spot. The audit used here resolves the effective background by
  walking ancestors until a non-transparent one, then computes the ratio
  directly — which is precisely the step axe refuses to guess at.

⚠️ **AND REPORT BOTH NUMBERS, ALWAYS.** *"0 violations"* on its own is not a
result. *"0 violations, 0 incomplete, 49 elements tested"* is — the third number
being the non-vacuity floor this house already requires everywhere else.
