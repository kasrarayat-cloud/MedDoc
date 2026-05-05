---
id: A10-P3-001
severity: P3
domain: UX — copy / terminology
title: Inconsistent "encounter" vs "visit" terminology in user-facing copy and metadata cards
---

## Issue

The product has settled on "visit" as its primary noun (URL is `/visits/[id]`, the dashboard tab is "All visits", buttons say "+ New visit", the empty state on the dashboard says "Start your first visit"). The user-facing copy is otherwise consistent.

However, **eight user-facing surfaces** still expose "encounter" as a noun, drawn from medical-billing terminology (encounter is what RCM/EHR systems call the same thing). Mixed terminology forces the user to map the same concept twice and feels unfinished.

## Evidence

User-facing strings using "encounter" (drawn from grep across `apps/transcribe-md/src/app/` and `src/components/`):

1. `apps/transcribe-md/src/app/visits/page.tsx:176` — empty state body: `body="Capture your first encounter — live recording, audio upload, or text."` This is the empty state on `/visits` which a brand-new user lands on after signup. **Highest priority** because every empty-state landing is "encounter".

2. `apps/transcribe-md/src/app/visits/new/page.tsx:115` — page subtitle: `'Pick the patient, then choose how you want to capture the encounter.'` First-time-create flow, second-most-visible.

3. `apps/transcribe-md/src/app/visits/[id]/extras/VisitMetaCard.tsx:69` — sub-heading: `sub={\`Encounter · ${data.encounterId}\`}`.

4. `apps/transcribe-md/src/app/visits/[id]/extras/VisitMetaCard.tsx:94` — Kv label: `<Kv label="Encounter ID" value={data.encounterId} mono />`.

5. `apps/transcribe-md/src/app/visits/[id]/transcript-tab.tsx:305` — meta row: `<MetaRow label="Encounter" value={encounterId} mono />`.

6. `apps/transcribe-md/src/app/visits/[id]/visit-ready-view.tsx:330` — fallback label: `props.specialtyLabel ?? props.inputMode ?? 'Encounter'`.

7. `apps/transcribe-md/src/components/ui/auth-shell.tsx:306` — auth shell trust strip: "SOAP, ICD-10, and CPT pulled from the encounter audio." Visible on `/login`, `/signup`, `/forgot-password`, `/reset-password`, `/check-email`.

8. Property names on `VisitMetaCard.tsx`: `encounterId: string` (the ID is the same as visit ID in this product — see `visit-ready-view.tsx:336` `encounterId: props.visitId` — there's no separate billing ID yet).

## Risk

- Onboarding clarity: a brand-new user sees "Start your first visit" on the dashboard, clicks `/visits` (or `/visits/new`), and the next surface says "Capture your first encounter." Cognitive friction — "is encounter different from visit?"
- Trust / polish: enterprise users will note the inconsistency and assume one of the surfaces is leaked from internals.
- The auth-shell strip is visible to *every* unauthenticated visitor — so the marketing → signup → first-experience pipeline includes a noun shift the user has to translate.

## Recommended fix

Pick "visit" as the canonical noun for user-facing strings. "Encounter" is fine as an internal billing concept once the product surfaces a billing-export surface (it doesn't yet — `encounterId` is just `visitId` truncated). Renames:

1. `apps/transcribe-md/src/app/visits/page.tsx:176`: `"Capture your first visit — live recording, audio upload, or text."`

2. `apps/transcribe-md/src/app/visits/new/page.tsx:115`: `"Pick the patient, then choose how you want to capture this visit."`

3. `apps/transcribe-md/src/app/visits/[id]/extras/VisitMetaCard.tsx:69`: `sub={\`Visit · ${data.encounterId}\`}` (the ID itself can keep its prop name since it's an internal label).

4. Same file, line 94: `<Kv label="Visit ID" ...>`.

5. `apps/transcribe-md/src/app/visits/[id]/transcript-tab.tsx:305`: `<MetaRow label="Visit" value={encounterId} mono />`.

6. `apps/transcribe-md/src/app/visits/[id]/visit-ready-view.tsx:330`: change fallback label to `'Visit'`.

7. `apps/transcribe-md/src/components/ui/auth-shell.tsx:306`: `"SOAP, ICD-10, and CPT pulled from the visit audio."`

Internal type/prop names (`encounterId`, `EncounterMeta` etc.) can stay — they're invisible to the user and changing them is a refactor cost without UX benefit.

Estimated effort: 7 string edits across 6 files. ~10 minutes.
