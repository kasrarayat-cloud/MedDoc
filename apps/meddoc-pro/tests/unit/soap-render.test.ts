// ============================================================================
// SOAP JSON → markdown renderer + JSON sniffing (@meddoc/types)
// ----------------------------------------------------------------------------
// Exercised when a Scribe-signed Document hits the patient chart UI.
// Keeping these in apps/meddoc-pro/tests/unit/ so they run in the
// existing CI pipeline without setting up a second runner.
// ============================================================================

import { describe, it, expect } from 'vitest';
import {
  parseSoapNote,
  renderSoapMarkdown,
  SoapNoteSchema,
  type SoapNote,
} from '@meddoc/types';

const validSoap: SoapNote = {
  confidence: 'medium',
  subjective: {
    chief_complaint: 'Cough and nasal congestion for 4 days.',
    hpi: 'Worse at night. No fevers. Denies shortness of breath.',
  },
  objective: {
    vitals: 'T 37.0, BP 122/78, HR 82, SpO2 98%.',
    general_exam: 'Alert, comfortable.',
  },
  assessment: [
    {
      icd10_candidate: 'J06.9',
      description: 'Acute upper respiratory infection, unspecified.',
      evidence_quote: 'cough and runny nose for about four days',
      confidence: 'high',
    },
  ],
  plan: {
    medications: 'OTC pseudoephedrine PRN.',
    counseling: 'Return if symptoms worsen or fever develops.',
  },
  missing_required_elements: ['heart', 'lungs'],
  ambiguities: [],
};

describe('parseSoapNote', () => {
  it('returns null for null/undefined/empty', () => {
    expect(parseSoapNote(null)).toBeNull();
    expect(parseSoapNote(undefined)).toBeNull();
    expect(parseSoapNote('')).toBeNull();
    expect(parseSoapNote('   ')).toBeNull();
  });

  it('returns null for plain text / markdown', () => {
    expect(parseSoapNote('Patient complained of headache.')).toBeNull();
    expect(parseSoapNote('# Header\n\nSome content.')).toBeNull();
  });

  it('returns null for non-matching JSON', () => {
    expect(parseSoapNote('{"foo": "bar"}')).toBeNull();
    expect(parseSoapNote('[1,2,3]')).toBeNull();
  });

  it('parses + validates a well-formed SOAP JSON', () => {
    const out = parseSoapNote(JSON.stringify(validSoap));
    expect(out).not.toBeNull();
    expect(out?.confidence).toBe('medium');
    expect(out?.assessment).toHaveLength(1);
  });

  it('trims whitespace before JSON', () => {
    const out = parseSoapNote('  \n' + JSON.stringify(validSoap));
    expect(out).not.toBeNull();
  });
});

describe('renderSoapMarkdown', () => {
  it('produces stable output for a given input', () => {
    const a = renderSoapMarkdown(validSoap);
    const b = renderSoapMarkdown(validSoap);
    expect(a).toBe(b);
  });

  it('includes all section headers', () => {
    const md = renderSoapMarkdown(validSoap);
    expect(md).toContain('## Subjective');
    expect(md).toContain('## Objective');
    expect(md).toContain('## Assessment');
    expect(md).toContain('## Plan');
  });

  it('surfaces missing required elements in a callout', () => {
    const md = renderSoapMarkdown(validSoap);
    expect(md).toMatch(/Missing documented elements:/);
    expect(md).toContain('Heart');
    expect(md).toContain('Lungs');
  });

  it('does NOT show the missing-elements callout when the array is empty', () => {
    const md = renderSoapMarkdown({ ...validSoap, missing_required_elements: [] });
    expect(md).not.toMatch(/Missing documented elements:/);
  });

  it('surfaces ambiguities only when non-empty', () => {
    const withAmb = { ...validSoap, ambiguities: ['Could not hear heart sounds clearly.'] };
    const md = renderSoapMarkdown(withAmb);
    expect(md).toContain('Could not hear heart sounds clearly.');
  });

  it('preserves ICD-10 candidates and evidence quotes in the Assessment block', () => {
    const md = renderSoapMarkdown(validSoap);
    expect(md).toContain('J06.9');
    expect(md).toContain('cough and runny nose for about four days');
  });

  it('handles empty sections gracefully', () => {
    const md = renderSoapMarkdown({
      ...validSoap,
      plan: {},
      assessment: [],
    });
    expect(md).toContain('## Assessment');
    expect(md).toContain('_No assessment items._');
    expect(md).toContain('_Not documented._');
  });
});

describe('SoapNoteSchema', () => {
  it('rejects inputs missing required sections', () => {
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    const { assessment, ...missing } = validSoap as any;
    expect(SoapNoteSchema.safeParse(missing).success).toBe(false);
    expect(assessment).toBeDefined();
  });

  it('rejects wrong confidence enum values', () => {
    const bad = { ...validSoap, confidence: 'maybe' };
    expect(SoapNoteSchema.safeParse(bad).success).toBe(false);
  });

  it('rejects assessment items without evidence_quote', () => {
    const bad = {
      ...validSoap,
      assessment: [
        {
          icd10_candidate: 'J06.9',
          description: 'URI',
          // evidence_quote intentionally missing
          confidence: 'high',
        },
      ],
    };
    expect(SoapNoteSchema.safeParse(bad).success).toBe(false);
  });
});
