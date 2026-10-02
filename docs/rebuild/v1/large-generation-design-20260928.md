# Large Word generation: implementation contract

2026-09-28. Engineering preparation, **not deployed or provider qualified**.
Parent approved implementation after this state/locking record. No provider or
token-count request, spending allowance, corpus attempt or activation is authorized.

## Recovered identity and actual constraints

Own tree `/opt/meddoc-pro/.worktrees/v1-large-generation-design`, branch
`v1/large-generation-design`, initially dab57b0a, advanced by authorized fast-forward
to reviewed `113eb72188d6099fbbe01749c48b8bf331f18c5c` before application edits.
Lead retains the shared and release trees. Dedicated fixture DB port 55706 only.
Word's proposal is `dd0a54f4928f69dda6672ca46b0b52977cec23dd`, retained at
[large-word-generation-proposal-20260928.md](large-word-generation-proposal-20260928.md).

Actual database/worker constraints inspected at this base:

| Existing contract | Consequence |
| --- | --- |
| `Usage.job` and `ProviderReceipt.job` are OneToOne | One child Job per Messages request; never combine receipts or replace old metering. |
| Reservation unique `(job,wallet)`; wallet balance >= reserved >= 0 | All child reservations must commit in one outer transaction before sending. |
| Job `request_key` unique, max160; config/payer and scope protected by DB triggers | Child identity is permanent; no generic `ended_key` retry for a consumed child. |
| Job exactly one encounter/mapping scope | Batch children use the same encounter; no fictitious patient or mapping scope. |
| Usage, receipt, ledger, mappings append-only; finalized Encounter immutable | New immutable plan/attempt records; no rewrite of historical financial/clinical data. |
| Worker dispatches mapping specially, generation explicitly, every other kind to transcription | Explicit batch dispatch and exclusion are mandatory. |
| Single-call worker settles before adoption; unknown outcome remains reconciliation | Preserve these boundaries per child; stage without partial encounter adoption. |
| Admin resolution releases holds and frees a request key | Batch children require parent-aware resolution; never let this endpoint authorize a repeated call. |
| Upload/manual/map-assistance capacity checks100; engine cap1500; source cap1000units/50000chars | Replace only feature-enabled v3 capacity admission; keep old paths unchanged. Mapping-assistance's own200field/100change limits remain separate. |

Sources: `core/models.py`, migrations0003/0006/0008/0022/0025/0026,
`billing.reserve/settle/release/absorb_failed_job`, `jobs.enqueue/run_one/cancel/mark_stale`,
`views.generate_view/admin_resolve_job/usage_quote`, `generation.maximum_cost/validated`,
`v3_mapping`, `retention.cleanup_file`, `retention_readiness`, `audit_billing`.

## Admission and immutable plan

New `QUILLMD_V3_GENERATION_BATCHES=0` by default. Only v3 extractive generation,
native `anthropic` / exact `claude-sonnet-5`, valid existing Sonnet5 profile/rates.
No WM/legacy/PDF conversion, no fallback provider, no activation of the separate
history-context contract. Preserve and compose its snapshot when explicitly present.

At most8 serial child requests; at most100 unique requested field IDs each.
No physical answer, option group or structural row is divided to fit. A group
over100, over8 groups-after-packing, unknown group identity, duplicate field key or
unbounded request refuses intact. Protected/signing/manual-only fields remain in
the full catalogue and are never requested. Limits are declared, never truncation.

Build source units ONCE using the entire generated-field catalogue and all context
labels. Every request carries identical complete notes, exact unit IDs/offsets,
full field catalogue, original context/review requirements and global rules. Its
`requested_field_ids` is the sole subset; full catalogues are never replaced by
child-local catalogues. Closed response schema plus exact subset comparison rejects
missing/duplicate/foreign keys and unknown/repeated unit IDs. Merge raw selections
before the existing whole-form validators, option conversion and review contracts.

Compile every request before reservation: exact model/profile, transformed native
schema, prompt and all payload bytes. The plan binds encounter/revision, source SHA,
original Word SHA, immutable mapping/version/digest, full field and unit catalogues,
row groups, structured constraints/coverage, child IDs and hashes, request/profile/
pricing versions, geography, all bounds and summed maximum customer charge. The
signed quote also binds this plan digest and a one-use admission UUID. Repeated POST
returns that admission, never more children. One active batch per encounter.

Input/output bounds use the actual compiled request and existing conservative
byte/token framing allowance, cold-input rate, profile output cap (thinking included),
applicable geography, and the existing1.5 retail multiplier. No provider token-count
call. Account context capacity and actual tokenizer/latency remain live qualification;
there is no claim that a locally compiled request proves endpoint support.

## Global rules are a separate necessary gate

The current importer emits **no structured cross-field rule metadata** (Word author
confirmed this for cf481504). D28's max3 diagnoses across76 rows/four tables and unique
priorities are original-map facts, not implemented validation. An empty dict is not
evidence of independent fields. Add nullable immutable
`TemplateVersion.generation_constraints`; old rows remain unknown.

The closed contract binds original/mapping hashes, full instruction references and
coverage disposition, and explicit cross-field rules. Unknown/incomplete coverage
refuses batch admission. Initial deterministic rule vocabulary can check maximum
active answer groups and uniqueness of stated priority values, with exact field IDs,
explicit active values and source references; never infer a diagnosis from any
nonempty cell. Unsupported conditions, applicability or source relationships remain
unresolved. The same constraint reader is required on aggregate adoption and later
save/finalize/export, including manually edited answers. The importer/mapping path
must produce qualified general coverage before a real form is admitted; this slice
does not invent that coverage or certify D28. A manually prepared manifest is assisted
evidence and cannot count as automatic template recognition.

## New records, migration0027

* `GenerationBatch`: immutable identity/plan/digest/approved total; mutable state and
  timestamps only as projections of append-only events. Unique admission UUID and
  partial uniqueness for active encounter. Same department/user/encounter scope.
* `GenerationBatchPart`: immutable parent, ordinal1..8, OneToOne existing child Job,
  requested IDs/request hash/individual bound. Unique parent+ordinal. Child kind
  `generation_part`; fixed config binds parent/part/plan. DB scope/identity guards.
* `GenerationBatchEvent`: append-only transition evidence with idempotency key.
  A unique send-intent per part is the consumed attempt. No UPDATE/DELETE/TRUNCATE.
* `GenerationBatchResponse`: immutable part/result private path/hash, actual model,
  stop reason and response identity; complete SDK body stays in the existing private
  per-child result file. `ProviderReceipt`/`Usage` remain financial authority.

Use private exclusive-create result files, fsync and hash verification. Persist known
financial evidence before clinical parsing/file-adoption work as the current worker
does. Missing raw-result persistence is a failed/reconciliation outcome, never an
excuse to repeat a completed request. Do not duplicate clinical SDK bodies into DB.
Register all new records/references with retention inventory and preservation guards;
unknown ownership or an active reference blocks cleanup. No new purge permission.

## State, locking and failures

Admission: lock Encounter, check membership/current revision/no clinician decisions/
no pending operation/source validity; create immutable parent and all children; lock
child Jobs then wallets in stable order; reserve **every** child in one outer atomic
transaction. Any insufficient funds/config/plan failure rolls back all records/holds.
Workers can only see the committed admitted plan. Hold sum equals approved sum.

Parent projections: `queued -> running -> validating -> succeeded`, or
`reconciliation/failed/cancelled/not_adopted`. Child projections: `queued -> running
-> staged -> succeeded`, or `reconciliation/failed/cancelled`. `staged` is never a
downloadable/clinically adopted success. Immutable events preserve every transition.

One worker iteration performs at most one request, within the existing120s request /
150s service-stop window. Parent lock serializes child claims. Before send, verify
plan/config/permission/source/holds and compile the SDK request; then commit a unique
send-intent under the parent/child locks, call once with SDK retries0 outside locks.
No existing send-intent may be sent again. A crash after intent, even before a socket
was actually opened, is uncertain. Stale running children move the parent to
reconciliation, halt remaining sends and keep uncertain holds. Unsent children may
be cancelled/released only with durable absence of send-intent and a locked state
transition that prevents the old worker from acquiring permission to send.

Receipt and raw result are staged per child; settle at the frozen rates and limits.
Successful earlier children do not write `Encounter.answers`. Known cost but unusable
response stops the batch: mark settled children as platform failures and use existing
idempotent compensating refunds/absorbed costs; original receipts remain. If usable
complete output is declined only because the user's source/permission/decisions changed,
preserve existing not-adopted billing policy. Cancellation after sending never claims
no provider request/cost. A child above its bound is handled by existing capped charge
and platform absorption; do not borrow another child's unused hold.

Before whole adoption, verify exact union coverage, no duplicate IDs, all receipts/
hashes/model/stop reasons, full source/catalogue and every global rule. Reuse complete
source governance, repeated-label/side/row/correction/consent guards. Then lock Encounter
before parent, recheck revision/source/mapping/clinician decisions/authorization, and
write the complete answer/review map exactly once with an adoption event. Financial
transactions lock parent -> child -> reservations -> wallets and never acquire an
Encounter lock afterwards; adoption takes Encounter -> parent without wallet work.
Generic cancel/reconcile routes identify child membership before locking and dispatch
to that ordering. No parallel parent worker may send or adopt twice.

Local recovery may settle/revalidate already recorded responses without network use.
Unknown outcomes require authentic reconciliation and explicit operator action. First
version has no automatic retry or replacement-child endpoint; a new request needs a
new quote/admission and cannot silently reuse a consumed attempt. Pending financial
reconciliation remains visible even if all definitely unsent children were released.

## Concrete change list and finite verification

New planner/wire/constraint module and batch-worker module; model/migration0027;
small explicit dispatch hooks in jobs; shared pending-operation query for generation,
notes/review/code writers and finalization; signed aggregate quote and generation route;
parent-aware cancellation/admin reconciliation/deliverable rules; capacity admission;
private references/preservation/readiness/billing audit additions. Reuse the current
review/charge UI patterns and follow refero-design before any UI implementation.
No direct Word engine edit or unrelated function rewrite is planned.

Mocked isolated tests only, preserving all first failures:

1.99/100 unchanged and101 admitted as bounded parts; stable IDs/full-catalogue payloads;
 801 or >100 indivisible group refused. Synthetic two/six-part partition fixtures.
2.Closed subset/union and cross-boundary duplicate label/side/correction/consent/numbered
 slots; global max/unique rules; unknown coverage refused. Missing signing/manual fields
 remain present. No model semantic correctness claimed by mocks.
3.Atomic insufficient-funds rollback; duplicate admission; two workers; no second send
 after intent; interrupted middle call; first staged result cannot alter answers.
4.Receipt/file failure, known settlement failure, unknown request, mode/profile/revision
 changes, cancellation, operator reconciliation, complete-response offline recovery;
 per-child ledger arithmetic and aggregate ceiling remain exact.
5.Authenticated synthetic >100 field request -> mocked workers -> existing review/save
 -> finalization -> Word download, with only complete aggregate adoption. Retain blank/
 missing and source-governed held answers honestly; no corpus compatibility count.
6.Affected single-call and accounting checks; finished independent clinical and financial
 REFUTE before integration. Feature stays off; endpoint/account proof and broad V1
 compatibility remain separate release gates.

## Existing-interface reference lock

Refero-design applied before the small status change. No Refero MCP tools are
available here; read its bundled copywriting and form/focus guidance. Primary
reference is `encounter_input.html`'s latest-operation notice; secondary references
are `encounter_detail.html`'s Document record and `voice_limit.html`'s disclosed
maximum charge. Preserve current type, colors, layout, notice roles and cancellation
button. No new visual system or extra mapping step. The doctor sees one complete-form
operation and the existing aggregate charge; only an adopted whole form can say the
draft is ready. Unknown outcomes direct the user to reconciliation, never blind retry.
Administrative child receipts remain individually inspectable. These decisions follow
the user's one usable workflow requirement and the skill's clear next-step/error rules.
