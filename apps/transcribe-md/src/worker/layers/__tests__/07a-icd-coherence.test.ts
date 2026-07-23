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

import {
  dropIncoherentVaricoseCodes,
  dropDenialContradictedCodes,
  dropUnsupportedDeficiencyCodes,
} from '../07a-icd-coding';
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

/** Same, but with an explicit evidence_quote — the deficiency guard reads it. */
function codeEv(c: string, evidence_quote: string, description = ''): IcdCode {
  return { code: c, description: description || c, evidence_quote, confidence: 0.9, confidenceLevel: 'high' };
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

  it('treats I83.0x (ulcer) and I83.1x (inflammation) as symptomatic too — drops the asymptomatic ride-along', () => {
    expect(dropIncoherentVaricoseCodes([code('I83.012'), code('I83.90')]).map((c) => c.code)).toEqual(['I83.012']);
    expect(dropIncoherentVaricoseCodes([code('I83.115'), code('I83.92')]).map((c) => c.code)).toEqual(['I83.115']);
    expect(dropIncoherentVaricoseCodes([code('I83.201'), code('I83.90')]).map((c) => c.code)).toEqual(['I83.201']);
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

describe('dropDenialContradictedCodes (denial-vs-code coherence)', () => {
  // Regression for the KUK bariatric visit (2026-07-23): K21.9 GERD was
  // med-inferred from chronic omeprazole while the note documented "no reflux
  // symptoms". A code contradicted by an explicit denial must be dropped.
  it('drops med-inferred K21.9 when the note explicitly denies reflux (the KUK bug)', () => {
    const note =
      '## Objective\nNo dysphagia, no persistent nausea, no vomiting, and no reflux symptoms.';
    const out = dropDenialContradictedCodes(
      [code('E66.01'), code('K21.9', 'GERD without esophagitis'), code('E11.9')],
      note
    );
    expect(out.map((c) => c.code)).toEqual(['E66.01', 'E11.9']);
  });

  it('drops K21.9 for "denies heartburn" / "negative for GERD" phrasings too', () => {
    expect(
      dropDenialContradictedCodes([code('K21.9')], 'Patient denies heartburn today.').length
    ).toBe(0);
    expect(
      dropDenialContradictedCodes([code('K21.9')], 'GI review negative for GERD.').length
    ).toBe(0);
    expect(
      dropDenialContradictedCodes([code('K21.0'), code('K21.9')], 'No acid regurgitation reported.')
        .length
    ).toBe(0);
  });

  it('KEEPS K21.9 when GERD is AFFIRMATIVELY documented — support is never suppressed', () => {
    // An explicit diagnosis line + a "no acute symptoms today" note: controlled
    // GERD still merits the code. Any non-negated mention protects it.
    const note =
      '## Assessment\nGERD, chronic — continue omeprazole.\n## Plan\nNo acute reflux today.';
    const out = dropDenialContradictedCodes([code('K21.9', 'GERD')], note);
    expect(out.map((c) => c.code)).toEqual(['K21.9']);
  });

  it('KEEPS K21.9 when the note is silent on reflux (only-remove on explicit denial)', () => {
    const out = dropDenialContradictedCodes(
      [code('K21.9'), code('E66.01')],
      '## Plan\nAdvance diet; multivitamin adherence.'
    );
    expect(out.map((c) => c.code)).toEqual(['K21.9', 'E66.01']);
    expect(dropDenialContradictedCodes([code('K21.9')], '').map((c) => c.code)).toEqual(['K21.9']);
  });

  it('does not affect unrelated codes governed by no rule (I83.9x path untouched)', () => {
    const note = 'No reflux symptoms. Bilateral varicose study.';
    const out = dropDenialContradictedCodes(
      [code('I83.891'), code('I83.90'), code('I10')],
      note
    );
    // No rule governs I83.x here — this guard leaves them all in; the varicose
    // floor (separate function) owns that coherence. Only K21.x is denial-gated.
    expect(out.map((c) => c.code)).toEqual(['I83.891', 'I83.90', 'I10']);
  });

  it('a negation for a DIFFERENT condition in the same clause does not deny reflux', () => {
    // "denies chest pain, reports reflux" — reflux itself is affirmative.
    const out = dropDenialContradictedCodes(
      [code('K21.9')],
      'Denies chest pain. Reports ongoing reflux on PPI.'
    );
    expect(out.map((c) => c.code)).toEqual(['K21.9']);
  });

  // Auditor edge case 1 — CARDIAC "regurgitation" must not read as GERD denial.
  it('does NOT drop K21.9 for a negated CARDIAC regurgitation (no reflux mention)', () => {
    expect(
      dropDenialContradictedCodes([code('K21.9')], 'Cardiac: no mitral regurgitation on echo.')
        .map((c) => c.code)
    ).toEqual(['K21.9']);
    // But an explicit "no acid regurgitation" IS a reflux denial → drop.
    expect(
      dropDenialContradictedCodes([code('K21.9')], 'GI: no acid regurgitation.').length
    ).toBe(0);
  });

  // Auditor edge case 2 — an adversative conjunction resets the negation scope,
  // so "no history of GERD but now has reflux" keeps the (supported) code.
  it('KEEPS K21.9 when a "no X but has X" conjunction re-affirms reflux (support-preserving)', () => {
    expect(
      dropDenialContradictedCodes(
        [code('K21.9')],
        'No history of GERD but now has reflux on omeprazole.'
      ).map((c) => c.code)
    ).toEqual(['K21.9']);
    // The serial-denial path (no adversative) still drops.
    expect(
      dropDenialContradictedCodes([code('K21.9')], 'No dysphagia, no heartburn, no reflux.').length
    ).toBe(0);
  });

  // Adversarial edge case — a leading denial must NOT leak across a comma onto a
  // later AFFIRMATIVE GERD mention (the confirmed support-suppression breach).
  it('KEEPS K21.9 when a denial precedes an affirmative GERD across a comma (the comma-leak breach)', () => {
    expect(
      dropDenialContradictedCodes(
        [code('K21.9')],
        'Denies heartburn currently, GERD stable on omeprazole.'
      ).map((c) => c.code)
    ).toEqual(['K21.9']);
    expect(
      dropDenialContradictedCodes([code('K21.9')], 'No chest pain, GERD confirmed on EGD.').map(
        (c) => c.code
      )
    ).toEqual(['K21.9']);
    expect(
      dropDenialContradictedCodes([code('K21.9')], 'Problems: no tobacco use, GERD, HTN.').map(
        (c) => c.code
      )
    ).toEqual(['K21.9']);
  });

  it('still drops when the SAME comma-run repeats the cue per item (order-insensitive)', () => {
    // Affirmative-first was already safe; assert denial-first serial still drops.
    expect(
      dropDenialContradictedCodes(
        [code('K21.9')],
        'No abdominal pain, no reflux, no early satiety.'
      ).length
    ).toBe(0);
  });
});

describe('dropUnsupportedDeficiencyCodes (E50–E64 deficiency-family coherence)', () => {
  // Principle: no unspecified deficiency-family code from prophylactic
  // supplementation / missed doses / ordered-but-unresulted labs ALONE.
  // Only-remove, support-preserving.

  // Regression: KUK #4 (post-bariatric plan) — prophylactic multivitamin/D3/B12
  // to PREVENT deficiency hoisted E63.9 with no deficiency ever diagnosed.
  it('drops E63.9 when its only support is prophylactic supplementation to PREVENT deficiency (KUK #4)', () => {
    const note =
      '## Plan\nStarted on chewable multivitamin, vitamin D3 2000 units daily, and B12 to prevent nutritional deficiency after sleeve.';
    const out = dropUnsupportedDeficiencyCodes(
      [
        code('E66.01'),
        codeEv('E63.9', 'Started on chewable multivitamin ... to prevent nutritional deficiency'),
        code('Z98.84'),
      ],
      note
    );
    expect(out.map((c) => c.code)).toEqual(['E66.01', 'Z98.84']);
  });

  // The E53.8 case — prophylactic B-complex supplementation, no B-vitamin
  // deficiency documented.
  it('drops E53.8 when B-complex is prophylactic (no deficiency documented)', () => {
    const note = '## Plan\nContinue daily B-complex supplement per bariatric protocol.';
    expect(
      dropUnsupportedDeficiencyCodes([codeEv('E53.8', 'Continue daily B-complex supplement')], note).length
    ).toBe(0);
  });

  // Missed doses / ordered-but-unresulted labs — neither establishes a diagnosis.
  it('drops on missed doses alone and on ordered-but-unresulted labs alone', () => {
    expect(
      dropUnsupportedDeficiencyCodes(
        [codeEv('E55.9', 'Patient missed several doses of vitamin D')],
        'Patient missed several doses of vitamin D.'
      ).length
    ).toBe(0);
    expect(
      dropUnsupportedDeficiencyCodes(
        [codeEv('E61.1', 'Ordered iron studies, results pending')],
        'Ordered iron studies; will recheck B12 and folate levels next visit.'
      ).length
    ).toBe(0);
  });

  // Support-preserving — an AFFIRMATIVE deficiency diagnosis is NEVER dropped.
  it('KEEPS E53.8 when a B12 deficiency is affirmatively documented (with a low level)', () => {
    const note = '## Assessment\nVitamin B12 deficiency, level 180. Start B12 injections.';
    const out = dropUnsupportedDeficiencyCodes(
      [codeEv('E53.8', 'Start B12 injections'), code('D51.9')],
      note
    );
    expect(out.map((c) => c.code)).toEqual(['E53.8', 'D51.9']);
  });

  it('KEEPS E55.9 when its OWN evidence asserts the deficiency (insufficiency counts)', () => {
    expect(
      dropUnsupportedDeficiencyCodes(
        [codeEv('E55.9', 'Vitamin D insufficiency documented; start supplementation')],
        '## Assessment\nVitamin D insufficiency; start supplementation.'
      ).map((c) => c.code)
    ).toEqual(['E55.9']);
  });

  it('a documented deficiency VETOES the drop for the whole family (support-preserving)', () => {
    // Iron deficiency is documented; a companion prophylactic B12 code rides along
    // — conservative keep (never suppress a documented deficiency).
    const note = '## Assessment\nIron deficiency anemia. ## Plan\nB12 supplement prophylactically.';
    const out = dropUnsupportedDeficiencyCodes(
      [codeEv('E61.1', 'iron deficiency anemia'), codeEv('E53.8', 'B12 supplement prophylactically')],
      note
    );
    expect(out.map((c) => c.code)).toEqual(['E61.1', 'E53.8']);
  });

  it('never touches non-deficiency-family codes and preserves order', () => {
    const out = dropUnsupportedDeficiencyCodes(
      [code('E66.01'), code('I10'), codeEv('E63.9', 'multivitamin to prevent deficiency'), code('K76.0')],
      'Started multivitamin to prevent deficiency.'
    );
    expect(out.map((c) => c.code)).toEqual(['E66.01', 'I10', 'K76.0']);
  });

  it('empty note / empty codes are safe no-ops', () => {
    expect(dropUnsupportedDeficiencyCodes([], 'anything')).toEqual([]);
    // No evidence framing at all → ambiguous → conservative keep.
    expect(
      dropUnsupportedDeficiencyCodes([codeEv('E63.9', 'nutritional status reviewed')], '').map((c) => c.code)
    ).toEqual(['E63.9']);
  });

  it('veto still fires when an incidental exam word co-occurs in the deficiency clause (GUARD-1)', () => {
    // "Vitamin D deficiency and lower extremity weakness" — "lower" must NOT read
    // as preventive framing; the documented deficiency vetoes the family drop.
    const note = '## Assessment\nVitamin D deficiency and lower extremity weakness.\n## Plan\nB12 supplement prophylactically; monitor and reduce fall risk.';
    const out = dropUnsupportedDeficiencyCodes(
      [codeEv('E55.9', 'Vitamin D deficiency'), codeEv('E53.8', 'B12 supplement prophylactically')],
      note
    );
    expect(out.map((c) => c.code)).toEqual(['E55.9', 'E53.8']);
  });

  it('KEEPS a documented deficiency when a later negation modifies a DIFFERENT verb (negation-scope hole)', () => {
    // "B12 deficiency NOT fully corrected" — the "not" negates "corrected", not
    // the deficiency; the deficiency is real + active → E53.8 must be kept.
    const note = 'B12 deficiency not fully corrected despite repletion.';
    expect(
      dropUnsupportedDeficiencyCodes(
        [codeEv('E53.8', 'B12 deficiency not fully corrected despite repletion')],
        note
      ).map((c) => c.code)
    ).toEqual(['E53.8']);
    // Symmetric: "iron deficiency, could not tolerate oral iron" keeps E61.1.
    expect(
      dropUnsupportedDeficiencyCodes(
        [codeEv('E61.1', 'iron deficiency, could not tolerate oral iron')],
        'Iron deficiency; could not tolerate oral iron, switched to IV.'
      ).length
    ).toBe(1);
    // But a genuine resolution qualifier right after DOES defeat it (drop path):
    expect(
      dropUnsupportedDeficiencyCodes(
        [codeEv('E55.9', 'started on vitamin D supplementation')],
        'Prior vitamin D deficiency resolved; continue vitamin D supplementation.'
      ).length
    ).toBe(0);
  });

  it('does not disturb the K21.9-denial and I83.9x guards on a shared code list', () => {
    // A code list carrying all four regression families: the deficiency guard
    // only governs E50–E64 and must leave the rest for their own guards.
    const codes = [code('K21.9'), code('I83.90'), codeEv('E63.9', 'multivitamin supplement'), code('E66.01')];
    const out = dropUnsupportedDeficiencyCodes(codes, 'Started multivitamin supplement daily.');
    expect(out.map((c) => c.code)).toEqual(['K21.9', 'I83.90', 'E66.01']);
  });
});
