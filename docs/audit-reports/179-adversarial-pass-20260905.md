# #179 — the mandatory pass over the finished diff

**2026-09-05. Run before merge, per the standing clinical-generation-path rule.**

## ⚠️ THE INDEPENDENCE PROPERTY IS MISSING, AND THAT IS STATED FIRST

`AGENTS.md`'s argument for this pass is that it **does not share the author's
context** — *"a reviewer asked whether the code is good says yes to code that is
good and wrong."* This pass was run by the author of the arms it examines, in
sequence, because the resource pre-flight ruled out a parallel fan-out (four
sessions on the box, swap 4091/4095 MB, pollers already being reaped).

**So it is weaker than the pass the rule describes, and it is filed as such.** A
fan-out pass over this diff is still owed and is not discharged by this file.

## Scope

`origin/main...HEAD` — **15 source files, ~2376 insertions**, on the clinical
generation path: L3 extraction, concept matching, checkbox derivation, the
verification-encounter generator, and the model client's temperature policy.

## What the pass drove at

The sharpest available target: **#179(7) made temperature handling fail-closed
with a `throw` on the clinical path.** A throw there does not degrade output, it
removes it.

### FINDING — the fail-closed throw is reachable from CONFIGURATION, not just code

`shouldOmitTemperature()` refuses any model matching neither list and is called
at **three request-building sites** (`anthropic.ts:373, 475, 739`).

**Concrete input → wrong output:**

| | |
|---|---|
| input | `TRANSCRIBE_MD_CLINICAL_MODEL=claude-sonnet5` — a plausible typo; the real id is `claude-sonnet-5` |
| result | `UnknownTemperaturePolicyError` thrown from `anthropic.ts:373`, **uncaught**, on every clinical call that passes a temperature |
| reach | **every** clinical layer passes one — L2 `0`, L4 `0.2`, L6 `0.1`, L7a `0`, L7b `0`, L7e `0.3`, 04b `0`, 06b `0` |
| and it is production code, not eval | `parse-note-to-template.ts:54` and `synthetic-test.ts:542/562` both read that env var |

⚠️ **THE FAIL-CLOSED CHOICE IS NOT THE DEFECT — THE TIMING IS.** Refusing rather
than guessing is the ruling, and it is right: a wrong guess is a 400 on the
clinical path or an undeclared change to sampling. But the refusal happens at
**request-build time, per call**, so a one-character env typo does not fail fast
with a clear message at startup — it fails on the first clinical request, inside
the pipeline, where it surfaces as a generation failure rather than a
configuration error.

**Suggested, NOT applied** (it widens the diff, and the ruling did not ask for
it): validate `TRANSCRIBE_MD_CLINICAL_MODEL` against the two lists **once at
startup**. Same refusal, same reasoning, moved to where a human is reading.

### Population check, with its re-arming condition

Every model id literal in the tree today is covered by the six patterns —
`claude-fable`, `claude-mythos`, `claude-haiku-4-5*`, `claude-opus-4*`,
`claude-opus-5`, `claude-sonnet-4-5/4-6/5`. **That is a fact about today's
corpus, not a property of the code.** The path re-arms the moment anyone sets
that env var to a family not in the lists — including any legacy-form id such as
`claude-3-5-sonnet-…`, which the `^claude-sonnet-` anchor does not match.

## Arm coverage, re-measured by MUTATION rather than by grep

| part | guard | arm |
|---|---|---|
| 1 — closed ROS lexicon | schema `superRefine` | **was NONE** (redded 0/5922) → armed, 6 arms |
| 2 — three-part concept form | registry | pre-existing, 9 files |
| 3 — `conceptScope` membership | validation | **was NONE** (redded 0/660) → armed, 8 arms |
| 5 — checkbox multi-scope refusal | derivation | **was NONE** (redded 0/668) → armed, 6 arms |
| 6 — temporality default / narrative table | validation + generator | **was NONE** (redded 0/674) → armed, 11 arms |
| 7 — temperature policy | model client | pre-existing and REAL — verified by mutation |

⚠️ **Part 7 was nearly filed as unarmed.** A grep for `TEMPERATURE_STRIPPED`,
`shouldOmitTemperature` and `UnknownTemperaturePolicyError` across `*.test.ts`
returned **nothing**. The arm exists and drives the policy through the PUBLIC
client instead of importing the private symbol — which is the better test and
the reason the grep missed it. *A grep that resolves a symbol has not found its
data.* Confirmed by mutation: replacing the throw with a silent default reds
exactly one arm, by name.

## What this pass did NOT do

- No fan-out, no independent lenses — see the header.
- It did not examine the four new `scripts/` files (~1017 insertions:
  `certify-active`, `transfer-certification-to-active`, `synthetic-only-active`,
  `l3-model-parity`). They are operator tooling, not the request path, and the
  pass spent its budget on the surface that can remove clinical output.
