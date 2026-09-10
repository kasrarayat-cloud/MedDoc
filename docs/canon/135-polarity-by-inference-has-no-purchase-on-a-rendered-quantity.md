# POLARITY BY INFERENCE HAS NO PURCHASE ON A **RENDERED QUANTITY** — STATE IT

**Ratified 2026-09-07, from REGISTRY-1's adversarial pass.**

`inferPolarity` decides whether a fact is affirmed or denied by locating its
VALUE inside its evidence quote and reading the words around it. That works
because, for almost every concept, the value **is a span of the doctor's own
speech**: `heartburn`, `Hypertension`, `factory operative`.

> **It stops working the moment the value is a RENDERING of the fact rather
> than a quotation of it.**

`total_time_minutes` projects `String(45)`. The clinician says *"forty five
minutes"*. The numeral is **not in the quote**, so the locator returns −1 and
polarity falls through to the **unscoped whole-quote** test — the very form the
scoping arms were built to narrow. Any `no` / `never` / `denies` anywhere in the
sentence then denies the quantity.

**MEASURED, on plainly affirmative dictation:**

| dictation | inferred |
|---|---|
| `"No fever, total time 25 minutes."` | **denied** — the digits ARE locatable, but `CLAUSE_BREAK` is `/[.;\n]/` and **a comma is not one**, so an unrelated ROS denial governs a billing number |
| `"Total time of forty minutes spent, no separate procedure performed."` | **denied** — spelled number ⇒ unlocatable ⇒ unscoped |
| `"No fever. Total time 25 minutes."` | affirmed — a period IS a clause break |

## WHY IT IS EXPENSIVE

A denied fact is **withheld** for every field kind except checkbox. On a
narrative control the reason is **certification-exempt**, so the field blanks
**silently and the template still certifies green**. The doctor's own figure
simply is not there.

## ⚠️ AND THE SELF-TEST WILL AGREE WITH THE BUG

The certification self-test's sentence spelled *"forty five minutes"* against a
projected `"45"` — so it took the unlocatable route too, and passed only because
that one sentence happened to contain **no denial token**. A proof built from
prose inherits the prose's accidents.

## THE RULE

> **Where the layer KNOWS the polarity, it STATES it and stops guessing it back
> out of the prose.** A quantity is not a clinical assertion that can be denied;
> there is no such thing as a denied total time.

This is the same doctrine Q1 §02.9 applied to ROS — *"L3 states these now, so
stop guessing them back out of the prose"* — reached again from the other end.

⚠️ **AND THE FIX IS AT THE SOURCE, NOT THE INFERENCE.** Do not widen
`CLAUSE_BREAK` to include commas: that changes polarity for every concept in the
product to fix one that should never have been asking. **The test is whether the
value is a QUOTATION or a RENDERING** — and `measurement.<metric>` already
projects a normalised number and shares this shape today.
