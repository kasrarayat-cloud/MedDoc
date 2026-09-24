# Narrative notes on the qualified WM IOV form — design (2026-09-24)

Status: **candidate, behind `QUILLMD_WM_NARRATIVE` (off by default). Not enabled for doctors. Not live-verified.**
Offline qualification only (retained provider-shaped responses and the real Word engine in CI). Live provider
verification is a separate, costed campaign (the last section) that needs the owner's authorization.

## Goal

Ordinary narrative notes, and reviewed voice transcripts adopted into the same `Encounter.notes` field, fill the
existing qualified WM IOV template without `Question label: value` lines and without `Prewritten statement: …`
lines. The template, its mapping, its content controls and the document engine stay the same; the model never
writes the document; finalized exports are never re-rendered.

## Why the form refused narrative (traced 2026-09-24 at `dedac162`)

1. Generation: WM used the legacy quote contract. An unlabelled sentence could only be quoted as a whole line, and
   in a multi-line note one unlabelled line turned every answer into a conflict (`inherited_context`).
2. The provider never received the dropdown options, the measurement units or the statements' variants.
3. WM review (`wm_review._field_decision`) required every answer's evidence to be a labelled line whose value
   equals the answer (`exact_labelled_source_required`), and every statement a `Prewritten statement: <label>:
   <wording>` line (`complete_assertion_source_required`).
4. The document engine (`WmAdapter.cs`) re-checked the same labelled-line rule at fill (`LabelledSupport`).
5. Nothing proposed a statement.

## The contract (`wm-narrative-v1`)

**One reader:** `core/wm_narrative.py`, used by generation, the page, save and finalization.

- **Units.** The notes are split by the existing `generation.source_units` (complete sentences with exact
  code-point offsets; labelled lines are units too). ⚠️ That splitter reads `ms.` as a title abbreviation, so
  `…1500 ms. The left…` is one unit; the frozen benchmark's responses cite those ids, so the splitter is unchanged
  and within a unit `wm_narrative.sentences` reads the sentences for sides and corrections.
- **Provider request.** For every field: key, label, kind, options, unit; for every assertion statement its
  variants (wording, required and omitted answers); the units; the notes. Instructions: `wm_narrative.INSTRUCTIONS`.
- **Provider response** (`NarrativeSelections`, strict): every field exactly once with `value`, `unit_ids`,
  `conflict`, `subject` (patient/family/other/unclear), `certainty` (definite/uncertain), `timing`
  (current/prior/planned/unclear); optional statement proposals `{key, variant, unit_ids}`.
- **The job.** `configuration()` stamps `narrative_contract` into the write-once job config only when the flag is
  on, so the job names the instructions it was sent. A job quoted with the contract and run after the flag went
  off is refused before any request (`NoProviderRequest`: nothing sent, charged or held). Narrative runs only on the
  Anthropic provider (12,000 output tokens, 240 s timeout, under the 5-minute stale-job threshold). The reservation
  is priced from the narrative payload itself.
- **Fixture mode** (never live): a retained response for exactly these notes is read from
  `QUILLMD_AI_REPLAY_DIR/<sha256 of the notes>.json`, else the labelled lines are read as the labelled fixture
  reads them. Either way the one validator judges it. The receipt names it (`synthetic-narrative-replay` /
  `synthetic-narrative-fixture`).

### What the parent decides, deterministically, per answer

| condition | outcome |
|---|---|
| empty value | missing |
| a cited unit is not a unit of the notes, a choice is not an original option, a value has no unit, a key is missing/duplicated/unknown | the response is refused |
| instruction-like text in the notes or a label | every answer held |
| `subject` family or other | missing (the candidate is shown as someone else's finding) |
| the value is not written in a cited unit: a measurement's number with a unit word of its column (or a reflux time in seconds), not approximate, bounded or ranged; text copied; a choice is an option | held |
| a unit labelled with this question gives another value, or any line labelled with this question disagrees (prose under a choice's label is interpretation, not disagreement); a unit labelled for another question supports nothing | held |
| a Right/Left question whose value the text does not place on that side (nearest side word before it in its sentence, else after it in the sentence, else before it in its paragraph; `both`, `bilateral`, `either` count for both) — ruling #127: the model never asserts laterality | held |
| `subject` unclear, `certainty` uncertain, `conflict`, or a timing that does not fit the question (previous-treatment questions ask about prior treatment; every other one about this examination; demographics have no timing) | held |
| an installed governor (a heading line or a pointer, read per sentence) governs the cited unit, unless every governor is a heading made only of structural words (sides, limbs, this form's veins, report sections) | held with the governing lines |
| the cited unit's own label (before its first colon) denies or reframes (`Denies:`, `Family history:`), by the installed vocabulary | held |
| a correction: inside the answer's own sentence it supersedes the text before it; any correction mentioning a measurement's number holds that measurement; a correction no answer cites holds the answers before it **in its paragraph** | held |
| otherwise | supported (pre-filled; the clinician still reviews every answer) |

No whole-note rule: an unrelated sentence, a correction elsewhere or a conditional instruction affects nothing else.

### Statements

A proposal only pre-selects the page and the resolve; the first save replaces it with the clinician's decision. It
is kept only when its variant exists, its required answers are supported, its omitted answers are empty, its cited
units are not held, and a fixed wording's sentence names its side. Identity and signature are never proposed.

What a statement may rest on at review (and at fill):

- a sentence of the notes (the wording's side must be named, the sentence must not be held);
- a wording **built from its answers** — the answers joined by at most 12 connecting words (`TYPE OF EXAM: {side}`,
  the previous-treatment sentence, `Right {vein} is {finding}`, `Right deep venous system {finding}`) — on those
  answers, each complete and reviewed;
- a `not_documented` wording on the answers whose absence it states, each reviewed and empty.

The technique paragraph (63 and 81 words of its own claims), `none`, `not_assessed`, the reflux findings and
clinical correlation need a sentence of the notes (the paragraph-39 recommendation keeps its recorded rule: it needs
support). The page offers "rests on its answers" as an explicit tick; the answer keys are named from the mapping,
never from the post.

### Review, page and finalization

`wm_review` accepts narrative evidence (`kind: unit`, `kind: answers`) only with the flag on and applies the same
support rules; finalization's `governed_decisions` rechecks every `supported` narrative answer with the same reader
(`wm_narrative.held_labels`), and the page and save show and keep exactly what it refuses
(`wm_narrative.as_currently_held`).

### The engine (`WmAdapter.cs`)

`Evidence` gains an optional `kind`/`answer_keys`; the mapping records are unchanged, so every stored mapping digest
is unchanged. At fill a narrative answer must be written in its cited sentences (the parent's quantity, bound and
word patterns, byte-identical and asserted by a test), agree with its labelled lines, and for a sided question have
a side word of that side (or both) between its paragraph's start and the sentence's end. Every engine check is
implied by the parent's (never stricter), so the export never refuses what review accepted.

## Qualification (offline — not live evidence)

- **Frozen benchmark** (`core/tests/benchmarks/wm_narrative/`), committed before the implementation: 23 cases, six
  labelled/narrative pairs, a transcript, positive findings, denials, family history, corrections, missing
  information and genuine conflicts; expectations by an independent author (`d6c661a1`), provider-shaped responses
  by a second author blind to the expectations (`17483cc1`): a careful set and a weak set with named injected errors.
  ⚠️ The validator's rules were iterated against it over five scoring rounds, so it is a development set.
- **Held-out benchmark**: written after the implementation by an author who did not read it; reported separately.
- **The real workflow**: `test_wm_workflow.WMNarrativeWorkflow` (CI, real Word runtime): retained narrative response
  → generation → the page as rendered → decisions → finalization → export into the unchanged original; forged
  narrative answers refused at fill.

## Live verification (NOT run; needs the owner's authorization)

**One campaign:** the 17 narrative and transcript cases of the frozen benchmark, then the held-out cases, through the
live provider on the synthetic account (`QUILLMD_WM_NARRATIVE=1` on the QA stack or a synthetic encounter; never a real
visit), scored by the same scorer (`core/tests/wm_narrative_benchmark.py`), with each response retained as a replay
file so every later run can be reproduced offline.

**Size, measured on the frozen cases:** 468,149 input bytes (27.5 KB per request: payload, instructions, schema) and,
from the careful responses, ~13.7 KB of output per request. The application reserves per request (input bytes +
12,000) input tokens and 12,000 output tokens at the configured rates and shows that maximum before sending.

**Cost** (the configured rates are in the private environment and were not read; three list-price assumptions):

| assumed $/M tokens (in / out) | expected, 17 requests | reservation bound | ×1.5 customer limit |
|---|---|---|---|
| 3 / 15 | ≈ $1.56 | $5.08 | $7.62 |
| 5 / 25 | ≈ $2.60 | $8.46 | $12.69 |
| 15 / 75 | ≈ $7.81 | $25.38 | $38.07 |

(expected = input bytes/3.5 and output bytes/3 tokens; the bound is what is held, not what is charged; add the
held-out cases at the same per-request figures.)

**Pass criteria, fixed before the run:** on the narrative/transcript cases, no wrong pre-filled answer; unnecessary
holds and missed answers reported separately with every row; any wrong pre-filled answer stops the campaign and is
analysed before anything else. Enabling the flag for doctors is a separate owner decision after it.
