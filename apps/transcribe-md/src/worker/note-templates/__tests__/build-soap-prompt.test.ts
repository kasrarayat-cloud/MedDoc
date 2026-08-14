// ============================================================================
// build-soap-prompt — custom-template + immutable-safety tests (Phase 1).
// ----------------------------------------------------------------------------
// The golden test (worker/layers/__tests__/l4-golden-prompt.test.ts) locks the
// SYSTEM-DEFAULT path to byte-identity. These tests exercise the CUSTOM path
// the engine now supports + prove the safety boundary holds.
// ============================================================================

import { describe, expect, it } from 'vitest';
import { validateSoapStructure } from '../../layers/soap-structure-validator';
import {
  SYSTEM_DEFAULT_NOTE_TEMPLATE,
  type NoteTemplateSection,
} from '../system-default-template';
import {
  buildSoapSystemPrompt,
  buildSoapUserPrompt,
  insertedDefaultSections,
  normalizeTemplate,
  requiredSectionLabels,
  SCAFFOLD_CONFIRM_MARKER,
  type ResolvedNoteTemplate,
} from '../build-soap-prompt';

const sect = (o: Partial<NoteTemplateSection> & Pick<NoteTemplateSection, 'key' | 'label' | 'order'>): NoteTemplateSection => ({
  formatHint: 'prose',
  styleInstructions: null,
  defaultText: null,
  defaultTextMode: 'omit_unless_supported',
  ...o,
});

// A custom template: different sections/order/format than SOAP, a custom
// (should-be-ignored) safety layer, and one scaffold_confirm default.
const CUSTOM: ResolvedNoteTemplate = {
  id: 'tmpl_custom_psych',
  version: 3,
  isSystemDefault: false,
  styleProfile: {
    tense: 'past',
    tone: 'concise',
    abbreviations: null,
    preamble: 'CUSTOM-PREAMBLE-SHOULD-BE-IGNORED',
    globalRules: ['CUSTOM-RULE-SHOULD-BE-IGNORED'],
  },
  sections: [
    sect({
      key: 'presenting_concern',
      label: 'Presenting Concern',
      order: 1,
      styleInstructions: 'Patient-stated reason for the visit.',
    }),
    sect({
      key: 'mental_status_exam',
      label: 'Mental Status Exam',
      order: 2,
      formatHint: 'bullets',
      styleInstructions: null, // exercises the formatHint fallback
      defaultText: 'Appearance: WNL. Mood: euthymic. Affect: full.',
      defaultTextMode: 'scaffold_confirm',
    }),
    sect({
      key: 'formulation',
      label: 'Formulation',
      order: 3,
      styleInstructions: 'Biopsychosocial formulation.',
    }),
  ],
};

const OPTS = {
  specialty: 'psychiatry',
  audioQualityAlert: null,
  interpreterAlert: null,
  specialtyGuidanceText: null,
};

describe('buildSoapSystemPrompt — custom structure', () => {
  const prompt = buildSoapSystemPrompt(CUSTOM, OPTS);

  it('reflects the custom section headings in order', () => {
    expect(prompt).toContain('## Presenting Concern');
    expect(prompt).toContain('## Mental Status Exam');
    expect(prompt).toContain('## Formulation');
    expect(prompt.indexOf('## Presenting Concern')).toBeLessThan(
      prompt.indexOf('## Mental Status Exam')
    );
    expect(prompt.indexOf('## Mental Status Exam')).toBeLessThan(
      prompt.indexOf('## Formulation')
    );
  });

  it('does NOT impose the default SOAP headings', () => {
    expect(prompt).not.toContain('## Subjective');
    expect(prompt).not.toContain('## Objective');
  });

  it('falls back to the formatHint when a section has no styleInstructions', () => {
    expect(prompt).toContain('Write this section as a bulleted list.');
  });
});

describe('buildSoapSystemPrompt — IMMUTABLE safety boundary', () => {
  const prompt = buildSoapSystemPrompt(CUSTOM, OPTS);

  it('emits the canonical safety preamble + guardrails regardless of the template', () => {
    expect(prompt).toContain('You are a senior clinician writing a SOAP note');
    expect(prompt).toContain('Do NOT invent clinical findings');
    expect(prompt).toContain('Output ONLY the SOAP note markdown');
  });

  it("ignores a custom template's attempt to override the safety layer", () => {
    expect(prompt).not.toContain('CUSTOM-PREAMBLE-SHOULD-BE-IGNORED');
    expect(prompt).not.toContain('CUSTOM-RULE-SHOULD-BE-IGNORED');
  });

  it('keeps the safety preamble first', () => {
    expect(prompt.startsWith('You are a senior clinician')).toBe(true);
  });
});

describe('buildSoapSystemPrompt — normals handling per defaultTextMode', () => {
  it('scaffold_confirm inserts the default text WITH the confirm marker', () => {
    const prompt = buildSoapSystemPrompt(CUSTOM, OPTS);
    expect(prompt).toContain('Appearance: WNL. Mood: euthymic. Affect: full.');
    expect(prompt).toContain(SCAFFOLD_CONFIRM_MARKER);
  });

  // ⚠️ THIS TEST USED TO ASSERT THE OPPOSITE, AND ITS INVERSION IS THE PROOF.
  // Until ruling #106(a) an `always_include` default was INSERTED INTO THE
  // PROMPT — "always_include inserts the default text WITHOUT a marker" — and
  // that is exactly how a doctor's fixed protocol paragraph became text a model
  // was asked to reproduce, and then normalised (`500 milliseconds` →
  // `0.5 seconds` on a real customer's note). The section is now SYSTEM-COMPOSED:
  // the model is told it exists, told which holes it may fill, and never
  // receives the bytes. See `assemble-note.ts` and `l4-assembly.test.ts` for the
  // other half — that the bytes reach the note by a different road.
  it('⚠️ always_include NEVER reaches the model — it is composed by code (#106(a))', () => {
    const t: ResolvedNoteTemplate = {
      ...CUSTOM,
      sections: [
        sect({
          key: 'disclaimer',
          label: 'Disclaimer',
          order: 1,
          defaultText: 'Generated with AI assistance.',
          defaultTextMode: 'always_include',
        }),
      ],
    };
    const prompt = buildSoapSystemPrompt(t, OPTS);
    expect(prompt).not.toContain('Generated with AI assistance.');
    expect(prompt).toContain('SYSTEM-COMPOSED SECTION');
    expect(prompt).not.toContain(SCAFFOLD_CONFIRM_MARKER);
  });

  it('a STRUCTURED always_include section keeps the pre-#106 injection', () => {
    // A table's cells carry dictated values, so it is a fill surface and not a
    // static region — `staticSections` excludes it and this path is unchanged.
    const t: ResolvedNoteTemplate = {
      ...CUSTOM,
      sections: [
        sect({
          key: 'grid',
          label: 'Grid',
          order: 1,
          defaultText: 'Grid scaffold text.',
          defaultTextMode: 'always_include',
          structure: { kind: 'table', columns: ['DIAMETER (mm)'] },
        }),
      ],
    };
    const prompt = buildSoapSystemPrompt(t, OPTS);
    expect(prompt).toContain('Grid scaffold text.');
    expect(prompt).not.toContain('SYSTEM-COMPOSED SECTION');
  });

  it('omit_unless_supported NEVER injects defaultText even if present', () => {
    const t: ResolvedNoteTemplate = {
      ...CUSTOM,
      sections: [
        sect({
          key: 'ros',
          label: 'ROS',
          order: 1,
          styleInstructions: 'Review of systems.',
          defaultText: 'All systems negative.',
          defaultTextMode: 'omit_unless_supported',
        }),
      ],
    };
    const prompt = buildSoapSystemPrompt(t, OPTS);
    expect(prompt).not.toContain('All systems negative.');
  });
});

describe('buildSoapUserPrompt', () => {
  it('carries specialty + entities JSON + wrapped transcript (unchanged mechanism)', () => {
    const user = buildSoapUserPrompt({
      specialty: 'psychiatry',
      entitiesJson: '{"x":1}',
      wrappedTranscript: '<transcript_abcd>hi</transcript_abcd>',
    });
    expect(user).toContain('Specialty: psychiatry');
    expect(user).toContain('Extracted entities');
    expect(user).toContain('{"x":1}');
    expect(user).toContain('Role-labeled transcript:');
    expect(user).toContain('<transcript_abcd>hi</transcript_abcd>');
  });
});

describe('helpers', () => {
  it('insertedDefaultSections returns only scaffold/always-include sections with a default', () => {
    expect(insertedDefaultSections(CUSTOM).map((s) => s.key)).toEqual([
      'mental_status_exam',
    ]);
    // System default: all omit_unless_supported → nothing inserted.
    expect(insertedDefaultSections(SYSTEM_DEFAULT_NOTE_TEMPLATE)).toEqual([]);
  });

  it('requiredSectionLabels: custom labels in order; system default = the 4 SOAP headers', () => {
    expect(requiredSectionLabels(CUSTOM)).toEqual([
      'Presenting Concern',
      'Mental Status Exam',
      'Formulation',
    ]);
    expect(requiredSectionLabels(SYSTEM_DEFAULT_NOTE_TEMPLATE)).toEqual([
      'Subjective',
      'Objective',
      'Assessment',
      'Plan',
    ]);
  });

  it('normalizeTemplate casts a DB-row shape into the builder shape', () => {
    const row = {
      id: 'r1',
      version: 2,
      isSystemDefault: false,
      sections: [{ key: 'x', label: 'X', order: 1, formatHint: 'prose', styleInstructions: 'y', defaultText: null, defaultTextMode: 'omit_unless_supported' }],
      styleProfile: { tense: null, tone: 't', abbreviations: null, preamble: 'p', globalRules: [] },
    };
    const norm = normalizeTemplate(row);
    expect(norm.id).toBe('r1');
    expect(norm.version).toBe(2);
    expect(norm.sections).toHaveLength(1);
  });
});

describe('generalized validator', () => {
  it('system-default note → unchanged 4-header behavior (no param)', () => {
    const note =
      '## Subjective\nx\n## Objective\nx\n## Assessment\nx\n## Plan\nx'.padEnd(60, '.');
    expect(validateSoapStructure(note).ok).toBe(true);
    const missingPlan = '## Subjective\nx\n## Objective\nx\n## Assessment\nx'.padEnd(60, '.');
    const r = validateSoapStructure(missingPlan);
    expect(r.ok).toBe(false);
    expect(r.missingSections).toEqual(['Plan']);
  });

  it('custom template → checks the custom required sections', () => {
    const labels = requiredSectionLabels(CUSTOM);
    const good =
      '## Presenting Concern\nx\n## Mental Status Exam\nx\n## Formulation\nx'.padEnd(
        80,
        '.'
      );
    expect(validateSoapStructure(good, labels).ok).toBe(true);

    // A note in DEFAULT SOAP shape FAILS the custom template's check.
    const soapShaped =
      '## Subjective\nx\n## Objective\nx\n## Assessment\nx\n## Plan\nx'.padEnd(80, '.');
    const r = validateSoapStructure(soapShaped, labels);
    expect(r.ok).toBe(false);
    expect(r.missingSections).toEqual([
      'Presenting Concern',
      'Mental Status Exam',
      'Formulation',
    ]);
  });
});

// ── Phase 2b end-to-end SAFETY re-verification ──────────────────────────────
// A template as PERSISTED by the 2b save action: a Prisma row whose styleProfile
// carries ONLY { tense, tone, abbreviations } — NO preamble/globalRules (the
// save action never stores them) — and Dr. A's COMBINED "Impression & Plan"
// section. Proves: the activated custom template still gets the immutable
// preamble (sourced from the canonical default, not the row), L5 normals-
// scrutiny stays active on inserted defaults, and a combined A&P survives intact
// for L7 (which codes from the full SOAP text, not per-heading).
describe('Phase 2b — activated custom template keeps the safety boundary', () => {
  // exactly what saveNoteTemplateAction persists (no safety fields)
  const DR_A_ROW = {
    id: 'tmpl_dr_a',
    version: 2,
    isSystemDefault: false,
    sections: [
      { key: 'subjective', label: 'Interval History', order: 1, formatHint: 'prose', styleInstructions: 'Narrative interval history.', defaultText: null, defaultTextMode: 'omit_unless_supported' },
      { key: 'objective', label: 'Exam', order: 2, formatHint: 'bullets', styleInstructions: 'By system.', defaultText: 'General: well-appearing. CV: RRR. Resp: CTAB.', defaultTextMode: 'scaffold_confirm' },
      { key: 'assessment_plan', label: 'Impression & Plan', order: 3, formatHint: 'numbered', styleInstructions: 'Numbered problem list; plan under each.', defaultText: null, defaultTextMode: 'omit_unless_supported' },
    ],
    styleProfile: { tense: 'past', tone: 'concise', abbreviations: null },
  };
  const tmpl = normalizeTemplate(DR_A_ROW);
  const prompt = buildSoapSystemPrompt(tmpl, {
    specialty: 'primary-care',
    audioQualityAlert: null,
    interpreterAlert: null,
    specialtyGuidanceText: null,
  });

  it('(a) still emits the immutable preamble, sourced from the canonical default', () => {
    expect(prompt.startsWith('You are a senior clinician')).toBe(true);
    expect(prompt).toContain('Do NOT invent clinical findings');
    expect(prompt).toContain('Output ONLY the SOAP note markdown');
    // a 2b row has no preamble of its own — but the canonical one is present
    expect(SYSTEM_DEFAULT_NOTE_TEMPLATE.styleProfile.preamble.length).toBeGreaterThan(0);
  });

  it('(a) a row that smuggled a preamble/globalRules would STILL be ignored', () => {
    const evilRow = {
      ...DR_A_ROW,
      styleProfile: { tense: null, tone: 'x', abbreviations: null, preamble: 'EVIL-OVERRIDE', globalRules: ['EVIL-RULE'] },
    };
    const evil = buildSoapSystemPrompt(normalizeTemplate(evilRow), {
      specialty: 'primary-care', audioQualityAlert: null, interpreterAlert: null, specialtyGuidanceText: null,
    });
    expect(evil).not.toContain('EVIL-OVERRIDE');
    expect(evil).not.toContain('EVIL-RULE');
    expect(evil.startsWith('You are a senior clinician')).toBe(true);
  });

  it('(b) L5 normals-scrutiny runs on the inserted default (scaffold marker present)', () => {
    expect(insertedDefaultSections(tmpl).map((s) => s.key)).toEqual(['objective']);
    expect(prompt).toContain('General: well-appearing. CV: RRR. Resp: CTAB.');
    expect(prompt).toContain(SCAFFOLD_CONFIRM_MARKER);
  });

  it('(c) the COMBINED Impression & Plan stays one section (intact for L7)', () => {
    expect(prompt).toContain('## Impression & Plan');
    expect(prompt).not.toContain('## Assessment');
    expect(prompt).not.toContain('## Plan\n');
    // the validator requires exactly the doctor's headings, combined A&P included
    expect(requiredSectionLabels(tmpl)).toEqual(['Interval History', 'Exam', 'Impression & Plan']);
  });
});
