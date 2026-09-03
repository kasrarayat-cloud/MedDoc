# STATE THE PROPERTY WHERE IT ACTS, NOT ON THE LIST

**Recorded 2026-09-03, from the final adversarial pass of the #165–#175 arc.**

> **Assert the property the list exists to buy, in the artifact where it acts.
> An assertion ABOUT the list is a different claim, and it is satisfied by
> versions of the list that break the property.**

## The setup

`STRUCTURE_KEEP_WHOLE` is a **17-member** set of OOXML property containers that
the renderer copies VERBATIM when it clears a template field — paragraph
properties, run properties, table grids, bookmarks, comment anchors,
editable-range marks. Losing a member is not a formatting nit: the renderer
silently **DELETES** that container from every cleared control, and a doctor
loses formatting, a bookmark or an editable range out of their own template.

Two arms watched it. Both missed its real failure.

| arm | what it asserts | mutation | redded |
|---|---|---|---|
| size floor | `size >= 15` — non-vacuity | delete `permStart`, `permEnd` | **0 of 756** |
| structural regex | file imports `./structure-keep`, and contains no `const STRUCTURE_KEEP_WHOLE … = new Set` | local 8-member copy under another name | **0 of 756** |

## Arm 1 — a floor on a 17-member set licenses losing two

`size >= 15` is a non-vacuity check, and it is a good one: it stops the set
being emptied. It also **states, in code, that fifteen is enough.** Deleting
`permStart` and `permEnd` sits inside the licence. Measured after the mutation:
`w:permStart` survives = **false**, `w:permEnd` survives = **false**; baseline,
both **true**.

## ⚠️ Arm 2 — the negative regex was pinned to a spelling the bug has never worn

The historical drift this arm was written for was named `PROPERTY_BLOCKS`. The
regex forbids `const STRUCTURE_KEEP_WHOLE … = new Set`. So the drift it exists
to catch **does not match its own pattern**, and neither does this:

```ts
import { STRUCTURE_KEEP_WHOLE } from './structure-keep';
const KEEP_WHOLE_LOCAL: ReadonlySet<string> = new Set([ /* 8 of 17 names */ ]);
void STRUCTURE_KEEP_WHOLE;
if (KEEP_WHOLE_LOCAL.has(local)) { … }
```

The import is present. The forbidden identifier never appears. Both regexes are
satisfied, and `bookmarkStart`, `bookmarkEnd`, `permStart` and `permEnd` are all
lost from every cleared control — baseline: all present.

⚠️ **BOTH ARE THE SAME DEFECT ONE LEVEL UP.** One asserts the list's SIZE, the
other its PROVENANCE. Neither asserts what the list is for. A guard aimed at the
list can only ever forbid the shapes of wrongness somebody enumerated; the
property is a fact about the OUTPUT DOCUMENT, and it does not care how the set
was spelled or how many names were in it.

## The cure, and it is cheap

Clear a control holding each container, then assert the container is **still
there in the rendered bytes**. A member lost by deletion, by a size the floor
tolerates, or by a local copy under ANY name now reds — because the renderer
really does delete it and the arm really does look. Both mutations above now
red, and the `permStart`/`permEnd` failure message names the two members
exactly.

**Two things that make it sound, and it is unsound without either:**

- **A WATCHED-SET DIFF FIRST** — [canon 28](28-a-gate-s-watched-set-is-diffed-against-the-spec-s-named-se.md).
  Every member of the SHIPPED set must have a fixture, or the arm refuses.
  Without that, a member added later is silently unproved — which is exactly how
  the two arms above failed, one enumeration at a time.
- **NON-VACUITY AT THE OTHER END** — the clear must be shown to really remove
  content: the doctor's stale text must be **GONE** from the same document. A
  renderer that clears nothing preserves everything, and every "it survived" row
  is then vacuous.

## Honest limits

- This does not retire the structural arm. It still catches the literal
  re-declaration, cheaply and at the right layer; it is simply not the thing
  standing between the set and the harm.
- The output arm proves the containers survive **the clear**. It says nothing
  about any other path through the renderer, and nothing about whether a
  container is copied *correctly* — only that it is still present.
- The refusal is only as wide as the shipped set. A container the product does
  not yet keep is outside every arm here, by construction.

## The generalisable move

> **When you catch yourself writing an assertion whose subject is a data
> structure, ask what that structure is FOR, and whether the answer is
> observable somewhere downstream. If it is, assert it there.**

The cheap mechanical check, before believing any list-shaped guard:

    Name the harm. Then ask: could I commit a version of this list that
    causes the harm and keeps this arm green? Write that version and run it.

Here the answer was yes, twice, and it took one mutation each to find out.
