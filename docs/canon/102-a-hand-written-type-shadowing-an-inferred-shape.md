# A HAND-WRITTEN TYPE SHADOWING THE QUERY'S INFERRED SHAPE IS TWO DESCRIPTIONS OF ONE THING

**Recorded 2026-09-03, from the final adversarial pass of the #165–#175 arc.**

> **A cast from an inferred shape to a hand-written one is not a type annotation.
> It is a SECOND description of the same data, maintained by hand, and nothing
> checks that the two still agree.**

## The specimen

```ts
const rows = await prisma.noteTemplate.findMany({ select: { /* … */ } });
…
(rows as Row[]).map(…)
```

`Row` is a locally declared interface listing the fields. A fix needed a new
column in the mapping, so the column was added to the query's `select` — the
obvious and correct edit. **The mapping still could not see it, and `tsc` was
silent**, because the cast had thrown the inferred shape away and replaced it
with a description that does not mention the new field.

The value arrived from the database and was dropped on the floor one line later.

| description | knows the new column? | who maintains it |
|---|---|---|
| the query's inferred result type | **yes**, the moment `select` changed | the compiler |
| `Row`, at the cast site | **no** | a person who has to remember |

## ⚠️ THE DIRECTION OF THE FAILURE IS THE DANGEROUS ONE

An **extra** property is assignable, so a field ADDED to the query can never
produce a type error at the cast. The compiler is not asleep here — it is
**structurally incapable** of catching this edit, and no amount of strictness
changes that.

⚠️ **AND THE OPPOSITE DIRECTION IS CAUGHT, WHICH IS EXACTLY WHY THE PATTERN FEELS
SAFE.** Remove a field from the `select` that `Row` declares and the cast reds
immediately. So the shape has a live, visible, reassuring failure mode on one
axis and total blindness on the other — and the blind axis is the one every
feature change travels down.

## What it cost, in this instance

The field was `blockingUnsupportedCount`. Its absence from the mapping meant a
clinical surface rendered **"Preparing your format…"** to a doctor whose
template the system had **already refused to certify**.

⚠️ The symptom of this defect is a feature that silently does nothing — which on
a clinical surface is not silence. It is an instruction. The doctor was told to
WAIT when the correct instruction was to ACT, and the code that knew better had
the number in hand and no way to say it.

## The cure, in order of preference

1. **DELETE the hand-written type and let the query's shape infer.** One
   description, and the drift is not possible rather than not-yet-happened.
2. **If a name is genuinely needed, DERIVE it from the query** rather than
   restating it, so the two cannot disagree.
3. **If neither is possible, the two must be edited in the SAME commit**, and
   that obligation belongs in a comment at the cast site. This is third because
   it is prose — it decays silently, like any other prose obligation.

## Honest limits

- This does not say every cast is a defect. It says a cast **onto a shape the
  compiler already derived** is a copy, and it names what copies do.
- No claim is made about how many such casts exist in this repository. The
  specimen is one, found by an adversarial pass reading a finished diff — not by
  a census.
- Nothing here would have been caught by a stricter compiler flag, a lint on
  `any`, or a review that read the diff. The diff was correct at both edited
  sites; the defect lived in the site that was **not** edited.

## The generalisable move, and it costs one question

> **Ask of any type you are about to write: *is this ASSERTING something the
> compiler already knows?*** If the answer is yes, it is not documentation — it
> is a copy, and copies drift.

Same family as two hand-maintained lists for one set: **the cure is one symbol,
not two careful editors.**

A cheap shortlist, for a tree you already suspect — it produces candidates to
read, never a verdict:

```bash
grep -rnE '\) as [A-Z][A-Za-z]*(\[\])?' --include='*.ts' src/
```

Each hit gets the one question above. The ones where the answer is *yes* are the
ones with a second description nobody is checking.
