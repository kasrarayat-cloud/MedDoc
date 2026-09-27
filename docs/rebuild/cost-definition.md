# Billable usage definition for private testing

QuillMD usage is metered provider usage × the configured USD unit rate captured with each usage row, less the configured provider discount fraction, followed by a ×1.5 charge. The owner-directed policy (2026-09-17) is: **the user charge is exactly 1.5 × the attributable metered provider cost after applicable discounts and allocated provider credits** — since 2026-09-18, within the binding limit shown and held before the request (see Recording charge limit). This definition excludes VPS hosting, payment fees, taxes and licenses, which are fixed overhead tracked separately (below) and never charged to users. No automatic payment or wallet refill exists. Promotional credit is personal and is consumed before the authorized paid payer. The payer is fixed when a reservation is authorized. Unused reservations release on known outcomes; uncertain provider outcomes hold for reconciliation and never retry automatically.

Text generation: returned input/output/cache token counts, priced by the configured model's published standard API rates. The live verified configuration is Anthropic claude-sonnet-4-6 at $3 input/$15 output/$0.30 cache-read per million tokens; cache writes are not requested. OpenAI adapter is implemented but its existing key returned 401. Source: https://platform.claude.com/docs/en/about-claude/pricing (verified 2026-09-17).

Voice: Deepgram nova-3-medical prerecorded audio, provider-returned seconds, $0.0043/minute public pay-as-you-go rate. Round the computed provider cost once to USD 0.0000000001 (half-even); multiply that defined cost by 1.5 exactly. This avoids rounding per-second repeating decimals. Source: https://deepgram.com/pricing (verified 2026-09-17). No optional billed add-ons requested.

Amounts retain twelve decimal places in the ledger; UI may show rounded dollars, but the ledger records exact amounts. Actual charges are never based on reservation estimates. Every simulated provider execution costs zero. Welcome credit is a unique append-only $10 grant after mailbox verification, including invitation acceptance. Stripe credits arrive only through validated, idempotent events; browser redirects do not grant funds.

Before real paid use, confirm account contract discounts and treatment of provider promotional credits against invoices, tax jurisdiction, refund policy, and accepted definition of included costs. Public list rates are verified; the account-specific provider invoices are not yet reconciled. Patient-data processing remains disabled. Stripe live mode is deliberately disabled; test keys and webhook secret are still needed.

Integration detail: the queued provider rate snapshot and user-approved maximum must remain fixed for the life of a job. Configuration changes must not silently change an already authorized job's rate. Reservation affordability and ledger writes are locked in PostgreSQL transactions; duplicate provider payment intent IDs and usage job IDs are unique.

## Configured estimate versus reconciled actual

Each usage row stores `actual_cost`, the **configured estimate**: provider-returned units × the recorded rates, less the recorded discount fraction, and `charged_cost` = 1.5 × that estimate, capped at the binding limit held for the request. The database check constraint `usage_charge_at_most_multiplier` forbids a charge above 1.5 × cost; `audit_billing` and the backup/restore invariant `usage_multiplier` require exactly min(1.5 × estimate, the settled holds), with anything above the cap recorded as one `absorbed_over_limit` platform cost. (The earlier constraint `exact_usage_multiplier` was replaced by migration 0013.) The estimate is labelled as an estimate on the billing page and in the audit report until it is reconciled to authentic provider evidence.

Discount basis: `core.generation.configuration()` carries `discount_rate`, read from `QUILLMD_PROVIDER_DISCOUNT_RATE` (default `0`; a decimal fraction in [0, 1), otherwise no billable request can run). It is part of the `price` dictionary hashed into `pricing_version`, so changing it changes the configured pricing fingerprint of every job queued afterwards. Adding the key itself changed the fingerprint of all jobs queued after this policy landed, even at the default `0`; rows queued earlier keep their recorded fingerprint and are recomputed with a discount of zero. Every live usage row records `discount_rate` and `list_cost_usd` in `rates`, so `audit_billing` recomputes the list cost and the discounted estimate independently. The attributable cost is always held to USD 0.00000000001 (eleven decimals, half-even, and never above the list cost) at any discount including zero, so that the exact 1.5× charge always fits the twelve-decimal ledger and settlement can never refuse a provider-paid job. A value of `-0` is stored as `0`. Provider credits are not a configured input: they are allocated at reconciliation time from provider evidence.

Reconciliation (`CostReconciliation`, one row per usage, append-only apart from its ledger status) records the reconciled actual cost, the allocated provider credit and discount applied (informational), a required evidence reference (invoice number, export file sha256 or report id), an optional evidence sha256, the administrator and a note. It never modifies the usage row or its original ledger entries. It computes `charge_delta` = 1.5 × (reconciled cost − configured estimate) and settles it by appended ledger entries of kind `reconciliation` (unique key `reconciliation:<usage>:<wallet>`):

- A negative delta is credited back to the wallets that were debited for that usage, in proportion to their original debits (promotional credit returns to the promotional wallet, paid funds to the paid wallet), to exact ledger precision.
- A positive delta is debited from the paid wallet of the payer recorded on the usage row. If that wallet's available balance (balance − reserved) is insufficient, nothing is debited, the reconciliation is stored with `ledger_status = pending_funds` and shown as such; `billing.apply_pending_reconciliations()` applies it once funds exist; it runs automatically when a Stripe top-up settles (`credit_payment`) and when a released reservation frees paid funds (`release`), scoped to the charges held by that wallet's payer and attributed to the paying user or to the system and locks the job before the reconciliation row, the same order as absorption, so the two cannot deadlock; each row is isolated so one failure is audited (`usage.reconciliation_apply_failed`) without blocking the payment. The unique ledger key makes application idempotent. A pending charge whose job was absorbed in the meantime is marked `absorbed` and is never applied. Reconciled costs are entered with at most eleven decimals so that the exact 1.5× delta always fits the twelve-decimal ledger; a usage already reversed by absorption records its evidence with `ledger_status = absorbed` and moves no wallet.
- A delta of zero records the evidence with no ledger entry.

`audit_billing` reports the reconciliation per usage row, checks `reconciliation_delta_arithmetic` (delta arithmetic and the applied ledger sum) and keeps `invoice_reconciled` false until such a row exists. Recording the model and the endpoints does not mean invoice reconciliation has been performed: no usage row has been reconciled to a provider invoice by this change.

## Fixed overhead and absorbed platform failures

`PlatformCost` rows carry costs QuillMD bears itself. `fixed_overhead` rows (hosting, licences, fees, recorded by an administrator with a period and evidence reference) are never part of any wallet ledger and are never charged to users. `absorbed_failure` rows (at most one per job) record the provider cost of a platform failure:

- When a job's provider cost was settled but its output was not adopted because of a platform or provider failure (validation failure, transcript unusable, file or database error — never a user-side non-adoption, see "Billing boundary"), `billing.absorb_failed_job` appends ledger entries of kind `absorbed` (key `absorbed:<job>:<wallet>`) that return exactly the user's NET charge for that job per wallet (the usage debits plus any reconciliation movement already applied), and records `PlatformCost(kind='absorbed_failure')` at the reconciled cost when authentic evidence exists, otherwise at the configured estimate. Only a `failed` job can be absorbed. The usage row and the original debits stay as evidence; the reversal is idempotent. A failed reversal is audited (`usage.absorb_failed`) and never stops the worker; `audit_billing` flags failed, settled, unabsorbed usage until the operator repairs it with the same idempotent call. Fixture (synthetic) jobs and uncertain jobs are unchanged.
- Uncertain jobs (state `reconciliation`, funds held) are resolved by an administrator through `POST /console/jobs/<id>/resolve/` with an evidence note: `release_no_cost` releases the held reservations; `absorb_platform_failure` additionally records the evidenced provider cost as an absorbed platform cost. If the worker had already settled the charge before the outcome became uncertain, the resolution reverses that settled charge through the same absorption and records the settled amount, whatever the form carried; a synthetic fixture job records no platform cost at all. Neither outcome leaves a charge on the user.

`audit_billing` checks `absorbed_reversal_matches_usage_debits` (net per-wallet reversal and platform-cost amount), `no_reconciliation_pending_after_absorption`, `reconciliation_wallets_valid` and `reconciliation_credit_split_proportional` (credits only to the wallets the usage debited, in the proportional split; additional debits only to the recorded payer's paid wallet), and a report-level `policy_ledger_entries_bound_to_jobs` (no `absorbed`/`reconciliation` entry without a job) and `failed_settled_usage_absorbed`, and reports platform-cost totals by kind. Wallet balances continue to equal the sum of all ledger entries, including the `reconciliation` and `absorbed` kinds.

## Billing boundary

Owner directive (2026-09-18): the charge follows the successful, user-requested provider request, not what happens to its output afterwards. Five rules, each mapped to code; regressions in `rebuild/core/tests/test_billing_boundary.py`.

1. **A successful, user-requested generation remains billable when the doctor later discards, edits or replaces its output.** Settlement (`billing.settle`) is independent of adoption. In `core.jobs.run_one` the adoption block first checks that the output is usable (a validated generation, a transcript string); unusable output is a platform failure under rule 2 whatever the user did meanwhile. Only usable output reaches the user-state checks, which raise `jobs.NotAdoptedByUser` when the encounter was finalized or its revision changed while the job ran, or the requesting user's membership was revoked before adoption. Such a job ends `failed` with `job.error` starting `not_adopted: `, keeps its `Usage` row and usage debits, is never absorbed (`absorb_failed_job` refuses it), and its `job.failed` audit event carries `billing = not_adopted`. Answer edits (`save_answers`) and source-note edits (`encounter_notes`) never touch usage, ledger or reservation rows. Provider output is delivered (`job_result`, and the "Download provider result" link) only for a request that stands charged: a success or a `not_adopted` decline. Output of an absorbed failure or of a job held for reconciliation is kept for audit and not delivered, so an absorbed failure can never hand over usable output for free.
2. **Every other post-settlement failure is a platform/provider failure and is absorbed.** Provider output that fails `generation.validated`, an unusable transcript, a transcript that would exceed the note limit, file or database errors: `job.error` starts `platform_failure: ` and `absorb_failed_job` reverses the user's net charge and records the platform cost exactly as before. Only QuillMD's own fixed messages (`jobs.PlatformFailure`) are shown; any other exception is named by class, so provider or validation text never reaches a job record. `job.error` is at most 250 characters. The doctor never sees the prefix: the encounter page shows the message in words, and a platform failure adds "This was a platform failure; it is not charged to you." A failed job frees its request key (`<key>:failed:<job id hex>`), so the user can retry the same revision; the retry is a new request, charged once if it succeeds. `audit_billing` splits the per-row check by that prefix: `failed_settled_usage_absorbed` (absorption required) for platform failures, administrator resolutions and older rows without a prefix; `user_declined_output_remains_charged` (absorption forbidden: a `not_adopted:` row with an `absorbed` ledger entry or platform cost is a policy violation and fails the audit). A transcription that fails before any provider request (recording missing or too large, transcription provider not connected) raises `jobs.NoProviderRequest`: in one transaction the job ends `failed` with `Not processed: …` and the held funds are released; nothing is charged. A live generation has no such separation, because the provider SDK builds and sends the request in one call: a generation that fails that way (for example a missing provider credential, an operator misconfiguration) is held for reconciliation like any uncertain outcome, and an administrator releases it with no cost. An administrator resolution also frees the request key. `audit_billing` checks that no ended job (succeeded, failed or cancelled) still holds funds. A failure after the request may have reached the provider stays `reconciliation` with funds held. When the provider completed and its receipt is durable but settlement failed (for example a cost above the held maximum), the job is labelled "Provider completed, but settlement needs administrator reconciliation; nothing is charged until it is resolved." Synthetic fixture jobs are unchanged.
3. **Explicitly requested additional generations are separately billable, with clear disclosure.** `encounter_detail` passes `prior_generations` and `prior_transcriptions` (succeeded jobs of each kind). When a generation already succeeded, or was charged but declined, and the generate form is shown again (after the notes were edited and the answers cleared), the form states: "This is an additional generation for this document. Earlier generations remain charged; this request is charged separately at provider usage × 1.5." The voice form carries the same disclosure for a new recording after a successful transcription.
4. **Cancellation is free only before any provider request.** `POST /encounters/<pk>/jobs/<job>/cancel/` (`job_cancel`, department-scoped like the other encounter views) calls `jobs.cancel`, which locks the `Job` row with `select_for_update` — the same lock `run_one` takes with `skip_locked`, so a job being picked up cannot be cancelled concurrently and a job being cancelled cannot be picked up. Only a `queued` job is cancelled: state `cancelled`, `error` = `cancelled: before any provider request`, `finished_at` set, held reservations released through `billing.release`, audit `job.cancelled`. Every other state answers HTTP 409 with a one-line reason (`running`: "Processing already started; the outcome will be billed by result."; `succeeded`, `failed`, `reconciliation` and `cancelled` likewise) and changes nothing. A cancelled job is not pending for `enqueue`, note edits, answer saves or finalization, and its `request_key` is renamed to `<key>:cancelled:<job id hex>` at cancellation (the `job_financial_immutable` trigger guards only `config` and `payer`; the longest key, a transcription's 115 characters, becomes 158 of the 160 allowed), so a fresh request for the same revision is accepted while the cancelled row keeps its history. `cancel` locks only the job row (`select_for_update(of=('self',))`); `settle` and `absorb_failed_job` do the same, so none of them can deadlock against the worker's encounter lock or against a request that holds the same wallet. The encounter page shows "Cancel queued request" only for queued jobs and only to viewers the server allows. `audit_billing` checks that cancelled jobs carry no usage, receipt, ledger entry or held funds.
5. **Duplicate processing never creates duplicate charges.** `enqueue` returns the existing job for the same encounter revision (or the same recording), so one reservation exists per request; `settle` locks the job and returns the existing `Usage` row on replay, so one usage row and one debit per wallet exist per job; the `usage_provider_request_once` and `usage_provider_resource_once` constraints refuse a second usage row for the same provider identifiers across jobs (`test_provider_dedup_refutation.py`).

Preserved unchanged: the 1.5× charge (within the approved limit, below), the $10 welcome credit, promotional-before-paid ordering and payer snapshot, the configured-estimate versus reconciled-actual distinction, and append-only accounting (no ledger, usage or receipt row is ever updated or deleted; cancellation and non-adoption move only job, reservation and wallet state).

## Recording charge limit

Owner policy (2026-09-18): the displayed maximum charge is a binding customer limit. Code: `core/audio.py`, `core/jobs.py` (`transcription_quote`, `recording_charge_limit`), `core/billing.py` (`reserve`, `settle`, `reconcile_usage`); tests `core/tests/test_recording_limit.py`.

1. **Measured before any paid request.** Every uploaded recording's duration is measured in pure Python as what a decoder would play, never from a header field a decoder ignores: WAV samples at sample rate × block size (all bytes after the data header, unless well-formed metadata chunks follow the declared data to the end of the file; an inconsistent byte-rate field is refused); MP3 frames, with trailing ID3v1/APEv2/ID3v2 tags treated as metadata (frame chains hidden inside them still count) and other non-frame bytes bounded and counted at the lowest bitrate seen; MP4/M4A AAC access units (the larger of `stts` and `stsz`, plus fragments) × their frame length at the stream's own AudioSpecificConfig rate, or an edit list's full play length if longer; WebM/Matroska unlaced Opus packet durations from each packet's table of contents (or the block timestamps, if larger). Other codecs (including Apple Lossless), laced WebM, AAC-LD/ELD, WAV files with two format chunks, MP3 tags holding more than 64 frame headers of other layouts, and malformed or truncated structures are refused. The reference for "what a decoder plays" is ffmpeg's decoded length; an adversarial harness of attack and legitimate files measures at or above it with "Nothing was sent for transcription".
2. **Quoted and held.** The recording's limit is (measured seconds × 1.02 + 2 s) × rate × (1 − discount) × 1.5, rounded **up** to a cent (a zero rate holds nothing). That exact limit is reserved before the request. Insufficient credit is refused before the request, with the amount needed; the payer's balance is never shown (an organization's paid balance is shown to its owners only).
3. **Within the displayed limit.** Notes with no room for even one more character refuse a recording before anything is sent (exact, never an estimate), and the recorder is hidden. A recording whose limit is at or below the displayed limit (`QUILLMD_VOICE_MAX_COST` × 1.5 rounded **down** to a cent, $0.30 by default, shown with the length that fits it; the amount shown is the amount enforced) is processed at once. The quote and settlement read one rate rule (`voice_rate_per_minute`: the per-minute rate when set, otherwise per-second × 60).
4. **Above it: explained first.** Nothing is sent and the upload is kept. The page shows the length, the quoted limit and whether the available balance covers it. It offers either a shorter segment (the upload is removed, even after the approval expired, and never once an approval queued it) or an explicit approval of that exact, priced higher limit. The approval is signed and bound to the doctor, the document, its version and the recording's hash, and is valid for 30 minutes; an upload nobody approved is removed by the worker 40 minutes after the quote. Recordings longer than `QUILLMD_VOICE_MAX_MINUTES` (60 by default) are refused before any request.
5. **Charged at most the limit.** The customer is charged exactly provider usage × 1.5 up to the held limit, never more. If the provider bills more than the estimate, QuillMD absorbs the difference as one `absorbed_over_limit` platform cost. The provider cost (`Usage.actual_cost`), the customer charge (`Usage.charged_cost` and the usage ledger debits) and the absorbed difference stay separate. The database now enforces `charged ≤ 1.5 × cost`, and `audit_billing` requires any shortfall to equal that platform cost exactly. A later cost reconciliation raises the customer charge only up to the limit and records the rest as `over_limit_delta`.
6. **Useful work is delivered.** A usable transcript is added to the notes. If the provider processed more than 2 seconds less audio than the measured recording, a visible "[Transcription incomplete …]" marker says which portion is missing, in the notes and in the downloaded transcript; nothing is silently truncated. A usable transcript that could not be added because the notes would exceed their limit is delivered for download from the document record and stays charged within the limit (`not_adopted:`), like any usable output the user's own state kept out of the notes: never discarded, and never free. Cancellation, platform failures, retries and duplicate prevention follow the billing boundary above.


## September 21, 2026 — evidence classification and current limits

The preserved metered-cost formula and ledger policy above are unchanged. The
reconciler now stores an explicit evidence kind: `provider_report`, `invoice`, or
`unclassified`. Existing rows acquire `unclassified` without inferring an invoice
from a reference or content hash; the finance form requires an explicit choice for
new evidence. Audit/export and customer/admin explanations distinguish
provider-reported actuals from invoice-reconciled amounts. These labels record an
administrator's reviewed attribution; they do not authenticate an external file
or establish whole-account invoice reconciliation.

A local metering receipt remains units at preserved configured rates. Its field
name `actual_cost` does not make it an authentic billed amount. The current
protected manifest contains 15 non-simulated operations totaling
$0.160260900700 configured cost and $0.240391351050 original charges. No authentic
billing export is present, no live reconciliation was applied, and the two
historical receipt gaps remain unresolved.

The installed importer is the existing MFA-protected manual per-usage entry.
There is no generic CSV/JSON/PDF importer or approved aggregate-to-job allocation
rule. Validate original evidence/provenance/currency/account/period before entry;
see [the business evidence procedure](business-readiness-20260921.md). One immutable
reconciliation per usage is supported. Re-import and a later corrected/overlapping
record both refuse without mutation; this is safe rejection, not an implemented
correction workflow. Preserve later originals and preview differences; do not
rewrite history or represent a provider-report record as an invoice upgrade.
Any future correction workflow must be reviewed and append-only. Keep the new
classification column and history during rollback.


## September 27, 2026 — Claude Sonnet 5: request profile and settlement fidelity

Everything above still holds: the exactly-1.5× charge, the binding hold,
promotional-before-paid, absorption, reconciliation and append-only records. No
historical row changes. `live-provider-verification.json` stays the
2026-09-17 claude-sonnet-4-6 record. What follows describes the code. The deployed
configuration is still whatever the owner has set. Switching it is described in
[the Sonnet 5 migration note](v1/sonnet5-migration.md).

**Rates.** From the pricing page, read 2026-09-27: Claude Sonnet 5 costs $2 input,
$2.50 5-minute cache write, $4 1-hour cache write, $0.20 cache read and $10
output per million tokens. The $2/$10 launch price "is now the standard price",
and the scheduled rise to $3/$15 "will not occur". Sonnet 4.6 stays at
$3/$15/$0.30. There is no long-context premium on Claude 4.6 and later.
Sonnet 5's tokenizer produces about 30% more tokens for the same text, so an
equivalent request costs less, but not in proportion to the rates.

**Request profile, part of the price.** `core.generation.request_profile` keys what one
generation request sends to (provider, model). For `claude-sonnet-5` it always
states `thinking` and `output_config.effort`:

- `thinking` is `{type: disabled}`, or `{type: adaptive, display: omitted}`, set by `QUILLMD_AI_THINKING` (default `disabled`).
- `effort` is `low`, `medium` or `high`, set by `QUILLMD_AI_EFFORT` (default `medium`).

It never sends sampling parameters, `budget_tokens` or a prefill. The Claude models listed
in `LEGACY_CLAUDE_MODELS` (`claude-sonnet-4-6`, `claude-haiku-4-5`, `claude-sonnet-4-5-20250929`,
each matched exactly as spelled) and every non-Claude model keep the pre-profile request
byte for byte. `claude-opus-4-1` is deliberately not on the list: Anthropic marks it
deprecated (retiring 2026-08-05) and this deployment never used it, so it is refused. The profile is
snapshotted into `Job.config` with the rates and hashed into `pricing_version`, except the
legacy profile, which hashes as absent. The rollback configuration therefore still
fingerprints as `configured-v1:fcc80267…`, and no stored fingerprint changes meaning. An
invalid choice refuses generation before any request, and the hold is released. So does a
`QUILLMD_AI_PROVIDER` that is not exactly `anthropic` or `openai` (generate() sends every other
value to OpenAI, so `Anthropic` would have sent a Claude id there), and so does
every other Claude model id, until it has its own profile. This is deny by default, not a
version comparison: a parser of `claude-<family>-<n>` let `claude-mythos-preview` through to
the old call, which on a newer model would change meaning.

**Hold.** `maximum_cost` prices the exact `max_tokens` the profile sends:

| Profile | `max_tokens` |
|---|---|
| legacy | 6000 |
| Sonnet 5, thinking disabled | 8000 (the 4.6-sized 6000 × 1.3) |
| Sonnet 5, thinking adaptive | 16000 |

`max_tokens` caps thinking and text together, and thinking is billed as output, so the output term is a true
bound. The input term is still one token per UTF-8 byte of the serialized payload plus 12000.
A byte-level token spans at least one byte, so no tokenizer yields more tokens than bytes.
That is why a tokenizer 30% larger does not move the bound. Anthropic does not document its
tokenizer, so the live check records `input_tokens` against this bound. With
`QUILLMD_AI_INFERENCE_GEO=us`, the request carries `inference_geo: us` and the bound is ×1.1,
rounded up to the settlement quantum.

**Settlement, new receipts only.** Anthropic receipts now also record the following units:

- `inference_geo`
- `thinking_tokens`, when the provider reports it. It is already inside `output_tokens` and is not priced again.
- `stop_reason`
- `stop_details_category`

When the provider meters `inference_geo: us` on a Claude 4.6+ model, the list cost is
multiplied by 1.1 across every token category, and `inference_geo_multiplier: 1.1` is written
into the recorded rates. This applies whether the request asked for it or the workspace
default is US-only. Standard-geography receipts keep exactly the rate shape they always had.
`audit_billing.recompute_list_cost` derives the same multiplier from the recorded units. A
recorded multiplier that disagrees with the metered geography fails the row. Historical
receipts carry none of the new units, so they recompute to the identical Decimal.

**Refusals.** A Sonnet 5 refusal is HTTP 200 with `stop_reason: refusal`, empty content and
token counts in `usage`. Like any stop other than `end_turn`, it is settled at the metered
tokens, never adopted, and absorbed as a platform failure. The customer is not charged.
Anthropic does not bill some refusals that arrive before any output: the documented
categories are other than `bio`, `frontier_llm` and `reasoning_extraction`. Whether that rule
covers Sonnet 5's cyber refusals is inferred, not documented. So an absorbed refusal's
recorded platform cost may overstate the invoice, and `stop_details_category` is on the
receipt for reconciliation.
