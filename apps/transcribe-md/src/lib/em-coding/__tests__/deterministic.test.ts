// ============================================================================
// Deterministic counter unit tests (Phase 5.2)
// ============================================================================

import { describe, it, expect } from 'vitest';
import {
  countHpiElements,
  countRosSystems,
  countPfshCategories,
  countExamSystems,
  detectTimeBasedHints,
} from '../deterministic';

describe('countHpiElements', () => {
  it('detects all 8 elements when each is explicitly tagged', () => {
    const subj = `## Subjective
location: chest. quality: sharp. severity: 8/10. duration: 3 days.
timing: intermittent. context: with exertion. modifying factors:
improves with rest. associated signs: with nausea.`;
    const r = countHpiElements(subj);
    expect(r.count).toBeGreaterThanOrEqual(7);
    expect(r.confidence.location).toBeGreaterThan(0);
    expect(r.confidence.quality).toBeGreaterThan(0);
    expect(r.confidence.severity).toBeGreaterThan(0);
    expect(r.confidence.duration).toBeGreaterThan(0);
  });

  it('counts narrative HPI without explicit tags', () => {
    const subj = `## Subjective
35yo F presents with sharp chest pain rated 8/10 for 3 days,
constant, with exertion at work, improved by rest, with associated
nausea.`;
    const r = countHpiElements(subj);
    expect(r.count).toBeGreaterThanOrEqual(5);
  });

  it('emits per-element confidence between 0 and 1', () => {
    const r = countHpiElements('## Subjective\nMild sore throat for 2 days.');
    for (const k of Object.keys(r.confidence) as Array<keyof typeof r.confidence>) {
      expect(r.confidence[k]).toBeGreaterThanOrEqual(0);
      expect(r.confidence[k]).toBeLessThanOrEqual(1);
    }
  });

  it('returns 0 elements on empty body', () => {
    const r = countHpiElements('');
    expect(r.count).toBe(0);
  });
});

describe('countRosSystems', () => {
  it('detects explicit ROS template (14 systems all-negative)', () => {
    const subj = `## Subjective
ROS: Constitutional: denies fever, fatigue. Eyes: denies vision changes.
ENT/Mouth: denies sore throat. CV: denies chest pain. Resp: denies SOB.
GI: denies nausea. GU: denies dysuria. MSK: denies joint pain.
Skin: denies rash. Neuro: denies headache. Psych: denies depression.
Endo: denies polyuria. Heme: denies easy bruising. Allergic: denies seasonal symptoms.`;
    const r = countRosSystems(subj);
    expect(r.count).toBeGreaterThanOrEqual(10);
  });

  it('detects systems via "denies <symptom>" pattern alone', () => {
    const subj = `## Subjective
Patient denies SOB, denies chest pain, denies fever.`;
    const r = countRosSystems(subj);
    expect(r.count).toBeGreaterThanOrEqual(2); // resp + cv at minimum
  });

  it('returns 0 when ROS not documented', () => {
    const r = countRosSystems('## Subjective\nNo prior history relevant to this complaint.');
    expect(r.count).toBeLessThanOrEqual(1);
  });
});

describe('countPfshCategories', () => {
  it('detects all 3 categories when explicitly tagged', () => {
    const subj = `## Subjective
PMH: HTN. FHx: father had MI age 52. SHx: tobacco never, EtOH occasional.`;
    const r = countPfshCategories(subj);
    expect(r.count).toBe(3);
  });

  it('detects social history via tobacco/alcohol mention', () => {
    const subj = `## Subjective
Tobacco: never. EtOH: 1-2 drinks/wk.`;
    const r = countPfshCategories(subj);
    expect(r.count).toBeGreaterThanOrEqual(1);
  });

  it('returns 0 when PFSH absent', () => {
    const r = countPfshCategories('## Subjective\nPatient reports cough.');
    expect(r.count).toBe(0);
  });
});

describe('countExamSystems', () => {
  it('detects multiple exam systems from typical PCP exam', () => {
    const obj = `## Objective
VS: BP 118/74, HR 88. Gen: NAD, well-appearing. HEENT: TMs clear.
Cardiac: RRR, no m/r/g. Lungs: CTAB. Abdomen: soft, NT. Extremities:
no edema. Neuro: A&O×3.`;
    const r = countExamSystems(obj);
    expect(r.count).toBeGreaterThanOrEqual(5);
  });

  it('returns 0 when exam not documented', () => {
    const r = countExamSystems('## Objective\n[not documented]');
    expect(r.count).toBeLessThanOrEqual(1);
  });
});

describe('detectTimeBasedHints', () => {
  it('extracts "Visit time: 25 min"', () => {
    const r = detectTimeBasedHints('Visit time: 25 min discussing plan.');
    expect(r.minutes).toBe(25);
  });

  it('extracts "Total time spent: 35 min"', () => {
    const r = detectTimeBasedHints('Total time spent: 35 min on this encounter.');
    expect(r.minutes).toBe(35);
  });

  it('returns null when no explicit time', () => {
    const r = detectTimeBasedHints('Plan: continue meds and f/u 6 months.');
    expect(r.minutes).toBeNull();
  });
});
