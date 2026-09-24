# Narrative notes on the qualified WM IOV form — design (2026-09-24)

Status: candidate, behind `QUILLMD_WM_NARRATIVE` (off by default). Not enabled for doctors. Live
provider verification is a separate, costed campaign (see the end).

## Goal

Ordinary narrative notes, and reviewed voice transcripts adopted into the same `Encounter.notes`
field, fill the existing qualified WM IOV template without `Question label: value` lines and
without `Prewritten statement: …` lines. The template, its mapping, its content controls and the
document engine stay the same; the model never writes the document; finalized exports are never
re-rendered.

## Why today's form refuses narrative (traced 2026-09-24 at `dedac162`)

1. Generation: WM uses the legacy quote contract. An unlabelled sentence can only be quoted as a
   whole line, and in a multi-line note one unlabelled line turns every answer into a conflict
   (`inherited_context`).
2. The provider never receives the dropdown options, the measurement units or the statements'
   variants.
3. WM review (`wm_review._field_decision`) requires every answer's evidence to be a labelled line
   whose value equals the answer (`exact_labelled_source_required`), and every statement a
   `Prewritten statement: <label>: <wording>` line (`complete_assertion_source_required`).
4. The document engine (`WmAdapter.cs`, pinned and qualified) re-checks the same labelled-line
   rule at fill (`LabelledSupport`), as a second boundary.
5. Nothing proposes a statement.

## Contract

### Source units

The notes are split by the existing `generation.source_units` (complete sentences with exact
code-point offsets; labelled lines are units too). The same splitter is the only reader of units
for generation, the page, save and finalization.

### Provider request (`wm-narrative-v1`)

The payload carries, for every field: `key`, `label`, `kind` (`choice` | `measurement` | `text`),
`options` (choice), `unit` (`mm` | `ms`); for every statement: `key`, `label`, its variants
(`id`, `label`, wording template, required and omitted controls); the source units (`id`, `quote`);
and the notes.

### Provider response schema

```json
{
  "fields": [
    {"key": "measurement_1_1", "value": "3.2 mm", "unit_ids": [4], "conflict": false,
     "subject": "patient", "certainty": "definite", "timing": "current"}
  ],
  "statements": [
    {"key": "claim_32", "variant": "negative", "unit_ids": [7]}
  ]
}
```

- Every field key appears exactly once. Missing information: `"value": ""`, `"unit_ids": []`.
- `value`: a choice is the exact option text; a measurement is digits and the column unit
  (`3.2 mm`, `650 ms`); text is copied from the cited units.
- `subject`: `patient` | `family` | `other` | `unclear`. `certainty`: `definite` | `uncertain`.
  `timing`: `current` | `prior` | `planned` | `unclear`. `conflict`: the notes support more than
  one value.
- `statements`: optional proposals; a statement not listed is not proposed.

### What the parent decides, deterministically, per answer

| condition | outcome |
|---|---|
| empty value | missing |
| a cited unit is not a unit of the notes, or a choice is not an original option | refused (the response is invalid) |
| a measurement's number and unit (or seconds for a reflux time) do not appear in a cited unit; a text value is not in a cited unit | held: the value is not supported by the source |
| `subject` is not `patient` | missing (kept as a non-patient candidate) |
| `certainty` is `uncertain`, `timing` is `unclear` or does not fit the question (previous-treatment questions ask about prior treatment; every other question about the current examination), or `conflict` | held for that answer only |
| a cited unit is governed by a heading, pointer or correction (the installed protections, read per sentence) | held for that answer only |
| a correction mentions the answer's value, or a correction is cited by no answer | held (fail closed) |
| otherwise | supported (pre-filled; the clinician still reviews each answer) |

An unrelated sentence, a correction cited for another answer, or a conditional instruction does
not affect other answers. The whole-note rule is not used in this contract. Instruction-like text
still holds everything (security).

### Statements

A proposal is kept only when its variant exists, every required control has a supported answer,
every omitted control is empty, and the engine's conflict rules accept it. Its evidence is the
cited units (fixed wording) or the supporting answers (`kind: answers`). Otherwise the statement
is not proposed. Either way the clinician chooses and ticks each statement; the review token binds
the wording they saw.

### Evidence kinds (parent and engine)

Existing labelled evidence (`{quote, start, end}`) is unchanged. Narrative evidence adds
`kind: "unit"` (an exact slice of the unchanged notes, value checked as above) and, for statements,
`kind: "answers"` (answer keys that must be supported and reviewed). The engine verifies both at
fill, in addition to its existing checks; labelled notes behave exactly as before.

## Qualification

- A fixed synthetic benchmark, written before the implementation by an author who did not see it:
  equivalent labelled and narrative notes, positive findings, denials, family history,
  corrections, missing information and genuine conflicts. Two numbers are reported separately:
  wrong supported answers, and unnecessary holds. Refusing everything fails.
- Offline: authored provider-shaped responses (a careful model and a weak model with realistic
  errors) through the real validator, review and statement proposal. These are not live evidence.
- The real workflow: generation → evidence review → clinician decisions → finalization →
  original-format export, with the Word runtime in CI.

## Live verification (not run; needs authorization)

One campaign: the benchmark's narrative cases through the live provider on the synthetic
account, measured by the same scorer; cost stated before it runs.
