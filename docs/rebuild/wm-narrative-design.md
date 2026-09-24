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

Two kinds of rule, and the difference is who can overrule them:

- **Support** (`wm_narrative.support`): whether the cited text CARRIES the value — written there, not struck by its own
  correction, on the question's side. No decision changes that, so review refuses it too and the engine re-checks the
  coarse part of it at fill; the clinician's way through is a sentence (or a labelled line) that carries the answer.
- **Governing** (`wm_narrative.governing`): whether something around the text makes the value uncertain — a heading, a
  label, a correction elsewhere, a relative nearby. It holds the PRE-FILL (the candidate is shown beside what holds it);
  the clinician who reads it may still choose the answer, and finalization re-checks every pre-filled answer.

| condition | outcome |
|---|---|
| empty value | missing |
| a cited unit is not a unit of the notes, a choice is not an original option, a value has no unit, a key is missing/duplicated/unknown | the response is refused |
| instruction-like text in the notes or a label | every answer held |
| `subject` family or other | missing (the candidate is shown as someone else's finding) |
| **support:** nothing it cites can carry it (only another question's labelled line, only a structural heading) | held |
| **support:** the value is not written in a cited unit: a measurement's number with a unit word of its column (a reflux time may be in seconds), not approximate, bounded, ranged or an alternative (`7.4 mm+`, not `7.4 mm + reflux`); text copied (ASCII case folded, every other character exact, as the engine compares it); a choice is an option | held |
| **support:** the value's own sentence strikes it in place: a correction inside a sentence strikes only what it stands right after — correcting to a number, the number just before it (with at most a few words after it) when of that unit or bare (`6.1 mm, correction, 7.6 mm`, `6.9 correction 6.6 millimeters`, spoken numbers too); correcting to words, the few words just before it; a SPOKEN correction opening its sentence still strikes what it stands right after (`The right sorry left great saphenous vein …`) — or it restates two values of its unit (`6.1 mm should read 7.6 mm`; a placed correction counts them up to the next location it names, so `7.4 millimeters sorry 7.6 millimeters proximal thigh 6.2 …` restates nothing) | held |
| **support:** a line labelled with this question disagrees, at a line start or after a bullet (prose under a choice's label is interpretation); a unit labelled for another question supports nothing | held |
| **support:** a Right/Left question whose value NO reading of the text places on that side (or both) — see *Sides* below; ruling #127: the model never asserts laterality | held |
| **governing:** a Right/Left question whose PRIMARY reading is not that side — the readings compete, or the side comes only from another cited unit | held (the clinician may choose any side a reading gives) |
| `subject` unclear, a relative before it in its sentence (in a transcript's run-on sentence, the 25 words before it) or after it to its clause's end (run-on: 12 words; `family physician` is not one), `certainty` uncertain, `conflict`, a timing that does not fit the question (previous treatment: prior, its outcome also current; a clinical indication: current or prior; demographics: any; everything else: this examination), or a previous treatment written as planned (`scheduled for ablation`, `recs: EVLA`) | held |
| **governing:** a heading or pointer the installed vocabulary says changes meaning (a denial, a family history, a hypothetical) holds its block, sub-headings and a spaced list included, to a new prose paragraph; any heading with a word nobody listed fails closed the same way | held with the governing lines |
| **governing:** a SECTION heading or label (`section_holds`) holds only what its content cannot answer: a plan holds everything (a plan joined to the assessment, `Assessment and plan:`, is the assessment's); a history or prior study holds all but a previous treatment and a clinical indication; a treatment/procedure section that does not say it was before holds a previous treatment; a complaint section (`HPI:`, `CC:`, `REASON FOR EXAM:`, `S:`) holds this examination's findings; demographics are never held by a section; a structural heading (sides, limbs, this form's veins and rows, report sections) holds nothing, and one naming the question's own section does not hold that question | held with the governing lines |
| **governing:** a cited sentence's own short label (up to four words) that is unknown, a section word before a comma in it (`Prior study 2019, right GSV:`), the question's own label with a denying value unless the answer is written there with no denial right before it (`Swelling: none.`, `Leg pain: denies leg pain.`; not `Right GSV SFJ: 7.4 mm, no reflux`), longer text before a colon with the denial vocabulary or a rule-out, or a fragment under a denying label (`Denies: leg pain. Swelling.`) | held |
| **governing:** a correction that may have replaced the value without striking it: one inside its sentence, after the value, that `concerns` it (unless it is PLACED: a number corrected to a number that opens what it corrects to, with no location of its own — `6.9 correction 6.6 millimeters`, not `…correction, SFJ 7.1 mm`); one opening its sentence in the answer's own unit or paragraph that concerns it; a later one whose corrected text mentions the value; an uncited one stating a quantity of its unit; a cited correction unit that does not write the value, a correction restating the value (`6.1 mm belongs to the left leg`); for a one-sided question, a sentence saying the legs were swapped (`transposed`, `mislabeled`) or a later paragraph's correction naming only a side. `concerns`: its value or words, a side for a one-sided question, a quantity of its unit (or a bare number, or none) for a measurement, and for anything else everything except a correction stating only a measurement (`Correction: it measures 7.6 mm there.`) — a side it names never releases it. What a written correction corrects TO ends at the first clause break after its first number, or its sentence's end, and in a run-on sentence after 40 words | held |
| otherwise | supported (pre-filled; the clinician still reviews every answer) |

**Sides.** Read from the text over a whole-text index (a search cut inside a word would read `both` in `bothersome`).
Each place a value is written has a PRIMARY reading and a set of CANDIDATE readings. The pre-fill needs the primary
reading to be the question's side (or both); review accepts the clinician's answer when any candidate is (every
candidate is a side word the engine also finds). The primary reading: a side word inside the value as written; else one
bound just after it by a preposition, bracket or dash (`5.0 mm on the left`, `(left)`, `- left`, `bilaterally`) whose
phrase closes there and that nothing before it in its sentence contradicts; else the nearest side before it in its
clause, then its sentence, unless a side just after it in its clause is its own phrase's and says otherwise; else such
a side after it; else the paragraph's nearest phrase, then the nearest side heading, walking up past anatomical
sub-headings. It is `ambiguous` — no pre-fill — when a phrase names both legs (`the right and left veins measure 7.4
and 5.0 mm`, `right greater than left`, `in the right or left lower extremity`), when a bound side runs on into the next
finding (`1.8 seconds on the left the great saphenous vein measures 5.0`), when a bare side word is all there is
(`1.2 seconds right and …`), when `right` stands as an adverb (`right below the knee`, `right in the groin`,
`…, right?`), when the sentence's side differs from the side heading above it (`RIGHT LEG:` over `…; the left GSV …`),
when a weak side form is in its clause, and for a measurement read as `both` from the context or from a sentence
writing two quantities of its unit (`Both GSVs measure 7.4 mm and 5.0 mm`). A WEAK form (a bracketed letter, `(R)`;
`right` before a position with no article, `right below knee`, unless the row's own words follow) is a candidate the
clinician may choose, never a primary reading. `the right` always names the side. A side after the value introduced
as a comparison (`larger than on the left`) is no reading of it; a sentence naming a side where its reading of the
value is not written never takes the context's side instead. In a run-on sentence (over 40 words) a side after the
value is read within 8 words. Another cited unit's side BEFORE the value is a candidate only: the model's choice of
what to cite never places a pre-fill. `R`/`L` count as capitals before an anatomical word or a number, as a label, in
brackets not closing a word (`(R)`, not `ClosureFast(R)`), sided or on a vein's abbreviation; `both` only before plural
limbs or a pair each leg has one of (`both legs`, `both deep venous systems`, not `both great and small saphenous
veins`), `either` before one limb; an unforeseen form names no side.

**Parity with the engine.** The four shared patterns are read over `wm_narrative.view(text)`, which classes every
character as .NET's regex does: the four letters Python's ignore-case folds onto ASCII (`İ ı ſ K`, measured over every
code point) become that ASCII letter in both boundaries (the engine's `Reading`), and Python's other class differences
(combining marks and connectors, numerics, U+001C..U+001F) are mapped to what .NET calls them. Text answers compare with
ASCII case folded and every other character exact in both (`JOSÉ` is not `José`, `GROSS` is not `Groß`): the engine's
invariant runtime has no Unicode normalisation to agree on. With the flag off the engine's labelled path is
byte-identical to `main`'s (it splits lines on `\n` only).

No whole-note rule: an unrelated sentence, a correction elsewhere or a conditional instruction affects nothing else.

### Statements

A proposal only pre-selects the page and the resolve; the first save replaces it with the clinician's decision. It
is kept only when its variant exists, its required answers are supported, its omitted answers are empty, its cited
units are not held, and a fixed wording's sentence names its side. Identity and signature are never proposed.

What a statement may rest on at review (and at fill):

- a sentence of the notes the clinician chose: the wording's side must be named; a one-leg statement cannot rest only on
  headings and titles (`BILATERAL LOWER EXTREMITY VENOUS DUPLEX` names both legs and asserts nothing; a title is a unit
  with no finite verb, no denial and no number that names the study); and only the
  installed denial and reframing vocabulary refuses the sentence here (every other governor held the PROPOSAL, and is
  the clinician's to read);
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
(`wm_narrative.held_labels`), and review runs that same function (a `narrative_held` blocker), so review never reports
complete what finalization refuses, whatever the answer now cites. The page and save show and keep exactly what it
refuses (`wm_narrative.as_currently_held`). The first page reviews the proposed statement wordings; a typed sentence
that the notes write twice goes to a distinct occurrence, preferring the one that carries the answer.

### The engine (`WmAdapter.cs`)

`Evidence` gains an optional `kind`/`answer_keys`; the mapping records are unchanged, so every stored mapping digest
is unchanged. At fill a narrative answer must be written in its cited sentences (the parent's quantity, bound and
word patterns, byte-identical and asserted by a test, read over the same classes of character), agree with its labelled
lines, and for a sided question have a side word of that side (or both) from the start of the notes to the sentence's
end. Every engine check is implied by the parent's (never stricter), so the export never refuses what review accepted.
It is a FLOOR, not a replica of the parent: a forged fill request (one that bypasses the parent) can still pass it
with a slice of a sentence, or on a side ANY earlier side word of that side (or `both`) names — `The left leg was
examined first.` anywhere above lets a forged left answer cite a right-leg sentence. The parent validates every posted unit as a
complete sentence of the unchanged notes, so that needs a compromised parent.

## Qualification (offline — not live evidence)

- **Frozen benchmark** (`core/tests/benchmarks/wm_narrative/`), committed before the implementation: 23 cases, six
  labelled/narrative pairs, a transcript, positive findings, denials, family history, corrections, missing
  information and genuine conflicts; expectations by an independent author (`d6c661a1`), provider-shaped responses
  by a second author blind to the expectations (`17483cc1`): a careful set and a weak set with named injected errors.
  ⚠️ The validator's rules were iterated against it over five scoring rounds, so it is a development set.
- **Held-out benchmark** (`heldout-cases.json`, `3af6e471`; blind careful responses `d92cc499`): 12 cases written
  after the implementation by an author who did not read it — headed reports, raw transcripts, shorthand, a letter,
  a SOAP note. Scored on the implementation as it stood: 201 correct, **0 wrong**, **70 unnecessary holds**. After the
  first refutation round's repairs: 253 correct, 2 wrong (choices whose only option overstates the note), 18
  unnecessary holds; after the second round's: 256 correct, the same 2 wrong, 15 unnecessary holds; after the third
  round's: **254 correct, the same 2 wrong, 17 unnecessary holds** (8 are unitless shorthand, `6.8/1.9s`, held by
  design; most of the rest are pre-fill holds the clinician clears at review), 83 statement proposals correct; the same
  after the fourth round's. Round 3 closed fourteen classes of wrong pre-fill that round 2's releases had opened; the
  price is two pre-fills that now read both ways. The repairs were checked against this set, so it is now a
  development set too.
- **Refutation.** Four rounds of four sealed, write-disabled lenses over the finished diff (false green, false
  rejection, parity and integrity, corrections and sides, cost). Every demonstrated break is a regression row in
  `test_wm_narrative.RefutationRegressions` (or a review, quotation or cost test) beside a control of its class.
  Round 4 found wrong pre-fills from weak side forms, a heading against its sentence, `both` read for one value,
  corrections placed on a located number, restated or transposed findings and a planned treatment; review and
  finalization disagreeing when an answer was re-cited; and review, the page and the save still quadratic or worse.
  The mutation proofs over round 4's repairs found two more wrong releases the lenses had not: a placed correction
  restating the value (`6.1 mm, correction, 6.1 mm should read 7.6 mm` pre-filled 6.1) and a spoken correction
  opening its sentence that struck nothing (`The right sorry left …` let review accept the right).
- **Cost.** The reader answers every per-place question by bisection over positions read once per text (sides, clause
  breaks, digits, words, numbers, quantities by unit, relatives, paragraphs, lines), the backtracking patterns are
  atomic, a correction's reach, its struck spans and the governors' blocks are read once per unit or note, what a
  correction corrects to is read as a window of the whole text rather than a copy, and every cache is bounded by the
  number of texts it keeps (a cache bounded only by entries kept every note a worker had read: 879 MB after four notes;
  now a plateau near 83 MB). Adversarial shapes at the 50,000-character note limit read in under a second each
  (`ReadingCost`), and through generation's validation, review of every answer and statement and finalization's recheck
  in seconds (`ReviewCost`): before round 4, one review of a transcript with a correction in every finding took 23
  minutes at 48,000 characters, a note of 940 pointer lines took the page and the save past the worker's 120 s timeout,
  and 400 correction headings took the page 273 s. Measured after: that review 0.6 s; the page 4.6 s and the save 4.9 s
  at 940 pointer lines (37,664 characters); the page 4.5 s at 400 correction headings (46,602 characters).
- **The real workflow**: `test_wm_workflow.WMNarrativeWorkflow` (CI, real Word runtime): retained narrative response
  → generation → the page as rendered → decisions → finalization → export into the unchanged original; forged
  narrative answers refused at fill.

## Known limits (this candidate does not solve them)

Every one of these fails closed (a hold, or a statement the clinician must source) unless it says otherwise.

- **Interpretation the text does not signal.** A model that misses a negation, swaps two values within a sentence,
  invents a choice, leaves a real conflict unflagged, misses hedging or reads a plan as the past can still pre-fill a
  wrong answer where no deterministic signal exists (the weak benchmark set: 11 such answers). Every pre-filled answer
  is reviewed by the clinician; that review is the control, and live verification measures how often it is needed.
- **Which row, not only which side.** The reader verifies that a value is written in the cited sentence and on the
  question's side, not which vein or segment it belongs to (`left GSV 5.0 mm, left SSV 7.4 mm` can pre-fill 7.4 on
  the left GSV row if the model puts it there).
- **Choices whose only option overstates the note** (a recanalized vein, a popliteal-only clot: the held-out set's two
  wrong answers) — wording the clinician judges.
- **Statement polarity.** A proposal's cited sentence is checked for its side and its governors, not for saying the
  variant (a `negative` wording on a sentence stating reflux is not refused); the clinician's review is the control.
  A one-leg statement cannot rest on a sentence naming both legs and the other one (`bilateral reflux, worse on the
  left`); a normal leg has no truthful `selected` impression variant (a mapping limitation).
- **Written forms held by design:** unitless shorthand (`6.8/1.9s`), grouped digits (`1,800 ms`), numbers as words
  (`six point one` — so a voice transcript's numbers must arrive as digits; Deepgram with `smart_format=false` is
  UNVERIFIED on that), a spoken `I mean`/`sorry` that is filler (it holds the value just before it), `right` used as an
  adverb (`Right at the SPJ`), a phrase naming both legs.
- **Corrections** are read by rule: only what a correction stands right after is struck; everything else it may
  concern is held for the clinician (in a transcript's one sentence, every earlier value of its kind), and one that
  names nothing identifiable holds every answer in its paragraph.
- **Sides that read both ways** are never pre-filled (`respectively`, a bound side running into the next finding, an
  adverb `right`): the clinician chooses among the readings the text gives.
- **Text answers** compare ASCII case-insensitively and every other character exactly (`JOSÉ` ≠ `José`): the clinician
  types a name as the notes write it.
- **Engine floor**, above; a pasted control character in a typed answer (`medial\x0bthigh`) is refused at finalize.
- **A text answer over 1,000 characters** is never read as written (the form's text answers are dates, names,
  identifiers and anatomical locations; its longest option is 89 characters): the clinician shortens it.
- **The engine's labelled-line reading is `main`'s** and is unchanged: it compares the text before every colon of every
  line with each missing field's label, so a note of 24,000 colons on one line runs to the engine's time limit and is
  refused (`advanced_processor_unavailable`, fails closed). The parent's reading of the same lines is linear.

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
