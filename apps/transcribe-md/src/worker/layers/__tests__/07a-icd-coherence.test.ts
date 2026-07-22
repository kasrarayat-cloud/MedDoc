// ============================================================================
// 07a ICD clinical-coherence floor — varicose-vein asymptomatic/symptomatic rule.
// Regression for the prod bug: a right-positive / left-normal bilateral vein
// study emitted I83.90 "Asymptomatic varicose veins, unspecified" alongside the
// correct symptomatic I83.891. Only-remove semantics.
// ============================================================================

import { describe, expect, it, vi } from 'vitest';

// Stub the side-effecting deps so importing 07a (which pulls logAudit → auth →
// next-auth) doesn't fail in the unit env. Only the pure export is exercised.
vi.mock('@meddoc/db', () => ({ default: { transcribeVisit: { update: vi.fn() } } }));
vi.mock('@/lib/audit', () => ({ logAudit: vi.fn() }));

import { dropIncoherentVaricoseCodes } from '../07a-icd-coding';
import type { IcdCode } from '../07a-icd-coding';

function code(c: string, description = ''): IcdCode {
  return {
    code: c,
    description: description || c,
    evidence_quote: 'e',
    confidence: 0.9,
    confidenceLevel: 'high',
  };
}

describe('dropIncoherentVaricoseCodes', () => {
  it('drops asymptomatic/unspecified I83.90 when symptomatic I83.891 is present (the prod bug)', () => {
    const out = dropIncoherentVaricoseCodes([
      code('I83.891', 'Varicose veins of right lower extremity with other complications'),
      code('I83.90', 'Asymptomatic varicose veins of unspecified lower extremity'),
    ]);
    expect(out.map((c) => c.code)).toEqual(['I83.891']);
  });

  it('drops the whole I83.9x family (unspecified + laterality-specific asymptomatic) when a symptomatic code is present', () => {
    const out = dropIncoherentVaricoseCodes([
      code('I83.892'),
      code('I83.90'),
      code('I83.91'),
      code('I83.92'),
      code('I83.93'),
    ]);
    expect(out.map((c) => c.code)).toEqual(['I83.892']);
  });

  it('unilateral-positive: keeps a lone symptomatic code unchanged (no asymptomatic ride-along to remove)', () => {
    const out = dropIncoherentVaricoseCodes([code('I83.891')]);
    expect(out.map((c) => c.code)).toEqual(['I83.891']);
  });

  it('bilateral-normal: no varicose codes in, none out (never invents)', () => {
    const out = dropIncoherentVaricoseCodes([code('Z01.812', 'Encounter for screening')]);
    expect(out.map((c) => c.code)).toEqual(['Z01.812']);
    expect(dropIncoherentVaricoseCodes([])).toEqual([]);
  });

  it('leaves a genuine asymptomatic code untouched when NO symptomatic varicose code is present', () => {
    // A truly asymptomatic-but-present varicosity study — nothing to conflict with.
    const out = dropIncoherentVaricoseCodes([code('I83.92', 'Asymptomatic varicose veins, left'), code('I10')]);
    expect(out.map((c) => c.code)).toEqual(['I83.92', 'I10']);
  });

  it('never touches supported non-varicose codes and preserves order', () => {
    const out = dropIncoherentVaricoseCodes([
      code('I10'),
      code('I83.891'),
      code('I83.90'),
      code('E11.9'),
    ]);
    expect(out.map((c) => c.code)).toEqual(['I10', 'I83.891', 'E11.9']);
  });
});
