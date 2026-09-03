# A LINT'S ZERO CAN BE A FACT ABOUT A NAME

**Recorded 2026-09-03, from the final adversarial pass of the #165–#175 arc.**

> **An escape hatch matched by IDENTIFIER TEXT, with no scope and no ordering,
> makes the gate's verdict depend on what the variable is called.**

## The instrument

An AST lint (TypeScript compiler API) refuses an **uncounted first of filter** —
`xs.filter(pred)[0]`, and its two-statement form:

```ts
const rows = xs.filter(pred);
// …
rows[0];
```

Taking the first of an unbounded filter silently selects one of several. The
lint let a site pass when the count had been asserted.

## The defect

That escape scanned the **whole source file** for any `<bound>.length`, **by
identifier text**. No scope. No ordering. Eleven probes driven through the real
predicate; **seven came back wrong, in both directions**:

| # | probe | shipped verdict | correct |
|---|---|---|---|
| 1 | a same-named variable in **another function** carries the `.length` | 🟢 clean | 🔴 offender |
| 2 | `.length` as a truthiness guard — `if (rows.length) return rows[0]` | 🟢 clean | 🔴 offender |
| 3 | `.length` as a **for-loop bound** | 🟢 clean | 🔴 offender |
| 4 | the count asserted **after** the take | 🟢 clean | 🔴 offender |
| 5 | a weak matcher — `expect(rows.length).toBeGreaterThan(0)` | 🟢 clean | 🔴 offender |
| 6 | a compliant site, plus an unrelated same-named `rows[0]` elsewhere | 🔴 offender | 🟢 clean |
| 7 | `.at(3)` — the argument was ignored, so it counted as taking the first | 🔴 offender | 🟢 clean |

Five false negatives and two false positives out of one escape clause.

## ⚠️ THE IN-SITU DEMONSTRATION IS THE ARGUMENT

Planting a **genuine offender in a watched gate file** left the gate **GREEN** —
because `refused.length` appears **twelve times elsewhere in that same file**.
Renaming the bound variable to `zzRows`, the code otherwise identical, **redded
it and named the line.**

**The gate's zero was a fact about a variable's name.** And the names are not
exotic: `rows`, `fields`, `refused` and `proofs` are exactly what this corpus
reuses across dozens of `it()` blocks per file — so the laundering gets more
likely as a file grows, which is to say as there is more to get wrong.

## The cure — and its shape is the lesson

The semantic question was **abandoned, not refined**. Deciding whether a given
`.length` reference constitutes an *assertion* is a judgement, and it was
falsified five times; that is
[canon 75](75-three-falsifications-is-data-about-the-instrument.md) — the next
counterexample always exists.

So the escape now requires the **one spelling that cannot mean anything else**:

- `expect(<bound>.length`,
- inside the **same enclosing function**,
- textually **before** the take,
- and **not** under an *at-least* matcher — `toBeGreaterThan`,
  `toBeGreaterThanOrEqual`, a closed list.

A truthiness guard, a loop bound and a later assertion are now all correctly
refused, because **none of them is that spelling**. The escape got narrower than
the concept it approximates, on purpose.

## And the second half: the predicate carries its own probes

Those **twelve probes are folded into the gate permanently**, four of them
**controls**, so that a predicate which flagged nothing could not pass.

⚠️ **"Every gate file is clean" is a fact about the CORPUS. It says nothing
about whether the predicate works.** A predicate with no probes reports a green
that means *nobody wrote the shape I happen to catch* — and that sentence is
true of a lint that catches nothing at all.

## Honest limits

- This does **not** claim the new escape admits every legitimate counted take.
  It is deliberately narrower than the concept; a compliant site spelled another
  way is refused, and the author writes the one spelling instead.
- The eleven probes are the shapes that were *thought of*. They bound the known
  failure modes, not the unknown ones.
- Nothing here says identifier-text matching is always wrong — it says it cannot
  carry a **scoped, ordered** claim, which is what an assertion is.

## The generalisable move

> **Before believing a lint's zero, rename the thing it is reasoning about.**

If the verdict moves, the gate is reading a name rather than a structure. It is
a one-character edit and it takes seconds:

```bash
# plant a real offender in a real watched file, then:
#   1. run the gate            -> expect RED
#   2. rename the bound var    -> run again
# a verdict that changes on the rename is a verdict about the NAME
```

Same family as
[canon 96](96-a-control-that-never-touches-a-file-cannot-guard-files.md) — the
control must be able to fail in the dimension the instrument fails in — and the
dimension here is *which identifier happened to be in scope somewhere else in
the file*.
