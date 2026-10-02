# Preservation administration — reference lock

Designing preservation controls for verified QuillMD administrators on the existing web console.
Goal: register exact scope and authority; inspect active/released state; record a second custodian's release.
Risk: broad or mistaken scope, accidental release, or implying data was deleted. Direct build in the existing design system.

Refero skill applied before UI implementation. No live Refero tools are available. Primary references read:
`rebuild/templates/admin_clinic_invitations.html` (one form, bounded history, explicit status/actions),
`admin_services.html` (configuration versus observed state), and bundled `craft-details.md` (labels, focus, paste, field semantics).

| Decision | Source | Role and reason |
|---|---|---|
| Existing base, page-heading, section, table-wrap and buttons | Current invitation screen | Preserve console typography, density, focus and colors; no new CSS or visual language |
| Active vs Released, without a green readiness claim | Services screen and user release gates | A release is not destruction or legal approval |
| Explicit scope, record ID, authority fingerprint, confirmation | Owner preservation requirements | Avoid copying PHI into instruction/audit metadata; require exact target |
| Separate release form and distinct custodian | Preservation safety contract | Deliberate reviewed action, no inline one-click removal |
| Server-rendered errors, retained input, CSRF, native details | Existing forms and craft guidance | Keyboard usable, no modal/JS dependency; long fingerprints can be inspected on demand |

No imagery or new tokens are appropriate for this operational form. Validation must exercise actual MFA/CSRF and rendered page, not merely API presence.
