# R3.0 — legacy-island census

Routes walked: 9. Matcher positive-controlled (class arm + colour arm).
Rows: 113 total, 25 UNHOSTED (islands), 88 inside `.qm-rounds-host` (already bridged).

| surface | class / colour | family | tag | sample |
|---|---|---|---|---|
| `/visits` | `qm-lin-btn-primary` | qm-lin-* | a | New visit |
| `/visits` | `qm-lin-btn-primary` | legacy sage --color-linear-sage | a | New visit |
| `/visits` | `qm-lin-btn-primary` | legacy sage --color-linear-sage (composite) | a | New visit |
| `/visits` | `qm-lin-pill` | qm-lin-* | a | All |
| `/visits` | `qm-lin-pill--sage` | qm-lin-* | a | All |
| `/visits` | `qm-lin-pill` | legacy sage --color-linear-sage (composite) | a | All |
| `/visits/new` | `qm-c3-nv-top` | qm-c3-* | div | New visitCancel |
| `/visits/new` | `qm-c3-nv-eyebrow` | qm-c3-* | span | New visit |
| `/visits/new` | `qm-lin-btn` | qm-lin-* | a | Cancel |
| `/visits/new` | `qm-c3-nv` | qm-c3-* | div | New visitStart a visitPick the patient — |
| `/visits/new` | `qm-c3-nv-card` | qm-c3-* | div | New visitStart a visitPick the patient — |
| `/visits/new` | `qm-c3-nv-card` | legacy surface-1 | div | New visitStart a visitPick the patient — |
| `/visits/new` | `qm-c3-nv-kicker` | qm-c3-* | span | New visit |
| `/visits/new` | `qm-c3-nv-h` | qm-c3-* | h1 | Start a visit |
| `/visits/new` | `qm-c3-nv-p` | qm-c3-* | p | Pick the patient — then you're one tap f |
| `/visits/new` | `qm-c3-nv-picker` | qm-c3-* | div | Who's this visit for?Search patientsCrea |
| `/visits/new` | `block` | legacy surface-1 | input |  |
| `/visits/rdoc_msd0uonwcen000000000` | `qm-c3-rev2-root` | qm-c3-* | div | ✓Captured✓Transcribed✓Drafted✓CheckedRea |
| `/visits/rdoc_msd0uonwcen000000000` | `qm-lin-btn` | qm-lin-* | button | Delete |
| `/visits/rdoc_msd0uonwcen000000000` | `qm-vdoc-format-on` | legacy sage --color-linear-sage | button | PDF |
| `/visits/rdoc_msd0uonwcen000000000` | `qm-vdoc-format-on` | legacy sage --color-linear-sage (composite) | button | PDF |
| `/visits/rdoc_msd0uonwcen000000000/record` | `qm-c3-rev2-root` | qm-c3-* | div | ✓Captured✓Transcribed✓Drafted✓CheckedRea |
| `/visits/rdoc_msd0uonwcen000000000/record` | `qm-lin-btn` | qm-lin-* | button | Delete |
| `/visits/rdoc_msd0uonwcen000000000/record` | `qm-vdoc-format-on` | legacy sage --color-linear-sage | button | PDF |
| `/visits/rdoc_msd0uonwcen000000000/record` | `qm-vdoc-format-on` | legacy sage --color-linear-sage (composite) | button | PDF |

## Per-surface island class count (unhosted)

- `/visits` — 3 distinct legacy classes
- `/visits/new` — 10 distinct legacy classes
- `/visits/rdoc_msd0uonwcen000000000` — 3 distinct legacy classes
- `/visits/rdoc_msd0uonwcen000000000/record` — 3 distinct legacy classes

## ARM 2 — source sweep (states the DOM walk cannot reach)

A DOM walk sees only rendered states. These components APPLY a legacy class
family in source; some are flag-OFF-only and are not islands. Over-reports by
design — for an inventory that is the right direction to be wrong in.

- `src/app/admin/_components/AdminOverview.client.tsx`
- `src/app/admin/hipaa/_components/AdminHipaa.client.tsx`
- `src/app/admin/threats/_components/AdminThreats.client.tsx`
- `src/app/admin/threats/_components/DismissModal.client.tsx`
- `src/app/admin/threats/_components/InvestigateDrawer.client.tsx`
- `src/app/admin/threats/_components/ResolveModal.client.tsx`
- `src/app/admin/usage/_components/AdminUsage.client.tsx`
- `src/app/admin/users/_components/AdminUsers.client.tsx`
- `src/app/admin/users/_components/ConfirmationModal.client.tsx`
- `src/app/check-email/check-email-resend.tsx`
- `src/app/dashboard/loading.tsx`
- `src/app/dashboard/page.tsx`
- `src/app/forgot-password/forgot-password-form.tsx`
- `src/app/layout.tsx`
- `src/app/login/login-form.tsx`
- `src/app/patients/[id]/delete-patient-dialog.tsx`
- `src/app/patients/[id]/edit-patient-dialog.tsx`
- `src/app/patients/[id]/page.tsx`
- `src/app/patients/[id]/problem-list-dialog.tsx`
- `src/app/patients/[id]/trashed-visit-card.tsx`
- `src/app/patients/page.tsx`
- `src/app/patients/patients-list-c3.tsx`
- `src/app/reset-password/reset-password-form.tsx`
- `src/app/settings/change-email-dialog.tsx`
- `src/app/settings/change-password-form.tsx`
- `src/app/settings/delete-account-dialog.tsx`
- `src/app/settings/loading.tsx`
- `src/app/settings/note-format/native-template-manager.tsx`
- `src/app/settings/note-format/template-review-editor.tsx`
- `src/app/settings/page.tsx`
- `src/app/settings/profile-form.tsx`
- `src/app/settings/security/mfa/mfa-enrollment-panel.tsx`
- `src/app/settings/security/mfa/mfa-management-panel.tsx`
- `src/app/settings/session-panel.tsx`
- `src/app/settings/settings-sections-c3.tsx`
- `src/app/signup/signup-form.tsx`
- `src/app/visits/[id]/back-link.tsx`
- `src/app/visits/[id]/billing-card-c3.tsx`
- `src/app/visits/[id]/code-evidence-popover.tsx`
- `src/app/visits/[id]/codes-tab.tsx`
- `src/app/visits/[id]/copy-section-button.tsx`
- `src/app/visits/[id]/edit-draft-dialog.tsx`
- `src/app/visits/[id]/extras-tab.tsx`
- `src/app/visits/[id]/extras/AllergiesCard.tsx`
- `src/app/visits/[id]/extras/AuditLogCard.tsx`
- `src/app/visits/[id]/extras/DemographicsCard.tsx`
- `src/app/visits/[id]/extras/ExtrasCard.tsx`
- `src/app/visits/[id]/extras/MedicationsCard.tsx`
- `src/app/visits/[id]/extras/ProblemsCard.tsx`
- `src/app/visits/[id]/extras/VisitMetaCard.tsx`
- `src/app/visits/[id]/extras/VitalsCard.tsx`
- `src/app/visits/[id]/not-found.tsx`
- `src/app/visits/[id]/page.tsx`
- `src/app/visits/[id]/processing-typewriter.tsx`
- `src/app/visits/[id]/record/recording-client-c3.tsx`
- `src/app/visits/[id]/record/recording-client.tsx`
- `src/app/visits/[id]/review-sign-bar.tsx`
- `src/app/visits/[id]/review-tabs-v2.tsx`
- `src/app/visits/[id]/rx-tab.tsx`
- `src/app/visits/[id]/rx-warnings-rail.tsx`
- `src/app/visits/[id]/sign-and-send-modal.tsx`
- `src/app/visits/[id]/signed-document-view.tsx`
- `src/app/visits/[id]/soap-editor.tsx`
- `src/app/visits/[id]/soap/SoapBody.tsx`
- `src/app/visits/[id]/soap/SoapInlineEdit.tsx`
- `src/app/visits/[id]/soap/SoapSection.tsx`
- `src/app/visits/[id]/transcript-tab.tsx`
- `src/app/visits/[id]/visit-failed-view.tsx`
- `src/app/visits/[id]/visit-lifecycle-actions.tsx`
- `src/app/visits/[id]/visit-ready-view.tsx`
- `src/app/visits/new/duplicate-modal.tsx`
- `src/app/visits/new/new-visit-client-c3.tsx`
- `src/app/visits/new/new-visit-client.tsx`
- `src/app/visits/new/page.tsx`
- `src/app/visits/new/patient-picker.tsx`
- `src/app/visits/new/visit-form-step2.tsx`
- `src/app/visits/page.tsx`
- `src/components/audio-uploader.tsx`
- `src/components/dashboard/dashboard-c3.tsx`
- `src/components/dashboard/dashboard-inbox-c3.tsx`
- `src/components/dashboard/drafts-ready.tsx`
- `src/components/dashboard/patient-card.tsx`
- `src/components/dashboard/patient-list.tsx`
- `src/components/dashboard/visit-list.tsx`
- `src/components/page-wrapper.tsx`
- `src/components/placeholder-advisory-dialog.tsx`
- `src/components/rate-limit-notice.tsx`
- `src/components/recording/live-orb.tsx`
- `src/components/rounds/patients-roster.tsx`
- `src/components/rx/override-confirm-modal.tsx`
- `src/components/specular-button.tsx`
- `src/components/text-composer.tsx`
- `src/components/ui/app-frame.tsx`
- `src/components/ui/auth-shell.tsx`
- `src/components/ui/icon-rail.tsx`
- `src/components/ui/mobile-nav-c3.tsx`
- `src/components/ui/page-header.tsx`
- `src/components/ui/sidebar-c3.tsx`
- `src/components/ui/top-nav-c3.tsx`
- `src/components/ui/top-nav.tsx`
- `src/components/visit-card.tsx`
- `src/components/visits/BumpCtaButton.tsx`
- `src/components/visits/BumpModal.tsx`
- `src/components/visits/CodingRail.tsx`
- `src/components/visits/CodingRailSkeleton.tsx`
- `src/components/visits/EmCheckList.tsx`
- `src/components/visits/EmCriterion.tsx`
- `src/components/visits/EmTimeTracker.tsx`
- `src/components/voice-dictator.tsx`

## STATED BOUNDARY

- Walked: 9 states on the flag-ON QA image, single filesystem.
- NOT walked (needs a live pipeline run), named rather than reported clean:
  the "Writing the note…" processing card, and the post-creation error/retry
  surface. Both are transient states of a real creation.
- The prescription-safety rail IS walked — `seedReviewDocVisit` writes
  `rxDrafts`, so it renders on the ordinary fixture. An earlier draft of this
  boundary claimed it needed MOCK_RX_WARNINGS and was wrong.
- The class/colour arms CANNOT see "correct tokens, wrong anatomy". `/patients`
  reports zero legacy classes and is still a redesign target (R3.1) — the
  owner's verdict was "a redesign, not a recolor", which no class matcher
  detects. A clean row here is not a claim that a surface is finished.