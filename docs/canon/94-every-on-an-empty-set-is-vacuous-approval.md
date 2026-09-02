# `every()` ON AN EMPTY SET IS VACUOUS APPROVAL

**Standing 2026-09-02, ruling #171(3).**

> **A guard that examined nothing reports `unevaluated`, never `eligible`.**

## The defect

```ts
return paragraphs.every(paragraphIsInert) ? 'eligible' : 'ineligible';
```

`[].every(...)` is `true`. So a call with an empty set returns the
**computed-and-approved** value from a guard that inspected nothing at all.

⚠️ **AND IT APPEARED ONE LAYER INSIDE THE FIX THAT EXISTS TO ABOLISH IT.** The
same slice had just replaced a boolean whose `true` was encoded as ABSENCE —
precisely because *unexamined* and *examined-and-approved* had become
indistinguishable, which let two whole bindings go unguarded while every test
stayed green. The three-state sentinel was introduced to separate them, and the
predicate feeding it re-merged them for the empty case.

**Measured:** a table cell with no `w:p`, and a legacy field whose containing
paragraph is `null`, both returned `eligible` and **counted** toward a clinical
certification's blank requirement.

## Why the empty case is not an edge case

The reason it survived review is that it reads as one — a region with no
paragraph cannot print a marker, so the harm looked bounded. **That reasoning is
about today's consequence, not about the property.** The property is that the
verdict must distinguish three states, and a vacuous `true` collapses two of
them. The next caller with an empty set is not obliged to be harmless.

## The practice

- **A universal quantifier over a possibly-empty collection is THREE cases, not
  two** — all-pass, any-fail, and nothing-to-check. Write the third one.
- Where a type already carries an *unknown* state, the empty case is almost
  always that state. Reach for it before reaching for the default.
- ⚠️ **AND IT HAD NO ARM, WHICH IS THE OTHER HALF.** Replacing `every` with
  `length === 0 || some` redded **0 of 757** tests. Instrumented, **2 171 of
  2 174** calls in the whole suite had exactly ONE element in scope. *A
  universal claim tested only on singletons is not tested* — the quantifier and
  the empty case each need a fixture that can tell them apart, and neither
  arrives by accident.
