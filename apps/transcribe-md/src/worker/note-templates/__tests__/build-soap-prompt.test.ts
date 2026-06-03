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

  it('always_include inserts the default text WITHOUT a marker', () => {
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
    expect(prompt).toContain('Generated with AI assistance.');
    expect(prompt).not.toContain(SCAFFOLD_CONFIRM_MARKER);
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
