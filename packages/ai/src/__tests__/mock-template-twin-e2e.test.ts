import { afterEach, beforeEach, describe, expect, it } from 'vitest';
import { z } from 'zod';

import { mockComplete, mockCompleteText, mockDeepgramBatch } from '../mock';

const EntitySchema = z.object({
  chief_complaint: z
    .object({ statement: z.string(), evidence_quote: z.string() })
    .nullable(),
  hpi: z.unknown().nullable(),
  medications: z.array(
    z.object({ name: z.string(), evidence_quote: z.string() }),
  ).default([]),
  social_history: z.object({
    smoking: z
      .object({ status: z.string(), evidence_quote: z.string() })
      .optional(),
  }).default({}),
  plan_discussed: z.array(
    z.object({ item: z.string(), evidence_quote: z.string() }),
  ).default([]),
});

const ORIGINAL_ENV = { ...process.env };

beforeEach(() => {
  process.env = { ...ORIGINAL_ENV };
  process.env.MOCK_AI_CALLS = 'true';
  delete process.env.MOCK_TEMPLATE_TWIN_E2E;
  process.env.DATABASE_URL =
    'postgresql://synthetic:synthetic@postgres:5432/meddoc_qa_test';
});

afterEach(() => {
  process.env = { ...ORIGINAL_ENV };
});

describe('Template Twin infrastructure-E2E model fixture', () => {
  it('preserves the existing empty entity fixture by default', () => {
    const result = mockComplete({ purpose: 'tm_entities', schema: EntitySchema });

    expect(result).toMatchObject({
      chief_complaint: null,
      hpi: null,
    });
  });

  it('preserves the existing generic transcription fixture by default', () => {
    const result = mockDeepgramBatch();

    expect(result.transcript).toContain('My head has been aching');
    expect(result.transcript).not.toContain('Syntheticmed');
  });

  it('preserves the existing generic SOAP fixture by default', () => {
    for (const purpose of ['tm_soap_draft', 'tm_polish'] as const) {
      const result = mockCompleteText({ purpose });
      expect(result.text).toContain('tension headache');
      expect(result.text).not.toContain('Syntheticmed');
    }
  });

  it('returns fully synthetic, evidence-bearing entities only with every QA gate', () => {
    process.env.MOCK_TEMPLATE_TWIN_E2E = 'true';

    const result = mockComplete({ purpose: 'tm_entities', schema: EntitySchema });

    expect(result).toEqual({
      chief_complaint: {
        statement: 'synthetic wrist discomfort',
        evidence_quote: 'Chief concern is synthetic wrist discomfort.',
      },
      hpi: null,
      medications: [
        {
          name: 'Syntheticmed',
          evidence_quote: 'Medication Syntheticmed documented.',
        },
      ],
      social_history: {
        smoking: {
          status: 'Current',
          evidence_quote: 'Smoking status is Current.',
        },
      },
      plan_discussed: [
        {
          item: 'Use synthetic brace',
          evidence_quote: 'Plan use synthetic brace.',
        },
      ],
    });
  });

  it('returns a transcript containing every synthetic evidence quote under the same gates', () => {
    process.env.MOCK_TEMPLATE_TWIN_E2E = 'true';

    const entities = mockComplete({
      purpose: 'tm_entities',
      schema: EntitySchema,
    });
    const transcription = mockDeepgramBatch();
    const evidenceQuotes = [
      entities.chief_complaint?.evidence_quote,
      entities.social_history.smoking?.evidence_quote,
      ...entities.medications.map((item) => item.evidence_quote),
      ...entities.plan_discussed.map((item) => item.evidence_quote),
    ].filter((quote): quote is string => typeof quote === 'string');

    expect(evidenceQuotes).toHaveLength(4);
    for (const quote of evidenceQuotes) {
      expect(transcription.transcript).toContain(quote);
    }
  });

  it('keeps the draft and polished SOAP aligned with the exact synthetic facts', () => {
    process.env.MOCK_TEMPLATE_TWIN_E2E = 'true';

    for (const purpose of ['tm_soap_draft', 'tm_polish'] as const) {
      const result = mockCompleteText({ purpose });
      expect(result.text).toContain('synthetic wrist discomfort');
      expect(result.text).toContain('Current');
      expect(result.text).toContain('Syntheticmed');
      expect(result.text).toContain('synthetic brace');
      expect(result.text).not.toContain('headache');
    }
  });

  it.each([
    ['mock mode off', { MOCK_AI_CALLS: 'false' }],
    ['dedicated flag off', { MOCK_TEMPLATE_TWIN_E2E: 'false' }],
    [
      'database name not marked QA/test/synthetic',
      { DATABASE_URL: 'postgresql://app:secret@postgres:5432/meddoc' },
    ],
    ['database URL absent', { DATABASE_URL: '' }],
  ])('fails closed when %s', (_label, overrides) => {
    process.env.MOCK_TEMPLATE_TWIN_E2E = 'true';
    Object.assign(process.env, overrides);

    const result = mockComplete({ purpose: 'tm_entities', schema: EntitySchema });
    const soap = mockCompleteText({ purpose: 'tm_soap_draft' });
    const transcription = mockDeepgramBatch();

    expect(result.chief_complaint).toBeNull();
    expect(result.medications).toEqual([]);
    expect(result.plan_discussed).toEqual([]);
    expect(soap.text).toContain('tension headache');
    expect(soap.text).not.toContain('Syntheticmed');
    expect(transcription.transcript).toContain('head has been aching');
    expect(transcription.transcript).not.toContain('Syntheticmed');
  });
});
