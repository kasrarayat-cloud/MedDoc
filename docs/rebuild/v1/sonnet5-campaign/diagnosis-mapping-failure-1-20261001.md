# Diagnosis: mapping failure 1 (2026-10-01)

reopen_stage: mapping
failed_attempts: 2
repair_commit: c184762552ab87d2bb910f800667b3898a471db5

**What stopped the stage.** Attempt 2 (runner `631d81af`, form `f1-guidance-confirmation`, served `claude-sonnet-5`,
`end_turn`, 4,365 input / 111 output tokens, $0.00984) returned a well-formed mapping proposal. One of its changes was
invalid; the application's validator refused the WHOLE proposal (`ValidationError`), the job ended
`platform_failure: Mapping output could not be adopted.` and the stage stopped as a contract failure before the other
nine declared sends. Nothing was adopted. No unsafe change reached a mapping.

**Repair.** The Word destination-roles work, integrated as `c1847625` (merge of `fix/v1-roles-salvage` 6cd7c1ee into
the candidate; first implementation `e555540d`, salvage `258650f2`/`8951fdec`, FV-01 `6cd7c1ee`; every round's
refutation and verification are recorded in `docs/rebuild/v1/word-destination-roles-20260930.md`):

- an envelope or integrity failure still refuses the response; an individually invalid change is HELD with its reason
  and no longer discards valid independent changes;
- a model addition is never adopted (it becomes a review item a clinician adds or dismisses); a replacement only
  relabels an automatic ordinary field with no role and keeps its place; dependent changes are held together;
  adoption is order-independent; the whole resulting mapping is re-validated with one overlap rule at proposal,
  resolve and confirm;
- permission to write any place comes from the original's structure (roles), never from the model.

Replayed offline on the repaired code, attempt 2's retained response adopts 0 and holds 2 changes; with an added
valid change the valid one is adopted (`rebuild/.runtime/v1-product-20260930/b2/mapping/impl/out`). The provider
request for attempt 2 is byte-identical on the repaired code (10,023 SDK bytes, sha256 `2c7d0e10…` equal to the
retained body), so the declared request profile and pricing are unchanged and no amendment is needed.

**What the remainder can show.** The remainder is the nine declared sends not yet made (`mapping:f2-leave-checkboxes`,
`mapping:f2b-leave-checkboxes-owner`, `mapping:f3-selection-instructions`, `mapping:f4-exam-grid`,
`mapping:f5-negative-controls`, `mapping:f6a-long-answer`, `mapping:f6b-admin-missing`,
`generation:f6a-long-answer`, `generation:f6b-admin-missing`). Attempt 2 remains a recorded stop, so the stage cannot
pass; the run measures the repaired mapping path on the live model. Model-assisted mapping stays OFF in every
installed profile; these sends run on the QA worker only.
