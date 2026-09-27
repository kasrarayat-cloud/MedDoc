# Model-assisted Word mapping — design and bounded measurement request

Status, 2026-09-27: **implemented locally for offline verification; disabled by default; no live model
generation measurement or deployment.** See `mapping-assistance-recovery-20260927.md` for exact checks and retained failures.
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
   labelled untrusted data. The v2 response schema uses grouped request-bound numeric IDs and source-span integer arrays. No
   template text goes into the schema. The server expands those IDs back into stable original locations and wording.
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

## Historical cost estimate — superseded for new mapping requests

The following original estimate is retained as history, **not a current quote**. Native token counts showed
that even a minimal old envelope could exceed the 8,000-token output limit. The mapping-only v2 envelope,
20,000-token reservation and measured compact sizing are recorded in
[`mapping-capacity-20260927.md`](mapping-capacity-20260927.md). Input-byte counts are not token counts.


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

## Compact capacity contract, 2026-09-27

`blank-mapping-v2` retains all source strings and stable locations in the request and review. Wire IDs are
array positions bound to that exact request. Every field and slot appears once in disjoint verdict groups.
Up to 100 combined replacements/additions and 400 printed-option spans are admitted (at most 100 options
per change); source spans use Unicode code points. A reference belongs to its target context; original
field labels cannot migrate to foreign destinations. All expanded proposals still pass the deterministic
writer, overlap, signature and counterpart checks. Exhaustion stays visibly incomplete and blocks
unassisted confirmation; the full source-area review remains available.

The mapping-only profile is 20,000 output tokens, 120 seconds, disabled thinking and medium effort. Its
hash is bound into the request/quote and immutable job config. Global generation profiles and historical
receipts are unchanged. Old queued mapping contracts refuse before the new compiler, release as unsent
and require a fresh quote. Both mapping flags remain off by default. One specifically authorized free
count call measured 8,659 native **input** tokens for the conservative compact output-text envelope; it is
not native generation or clinical qualification evidence. See the capacity report for exact hashes,
focused checks, preserved earlier counts and narrow limits.


After local integration567ada8a,42 mapping/wire/actual-SDK-schema/WM-profile checks passed49.145s using isolated synthetic DB55707. This includes the shared native-schema repaird798ea7e. Independent root wire validation passed34 cases; source-bound proposal quality and live Sonnet5 behavior remain unverified. Evidence `integration-evidence-20260927/mapping-schema-union.txt`.
