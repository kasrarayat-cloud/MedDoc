# Template Twin rollback compatibility v2

## Supported rollback boundary

After `note_templates.lineageId` is contracted `NOT NULL`, the pre-stack app
and worker are not schema-compatible rollback targets. In particular, generic
template creates in code before the final lineage protocol do not provide the
required lineage, and those images do not carry the final automation,
provider-ownership, queue, or audit contracts.

The only supported application rollback is a reviewed image built from current
final-schema-compatible code and started with:

```text
TEMPLATE_TWIN_RUNTIME_MODE=rollback-compat-v2
TEMPLATE_TWIN_KILL_SWITCH=true
QUILLMD_REQUIRED_RUNTIME_PROTOCOL_EPOCH=template-twin-final-schema-v2
```

This is not a database bypass or a down migration. Bridge mode leaves the
final schema and immutable evidence in place. It hard-disables Template Twin
admission, onboarding, server-side list/resolution, lifecycle mutations,
provider/fill work, review/signing, and original-DOCX download. Generic visits
and structured templates continue through the current v2 automation manifest,
provider-ownership, queue, signing, and audit protocols. Audit-outbox delivery,
object-ledger reconciliation, and other worker maintenance remain available;
purge still requires its independent approval.

The exact pre-stack production image IDs below are explicitly rejected by the
deployment guard and also lack the required OCI epoch label:

```text
app    sha256:95f57158e3fe56acc832793be3f5da972cc1fdc6c3b85166f8387b3a103f1f90
worker sha256:412dd3157475fd60a77d417a6db6880343d58755aaf76f044be035fba4acf44e
```

Do not use either image after Template Twin migrations. A retained archive of
them is disaster evidence for the pre-migration database only, not a
post-contract application rollback.

## Required pause, drain, and revoke sequence

All checks are fail-closed. Do not swap a process while any item is unknown.
The existing physician deactivation action itself requires a currently valid
rollout token. It therefore cannot be used after either the process kill switch
or persisted rollout revocation. Before an incident, Operations must name and
rehearse an audited maintenance fence that prevents new Template Twin
admissions while still permitting the specifically authorized deactivation and
revocation sequence below. If that control is unavailable, stop: the bridge
preconditions have not been met. Direct SQL is not an acceptable substitute.

1. Engage that rehearsed maintenance fence. Keep ordinary visits available
   only if the fence has been proven to isolate Template Twin admission.
2. While the current rollout tokens are still valid, deactivate every active
   Template Twin version through its reviewed lifecycle. Do not let a generic
   lifecycle action mutate a Twin row.
3. Activate the process kill switch in both target app and worker
   configurations.
4. Revoke every practice rollout and then the persisted global rollout through
   the controlled audited operation.
5. Drain both the visit and maintenance workers' active queues. Resolve every
   Twin provider execution in `RESERVED`, `IN_FLIGHT`, or `UNKNOWN_OUTCOME`;
   never guess or replay an ambiguous outcome. Classify every Twin visit in a
   processing status and every synthetic run in `PENDING_ENQUEUE`, `ENQUEUED`,
   `RETRY_ENQUEUED`, or `PROCESSING`; the bridge intentionally will not mutate
   those lifecycle rows.
6. Confirm lineage phase `CONTRACTED`, zero enabled practices, zero active Twin
   versions, zero nonterminal Twin visits/runs, and zero unsettled Twin provider
   executions.
7. Verify an app/worker image pair from one accepted exact SHA. Each image must
   carry:

   - `com.quillmd.runtime-protocol-epoch=template-twin-final-schema-v2`;
   - its exact component label; and
   - `org.opencontainers.image.revision=<accepted exact SHA>`.

8. Run the checked deployment guard from the immutable release directory.
   Both image arguments must be a local `sha256:<image-id>` or a repository
   reference pinned with `@sha256:<manifest-digest>`; tags are rejected:

   ```bash
   scripts/template-twin-runtime-swap.sh \
     --app-image '<immutable-app-ref>' \
     --worker-image '<immutable-worker-ref>' \
     --release-sha '<accepted-40-hex-sha>'
   ```

   This first invocation is read-only. Preserve its safe output in the release
   evidence. Then repeat the exact command with `--execute`. The executable
   path rechecks image identity immediately before the swap, stops the drained
   worker, recreates only app/worker with bridge mode and the kill switch, and
   verifies the running container image IDs and health.

Raw `docker compose up`, a mutable `latest` tag, and rebuilding an old Git SHA
are prohibited for this post-contract rollback. The script is a verifiable
deployment guard for the documented path; it is not claimed to be a
host/cluster admission allowlist. Privileged operators can bypass repository
scripts, so production change control must restrict direct Docker authority and
retain the command/evidence record.

## Verification and rollback of the bridge

Require all of the following before returning ordinary traffic:

- `/api/health` reports `runtime_protocol_epoch` as
  `template-twin-final-schema-v2` and `runtime_mode` as
  `rollback-compat-v2`;
- app and worker image IDs equal those accepted by the guard;
- Template Twin upload, list, certification, selection, processing, review,
  signing, and original-DOCX download fail closed using only reserved
  synthetic identities;
- a reserved synthetic generic text visit reaches ready/signing through the
  current automation manifest/provider ledger and audit path;
- generic template create/edit/activate works without reading or changing a
  `template_twin_docx` row; and
- outbox delivery and object reconciliation continue, with purge state
  unchanged.

If the bridge itself is unhealthy, keep every Template Twin rollout control
revoked. Replace it only with another independently accepted image carrying the
same final-schema epoch (standard-disabled or bridge mode). Do not fall back to
a pre-stack image. If no compatible image is healthy, stop the affected app or
worker and execute the separately approved database restore/incident plan; do
not improvise schema drops or lineage trigger recreation.

Exiting bridge mode requires a new accepted image pair, exact-head review,
healthy generic smoke tests, and the normal Template Twin human and rollout
gates. Merely setting `TEMPLATE_TWIN_RUNTIME_MODE=standard` is not production
authorization.
