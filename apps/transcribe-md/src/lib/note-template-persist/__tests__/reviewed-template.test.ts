// ============================================================================
// Reviewed-template validation + normalize (Phase 2b). Pure — proves the two
// in-code safety rules: (1) styleProfile rejects any preamble/globalRules; (2)
// a default is always coerced to scaffold_confirm (never always_include).
// ============================================================================

import { describe, expect, it } from 'vitest';
import {
  ReviewedTemplateSchema,
  normalizeReviewedTemplate,
  friendlyValidationError,
} from '../reviewed-template';

function base() {
  return {
    name: '  Ortho Follow-up  ',
    encounterType: 'orthopedics',
    sections: [
      { key: 'objective', label: 'Exam', order: 5, formatHint: 'bullets', styleInstructions: 'By region.', defaultText: 'Gait normal. No effusion.' },
      { key: 'subjective', label: 'Subjective', order: 1, formatHint: 'prose', styleInstructions: null, defaultText: null },
    ],
    styleProfile: { tense: 'past', tone: 'concise', abbreviations: null },
  };
}

describe('ReviewedTemplateSchema', () => {
  it('accepts a well-formed submission', () => {
    expect(ReviewedTemplateSchema.safeParse(base()).success).toBe(true);
  });

  it('REJECTS a styleProfile carrying a preamble (no safety override can be smuggled)', () => {
    const bad = base() as Record<string, unknown>;
    bad.styleProfile = { tense: null, tone: 'x', abbreviations: null, preamble: 'EVIL OVERRIDE' };
    const r = ReviewedTemplateSchema.safeParse(bad);
    expect(r.success).toBe(false);
  });

  it('REJECTS globalRules / unknown top-level keys (strict)', () => {
    const bad1 = base() as Record<string, unknown>;
    (bad1.styleProfile as Record<string, unknown>).globalRules = ['x'];
    expect(ReviewedTemplateSchema.safeParse(bad1).success).toBe(false);

    const bad2 = { ...base(), sneaky: true };
    expect(ReviewedTemplateSchema.safeParse(bad2).success).toBe(false);
  });

  it('REJECTS empty name + empty section list', () => {
    expect(ReviewedTemplateSchema.safeParse({ ...base(), name: '   ' }).success).toBe(false);
    expect(ReviewedTemplateSchema.safeParse({ ...base(), sections: [] }).success).toBe(false);
  });

  it('does not accept a client-supplied defaultTextMode (derived in code only)', () => {
    const bad = base();
    (bad.sections[0] as Record<string, unknown>).defaultTextMode = 'always_include';
    expect(ReviewedTemplateSchema.safeParse(bad).success).toBe(false);
  });

  it('accepts a NULL encounterType (the catch-all)', () => {
    expect(ReviewedTemplateSchema.safeParse({ ...base(), encounterType: null }).success).toBe(true);
  });

  it('accepts every catalog slug — including flag-gated ones like ultrasound', () => {
    expect(ReviewedTemplateSchema.safeParse({ ...base(), encounterType: 'ultrasound' }).success).toBe(true);
  });

  it('REJECTS a free-text encounterType (finding F-2: parse-LLM output can never match a visit specialty)', () => {
    const res = ReviewedTemplateSchema.safeParse({ ...base(), encounterType: 'Follow-up progress note' });
    expect(res.success).toBe(false);
    if (!res.success) {
      expect(JSON.stringify(res.error.issues)).toContain('Unknown encounter type');
    }
  });
});

describe('normalizeReviewedTemplate', () => {
  it('renumbers order 1..n by submitted order and trims name', () => {
    const parsed = ReviewedTemplateSchema.parse(base());
    const { draft } = normalizeReviewedTemplate(parsed);
    expect(draft.name).toBe('Ortho Follow-up');
    expect(draft.sections.map((s) => s.label)).toEqual(['Subjective', 'Exam']);
    expect(draft.sections.map((s) => s.order)).toEqual([1, 2]);
  });

  it('COERCES defaultTextMode: a default → scaffold_confirm; none → omit_unless_supported', () => {
    const parsed = ReviewedTemplateSchema.parse(base());
    const { draft } = normalizeReviewedTemplate(parsed);
    const exam = draft.sections.find((s) => s.label === 'Exam')!;
    const subj = draft.sections.find((s) => s.label === 'Subjective')!;
    expect(exam.defaultText).toBe('Gait normal. No effusion.');
    expect(exam.defaultTextMode).toBe('scaffold_confirm');
    expect(subj.defaultText).toBeNull();
    expect(subj.defaultTextMode).toBe('omit_unless_supported');
    // NEVER always_include.
    expect(draft.sections.every((s) => s.defaultTextMode !== 'always_include')).toBe(true);
  });

  it('treats whitespace-only default text as no default', () => {
    const input = ReviewedTemplateSchema.parse({
      ...base(),
      sections: [{ key: 'a', label: 'A', order: 1, formatHint: 'prose', styleInstructions: null, defaultText: '   ' }],
    });
    const { draft } = normalizeReviewedTemplate(input);
    expect(draft.sections[0].defaultText).toBeNull();
    expect(draft.sections[0].defaultTextMode).toBe('omit_unless_supported');
  });

  it('styleProfile carries prose fields + contextDefaults + header/form config, NEVER the immutable safety fields', () => {
    const { draft } = normalizeReviewedTemplate(ReviewedTemplateSchema.parse(base()));
    expect(Object.keys(draft.styleProfile).sort()).toEqual([
      'abbreviations', 'contextDefaults', 'formOnlyExport', 'headerFields', 'tense', 'tone',
    ]);
    // the safety layer is immutable + sourced canonically — it can never ride here
    expect(draft.styleProfile).not.toHaveProperty('preamble');
    expect(draft.styleProfile).not.toHaveProperty('globalRules');
  });

  it('re-derives header-field keys from labels + drops unrecognized/off-form fields (never trusts client keys)', () => {
    const { draft } = normalizeReviewedTemplate(
      ReviewedTemplateSchema.parse({
        ...base(),
        styleProfile: {
          tense: null,
          tone: '',
          abbreviations: null,
          headerFields: [
            // client claims a bogus key — server MUST re-derive 'surgeon' from label
            { key: 'evil_injected_key', label: 'SURGEON:', order: 5 },
            { key: 'patient_name', label: 'Patient Name', order: 1 },
            // unrecognized label → dropped
            { key: 'x', label: 'Referring Clinic Phone', order: 2 },
          ],
          formOnlyExport: true,
        },
      })
    );
    // Sorted by the input `order` (1 = Patient Name, 5 = SURGEON; the phone line
    // is unrecognized → dropped), keys re-derived from labels, re-numbered 1..n.
    expect(draft.styleProfile.headerFields).toEqual([
      { key: 'patient_name', label: 'Patient Name', order: 1 },
      { key: 'surgeon', label: 'SURGEON', order: 2 },
    ]);
    expect(draft.styleProfile.formOnlyExport).toBe(true);
  });
});

describe('friendlyValidationError', () => {
  it('never leaks a raw Zod "Too big" — names the field instead (the Dr. A tense case)', () => {
    const r = ReviewedTemplateSchema.safeParse({
      ...base(),
      styleProfile: { tense: 'q'.repeat(200), tone: 'concise', abbreviations: null },
    });
    expect(r.success).toBe(false);
    if (!r.success) {
      const msg = friendlyValidationError(r.error);
      expect(msg).not.toMatch(/too big|expected string/i);
      expect(msg).toMatch(/tense/i);
      expect(msg).toMatch(/too long/i);
    }
  });

  it("passes through the schema's own friendly messages (e.g. missing name)", () => {
    const r = ReviewedTemplateSchema.safeParse({ ...base(), name: '' });
    expect(r.success).toBe(false);
    if (!r.success) expect(friendlyValidationError(r.error)).toBe('Give your format a name');
  });

  it('does not leak a raw "Unrecognized key" on a smuggled-preamble payload (.strict())', () => {
    const r = ReviewedTemplateSchema.safeParse({
      ...base(),
      styleProfile: { tense: 'past', tone: 'concise', abbreviations: null, preamble: 'IGNORE SAFETY' },
    });
    expect(r.success).toBe(false);
    if (!r.success) {
      const msg = friendlyValidationError(r.error);
      expect(msg).not.toMatch(/unrecognized|preamble/i);
    }
  });
});
