// ============================================================================
// GATE — RC-3: a template-bound visit that got the GENERIC layout says so
// (ruling #106(c), SPEC §4.3a(d)).
// ----------------------------------------------------------------------------
// ⚠️ BOTH DIRECTIONS ARE ASSERTED, AND THE SILENT ONE IS THE HARDER HALF. A
// detector that flags everything satisfies every "it warns" test and is worse
// than no detector: a clinician who sees the banner on every visit stops
// reading it, and the visit where their form really did fail looks like all the
// others. So the null cases are enumerated as carefully as the positives.
//
// ⚠️ WHAT THIS FILE DOES NOT COVER, NAMED RATHER THAN IMPLIED: the WIRING in
// `worker.ts`. Nothing in this repository unit-tests `worker.ts` — no test
// imports it — so the wiring is proved by ATTEMPT on QA (a visit bound to a
// template that resolves away shows the banner; one that resolves shows
// nothing), not here. This file proves the decision.
// ============================================================================
import { describe, expect, it } from 'vitest';

import { detectTemplateFallback } from '../detect-template-fallback';
import { SYSTEM_DEFAULT_TEMPLATE_ID } from '../system-default-template';

const CUSTOM = { id: 'tmpl_custom', isSystemDefault: false };
const GENERIC = { id: SYSTEM_DEFAULT_TEMPLATE_ID, isSystemDefault: true };

const base = {
  requestedTemplateId: null as string | null,
  effective: GENERIC,
  resolutionFailed: false,
  hasApplicableActiveTemplate: false,
};

describe('SILENT IS CORRECT — the cases that must NOT raise a banner', () => {
  it('a doctor with no uploaded form gets the generic layout', () => {
    expect(detectTemplateFallback(base)).toBeNull();
  });

  it('a doctor who deliberately picked "Standard SOAP"', () => {
    expect(
      detectTemplateFallback({ ...base, requestedTemplateId: SYSTEM_DEFAULT_TEMPLATE_ID })
    ).toBeNull();
  });

  it('⚠️ a doctor who picked "Standard SOAP" while HAVING an activated format', () => {
    // Their explicit choice is not a failure, and warning here would train the
    // banner out of existence.
    expect(
      detectTemplateFallback({
        ...base,
        requestedTemplateId: SYSTEM_DEFAULT_TEMPLATE_ID,
        hasApplicableActiveTemplate: true,
      })
    ).toBeNull();
  });

  it('the doctor\'s own template produced the note', () => {
    expect(detectTemplateFallback({ ...base, effective: CUSTOM })).toBeNull();
  });

  it('the doctor\'s own template produced the note AND it is the one asked for', () => {
    expect(
      detectTemplateFallback({
        ...base,
        effective: CUSTOM,
        requestedTemplateId: 'tmpl_custom',
      })
    ).toBeNull();
  });

  it('⚠️ a format scoped to ANOTHER specialty resolving away is correct behaviour', () => {
    // `hasApplicableActiveTemplate` is false precisely because the doctor's
    // dermatology format does not apply to this primary-care visit.
    expect(detectTemplateFallback({ ...base, hasApplicableActiveTemplate: false })).toBeNull();
  });
});

describe('LOUD — the cases that must raise a banner, and NAME the cause', () => {
  it('resolution threw: the note is generic and the doctor is told why', () => {
    const out = detectTemplateFallback({ ...base, resolutionFailed: true });
    expect(out?.kind).toBe('resolution_failed');
    expect(out?.reason).toContain('could not be loaded');
    expect(out?.reason).toContain('standard layout');
  });

  it('⚠️ resolution threw even though a custom template object was installed', () => {
    // The catch installs the SOAP constant, but a caller that installed
    // something else must still be treated as a failure — the fallback is the
    // fact, not the object.
    const out = detectTemplateFallback({
      ...base,
      effective: CUSTOM,
      resolutionFailed: true,
    });
    expect(out?.kind).toBe('resolution_failed');
  });

  it('the visit named a format and the GENERIC layout produced the note', () => {
    const out = detectTemplateFallback({ ...base, requestedTemplateId: 'tmpl_custom' });
    expect(out?.kind).toBe('pinned_template_not_applied');
    expect(out?.reason).toContain('was not available');
    expect(out?.reason).toContain('Settings');
  });

  it('the visit named one format and a DIFFERENT custom one produced the note', () => {
    const out = detectTemplateFallback({
      ...base,
      requestedTemplateId: 'tmpl_other',
      effective: CUSTOM,
    });
    expect(out?.kind).toBe('pinned_template_not_applied');
    expect(out?.reason).toContain('a different one produced the note');
  });

  it('no pick, but an APPLICABLE activated format existed and was not used', () => {
    const out = detectTemplateFallback({ ...base, hasApplicableActiveTemplate: true });
    expect(out?.kind).toBe('active_template_not_applied');
    expect(out?.reason).toContain('activated note format');
  });
});

describe('every reason is doctor-facing and actionable', () => {
  const all = [
    detectTemplateFallback({ ...base, resolutionFailed: true }),
    detectTemplateFallback({ ...base, requestedTemplateId: 'tmpl_custom' }),
    detectTemplateFallback({ ...base, hasApplicableActiveTemplate: true }),
  ];

  it('names a place to go and says what happened', () => {
    for (const f of all) {
      expect(f).not.toBeNull();
      expect(f!.reason.length).toBeGreaterThan(60);
      expect(f!.reason).toMatch(/Settings/);
    }
  });

  it('⚠️ never says only "your form needs review" — a cause with no cure is a dead end', () => {
    for (const f of all) {
      expect(f!.reason).not.toBe('Your form needs review.');
    }
  });

  it('the three kinds are distinct', () => {
    expect(new Set(all.map((f) => f!.kind)).size).toBe(3);
  });
});
