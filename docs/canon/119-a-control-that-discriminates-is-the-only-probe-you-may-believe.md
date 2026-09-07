# A CONTROL THAT DISCRIMINATES IS THE ONLY PROBE YOU MAY BELIEVE

**Standing 2026-09-07, from the #179 repair. Three instances in one session,
each caught only because a control was run beside the probe — and one that was
NOT caught until the answer was already reported.**

`docs/canon/114` and `117` are about a CONTROL that passes when it should fail.
This is the layer under them: **a PROBE that produces the right answer for the
wrong reason.** Both are green, both are believed, and only a second reading
that must come out DIFFERENTLY can tell them apart.

## THE REFERENCE CASE — `citedFactIds`

A probe compared the validator's verdict against the resolver's, to show that a
consolidation had closed a divergence:

```js
const resolverCites = (resolution?.citedFactIds?.length ?? 0) > 0
                   || resolution?.status === 'supported';
```

It printed **20 cells, 0 disagreements** — the correct answer.

⚠️ **`citedFactIds` DOES NOT EXIST. The field is `sourceFactIds`.** Every read
was `undefined`, `?? 0` made it `0`, and the `||` fallback silently carried the
whole probe. The right answer arrived from the arm nobody meant to rely on.

**It surfaced only because the same logic was then written into a test WITHOUT
the fallback**, where it failed 11 of 20 cells in the opposite direction. Had
the arm been written with the fallback too — the natural thing, since the probe
"worked" — it would have shipped green and measured nothing.

> **A FALLBACK IN A PROBE HIDES A TYPO IN THE FIELD IT IS READING.** Read the
> real field, with no alternative, and let it throw.

## AND THE CONTROL IS WHAT MAKES A ZERO MEAN ANYTHING

Two more from the same session, both zeros that were about the instrument:

| probe | reported | actually measured |
|---|---|---|
| `for f in $(find / -name "*.docx")` | *no form above 30 controls* | the shell **word-split a filename containing spaces** — it was looking straight at a 35-control form. `-print0 \| while IFS= read -r -d ''` answers |
| prompt reach, via an exported constant | `0/13` systems on the control tree | **the constant is not exported there** — it measured the export, not the prompt. Source-extract BOTH sides |

**In both, the number was correct about something.** It was correct about the
wrong subject, which is `docs/canon/114`'s watched-set failure wearing a probe's
clothes.

## THE RULE

> **Run the probe against a tree, a fixture or an input where the answer MUST
> come out differently — and require that it does.**

The `citedFactIds` harness earned belief only when it was run against the
UNMODIFIED branch and returned **3 disagreements** where the fixed tree returned
**0**. Same code, two trees, opposite answers. Until that ran, `0 disagreements`
was indistinguishable from `0 things measured`.

⚠️ **AND THE CHEAPEST FORM OF THIS IS FREE:** when a probe reads a field, delete
its fallback. When it counts, assert the count is non-zero AND non-total. When
it greps, grep for something that must NOT be there. A probe with no failing
case is a print statement.
