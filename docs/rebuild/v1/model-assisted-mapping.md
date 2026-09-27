# Model-assisted Word mapping — design and bounded measurement request

Status: **designed, not built, not measured.** Offline implementation and synthetic verification are authorized
engineering work. Only provider calls require eligible spending authority. Lack of funding does not prevent
the parser, proposal validation, review path or accounting preparation from being implemented.

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
5. The result is still a **proposal the clinician reviews and confirms**. Unmodified confirmation may count;
   corrective manual mapping is assisted completion and does not. Automatic success requires the full app
   workflow and export evidence under `word-compatibility-target.md`, not only a plausible response.
   Freeze candidate, source/schema/model/profile and first-pass harness before opening an unseen cohort.
   The original corpus's 44-lineage provenance gap remains separately visible.

## Cost (measured sizes, estimated tokens)

Measured on the 40 development forms: payload median 26.5 KB, p90 126 KB, max 344 KB. That is roughly
8.8k / 42k / 115k input tokens with Sonnet 5's denser tokenizer. Output is about 40 tokens per proposed field
plus 500. At $2/M input and $10/M output: **median $0.05, p90 $0.21, max $0.42 per form; one development pass
≈ $3.41.**

These sizing estimates are not token counts or authority. Free native token counting can size exact requests
once the request compiler exists. The $25 proposal below is an **unapproved ceiling**, not permission to start
or a claim that the layer will meet the gate.

| step | runs | cap |
|---|---|---|
| development tuning | ≤ 4 passes over 40 dev forms | $15 |
| qualification cohort (one frozen first pass; every failure/refusal retained) | **one run over 20 forms** | $6 |
| declared transport-failure reserve (no automatic retries or tuning on this cohort) | reconciled case by case | $4 |
| **total** | | **$25** |

Each request needs a hard bound and attempt record before sending. Unknown outcomes stop that case for
reconciliation. Caps include failed/absorbed charges. A qualification failure that informs a repair consumes
its unseen status: preserve the entire cohort and first results, then predeclare a new independent cohort
of at least 20 before qualifying that repaired candidate. No cap authorizes a new campaign.

## What it will not do

It will not fill answers, see notes, change the writers or skip clinician confirmation, and it will not count
manual corrections as automatic success.
