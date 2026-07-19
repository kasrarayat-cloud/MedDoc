# Template Twin audited rollback control

Status: **implemented for review; production rollback remains unproven and
must not be marked PASS until a disposable restore/rehearsal and independent
exact-head review accept it.** No production operation was invoked while this
control was built.

## Purpose and boundary

`/api/admin/template-twin/rollback` is the callable, database-backed boundary
for preparing and revoking Template Twin. Every handler is protected by the
existing `adminApi` gate: the account must still have `SUPER_ADMIN`, be active,
and hold an admin session younger than 12 hours. Mutations also require a
same-origin request, an RFC UUID operation id, a bounded change id/reason code,
and an exact action-specific confirmation string.

The control changes only Template Twin state:

- the singleton rollback fence and its monotonic epoch;
- active `template_twin_docx` versions (`active` to `inactive` only);
- Template Twin practice flags and their monotonic rollout generations; and
- the persisted global rollout flag/generation.

It does not update ordinary visits, ordinary structured templates, signed fill
manifests, source/candidate bytes, certifications, audit history, object-ledger
lineage, or provider results. Audit-outbox delivery and object reconciliation
remain available while the fence is active.

## State machine

| Fence      | Meaning                                                                                                                                                          | Allowed next action                                                     |
| ---------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------- | ----------------------------------------------------------------------- |
| `OPEN`     | No rollback maintenance fence. Rollout still requires the independent environment, global, and practice gates.                                                   | `prepare`                                                               |
| `PREPARED` | New Template Twin admissions and final claims fail with `TEMPLATE_TWIN_ROLLBACK_FENCE_ACTIVE`; existing failure/reconciliation paths can still remove authority. | `revoke` after blockers are zero, or `cancel_prepare` before any revoke |
| `REVOKED`  | Template Twin versions are inactive, practice rollout is disabled, global rollout is disabled, and the rollback fence is terminal for this operation.            | No reopen through this endpoint                                         |

Operation records are `PREPARED`, `REVOKED`, or `CANCELLED`. Repeating the same
request with the same operation id is idempotent and creates no second state
transition or audit event. A different operation cannot steal an engaged
fence. A revoked operation cannot be cancelled. Database triggers require each
operation to begin in `PREPARED`, permit only one transition to `REVOKED` or
`CANCELLED`, and reject identity rewrites, terminal rewrites, and deletion.

## Operator sequence

1. Confirm a verified backup/restore identifier, named incident owner,
   approved change id, and current immutable application/worker digests.
2. With a fresh `SUPER_ADMIN` session on `admin.quillmd.com`, `GET` the endpoint.
   This is the read-only dry run. Preserve the PHI-free JSON response with the
   release evidence, including all inventory counts and generations.
3. Generate one UUID outside the request log and retain it as the operation
   id. Send `prepare` with:

   ```json
   {
     "action": "prepare",
     "operationId": "00000000-0000-4000-8000-000000000000",
     "reasonCode": "RELEASE_CRITERION_FAILED",
     "changeId": "approved-change-reference",
     "confirmation": "FENCE_TEMPLATE_TWIN"
   }
   ```

4. Confirm every new admission, render/final claim, signing, and download path
   fails closed with the rollback-fence code while an ordinary reserved
   synthetic visit remains healthy. Do not use a real patient.
5. Repeatedly `GET` the endpoint while queues drain and provider ownership is
   classified. `revoke` fails with HTTP 409 while any of these remain:
   `RESOLVING_FILLS`, `PROCESSING_SYNTHETIC_RUNS`,
   `RUNNING_AUTOMATION_MANIFESTS`, `RESERVED_PROVIDER_EXECUTIONS`,
   `IN_FLIGHT_PROVIDER_EXECUTIONS`, or `UNKNOWN_PROVIDER_OUTCOMES`.
   Unknown outcomes require the provider-ownership runbook; never replay them.
6. When `readyToRevoke` is true, send:

   ```json
   {
     "action": "revoke",
     "operationId": "00000000-0000-4000-8000-000000000000",
     "confirmation": "REVOKE_TEMPLATE_TWIN"
   }
   ```

   One serializable transaction locks global, then enabled practices by id,
   then active Template Twin versions by id. It deactivates those versions,
   disables every enabled practice, disables global rollout, advances every
   affected epoch, records per-template/per-practice and aggregate PHI-free
   audit-outbox events, and verifies that the signed-manifest census did not
   change. Any mismatch or audit failure rolls the transaction back.

7. Activate the process kill switch in both app and worker deployment
   configuration, using the separately approved immutable deployment path.
   The database operation cannot and does not rewrite process environment.
8. Continue reconciliation until `rollbackComplete` is true. That status
   requires queue/provider blockers, nonterminal synthetic work, undelivered
   audit outbox entries (including failed delivery), and object-maintenance
   backlog all to be zero. `REVOKED` alone is not a claim that bridge-image
   health or production rollback succeeded.
9. Verify ordinary physician journeys, audit delivery, object reconciliation,
   and rollback-compatible app/worker health using only reserved synthetic
   identities. Record exact SHA, image digests, backup/restore id, operation
   id, before/after response hashes, and monitoring window.

## Cancelling preparation

Only an incident owner who has confirmed that revoke did not run may send:

```json
{
  "action": "cancel_prepare",
  "operationId": "00000000-0000-4000-8000-000000000000",
  "confirmation": "REOPEN_TEMPLATE_TWIN_FENCE"
}
```

Cancellation reopens only the maintenance fence. It does not enable or disable
the persisted global/practice rollout flags and does not change any template.
It is forbidden after `REVOKED`. Recovery after revoke is a new release: keep
the fence and rollout disabled until all technical/human gates pass, then use a
separately reviewed rollout-enable operation that advances fresh generations.

## Evidence and remaining gates

Each transition writes a PHI-free transactional outbox event:

- `TEMPLATE_TWIN_ROLLBACK_PREPARED`;
- `TEMPLATE_TWIN_ROLLBACK_CANCELLED`; or
- `TEMPLATE_TWIN_ROLLOUT_REVOKED` plus per-target deactivation events.

The status response contains counts and state identifiers only. It never
returns physician, patient, document, transcript, field, or provider payloads.

Before production use, independently verify the exact release head in a fresh
detached workspace and rehearse prepare, concurrent admission rejection,
in-flight blocking, provider failure reconciliation, revoke, idempotent retry,
audit delivery, object maintenance, ordinary-visit continuity, bridge-image
swap, roll-forward, and restore in a disposable data-bearing environment. The
control does not make the broader production rollback plan PASS by itself.
