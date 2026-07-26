import { describe, expect, it } from 'vitest';

import type { SemanticMapping } from '../ir';
import { templateTwinMappingsSha256 } from '../mapping-hash';

const base: SemanticMapping = {
  fieldId: `ttf_${'a'.repeat(24)}`,
  sourceType: 'extraction' as const,
  clinicalConcept: 'synthetic finding',
  expectedDataType: 'text',
  polarityBehavior: 'value_only',
  temporality: 'current',
  laterality: 'optional',
  unitPolicy: 'not_applicable',
  approvedSynonyms: [],
  required: false,
  blankPolicy: 'blank',
  unknownPolicy: 'blank',
  practiceDefault: null,
  status: 'needs_confirmation',
};

describe('templateTwinMappingsSha256', () => {
  it('is stable across database return order and changes when approval changes', () => {
    const second = { ...base, fieldId: `ttf_${'b'.repeat(24)}` };
    expect(templateTwinMappingsSha256([base, second])).toBe(
      templateTwinMappingsSha256([second, base]),
    );
    expect(
      templateTwinMappingsSha256([{ ...base, status: 'certified' }, second]),
    ).not.toBe(templateTwinMappingsSha256([base, second]));
  });
});
