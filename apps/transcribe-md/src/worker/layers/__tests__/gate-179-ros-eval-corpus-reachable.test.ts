/**
 * ⚠️ THE PARITY EVAL'S GROUND TRUTH MUST BE REACHABLE BY THE LEXICON IT
 * MEASURES — OR IT SCORES EVERY MODEL AGAINST AN IMPOSSIBLE TARGET.
 *
 * `l3-model-parity` matched its expectations against the emitted `finding`,
 * which #179 turned into a CLOSED-LEXICON TOKEN. The expectations were still
 * written as prose fragments and compared by substring. Measured, 3 of 8 ROS
 * rows could never score on ANY model:
 *
 *   'chest pain'  vs  chest_pain     — the SPACE never matches
 *   'breath'      vs  dyspnea        — no character in common
 *   'blood'       vs  hematochezia   — likewise
 *
 * and a fourth, 'weight', matched TWO tokens (`weight_loss`, `weight_gain`), so
 * it could score on the wrong one.
 *
 * ⚠️ THE DIRECTION OF THE ERROR IS WHAT MAKES THIS MORE THAN TIDINESS. The eval
 * reported a score WORSE than reality, equally on both models — so it could not
 * have flagged a regression, and it could have condemned a model that was
 * extracting perfectly. A harness that cannot be satisfied is not a
 * conservative harness; it is a broken instrument that reads as a strict one.
 *
 * ⚠️ AND NOTHING COULD CHECK IT BEFORE, BY CONSTRUCTION: importing the eval ran
 * its top-level IIFE and attempted twelve live model calls. The corpus is now a
 * side-effect-free module, which is the only reason this arm can exist.
 */
import { describe, it, expect } from 'vitest';
import { CASES } from '../../../../scripts/eval/l3-model-parity-cases';
import { ROS_LEXICON, symptomsFor, ROS_SYSTEMS } from '@/lib/template-twin/ros-lexicon';

describe('the L3 parity corpus is satisfiable by the shipped lexicon', () => {
  const rosRows = CASES.flatMap((c) => c.expected.ros.map((r) => ({ case: c.name, ...r })));

  it('NON-VACUITY: the corpus carries ROS expectations at all', () => {
    // Without this, "every row is reachable" is satisfied by an empty corpus —
    // and an empty corpus is exactly what a careless extraction would leave.
    expect(CASES.length).toBeGreaterThanOrEqual(5);
    expect(rosRows.length).toBeGreaterThanOrEqual(6);
  });

  it('⚠️ every expected ROS finding is a REAL token of its own system', () => {
    const unreachable = rosRows
      .filter((r) => !symptomsFor(r.system).includes(r.finding))
      .map((r) => `${r.case}: ${r.system}.${r.finding}`);
    expect(
      unreachable,
      `expectations no model could ever satisfy: ${unreachable.join('; ')}`,
    ).toEqual([]);
  });

  it('every expected system is a real lexicon system', () => {
    const unknown = rosRows.filter((r) => !ROS_SYSTEMS.includes(r.system)).map((r) => r.system);
    expect(unknown, `systems absent from the lexicon: ${unknown.join(', ')}`).toEqual([]);
  });

  it('⚠️ and each expectation identifies exactly ONE token, so a hit is unambiguous', () => {
    // `weight` matched both `weight_loss` and `weight_gain`. Exact matching
    // makes that impossible by construction, and this asserts the property
    // rather than trusting the operator to have changed.
    for (const r of rosRows) {
      const matches = symptomsFor(r.system).filter((t) => t === r.finding);
      expect(matches.length, `${r.system}.${r.finding} should match exactly one token`).toBe(1);
    }
  });

  it('DISCRIMINATION: the arm rejects the prose forms that used to be here', () => {
    // Every arm above passes against a corpus of arbitrary strings if
    // `symptomsFor` were permissive. These are the four values the corpus
    // actually carried, and each must be refused by the same predicate.
    for (const [system, prose] of [
      ['cardiovascular', 'chest pain'],
      ['respiratory', 'breath'],
      ['gastrointestinal', 'blood'],
    ] as Array<[string, string]>) {
      expect(symptomsFor(system).includes(prose), `${system}.${prose}`).toBe(false);
    }
    // ...and the corrected values ARE accepted, so the predicate is not simply
    // refusing everything.
    expect(ROS_LEXICON.cardiovascular.includes('chest_pain')).toBe(true);
    expect(ROS_LEXICON.respiratory.includes('dyspnea')).toBe(true);
  });
});
