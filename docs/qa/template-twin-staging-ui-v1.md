# Template Twin synthetic staging UI v1

## Purpose

This workflow proves the authenticated QuillMD browser integration with
synthetic data and disposable QA infrastructure. It is not a production,
clinical, privacy, operations, or Microsoft Word approval.

The workflow uses the existing Template Twin compiler, certification, visit
queue, worker, provider abstraction, artifact store, renderer, independent
readback, review, signing, audit outbox, and download route. It does not have a
frontend-only result path.

## Fail-closed runtime boundary

All of the following must be true before the staging entry or staging APIs are
available:

- `TEMPLATE_TWIN_STAGING_QA_ENABLED=true`;
- `TEMPLATE_TWIN_STAGING_QA_ENVIRONMENT` is exactly `qa`, `test`, or
  `synthetic`;
- `TEMPLATE_TWIN_STAGING_QA_RESOURCE_ATTESTATION` is exactly
  `isolated-disposable-qa-v1`;
- the PostgreSQL database name contains a bounded QA/test/synthetic marker;
- Redis is a local or QA-named service using a dedicated logical database from
  1 through 15 (the committed stack uses 15);
- the audio and Template Twin buckets have bounded QA/test/synthetic names,
  are distinct, and use a local MinIO endpoint or TLS for a QA-named remote
  endpoint;
- the Template Twin storage profile is the isolated QA profile;
- the deterministic QA provider fixture is explicitly enabled;
- `TEMPLATE_TWIN_KILL_SWITCH=false`;
- the persisted global rollout control is enabled;
- the practice flag is enabled; and
- the authenticated user is a current, active physician in that practice.

The committed QA Compose baseline keeps
`TEMPLATE_TWIN_KILL_SWITCH=true` for both APP and WORKER and exposes no
environment override. A future E2E enablement path must first admit distinct
short-lived APP and WORKER attestations in a guarded disposable release
manifest through the production release-control contract. A staging flag or
direct rollout-row update is not sufficient.

Missing or unknown configuration denies access. QA images use an optimized
`NODE_ENV=production` build, so `NODE_ENV` is not treated as an environment
attestation.

`isolated-disposable-qa-v1` is the only accepted resource-attestation string.
It is necessary but insufficient: changing the string alone cannot admit the
workflow. The runtime also verifies the bounded QA/test/synthetic database
identity, local or QA Redis host with logical database 1 through 15, distinct
QA/test/synthetic audio and artifact buckets, isolated storage profile,
locality or TLS of the storage endpoint, deterministic provider fixture, and
the exact source fixture digest and size. There is no production-resource
exception and no substring/fallback attestation.

A committed root admission precedes upload inspection and every lifecycle
provider callback. Each visit then receives a separate committed child
admission before evidence privacy processing. The child and staging-run rows
pin the exact doctor, practice, visit, immutable template version, source,
certification/mapping, fixture version, idempotency digest, provider mode, and
rollout generations. The queue contains only identifiers. The worker validates
both rows and enters a request-local mocked-provider context; it never switches
process environment variables for one job. A disable/re-enable changes
generations and permanently invalidates the old admission.

### Synthetic-only process fence

When `TEMPLATE_TWIN_STAGING_QA_ENABLED=true` is explicitly requested for a
process, that process must not expose the generic Template Twin DOCX upload,
generic lifecycle mutations, generic worker admission, or generic static-asset
review and approval workflow. Only the exact allowlisted synthetic fixture may
compile, and only a job matching its tenant-scoped durable staging run may enter
the worker. A rejected staging request must never fall through to a generic
Template Twin route, worker, asset, or provider path.

Leaving the staging-QA flag absent preserves the existing generic production
behavior; it does not turn production into the staging profile or disable the
ordinary production authorization and safety gates.

## Database lock order and linearization

Every state-changing staging transaction takes the rows it needs in this
single order:

1. global rollout control;
2. owning practice;
3. durable synthetic-QA admission;
4. durable synthetic-QA run;
5. current actor/user;
6. visit; and
7. fill manifest or final output claim, when applicable.

This is `global -> practice -> admission -> run -> actor -> visit -> fill/output`.
Operations may omit rows that do not apply, but they must not acquire a later
applicable row and then an earlier one. The actor lock repeats the tenant,
active-account, and DOCTOR-role check at the commit boundary.
Worker attempt claim, retry, correction, READY publication, signing, and
download authorization compare the immutable attempt and rollout generations
under this ordering. A rollout disable takes the same global-then-practice
prefix. Whichever transaction commits first defines the result; work admitted
under an older generation cannot publish READY, claim an output, sign, or
authorize download after disable commits. Bytes written before a rejected
claim remain unclaimed for durable reconciliation.

## Synthetic fixtures

Only the versioned fixture served by QuillMD's authenticated staging route is
accepted while the staging profile is active. Its DOCX and WAV bytes are built
deterministically in code. They contain only visibly labelled synthetic
content. The browser never uploads the WM IOV source or its media.

Typed evidence is bounded and runs through the existing pre-persistence
synthetic-evidence privacy gate. Mocked voice stores a deterministic synthetic
WAV in the isolated audio bucket, then traverses the normal dictation and
provider boundaries. Both modes converge on the same encounter-fact,
resolution, rendering, verification, and signing pipeline.

## QA operator sequence

1. Build the app, worker, and migrator images from the exact branch SHA.
2. Start only `docker-compose.qa.yml` PostgreSQL, Redis, and MinIO services.
3. Apply migrations to `meddoc_qa_test` and complete the existing online
   NoteTemplate lineage contract.
4. Provision the disposable audio and Template Twin artifact buckets through
   the committed QA initializer.
5. Start the app and worker with the explicit staging variables above and only
   deterministic mock provider credentials.
6. Use a new `@synthetic.test` physician account and enable only that disposable
   practice through the guarded QA helper.
7. Complete the browser journey and retain only synthetic screenshots, hashes,
   and validation evidence.
8. Tear down the QA Compose project with its disposable volumes.

No step may point to a production database, Redis, bucket, provider, or
credential. The database-name guard and staging gate are independent checks,
not documentation-only conventions.

Deployment is not authorized by this runbook alone. It remains blocked until a
fresh independent exact-head audit accepts the remediation, the environment has
network-enforced provider egress denial, access is private and authenticated
with public registration disabled, and isolated synthetic ADMIN and DOCTOR
accounts have been provisioned through an approved non-production procedure.

## Browser journey

1. Open **Settings → My Note Format → Template Twin — Synthetic QA**.
2. Download the approved synthetic fixture and upload those exact bytes.
3. Review package, OOXML, privacy, media, and structural inspection results.
4. Confirm every synthetic field's intent. No clinical answer is preselected.
5. Run the field-level synthetic certification cases and inspect facts and
   evidence anchors.
6. Certify the exact immutable synthetic version.
7. Start either a typed synthetic encounter or the deterministic mocked-voice
   encounter.
8. Wait for the real worker, review every field, resolve blockers, and confirm
   the document review.
9. Sign through the existing server gate.
10. Download **Original Template DOCX** and inspect it manually in desktop
    Microsoft Word.

The UI must continue to show `Microsoft Word compatibility: PENDING`. A package
check, independent readback, Open XML validation, or LibreOffice result cannot
change that status.

## Retry and rollback

The browser supplies a random idempotency token; only its tenant/doctor-scoped
SHA-256 is stored. Repeating an uncertain request with the same payload returns
the same run. Reusing the token with another template, version, mode, fixture,
or evidence digest is rejected. Queue/storage retries and review regeneration
receive a monotonically increasing attempt and a stable BullMQ job ID. A
provider-owned admission that reaches terminal `FAILED` cannot be revived; the
physician must start a new synthetic run.

The feature can be rolled back by disabling the staging environment gate or
either existing rollout gate. Existing rows remain inert. No migration rollback
or object deletion is required to stop admission. Objects from rejected final
claims stay on the existing reconciliation path.

## Additive migration and expected locks

The initial staging migration and
`20260717170000_template_twin_durable_staging_admission_v1` are bounded
transactions with `SET LOCAL lock_timeout = '2s'` and
`statement_timeout = '30s'`. The durable migration creates an empty admission
table and adds one nullable relation to the existing default-off staging-run
table; it does not scan, backfill, or rewrite a clinical table or auto-admit an
existing template. See
`docs/runbooks/template-twin-durable-staging-admission.md` for exact locks and
recovery.

An incompatible concurrent DDL or long transaction must therefore produce a
timeout and roll back the entire migration, never a partial “complete” state.
Operators should pause the release, identify the blocking transaction through
the normal non-PHI database-lock dashboard, let that transaction finish or
schedule a quieter window, and retry the unchanged migration. Do not raise or
remove the committed timeouts ad hoc. Rollback of the product surface is to
leave the default-off staging and rollout gates disabled; the additive table,
enum values, functions, and triggers remain inert. Destructive down-migration
is neither required nor authorized on production.

## Separate QA-tool issue

The Windows CMD/Word COM launcher hang reported by prior QA remains a known,
separate human-gate tooling defect. It was not diagnosed, reproduced as fixed,
or changed in this browser slice. The website does not invoke or depend on the
launcher, and a launcher hang must be recorded as `BLOCKED`, never converted
to a Microsoft Word pass. Desktop Microsoft Word observation and returned
evidence remain a release blocker.
