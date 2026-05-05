---
id: A06-P2-012
title: SPECIALTY_GUIDANCE has dead keys (`internal-medicine`, `ob-gyn`, `obstetrics-gynecology`)
severity: P2
domain: AI safety / specialty-template hygiene
files:
  - apps/transcribe-md/src/worker/prompts/specialty-guidance.ts (lines 38-43, 64-74)
  - packages/shared/src/specialties.ts (canonical catalog, 9 entries)
---

## Issue

The `SPECIALTY_GUIDANCE` map in
`apps/transcribe-md/src/worker/prompts/specialty-guidance.ts`
contains keys for specialties that **do not exist in the canonical
catalog** in `packages/shared/src/specialties.ts`:

- `'internal-medicine'` — has a guidance entry; not in `SPECIALTY_IDS`.
- `'ob-gyn'` — has a guidance entry; not in `SPECIALTY_IDS`.
- `'obstetrics-gynecology'` — has a guidance entry; not in `SPECIALTY_IDS`.

These three keys are dead code paths. The Zod input validator at the
API edge rejects unknown ids:

```ts
// specialty-catalog.test.ts:78-82
expect(() => Schema.parse('internal-medicine')).toThrow();
```

So the `SPECIALTY_GUIDANCE['internal-medicine']` entry can never
fire. Three risks:

1. **Misleading guidance** — a developer reading
   `specialty-guidance.ts` would conclude that internal-medicine
   and ob-gyn are first-class specialties with curated prompts.
   Both legacy ids map to `'unspecified'` (`specialties.ts:69-70,78`)
   which has `templateId: 'generic'` → no specialty guidance.

2. **OB-Gyn specifically is unsupported in production** despite
   having a substantive guidance string about LMP, gravida/para,
   prenatal visits, and Pap/HPV screening. Any visit a doctor
   intends to handle as obstetric is silently routed to the
   generic SOAP path with NO obstetric-specific guidance.

3. **Internal Medicine is conflated with Primary Care.** The
   legacy mapping is `'Internal Medicine' → 'primary-care'`. The
   IM-specific guidance ("comprehensive ROS", "chronic disease
   management with quantified A1c examples") is never used; the
   visit gets the generic primary-care guidance instead.

## Evidence

```ts
// packages/shared/src/specialties.ts:22-32
export const SPECIALTIES = [
  { id: 'unspecified',     ...},
  { id: 'primary-care',    ...},
  { id: 'cardiology',      ...},
  { id: 'psychiatry',      ...},
  { id: 'pediatrics',      ...},
  { id: 'dermatology',     ...},
  { id: 'orthopedics',     ...},
  { id: 'urgent-care',     ...},
  { id: 'pain-management', ...},
] as const;
```

Only 8 active specialties (excluding `unspecified`).

```ts
// apps/transcribe-md/src/worker/prompts/specialty-guidance.ts
SPECIALTY_GUIDANCE: Record<string, string> = {
  cardiology: ...
  psychiatry: ...
  pediatrics: ...
  'internal-medicine': ...      // DEAD
  'primary-care': ...
  dermatology: ...
  orthopedics: ...
  'ob-gyn': ...                 // DEAD
  'obstetrics-gynecology': ...  // DEAD
  'urgent-care': ...
  'pain-management': ...
};
```

`specialty-catalog.test.ts:53-66` only validates that every
catalog templateId has a guidance entry — not the reverse.

## Risk

P2 because:

- No clinical harm — patients seeing IM doctors get the same SOAP
  quality as before, but the maintainer documentation suggests
  IM-specific guidance is in effect when it isn't.
- A doctor selecting "Primary Care" who is in fact an internist
  may expect richer ROS / chronic-disease formatting and not get
  it.
- Marketing claims of "supports internal medicine" or "supports
  OB-Gyn" would be inaccurate.

## Recommended Fix (plan only)

1. Either:
   - **Add `internal-medicine` and `obstetrics-gynecology` to the
     canonical catalog** (`SPECIALTIES` in `specialties.ts`), the
     Zod validator (`SPECIALTY_IDS`), the visit-create form, and
     the marketing page H2 ("Eight specialty templates" → "Ten").
     This activates the existing guidance without prompt rewrites.

   - **OR remove the three dead keys** from
     `SPECIALTY_GUIDANCE` to align the file with what's actually
     used. The IM and OB-Gyn paragraphs are valuable prose — move
     them to a future-work doc, not dead code.

2. Bidirectional test: add a check in
   `specialty-catalog.test.ts` that every key in
   `SPECIALTY_GUIDANCE` corresponds to a row in `SPECIALTIES`.
   Currently the test only checks the forward direction.

3. Decision must be made before pilot: enable the two specialties
   or document that they're not yet supported.
