# P2-002 — Specialty dropdown vocab differs between Settings and Visit-create

**Severity:** P2 (UX confusion + downstream template-mapping risk)
**Files:**
- `apps/transcribe-md/src/app/settings/...` (Profile section's `<select name="specialty">`)
- `apps/transcribe-md/src/app/visits/new/...` (step-2 specialty `<select>`)

## What

Two separate dropdowns offer different specialty sets:

| Specialty | Settings | Visit-create |
|---|:---:|:---:|
| Cardiology | ✓ (`cardiology`) | ✓ (`Cardiology`) |
| Dermatology | ✗ | ✓ |
| Internal Medicine | ✗ | ✓ |
| OB-Gyn | ✗ | ✓ |
| Pain | ✓ (`pain`) | ✗ |
| Pediatrics | ✗ | ✓ |
| Psychiatry | ✗ | ✓ |
| Pulmonology | ✓ (`pulmonology`) | ✗ |
| Ophthalmology | ✓ (`ophthalmology`) | ✗ |
| Orthopedics / Ortho | ✓ (`ortho`) | ✓ (`Orthopedics`) — different label |
| Primary Care / Primary | ✓ (`primary`) | ✓ (`Primary Care`) — different label |

11 distinct specialties across the two dropdowns; only **2 fully
overlap** (Cardiology) and **2 overlap with mismatched labels**
(Ortho/Orthopedics, Primary/Primary Care).

## Why it matters

1. **A doctor in Dermatology cannot set their default specialty.**
   Settings only offers 6 specialties; Dermatology isn't one. So
   they must pick a non-applicable default like "Unspecified" or
   "Primary".

2. **A doctor sets default = "Pain" in Settings → opens new visit →
   no "Pain" option → must pick something else (Internal
   Medicine?)**. The default-specialty UX is broken.

3. **The label inconsistency hints at two different specialty
   tables in the codebase.** Each may map to a different SOAP-
   template. A visit explicitly chosen as "Orthopedics" might use
   one template; a default specialty of "Ortho" set in Settings
   might map to a different template (or fall through to generic).

4. **AI pipeline implications**: if the visit's specialty value is
   "Pain", but the L4 SOAP-generation layer's `specialty-guidance.ts`
   only knows the Visit-create vocabulary, the specialty-aware
   prompt would default to generic — degrading SOAP quality
   silently.

## Reproduction

1. Sign in as any DOCTOR
2. Navigate to `/settings` → look at Profile → Specialty dropdown
3. Compare to `/visits/new` step-2 specialty dropdown

Or via DOM probe:
```ts
const settingsOptions = await page.evaluate(() =>
  Array.from(document.querySelectorAll('select[name="specialty"] option'))
       .map(o => ({ value: o.value, label: o.textContent.trim() }))
);
// Settings: ['', cardiology, pain, ortho, primary, pulmonology, ophthalmology] = 7 options
// Visit-create: 8 options (Cardiology, Dermatology, Internal Medicine, OB-Gyn, Orthopedics, Pediatrics, Primary Care, Psychiatry)
```

## Proposed remediation

Centralize the specialty catalog in a single source of truth, e.g.,
`packages/ai/src/specialty-catalog.ts`:

```ts
export const SPECIALTIES = [
  { value: 'cardiology',          label: 'Cardiology' },
  { value: 'dermatology',         label: 'Dermatology' },
  { value: 'family_medicine',     label: 'Family Medicine' },
  { value: 'internal_medicine',   label: 'Internal Medicine' },
  { value: 'obgyn',               label: 'OB-Gyn' },
  { value: 'ophthalmology',       label: 'Ophthalmology' },
  { value: 'orthopedics',         label: 'Orthopedics' },
  { value: 'pain_management',     label: 'Pain Management' },
  { value: 'pediatrics',          label: 'Pediatrics' },
  { value: 'psychiatry',          label: 'Psychiatry' },
  { value: 'pulmonology',         label: 'Pulmonology' },
  { value: 'urgent_care',         label: 'Urgent Care' },
] as const;
```

Both dropdowns import from this catalog. The L4 SOAP prompt's
`specialty-guidance.ts` uses the same `value` keys. Audit each
specialty has a template; for any without, default to
`family_medicine` with an inline note in the SOAP draft.

## Effort

- Catalog file: ~15 min
- Patch 2 dropdown components: ~10 min
- Audit specialty-guidance for missing entries: ~15 min
- Verify L4 prompt fallback is graceful: ~10 min
- Total: ~50 min

## Risk to fix

MEDIUM. Existing user `users.specialty` values use the OLD vocab
(`cardiology`, `pain`, `ortho`, `primary`, etc.). A migration is
needed:
```sql
UPDATE users SET specialty = 'orthopedics' WHERE specialty = 'ortho';
UPDATE users SET specialty = 'primary_care' WHERE specialty = 'primary';
UPDATE users SET specialty = 'pain_management' WHERE specialty = 'pain';
-- etc.
```

Without migration, existing doctors with `specialty = 'pain'` would
see "Unspecified" after the change.

## Status

Plan-only per audit rules. Recommend bundling with a "specialty
catalog cleanup" PR that includes the migration + dropdown patches
+ specialty-guidance audit.
