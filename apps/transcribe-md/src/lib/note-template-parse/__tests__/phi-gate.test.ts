// ============================================================================
// PHI gate — pure detection + fail-safe policy tests (Phase 2a).
// ============================================================================

import { describe, expect, it } from 'vitest';
import {
  detectStructuredPhi,
  enumerateTextFields,
  applyPhiGate,
  detectPhiKeywords,
  isAdministrativeChrome,
  dropAdministrativeChrome,
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

// ── Over-rejection fix: VALUE-shape detection, NOT bare keywords ──────────
describe('detectStructuredPhi — value-shape, not field-name keywords', () => {
  it('catches actual ID VALUES — including alphanumeric-prefixed + hyphenated', () => {
    // The exact bug-hunt MRN must still be caught (no leak).
    expect(detectStructuredPhi('MRN: RFM-0098214')).toContain('id');
    expect(detectStructuredPhi('RFM-0098214')).toEqual(
      expect.arrayContaining(['id'])
    );
    expect(detectStructuredPhi('Insurance #XQ4471892')).toContain('id');
    expect(detectStructuredPhi('NPI 1487654321')).toContain('long-id');
    expect(detectStructuredPhi('MRN 0093312')).toContain('mrn');
    expect(detectStructuredPhi('record number 4421')).toContain('mrn');
  });

  it('does NOT fire on bare PHI field-NAME labels (the over-rejection trigger)', () => {
    // This is the styleInstructions string that wrongly rejected 4/5 bug-hunt runs.
    expect(
      detectStructuredPhi('patient identifiers (name, MRN, DOB/age/sex, date of visit, insurance, provider)')
    ).toEqual([]);
    expect(detectStructuredPhi('a labeled key:value line with MRN and DOB')).toEqual([]);
    expect(detectStructuredPhi('record number')).toEqual([]);
    expect(detectStructuredPhi('include the date of birth field')).toEqual([]);
  });

  it('is not vulnerable to catastrophic backtracking (ReDoS) on a label + long dash run', () => {
    // Attacker-influenceable defaultText: a record label with no terminal
    // value. The detector classes must not overlap on "-" (quadratic) — this
    // must stay linear/fast and return no match (no value present).
    const evil = 'medical record ' + '-'.repeat(50000);
    const t0 = Date.now();
    expect(detectStructuredPhi(evil)).toEqual([]);
    expect(Date.now() - t0).toBeLessThan(150);
    // And the value form still matches after the fix.
    expect(detectStructuredPhi('MRN: RFM-0098214')).toContain('mrn');
  });
});

describe('detectPhiKeywords — soft signal only', () => {
  it('flags label words for LLM double-check, without auto-rejecting', () => {
    expect(detectPhiKeywords('patient identifiers (name, MRN, DOB)')).toBe(true);
    expect(detectPhiKeywords('record number field')).toBe(true);
    expect(detectPhiKeywords('Exam grouped by region; positives first.')).toBe(false);
    expect(detectPhiKeywords(null)).toBe(false);
  });
});

// ── Administrative-chrome exclusion ──────────────────────────────────────
describe('isAdministrativeChrome / dropAdministrativeChrome', () => {
  it('flags letterhead / demographics / signature chrome (by key OR label)', () => {
    expect(isAdministrativeChrome('Clinic & Patient Header', 'header')).toBe(true);
    expect(isAdministrativeChrome('Signature', 'signature')).toBe(true);
    expect(isAdministrativeChrome('Patient Demographics', 'misc')).toBe(true);
    expect(isAdministrativeChrome('Letterhead', 'x')).toBe(true);
  });

  it('does NOT flag clinical sections', () => {
    expect(isAdministrativeChrome('Subjective', 'subjective')).toBe(false);
    expect(isAdministrativeChrome('EXAM', 'objective')).toBe(false);
    expect(isAdministrativeChrome('IMPRESSION & PLAN', 'assessment_plan')).toBe(false);
    expect(isAdministrativeChrome('PATIENT INSTRUCTIONS', 'patient_education')).toBe(false);
  });

  it('drops chrome, keeps the clinical body', () => {
    const secs = [
      { key: 'header', label: 'Clinic & Patient Header' },
      { key: 'subjective', label: 'INTERVAL HISTORY' },
      { key: 'objective', label: 'EXAM' },
      { key: 'signature', label: 'Signature' },
    ];
    const { kept, droppedLabels } = dropAdministrativeChrome(secs);
    expect(kept.map((s) => s.key)).toEqual(['subjective', 'objective']);
    expect(droppedLabels).toEqual(['Clinic & Patient Header', 'Signature']);
  });
});
