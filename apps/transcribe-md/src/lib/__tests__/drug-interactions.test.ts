// ============================================================================
// F-8 regression battery (2026-07-02) — deterministic drug-pair interaction
// floor. Pins the exact miss from the custom-template QA matrix (amlodipine +
// simvastatin 40 mg fired in 0/3 real-pipeline phrasings) plus the
// high-severity pairs the curated table claims to cover. Mirrors
// dose-range.test.ts: exercises the @meddoc/ai module directly.
// ============================================================================

import { describe, expect, it } from 'vitest';
import {
  checkDrugInteractions,
  DRUG_INTERACTION_RULE_COUNT,
  type InteractionMed,
} from '@meddoc/ai';

function med(name: string, doseMgPerDay: number | null = null, source: 'draft' | 'current' = 'draft'): InteractionMed {
  return { name, doseMgPerDay, source };
}

describe('checkDrugInteractions — the F-8 pair', () => {
  it('CATCHES simvastatin 40 mg/day + amlodipine as CRITICAL (the QA-matrix miss)', () => {
    const w = checkDrugInteractions([med('Simvastatin', 40), med('Amlodipine', 10, 'current')]);
    expect(w).toHaveLength(1);
    expect(w[0].severity).toBe('critical');
    expect(w[0].ruleId).toBe('simvastatin-amlodipine-cap20');
    expect(w[0].message).toMatch(/20 mg\/day/);
    expect(w[0].message).toMatch(/rhabdomyolysis/i);
  });

  it('catches it regardless of which side is drafted vs current (phrasing-independent)', () => {
    for (const [sSrc, aSrc] of [['draft', 'draft'], ['current', 'draft'], ['current', 'current']] as const) {
      const w = checkDrugInteractions([med('simvastatin', 40, sSrc), med('amlodipine', 5, aSrc)]);
      expect(w, `${sSrc}+${aSrc}`).toHaveLength(1);
      expect(w[0].severity).toBe('critical');
    }
  });

  it('caution-first: unknown simvastatin dose + amlodipine → MAJOR verify warning, never silent', () => {
    const w = checkDrugInteractions([med('simvastatin', null), med('amlodipine', 10)]);
    expect(w).toHaveLength(1);
    expect(w[0].severity).toBe('major');
    expect(w[0].message).toMatch(/verify/i);
  });

  it('compliant dose (20 mg/day) with amlodipine does NOT fire', () => {
    expect(checkDrugInteractions([med('simvastatin', 20), med('amlodipine', 10)])).toHaveLength(0);
  });

  it('brand names match (Zocor 40 + Norvasc)', () => {
    const w = checkDrugInteractions([med('Zocor', 40), med('Norvasc', 5, 'current')]);
    expect(w).toHaveLength(1);
    expect(w[0].severity).toBe('critical');
  });

  it('dose/formulation tails in names still match ("Simvastatin 40 mg tablet")', () => {
    const w = checkDrugInteractions([med('Simvastatin 40 mg tablet', 40), med('Amlodipine 10 mg', 10, 'current')]);
    expect(w).toHaveLength(1);
  });

  it('simvastatin >10 with diltiazem/verapamil → critical (10 mg cap)', () => {
    expect(checkDrugInteractions([med('simvastatin', 20), med('diltiazem', null, 'current')])[0]?.severity).toBe('critical');
    expect(checkDrugInteractions([med('simvastatin', 20), med('verapamil', null, 'current')])[0]?.severity).toBe('critical');
    expect(checkDrugInteractions([med('simvastatin', 10), med('diltiazem', null, 'current')])).toHaveLength(0);
  });
});

describe('checkDrugInteractions — high-severity battery', () => {
  it('warfarin + NSAIDs → CRITICAL (each class member)', () => {
    for (const nsaid of ['ibuprofen', 'naproxen', 'diclofenac', 'meloxicam', 'ketorolac', 'Advil', 'Aleve']) {
      const w = checkDrugInteractions([med('warfarin', null, 'current'), med(nsaid, null)]);
      expect(w, nsaid).toHaveLength(1);
      expect(w[0].severity, nsaid).toBe('critical');
      expect(w[0].message).toMatch(/bleeding/i);
    }
  });

  it('ACE inhibitor + potassium-raisers → MAJOR', () => {
    for (const [acei, k] of [['lisinopril', 'spironolactone'], ['enalapril', 'potassium chloride'], ['ramipril', 'eplerenone']] as const) {
      const w = checkDrugInteractions([med(acei), med(k, null, 'current')]);
      expect(w, `${acei}+${k}`).toHaveLength(1);
      expect(w[0].severity).toBe('major');
      expect(w[0].message).toMatch(/hyperkalemia/i);
    }
  });

  it('methotrexate + trimethoprim/Bactrim → CRITICAL', () => {
    for (const tmp of ['trimethoprim', 'Bactrim', 'trimethoprim-sulfamethoxazole']) {
      const w = checkDrugInteractions([med('methotrexate', null, 'current'), med(tmp)]);
      expect(w, tmp).toHaveLength(1);
      expect(w[0].severity).toBe('critical');
    }
  });

  it('opioid + benzodiazepine → MAJOR (boxed warning, sometimes intentional)', () => {
    const w = checkDrugInteractions([med('oxycodone', null), med('alprazolam', null, 'current')]);
    expect(w).toHaveLength(1);
    expect(w[0].severity).toBe('major');
    expect(w[0].message).toMatch(/boxed warning/i);
  });
});

describe('checkDrugInteractions — no false fires', () => {
  it('unrelated meds fire nothing', () => {
    expect(checkDrugInteractions([med('metformin', 2000), med('lisinopril', 10), med('atorvastatin', 40)])).toHaveLength(0);
  });

  it('atorvastatin + amlodipine does NOT fire (cap rule is simvastatin-specific)', () => {
    expect(checkDrugInteractions([med('atorvastatin', 80), med('amlodipine', 10)])).toHaveLength(0);
  });

  it('single drug alone never fires', () => {
    expect(checkDrugInteractions([med('warfarin', null)])).toHaveLength(0);
    expect(checkDrugInteractions([med('simvastatin', 80)])).toHaveLength(0);
  });

  it('duplicate mentions dedupe to one warning per rule per pair', () => {
    const w = checkDrugInteractions([
      med('simvastatin', 40), med('simvastatin 40 mg tablet', 40, 'current'),
      med('amlodipine', 10), med('Amlodipine 10 mg', 10, 'current'),
    ]);
    expect(w.filter((x) => x.ruleId === 'simvastatin-amlodipine-cap20')).toHaveLength(1);
  });

  it('empty input → empty output', () => {
    expect(checkDrugInteractions([])).toHaveLength(0);
  });

  it('table size is pinned (curated floor, additions reviewed deliberately)', () => {
    expect(DRUG_INTERACTION_RULE_COUNT).toBe(6);
  });
});
