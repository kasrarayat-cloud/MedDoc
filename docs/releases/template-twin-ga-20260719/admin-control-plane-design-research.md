# Template Twin administration control-plane design lock

Date: 2026-07-19 UTC  
Status: REFERENCE LOCKED — implementation and independent review pending

## Brief

Designing a production rollout and approval workbench for QuillMD platform
operators on the web. The operator's goal is to prove the exact release is
eligible, inspect a checkpoint's health evidence, and either advance or revoke
without confusing a pending human gate for a technical pass. The tone is
precise, compact, and clinical. The main risk is treating release enablement as
an ordinary feature toggle. The memorable rule is: **the release is a chain of
evidence, not a toggle**.

Constraints: preserve the existing QuillMD admin system, dedicated admin host,
fail-closed authorization, exact-SHA/image/backup evidence, no self-approval,
canary → 10% → 25% → 50% → 100%, 44 px touch targets, keyboard operation,
explicit abort criteria, and no PHI in operational metrics.

## References reviewed

- Primary visual reference: the existing QuillMD admin surface in
  `apps/transcribe-md/src/app/admin`. It establishes the dark Linear-style
  canvas, Inter/mono hierarchy, thin dividers, compact density, sage active
  state, and semantic warning/danger roles.
- [LaunchDarkly progressive rollouts](https://launchdarkly.com/docs/home/releases/progressive-rollouts):
  percentage stages are explicit, context bucketing is stable only when the
  targeting unit is stable, and stopping/restarting can change the exposed
  population. QuillMD therefore needs immutable practice assignment and a
  visible stage record, not a transient slider.
- [LaunchDarkly approvals](https://launchdarkly.com/docs/home/releases/approvals/):
  pending changes stay visible beside the affected control and are applied
  only after review. QuillMD will show approval evidence inline with the
  release it binds, never in a detached generic checklist.
- [GitHub deployment environments](https://docs.github.com/en/actions/reference/workflows-and-actions/deployments-and-environments):
  protected environments can require reviewers, prohibit self-review, and
  withhold authority until gates pass. QuillMD will separate evidence authors,
  human approvers, and the operator who advances a checkpoint.
- [Microsoft safe deployment practices](https://learn.microsoft.com/en-us/azure/well-architected/operational-excellence/safe-deployments):
  every progressive-exposure phase needs a health model and failures should
  halt the release and initiate recovery. QuillMD will make the kill switch
  persistent and visually dominant whenever a guardrail fails.
- [Google Cloud canary strategy](https://docs.cloud.google.com/deploy/docs/deployment-strategies/canary):
  named percentage phases, per-phase verification, and a distinct stable phase
  support an ordered checkpoint rail with immutable metric snapshots.

Refero live tools were not configured. The bundled Refero typography, color,
icons, craft, and anti-AI-slop references were used with the repository's
existing admin implementation as the visual source of truth.

## Reference lock

Primary direction: existing QuillMD admin workbench.

Preserve:

- near-black canvas and layered neutral surfaces already defined by
  `linear-*` tokens;
- compact Inter UI type with mono, tracked labels for hashes, generations,
  timestamps, and percentages;
- 1440 px working width, table/rail density, thin borders, and restrained
  radius;
- sage only for confirmed healthy/active state, amber only for pending or
  degraded state, and red only for failed/aborted/destructive state;
- Lucide outline icons and visible text labels; icons never carry status alone.

Borrow only:

- LaunchDarkly's visible pending-change context beside the affected rollout;
- GitHub's explicit reviewer identity and no-self-review language;
- Google Cloud's named, ordered stage model and per-stage verification status.

Reject:

- a free-form percentage slider;
- generic KPI-card grids, gradients, decorative status stripes, or a new accent;
- a green page-level state while any required gate is pending;
- unlabeled icon buttons, color-only meaning, hidden failure criteria, or an
  action named merely “Continue”;
- automatic stage advancement in the first GA release. Metrics may trigger an
  automatic revoke, but a human operator must deliberately advance each stage.

## Product pattern and journey

The page is one workbench with three vertically ordered regions:

1. **Release identity** — exact commit, immutable image digests, backup/restore
   identifiers, migration state, global generation, and current kill-switch
   state. A mismatch makes the whole workbench ineligible.
2. **Gate ledger** — Word, Clinical Safety, Privacy/Legal, Operations, and
   independent exact-head review. Each row shows PASS, FAIL, or HUMAN PENDING,
   approver identity, decision time, and evidence hash. No aggregate green badge
   is shown unless every required row passes for the same release identity.
3. **Checkpoint rail** — Disabled, Canary, 10%, 25%, 50%, and 100%. One stage is
   current; future stages remain locked. Each completed stage owns an immutable
   metric snapshot, bake interval, decision, operator, and audit receipt.

Advance flow:

1. Operator opens a locked checkpoint and reviews the exact diff from the
   previous checkpoint.
2. The system recomputes identity and approval eligibility server-side.
3. Operator reviews PHI-free metric values and explicit abort thresholds.
4. Operator types the checkpoint label and confirms **Advance to 25%** (or the
   applicable stage).
5. The server serializes the change with rollout generations, emits the audit
   outbox event, and returns the new generation. Stale pages fail and refresh.

Abort flow is available at every stage, requires a reason, revokes globally
before any practice mutation can enter, and shows rollback verification as a
separate terminal step. A guardrail breach invokes the same server-side revoke
path automatically; the UI reports the observed metric and receipt rather than
simulating a client-side toggle.

## Decision ledger

| Decision | Source | Role preserved | Reason |
| --- | --- | --- | --- |
| Existing dark, compact admin language | QuillMD admin | Canvas/type/density | Avoids a second design system in a safety-critical workbench. |
| Ordered fixed checkpoint rail | Google canary + user mandate | Journey structure | Prevents arbitrary percentage mutation and makes skipped stages impossible. |
| Immutable metrics on each checkpoint | Microsoft health model | Gate evidence | A later dashboard value cannot rewrite the decision basis. |
| Approval rows beside release identity | LaunchDarkly approvals | Pending-change context | Makes stale or cross-release approval visibly ineligible. |
| Initiator cannot approve | GitHub environments + user mandate | Reviewer role | Preserves independent human authorization. |
| Sage/amber/red remain semantic | QuillMD tokens + Refero color | Status only | Prevents false green and color-role drift. |
| 44 px labeled controls and visible focus | Refero craft/icons | Interaction | Supports touch and keyboard without enlarging the visual glyphs. |
| Manual advance, automatic revoke | User mandate + Microsoft SDP | Authority boundary | Automation may reduce harm, never fabricate release approval. |

