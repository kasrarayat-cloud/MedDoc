// ============================================================================
// Specialty-guidance coverage check — every templateId in the shared
// catalog (except 'generic'/'unspecified') should resolve to non-empty
// guidance text. A specialty without guidance falls through to the
// generic SOAP prompt, which is correct behaviour but easy to miss
// when adding a new specialty.
// ============================================================================

import { describe, expect, it } from 'vitest';

import { SPECIALTIES } from '@meddoc/shared/specialties';
import {
  SPECIALTY_GUIDANCE,
  specialtyGuidance,
} from '../specialty-guidance';

describe('SPECIALTY_GUIDANCE', () => {
  it('every non-generic templateId has guidance text', () => {
    const missing: string[] = [];
    for (const s of SPECIALTIES) {
      if (s.templateId === 'generic') continue;
      const text = SPECIALTY_GUIDANCE[s.templateId];
      if (!text || text.trim().length === 0) {
        missing.push(s.templateId);
      }
    }
    expect(missing).toEqual([]);
  });

  it('specialtyGuidance() returns the per-specialty append', () => {
    expect(specialtyGuidance('cardiology')).toContain('NYHA');
  });

  it('specialtyGuidance() returns empty for unknown slug (safe fallback)', () => {
    expect(specialtyGuidance('martian-medicine')).toBe('');
  });

  it('weight-management guidance covers Body Composition + Behavioral + GLP-1 safety', () => {
    const text = specialtyGuidance('weight-management');
    // The L5 critique uses these substrings as "did the doctor get the
    // right scaffolding?" anchors — if the guidance drops one of these,
    // the critique misses + L7c can't enforce GLP-1 titration capture.
    expect(text).toMatch(/Body Composition/i);
    expect(text).toMatch(/BMI/i);
    expect(text).toMatch(/Behavioral Counseling/i);
    expect(text).toMatch(/dietary pattern/i);
    expect(text).toMatch(/physical[-\s]activity/i);
    expect(text).toMatch(/medullary thyroid|MEN-2/i);
    expect(text).toMatch(/pancreatitis/i);
    expect(text).toMatch(/A1c/i);
    expect(text).toMatch(/titration/i);
  });

  it('bariatric-surgery guidance branches on all three lifecycle phases', () => {
    const text = specialtyGuidance('bariatric-surgery');
    // Phase labels — the SOAP draft is wrong without correct phase
    // identification because the required sections differ per phase.
    expect(text).toMatch(/PRE-OP/);
    expect(text).toMatch(/EARLY POST-OP/);
    expect(text).toMatch(/LATE POST-OP/);
  });

  it('bariatric-surgery guidance enforces calcium citrate vs carbonate', () => {
    const text = specialtyGuidance('bariatric-surgery');
    // Bypass patients lose the acidic gastric environment that dissolves
    // carbonate — citrate is non-substitutable. The L7c Rx layer treats
    // this as a hard safety bullet so the guidance MUST surface it.
    expect(text).toMatch(/calcium citrate/i);
    expect(text).toMatch(/carbonate/i);
    expect(text).toMatch(/non-substitutable|hard safety/i);
  });

  it('bariatric-surgery covers required complication / nutritional / comorbidity screens', () => {
    const text = specialtyGuidance('bariatric-surgery');
    // Early post-op MUST screen: anastomotic leak, GI bleed, DVT,
    // dehydration, wound infection. The L5 critique flags any of these
    // missing on a POD-30 visit.
    expect(text).toMatch(/anastomotic leak/i);
    expect(text).toMatch(/DVT|PE/);
    expect(text).toMatch(/dehydration/i);
    // Late post-op nutritional + comorbidity scaffolding
    expect(text).toMatch(/B12/);
    expect(text).toMatch(/vitamin D|cholecalciferol/i);
    expect(text).toMatch(/% EWL|excess weight loss/i);
    expect(text).toMatch(/dumping syndrome/i);
    expect(text).toMatch(/T2DM|diabetes/i);
    expect(text).toMatch(/CPAP|OSA/);
    // Procedure variants — the SOAP must specify which procedure
    expect(text).toMatch(/RYGB|sleeve|gastric bypass/i);
  });
});
