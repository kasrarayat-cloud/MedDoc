# Template Twin provider authentication and authorization root audit

Date: 2026-07-19 UTC

Scope: defensive review of the additive B-017 provider-ownership worktree. No
provider egress, PHI, production mutation, push, merge, or deployment occurred.
The component implementer may not approve this work; a fresh detached review is
required after the branch is frozen.

## Defensive findings routed to implementation

| ID | Defensive invariant | State |
| --- | --- | --- |
| AUTH-01 | Revalidate current actor, visit, artifact, admission, and rollout authority atomically before provider egress, after provider return, and before returning an ambiguously committed success. | Fix in progress; focused memory suite reported green. |
| AUTH-02 | Every update that leaves a Template Twin active, including template-kind conversion or physician-owner transfer, must re-run the exact LIVE provider-compilation predicate. | Fix in progress. |
| AUTH-03 | An inactive pinned template may continue only from exact, current, durable visit provenance; a stale or unrelated successful execution is not authorization. | Fix in progress. |
| AUTH-04 | Current authority must bind the persisted visit input mode so a mid-flight mode change cannot authorize a different provider-operation plan. | Fix in progress. |
| AUTH-05 | Provider receipts and downstream gates must bind the exact execution plan, including repeated operation instances and explicit deterministic NOT_APPLICABLE decisions; missing, extra, duplicate, stale, or cross-mode executions fail closed. | Fix in progress. |
| AUTH-06 | Final source, compiled, static-asset, custom-example, and fill claims must revalidate current actor/visit/admission authority after provider receipt creation and inside the artifact transaction. | Fix requested. |
| AUTH-07 | The synthetic lifecycle must remain end-to-end testable while its receipts, certification state, and activation state remain categorically unusable for LIVE physician processing, signing, or export. | Proof/fix requested. |
| AUTH-08 | The synthetic voice route must use the exact owned synthetic-evidence boundary with immutable audio identity, one attempt, no fallback, and no server-only receipt identifiers in responses or telemetry. | Fix in progress. |
| AUTH-09 | Every final fill, review, correction, sign, and download/export claim must lock a current physician with the exact practice, `DOCTOR` role, active lifecycle, and `TRANSCRIBE_MD` product; revocation after an earlier session/read/provider check must fail closed. | Defensive P1 confirmed; fix requested. |
| AUTH-10 | LIVE Template Twin visits may not use ordinary DOCX, PDF, email, or clipboard export routes to bypass Twin review, signing, provider-receipt, rollout, and final-claim gates; ordinary non-Twin visits must remain unchanged. | Defensive P1 confirmed; fix requested. |
| AUTH-11 | The exact fill provider receipt and hash must be selected, identity-validated, and included in compare-and-swap predicates at review acknowledgement, corrections, signing, original-DOCX download, and every export path. | Defensive P1 confirmed; fix requested. |
| AUTH-12 | Downstream assessment must distinguish exact LIVE authority from exact SYNTHETIC_QA admission authority so staging remains testable while synthetic evidence remains unusable in LIVE processing/export. | Defensive P1 confirmed; fix requested. |
| AUTH-13 | Client responses, logs, audit metadata, and account-deletion summaries must not leak provider result/claim/receipt internals or raw delivery errors, and must explicitly account for retained admissions and plan-decision evidence. | P2 hardening and sentinel tests requested. |
| AUTH-14 | A durable LIVE `NOT_APPLICABLE` provider-plan decision must prove the same current global kill-switch, practice, release approval, runtime-attestation, and pinned-generation authority as a LIVE provider claim; deterministic-mock decisions cannot authorize production artifacts. | Defensive P1 confirmed; database guard and PostgreSQL negatives requested. |
| AUTH-15 | Provider-plan decisions are immutable evidence: UPDATE, DELETE, and TRUNCATE must all fail independently of runtime role grants, and each outbound delivery destination must obtain a fresh final physician claim immediately before its side effect. | Defensive P1 confirmed; fix and race/immutability tests requested. |
| AUTH-16 | Synthetic mock-voice evaluation must create and bind an authorized pre-certification VISIT child admission and persisted synthetic visit before transcription; a correlation string alone is not provider authority, and no synthetic child/receipt may cross into LIVE certification, activation, signing, or export. | Defensive P1 confirmed; owned child-admission/audio-identity implementation and direct-call negatives requested. |
| AUTH-17 | Template classification must be fixed before L1 provider egress whenever Twin eligibility is enabled. A known ordinary visit cannot upgrade to Twin at the later L4 resolution, and an unresolved preflight cannot fall through to unowned provider calls; the globally disabled path must retain legacy ordinary behavior. | Defensive P1 confirmed in mutable worker census; pre-L1 pin/fail-retry fix and activation-race tests requested. |
| AUTH-18 | A Template Twin email destination must be the physician's current persisted account email at the same linearizable final claim that authorizes delivery. A JWT/session email captured before a confirmed account-email change is not current authority and cannot receive PHI. | Defensive P1 confirmed; current-email row-lock binding and stale-session/concurrent-change tests requested while preserving ordinary non-Twin behavior. |
| AUTH-19 | The L7 automation provider ledger must inherit the active Template Twin visit ownership boundary. Its pre-egress, post-return, and committed-result reuse claims must lock the exact rollout generation and full current physician lifecycle/product/practice/visit/template authority; the ordinary automation path remains unchanged. | Defensive P1 confirmed; the separate automation lock currently checks only practice and `isActive` for LIVE visits, so suspension, soft deletion, product/role changes, or Twin rollout revocation are not exact provider fences. |
| AUTH-20 | A signed Template Twin SOAP may not enter the asynchronous edit-pattern embedding provider outside the owned provider ledger. Until an independently reviewed owned embedding workflow exists, Twin signing must skip this optional capture while ordinary visits remain unchanged. | Defensive P1 confirmed; the live Twin sign route currently fire-and-forgets `captureEditPattern`, which calls OpenAI without a Twin ownership/current-authority claim. |
| AUTH-21 | No E/M presentation, suggestion, sign, rescore, or bump-addition surface may send a LIVE Template Twin SOAP (or caller-supplied substitute text) through the direct MDM judge outside provider ownership. These optional Twin surfaces remain unavailable until they have a separate reviewed ledger; deterministic override and ordinary behavior remain unchanged. | Defensive P1 confirmed; page render, suggestion actions, sign-time code freezing, rescore, and bump additions can currently reach the direct Anthropic/Redis helper for LIVE Twin data without exact current physician, rollout, input, or result ownership. |
| AUTH-22 | Every generic clinical mutation that remains available for a LIVE Template Twin visit must obtain a fresh current-physician and rollout claim and bind the exact visit/version inside its final write transaction. A stale JWT role, removed product, practice transfer, or revoked rollout may not edit SOAP, speaker evidence, suggestions, deterministic E/M overrides, or other Twin review state. | Defensive P1 confirmed; several legacy actions use the general session helper and therefore do not establish the stricter current Template Twin physician/rollout authority before mutating a Twin visit. |
| AUTH-23 | Every Template Twin PHI read/review surface must re-establish current physician role, lifecycle, product, and exact practice ownership; a user-id match or stale JWT claim alone is not tenant authorization. Generic visit/page/status/progress reads must either prove the current Twin authority or suppress the Twin visit and its review data. | Defensive P1 confirmed; live Twin visit/page reads currently reuse generic user-id ownership in places where a role/product change or practice transfer is not re-bound to the fill/source practice. |
| AUTH-24 | Generic retention, stale-visit, trash, and watchdog workers may not reinterpret durable Template Twin rows as ordinary cleanup targets. Any Template Twin deletion or terminal transition must preserve immutable fill/provider evidence, use its reviewed lifecycle authority, and durably audit the exact result. | Defensive P1 confirmed; generic sweeps currently classify only the synthetic-run marker, allowing live or detached Twin provenance to reach legacy deletion or FAILED-state updates. |
| AUTH-25 | Bulk account/patient export and other long-running delivery flows must apply exact query-time Twin visibility before projecting clinical text or object keys, then re-establish the current physician/delivery claim immediately before each response or external side effect. A claim released before an asynchronous stream is not continuing authority. | Defensive P1 confirmed; generic archive loaders can project edit-pattern SOAP/object identities before per-visit claims and then stream after the authorizing locks have been released. |
| AUTH-26 | Every shared durable-provenance classifier must include provider-execution-only, fill-only, admission-only, detached-template, and inconsistent-lineage states. A missing current template relation must never downgrade immutable Twin evidence to the ordinary provider, mutation, read, or cleanup path. | Defensive P1 confirmed across the worker census, direct E/M boundary, mutation helper, and cleanup predicates; exact compiled/source negatives requested. |
| AUTH-27 | Every successful generic mutation of a live Template Twin must commit its PHI-free audit-outbox event in the same final authority/CAS transaction. A best-effort audit scheduled after the clinical write is not the preserved Template Twin audit contract. | Defensive P1 confirmed in lifecycle, SOAP, suggestion, E/M override, Rx-warning, and input/retry surfaces; atomic outbox coverage and rollback tests requested. |
| AUTH-28 | Generic structured-note-template lifecycle actions must never edit, activate, deactivate, delete, or expose a `template_twin_docx` version, regardless of runtime enablement. Only the certified Twin lifecycle owns those immutable versions. | Defensive P1 confirmed; the legacy bridge exclusion was conditional on runtime enablement, which converted availability into mutation authority and could route a Twin through generic lifecycle writes. |
| AUTH-29 | The reserved synthetic-QA patient identity is itself durable restricted provenance. Missing or concurrently detached run, admission, fill, template, or execution relations must never downgrade that visit to an ordinary read, mutation, cleanup, export, or provider path. | Defensive P1 confirmed in shared classifiers; additive cross-boundary fix and orphaned-identity negatives requested. |
| AUTH-30 | An operation admitted as ordinary must prove at its final read, provider-egress, and write boundary that no durable Template Twin provenance appeared in the interim. Ordinary-to-Twin races must fail closed before a side-table or clinical write and may not apply an unowned provider result. | Defensive P1 confirmed in speaker, suggestion, warning-override, input, retry, and other generic paths; final exclusion/CAS coverage and race tests requested. |
| AUTH-31 | Durable read/provider classifiers must return strict booleans and require a real non-reserved patient on the ordinary branch. SQL NULLs or a missing patient relation may not bypass a failed Twin authorization CASE through application-language truthiness. | Defensive P1 confirmed in the query-native read classifier and shared malformed-provenance census; COALESCE/ordinary-existence fix and PostgreSQL negatives requested. |
| AUTH-32 | A definite failed provider execution may advance only through a server-owned durable logical-attempt allocator. A nonterminal, successful reusable, or unknown/ambiguous execution must share or block the same attempt; concurrent duplicate requests may not manufacture parallel provider calls. | Defensive P1 exposed by the detached stateful certification test; additive idempotency/retry implementation and concurrency proof requested. |
| AUTH-33 | Every synthetic generic-read exception must prove one exact full QA run, current physician/practice/rollout authority, and the exact visit/run/attempt before any clinical field or object identity is projected. Admission-only, pre-certification, reserved-patient orphan, and direct-delivery paths fail closed. | Defensive P1 confirmed in page/API/status/audio/sign/delivery ordering; shared PHI-minimal admission and direct-delivery negatives requested. |
| AUTH-34 | The compiled-version relation is immutable durable Twin lineage even if mutable `noteTemplate.templateKind` drifts. Every read, mutation, worker, cleanup, export, lifecycle, and active/pinned-template classifier must treat a compiled relation with non-Twin kind as inconsistent Twin state, never ordinary. | Defensive P1 confirmed across shared classifiers and generic template lifecycle; additive projections, SQL exclusions, and PostgreSQL kind-drift negatives requested. |
| AUTH-35 | An ordinary PHI admission followed by an unrestricted clinical SELECT is not sufficient: the PHI-producing statement itself must conditionally exclude the complete durable Twin census. A marker or compiled relation committed between admission and the clinical SELECT must yield no PHI row, followed by the existing post-read/final fences. | Defensive P1 confirmed across detail/status/record/audio/delivery, E/M/sign, and generic mutation/lifecycle snapshots; same-statement exclusions and deterministic interleaving negatives requested. |
| AUTH-36 | Every visit-scoped provider fence, including L7 automation, must bind the current patient row to the exact practice and lifecycle. LIVE work rejects the reserved synthetic identity; synthetic work requires the complete reserved, PHI-free patient invariant rather than relying on an admission label alone. | Preliminary independent census found patient checks limited to pre-certification voice; additive L1-L7 current-authority locks and tenant/identity negatives requested. |
| AUTH-37 | Initial certification admission is not continuing provider authority. Immediately before egress, after return, and before reusing a committed result, L1-L7 must reassert the exact certified compiled/source ownership hashes, certification actor/mode/admission, and canonical live or staging provider-compilation predicate. | Preliminary independent census found the generic current-authority query omitted certification and ownership-receipt validity after initial pin; additive final-fence and revocation tests requested. |
| AUTH-38 | A process-local synthetic lease bit is only supplemental evidence. Each synthetic provider fence must bind the exact durable run ID, admission, visit, attempt, worker claim, PROCESSING status/phase, generations, and unexpired database lease immediately before egress, after return, and on committed-result reuse. | Preliminary independent census found exact run/attempt/claim/lease fields absent from provider current-authority rechecks; additive durable lease and attempt-replacement tests requested. |
| AUTH-39 | A PHI-minimal mutation or synthetic-read admission must bind the requesting actor in the same database statement that projects patient or run provenance. A prior visibility decision followed by an actor check in application code is not authority to project a foreign or concurrently reassigned record. | Root full-census review found actor ownership checked only after the mutation-admission and synthetic-run projections; same-statement actor predicates and focused regressions added, exact-head review pending. |

## Required freeze evidence

- Exact branch, commit, tree, and parent; clean worktree.
- Direct-provider-call census showing no unowned Template Twin calls.
- Same-statement actor-scoping tests for every PHI-minimal mutation and
  synthetic-read admission projection, including foreign-ID and concurrent
  ownership-change denial before provenance is returned.
- Runtime and PostgreSQL negatives for revocation before egress, after provider
  return, and after receipt creation but before artifact claim.
- Exact receipt-plan positives and omission/extra/duplicate/instance/mode/admission
  negatives.
- LIVE versus SYNTHETIC_QA certification, activation, visit, sign, and export
  separation.
- Current-physician revocation races at fill, review, correction, sign, original
  DOCX, generic DOCX/PDF/email/clipboard export, and object-delivery claims.
- Exact fill-receipt selection and compare-and-swap identity at every
  downstream gate, including stale-between-read-and-claim negatives.
- LIVE plan-decision insertion negatives for disabled/revoked/stale rollout,
  release, runtime, practice, and actor authority; row deletion and statement
  truncation immutability negatives for both evidence-ledger tables.
- Multi-destination delivery proof showing a physician revocation after one
  destination blocks every later email, clipboard, URL, or artifact side
  effect without changing ordinary non-Twin delivery behavior.
- Synthetic mock-voice proof for exact root/child admission, actor, practice,
  source, template/version, visit, input mode, logical attempt, fixture/audio
  digest, one-attempt/no-fallback execution, terminal cleanup, and categorical
  rejection of missing/mismatched or LIVE-crossed identities.
- Worker race proof for ordinary-at-preflight to Twin-at-L4, preflight failure
  to later Twin, concurrent active-template change, absent ownership context,
  and unchanged legacy behavior when Twin is definitively globally disabled.
- Dedicated and sign-and-send email proof that a stale session email cannot be
  selected after an account-email change, and that a concurrent email update is
  ordered by the same final physician row lock before any Twin email side effect.
- L7 automation races proving current Template Twin physician and rollout
  authority immediately before provider invocation, after return, and before
  committed-result reuse, with terminal no-replay handling for ambiguity.
- A sign-route provider census proving LIVE and synthetic Twin visits schedule
  no asynchronous edit-pattern embedding, with the legacy ordinary capture
  behavior covered by an unchanged-path regression.
- Route negatives proving LIVE and synthetic Twin E/M rescore and
  provider-backed bump-addition requests, page rendering, suggestion actions,
  and sign-time code freezing perform no direct model/cache call and no
  unauthorized visit mutation, while ordinary and deterministic override
  behavior remain covered by exact regressions.
- Generic-mutation races proving role/product/practice/rollout revocation
  prevents every remaining LIVE Twin SOAP, speaker-evidence, suggestion, and
  deterministic E/M override write at the final locked compare-and-swap while
  ordinary non-Twin behavior remains unchanged.
- Twin PHI-read tests proving stale role/product/practice claims cannot read a
  live or synthetic Twin through the page, generic visit API, status/progress,
  review, or related-data loaders; tenant mismatch returns the same not-found
  boundary without serializing Twin fields or provider evidence.
- Query-native list/count/cursor tests at production-scale visit cardinalities;
  a fixed lifetime-visit branch ceiling that disables normal physician lists
  is a release blocker, not an acceptable fail-closed production design.
- Generic cleanup and watchdog tests proving every durable Twin marker is
  excluded from legacy deletion/terminal paths, immutable fill/provider
  evidence cannot cascade-delete, and any dedicated lifecycle operation uses
  a current authority/CAS plus atomic audit outbox.
- Bulk export tests proving no Twin SOAP/edit-pattern/object identity is
  projected before exact visibility and that revocation during a long-running
  archive prevents every later read, response, and delivery side effect.
- Exact fill/execution compiled-version and source-artifact mismatch negatives
  for every shared provenance classifier; provider-execution-only and detached
  Twin rows must never enter an ordinary provider/mutation/read/cleanup path.
- Transactional audit tests proving a Twin clinical mutation rolls back when
  its required outbox event cannot be enqueued and never reports success with
  only a best-effort post-commit audit attempt.
- Generic note-template lifecycle tests proving runtime-enabled structured
  edit/activate/deactivate/delete/read actions still exclude every Twin row,
  while ordinary structured-template behavior is unchanged.
- Orphaned reserved-synthetic-patient tests proving the patient identity alone
  blocks generic reads, mutations, provider calls, exports, cleanup, and
  watchdog rescue even when every Twin relation marker is absent.
- Ordinary-to-Twin race tests proving every generic provider and mutation
  path rechecks the complete durable provenance census at its final side
  effect and cannot write or apply a provider result after provenance appears.
- PostgreSQL NULL/missing-relation tests proving classifier results are strict
  booleans and an incomplete ordinary patient join cannot bypass authorization.
- Provider logical-attempt tests proving a definite failure can recover once,
  concurrent duplicates share the same claim, and UNKNOWN/nonterminal results
  never trigger a second provider invocation.
- Synthetic-read admission tests proving only one exact full run reaches a
  clinical projection or original-template delivery, with admission-only,
  pre-certification, and reserved-patient orphan states denied before PHI.
- Compiled-relation drift tests proving mutable template-kind changes cannot
  reclassify durable compiled lineage through read, mutation, provider,
  lifecycle, cleanup, list, aggregate, or export boundaries.
- Admission-to-projection race tests proving every ordinary clinical SELECT
  embeds the durable ordinary exclusion and returns no PHI row when a Twin
  marker appears between the initial identifier admission and that SELECT.
- L1-L7 patient-authority races proving practice transfer, patient deletion,
  reserved-identity drift, or non-PHI-free synthetic patient state blocks the
  next provider fence before any further egress or result reuse.
- Certification-revocation races proving compiled/source ownership-hash,
  certification mode/admission, or canonical compilation-validity changes
  block pre-egress, post-return, and committed-result reuse.
- Synthetic run-replacement and lease tests proving attempt, worker claim,
  status, admission phase, heartbeat/expiry, or rollout-generation drift is
  rejected at every provider fence even while the process-local bit is true.
- Focused and full test census, TypeScript, Prisma, lint/format, migrations,
  concurrency, retry/ambiguity, and bounded secret scans.
- Independent detached exact-head ACCEPT before integration.

## Additive author checkpoint (not approval)

Downstream current-physician, review/correction, signing, delivery, bulk-export,
account-deletion census, receipt/CAS, and non-leak changes were committed as
`184592925a15c7f421bcc30783737c50ba6fbe80` (tree
`2fa5e7f537c9fb50ba85d9c7ad8e5100a084a2d8`, parent `1fa5671`). The author
reported 14 focused files / 217 tests, strict TranscribeMD TypeScript, and
focused ESLint PASS. Root independently verified the commit identity, clean
index, explicit 34-path scope, and diff check; 46 provider/worker/migration/AI
paths remained preserved and unstaged. This checkpoint is an implementation
claim only and remains subject to combined-head tests and fresh detached
exact-head review.
