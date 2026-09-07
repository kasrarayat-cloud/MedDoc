# PROJECTOR-1 — bare-keyword temporality, and why the arm has to cover the WHOLE registry

**Filed 2026-09-07 by the custom-file session, under ruling #266.** Two clinical
fields are mis-stamped today. The two fixes are cheap; **the two fixes are not
the item.** The item is an arm that makes the next one impossible.

## THE DEFECT, REPRODUCED — not described

`inferTemporality` (`apps/transcribe-md/src/lib/template-twin/encounter-facts/index.ts:434-441`)
is two case-insensitive regexes over `value + ' ' + evidenceQuote`, with
`PLANNED` tested **first**:

```
PLANNED    = /\b(?:plan(?:ned)?|will|schedule(?:d)?|refer(?:red|ral)?|start(?:ing)?|follow[- ]?up)\b/i
HISTORICAL = /\b(?:history\s+of|historical|previous(?:ly)?|prior|in\s+the\s+past|resolved)\b/i
```

Run against the two sentences the ruling names, using those exact patterns:

| input | matches | stamped | should be |
|---|---|---|---|
| `History of present illness, onset: three days of burning chest pain.` | `history\s+of` | **`historical`** | `current` |
| `The patient was referred by Dr. Alan Whitfield for evaluation.` | `refer(?:red|ral)?` | **`planned`** | `current` |

Both reproduce through the **shipped** code. The per-call-site
`defaultTemporality` is only the fallback when neither regex matches, so it
cannot rescue either.

⚠️ **AND A MIS-STAMP IS NOT A COSMETIC LABEL.** A mapping declaring
`temporality: 'current'` does not approve a fact stamped `historical`, so the
resolver returns `status: not_mentioned, value: null, sourceFactIds: []`,
`reasonCode: 'temporality_not_approved'` — **a permanently blank control, with
validation green.** The field is not wrong; it is absent, and nothing on the
page says why.

## THE PATCH THAT ALREADY EXISTS IS THE ARGUMENT FOR THE ARM

The referral half is **already closed at one site**:
`visit_metadata.referring_physician` states `temporality: 'current'` explicitly
(`encounter-facts/index.ts:833`). So the class is being closed **per concept, by
hand, as each one is noticed.**

> Feed the identical referral sentence to any concept that does not state its
> tense and it still stamps `planned`.

That is the shape ruling #266 is aimed at: *fixing two keywords closes two
instances of a class that produces a new one every time a concept is added.*

## THE ARM — and its precondition, which does not exist yet

**Ordered:** every registered concept's **self-test sentence** must project to
its **declared temporality**, armed over the **whole registry**.

⚠️ **THERE IS NO CONCEPT-LEVEL DECLARED TEMPORALITY TO ARM AGAINST.**
`grep -c temporality concept-registry.ts` = **0**. The declaration exists only as
**~30 inline `defaultTemporality:` literals** inside `projectEncounterFacts`, none
of them exported.

> **An arm written before that table is extracted has to RE-TYPE the expected
> values, which makes it a control that agrees with itself rather than with the
> shipped projector.**

That is not a hypothetical objection in this repository: `narrativeSentence` is
exported from `verification-encounter.ts:420-424` **for exactly this reason and
says so in its own comment**, and `fromPersistedMapping` was exported after
`gate-217`'s first form re-implemented its rule inside the test file, *"so the
two moved together and the arm could never fail"*.

**So the first step is not the arm. It is exporting a concept → declared-temporality
table and having every `add()` call site READ from it.**

## THE COVERAGE THE ARM CANNOT HAVE, STATED UP FRONT

⚠️ **A sentence-driven arm is structurally blind to part of the registry, and it
must SAY SO rather than report full coverage.** Measured by importing the shipped
modules:

| | count | consequence |
|---|---|---|
| concepts the projector emits | 122 | |
| **with no self-test sentence** | **17** | invisible to a sentence-driven arm |
| registry concepts with a sentence but **no projector call site** | 4 | no declared temporality to compare against |

The 17: `medication.name/.dose/.route/.frequency`, `allergy.substance/.reaction`,
`family_history.relation/.condition`,
`social_history.smoking/.alcohol/.drugs/.occupation`, and the five
`measurement.*` kinds. The 4: bare `family_history`, `social_history`,
`medication`, `allergy` — only their sub-concepts are emitted.

**An arm reporting "the whole registry" while measuring 105 of 122 is the
emptiness failure this house names on sight.** It must print the covered count,
the excluded count, and the exclusion list.

## AND IT NEEDS A NON-VACUITY PAIR

⚠️ **An arm over ~105 concepts that all declare `current` is satisfied by a
projector hard-wired to `current`.** The house idiom is already in
`gate-179-narrative-and-temporality.test.ts:308-313` — assert `matched > 0`
**and** `matched < total`. The discriminating row is the `plan` concept
(declared `planned`, sentence `"Plan: …"`): if it does not come back `planned`,
the arm is measuring nothing.

## ORDER — ruled, not a preference

Ruling **#207(b)** already orders the projector fixed **first**, armed by the
self-test's own HPI dictation yielding `current`. Its prerequisite, #985, merged
as `3869851c`. So:

1. **export** the concept → declared-temporality table; every `add()` reads it
2. **fix** `inferTemporality` — the HPI header is not a temporal marker, and the
   `refer(?:red|ral)?` patch generalises from the table rather than from a 31st
   hand-stated site
   ⚠️ **shape trap:** the text under test is `value + ' ' + quote`, so the header
   is **not reliably at offset 0** and a naive prefix strip will miss it
3. **arm** it over the registry, with the coverage figures and the non-vacuity
   pair printed

## WHAT WAS NOT DONE HERE, NAMED

This is a **filing**. No projector code changed under #266. The two mis-stampings
are reproduced above so the next session starts from evidence rather than from
the ruling's prose — and so that if either stops reproducing, that is itself a
finding.

⚠️ **One claim in this note is inherited and NOT independently re-measured
here:** the 122 / 17 / 4 counts come from the reconnaissance that raised the
item. The two reproductions, the regexes, the `grep -c temporality` = 0, and the
`:833` referring-physician patch were each verified directly. **Re-run the counts
before sizing the work.**
