# Model-assisted Word mapping — design and bounded measurement request

Status: **designed, not built, not measured.** It needs specific spending authority before any provider call.

## Why

The deterministic v3 detector met the V1 bar on neither set: development 3/40, **holdout 0/20**
(`word-holdout-first-pass-1.md`). On unseen forms it found most areas but read many of them wrong: 630 of 1171
holdout areas had a wrong kind, grouping or option count. The misses are idiomatic: printed option words to
circle, blue guidance text to overwrite, floating initials boxes, lists without blanks, author placeholders.
They are judgement calls a reader of the blank form makes easily and a rule set does not.

## Shape (proposal only; never trusted, never writing XML)

1. Input: the **blank template only**. That is the v3 outline (slot id, kind, preview text, heading context) plus the
   deterministic proposals (slot, kind, label, options). No patient data exists at this stage, and none is ever
   sent here.
2. One structured-output request to `claude-sonnet-5`, with thinking disabled and effort medium. Template text is
   labelled untrusted data. The response schema is generic: field keys, verdict enums and slot-id strings. No
   template text goes into the schema.
3. The model returns verdicts on each proposal (keep / not an answer / kind / options / label) and additions
   (slot id + kind + label + options).
4. **Deterministic validation**:
   - every slot id must exist;
   - options must appear verbatim in that slot's printed text;
   - kinds come from the fixed set;
   - signature/initials areas stay unfillable;
   - additions go through the same `locate` writers a clinician uses.

   Anything that fails validation is dropped *and listed*.
5. The result is still a **proposal the clinician reviews and confirms**. Automatic success is scored exactly as
   predeclared (`word-compatibility-target.md`) on the **qualification cohort** (20 predeclared documents,
   unopened), with the layer switched on.

## Cost (measured sizes, estimated tokens)

Measured on the 40 development forms: payload median 26.5 KB, p90 126 KB, max 344 KB. That is roughly
8.8k / 42k / 115k input tokens with Sonnet 5's denser tokenizer. Output is about 40 tokens per proposed field
plus 500. At $2/M input and $10/M output: **median $0.05, p90 $0.21, max $0.42 per form; one development pass
≈ $3.41.**

Bounded request (blank forms only, no patient data):

| step | runs | cap |
|---|---|---|
| development tuning | ≤ 4 passes over 40 dev forms | $15 |
| qualification cohort (judged once, with every attempt reported) | ≤ 3 runs over 20 forms | $6 |
| margin for retries and failures | — | $4 |
| **total** | | **$25** |

Each request carries its own hard bound (max output tokens), and the run stops at the cap.

## What it will not do

It will not fill answers, see notes, change the writers or skip clinician confirmation, and it will not count
manual corrections as automatic success.
