# Disposition preparation — implementation lock

Policy-independent review_only patient/encounter scope within an exact department. No purge, effective tombstone or usable restore admission. Restore preparations stay quarantined.

Schema: immutable DispositionRequest, DispositionPlan, distinct DispositionReview, RestorePreparation. Migration0028 depends0026; later batch merge0029 is separately required. All schema additions protected from UPDATE/DELETE/TRUNCATE and included in catalogue/integrity.

UI reference lock (Refero skill): preservation_holds owns compact server-rendered sections, labels, action hierarchy, native details and bounded history; admin_clinic_invitations contributes submitted-form errors/idempotent return; admin_services contributes explicit configured/observed distinction. Existing base typography/colors/focus/borders only; no new CSS/media/visual campaign. Bundled craft-details forms/paste/focus guidance reviewed. Clear status “Review only — deletion unavailable”; primary action “Record review proposal”, second custodian “Record proposal review”. No success badge implying deletion authority.

Graph: bounded explicit model/edge catalogue; unknown schema refuses. Patient/encounter roots, source/mapping, jobs and immutable finance/hold/archive/shared file references; no filesystem reads/deletes. New batch model presence refuses pending explicit forward-port, and all jobs are inspected regardless terminal parents. Snapshot review rechecks exact graph; it never grants execution.

Restore: environment-selected quarantine guards web/direct download, worker and cleanup. Health/auth and this verified admin preparation surface remain. Target must match selected restore UUID/database/state root; all reports keep journal freshness/replay/admission unavailable. No external authenticity claims.

## Recovery continuation — 2026-09-28

The original draft above is preserved. The isolated integrated recovery at base9f2bdad0 now supplies the explicit batch graph forward-port and additive merge0029. Its bounded design, demonstrated defects and validation are recorded in `../disposition-integration-20260928/`. This continuation is still review-only: it implements neither deletion nor restored-target admission.
