// ============================================================================
// PHI gate — pure detection + fail-safe policy tests (Phase 2a).
// ============================================================================

import { describe, expect, it } from 'vitest';
import {
  detectStructuredPhi,
  enumerateTextFields,
  applyPhiGate,
} from '../phi-gate';
import type { ParsedTemplateDraft } from '../note-template-schema';

function draft(over: Partial<ParsedTemplateDraft> = {}): ParsedTemplateDraft {
  return {
    name: 'Ortho Follow-up',
    encounterType: 'orthopedics',
    styleProfile: { tense: 'past', tone: 'concise', abbreviations: 'standard' },
    sections: [
      {
        key: 'subjective',
        label: 'Subjective',
        order: 1,
        formatHint: 'prose',
        styleInstructions: 'Interval history since last visit.',
        defaultText: null,
        defaultTextMode: 'omit_unless_supported',
      },
      {
        key: 'objective',
        label: 'Objective',
        order: 2,
        formatHint: 'bullets',
        styleInstructions: 'Exam grouped by region.',
        defaultText: 'Normal gait. No effusion. Full range of motion.',
        defaultTextMode: 'scaffold_confirm',
      },
    ],
    ...over,
  };
}

describe('detectStructuredPhi', () => {
  it('catches structured identifiers', () => {
    expect(detectStructuredPhi('jane@example.com')).toContain('email');
    expect(detectStructuredPhi('call (415) 555-0142')).toContain('phone');
    expect(detectStructuredPhi('123-45-6789')).toContain('ssn');
    expect(detectStructuredPhi('seen on 01/02/2026')).toContain('date');
    expect(detectStructuredPhi('DOS 2026-01-02')).toContain('date');
    expect(detectStructuredPhi('on Jan 3, 2026')).toContain('date');
    expect(detectStructuredPhi('45-year-old male')).toContain('age');
    expect(detectStructuredPhi('age 72')).toContain('age');
    expect(detectStructuredPhi('7 yo')).toContain('age');
    expect(detectStructuredPhi('MRN 0093312')).toEqual(
      expect.arrayContaining(['mrn', 'long-id'])
    );
    expect(detectStructuredPhi('record # 4421')).toContain('mrn');
    expect(detectStructuredPhi('id 889214')).toContain('long-id');
  });

  it('does NOT flag generic format/style text or generic normals', () => {
    expect(detectStructuredPhi('Write this section as a numbered list.')).toEqual([]);
    expect(detectStructuredPhi('All systems reviewed and negative.')).toEqual([]);
    expect(detectStructuredPhi('Normal gait. No effusion. Full range of motion.')).toEqual([]);
    expect(detectStructuredPhi('Use the MM/DD/YYYY format for any dates.')).toEqual([]);
    expect(detectStructuredPhi('Vitals within normal limits.')).toEqual([]);
    expect(detectStructuredPhi(null)).toEqual([]);
  });
});

describe('enumerateTextFields', () => {
  it('lists non-empty text fields with canonical paths', () => {
    const paths = enumerateTextFields(draft()).map((f) => f.path);
    expect(paths).toEqual(
      expect.arrayContaining([
        'name',
        'encounterType',
        'styleProfile.tone',
        'sections[0].label',
        'sections[0].styleInstructions',
        'sections[1].defaultText',
      ])
    );
    // null fields omitted (sections[0].defaultText is null).
    expect(paths).not.toContain('sections[0].defaultText');
  });
});

describe('applyPhiGate — fail-safe policy', () => {
  it('passes a clean draft unchanged', () => {
    const r = applyPhiGate(draft(), [], [], false);
    expect(r.rejected).toBe(false);
    if (!r.rejected) {
      expect(r.template.sections[1].defaultText).toBe(
        'Normal gait. No effusion. Full range of motion.'
      );
      expect(r.flags).toEqual([]);
    }
  });

  it('REJECTS when the LLM scan is uncertain', () => {
    const r = applyPhiGate(draft(), [], [], true);
    expect(r.rejected).toBe(true);
    if (r.rejected) expect(r.reason).toMatch(/could not confidently clear/i);
  });

  it('SCRUBS a defaultText with structured PHI (regex) and keeps the template', () => {
    const d = draft();
    d.sections[1].defaultText = 'Patient seen 01/02/2026, BP fine.';
    const r = applyPhiGate(d, [], [], false);
    expect(r.rejected).toBe(false);
    if (!r.rejected) {
      expect(r.template.sections[1].defaultText).toBeNull();
      expect(r.template.sections[1].defaultTextMode).toBe('omit_unless_supported');
      expect(r.flags.join(' ')).toMatch(/Dropped a possible-PHI default/);
      // The PHI string is gone from every field.
      expect(JSON.stringify(r.template)).not.toContain('01/02/2026');
    }
  });

  it('REJECTS when PHI lands in a STRUCTURAL field (regex)', () => {
    const d = draft();
    d.sections[0].label = 'Visit 2026-01-02';
    const r = applyPhiGate(d, [], [], false);
    expect(r.rejected).toBe(true);
    if (r.rejected) expect(r.reason).toMatch(/structural field/i);
  });

  it('SCRUBS when the LLM flags a defaultText path', () => {
    const r = applyPhiGate(draft(), [], ['sections[1].defaultText'], false);
    expect(r.rejected).toBe(false);
    if (!r.rejected) expect(r.template.sections[1].defaultText).toBeNull();
  });

  it('REJECTS when the LLM flags a structural path', () => {
    const r = applyPhiGate(draft(), [], ['sections[0].label'], false);
    expect(r.rejected).toBe(true);
  });

  it('REJECTS when the LLM flags an unrecognized path', () => {
    const r = applyPhiGate(draft(), [], ['sections[99].mystery'], false);
    expect(r.rejected).toBe(true);
    if (r.rejected) expect(r.reason).toMatch(/unrecognized field/i);
  });

  it('preserves extraction-time flags on a clean pass', () => {
    const r = applyPhiGate(draft(), ['a normal cardiac line — confirm'], [], false);
    expect(r.rejected).toBe(false);
    if (!r.rejected) expect(r.flags).toContain('a normal cardiac line — confirm');
  });
});
