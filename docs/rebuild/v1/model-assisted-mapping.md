# Model-assisted Word mapping — design and bounded measurement request

Status, 2026-09-27: **implemented locally for offline verification; disabled by default; no live model
measurement or deployment.** See `mapping-assistance-recovery-20260927.md` for exact checks and retained failures.
Provider calls still require eligible spending authority and launch/account admission. This implementation does
not change any corpus result or establish Word compatibility.

## Why

The deterministic v3 detector met the V1 bar on neither set: development 3/40, **holdout 0/20**
(`word-holdout-first-pass-1.md`). On unseen forms it found most areas but read many of them wrong: 630 of 1171
holdout areas had a wrong kind, grouping or option count. The misses are idiomatic: printed option words to
circle, blue guidance text to overwrite, floating initials boxes, lists without blanks, author placeholders.
They are judgement calls a reader of the blank form makes easily and a rule set does not.

## Shape (model output remains a proposal; it never writes XML)

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

   A rejected replacement preserves the existing field. Rejected additions, proposed removals and uncertain
   areas are retained as unresolved review records. Confirmation is blocked until a clinician resolves them.
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

## Local implementation and operational gates

- `core.mapping_assistance`: source-bound request compiler and strict proposal schema; full blank-source text
  from an isolated `assistance_outline` operation. The 120-character display preview is never the source text.
  Requests above 400,000 serialized bytes, 1,200 outline slots or 200 existing fields refuse whole, without
  truncation. Output remains bounded by the recorded Sonnet profile; incomplete responses refuse adoption.
- `core.mapping_jobs`: template-version-scoped queue with no patient/encounter stand-in. The existing Job,
  Reservation, ProviderReceipt, Usage and ledger handle holds, settlement, absorption and uncertain outcomes.
  The new forward migration permits exactly one Job scope, freezes its actor/kind/source binding and prevents
  changing a referenced template's department/original identity. Reversal refuses while mapping jobs exist.
- The existing mapping review page receives a new immutable version. The assistance page lists **all**
  source-area verdicts and every unresolved area. Corrected versions carry `assisted=true`; fixture results
  carry `simulated=true`. Neither is evidence of automatic model recognition. Existing documents retain their
  mapping versions and export hashes.
- `QUILLMD_MAPPING_ASSISTANCE=0` and `QUILLMD_MAPPING_ASSISTANCE_LIVE=0` are the defaults. Offline fixture
  operation requires the first flag, fixture AI mode and the selected Sonnet 5 profile. The second flag remains
  off until account/model, spending and release qualification prerequisites are met. No provider calls were
  made during this engineering work. Do not enable either flag on the installed application as part of recovery.
- Native requests reuse Sonnet 5 profile/rates, disabled thinking, medium effort, no sampling overrides and
  no automatic transport retries. Quotes bind user, source version, request hash and configuration for ten
  minutes. The current source/profile is checked again at enqueue and before submission. Unknown outcomes
  retain their attempt and funds for reconciliation. Receipts commit before output parsing/adoption; invalid
  settled output is absorbed through the existing ledger machinery.
- The compiler records a conservative input-byte token bound, **not an exact native token count**. Actual
  tokenizer/account/model qualification is still pending. The earlier corpus sizing/cost estimates above are
  historical design estimates; they are not measured prices for this compiler, an approved allowance, or a
  new authorization to run development/acceptance requests.

### Current narrow capability limits

Proposals use the existing deterministic `locate` writers. They cannot invent a writer for a printed-option
layout, reorder XML, insert fabricated choices, execute document instructions, or turn a signature/initials
area into a generated answer. Unsupported kind/options/destination changes remain visible refusals. Signature
and consent wording stays in the preserved original. A model's semantic judgement that an area is not an
answer still requires qualification against independently established expected fields; schema validation is
not a completeness oracle. Existing corpus failures and first-pass denominators remain unchanged.

The retained synthetic workflow checks cover upload, request/review, an added missed field, clinician
correction/confirmation/finalization and original-based export, including missing and long answers. Browser
renders verify the local review surface only. Native Microsoft Word and original/export rendered acceptance,
current model access and genuine broad-template qualification remain release gates.
