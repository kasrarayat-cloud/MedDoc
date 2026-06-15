// ============================================================================
// Specialty-guidance coverage check — every templateId in the shared
// catalog (except 'generic'/'unspecified') should resolve to non-empty
// guidance text. A specialty without guidance falls through to the
// generic SOAP prompt, which is correct behaviour but easy to miss
// when adding a new specialty.
// ============================================================================

import { describe, expect, it } from 'vitest';

import { SPECIALTIES, isImagingReportSpecialty } from '@meddoc/shared/specialties';
import {
  SPECIALTY_GUIDANCE,
  specialtyGuidance,
} from '../specialty-guidance';
import { ULTRASOUND_REPORT_TEMPLATE } from '../../note-templates/ultrasound-report-template';

describe('SPECIALTY_GUIDANCE', () => {
  it('every non-generic SOAP templateId has guidance text', () => {
    const missing: string[] = [];
    for (const s of SPECIALTIES) {
      if (s.templateId === 'generic') continue;
      // Imaging-report specialties (e.g. ultrasound) do NOT use the SOAP
      // SPECIALTY_GUIDANCE append — L4 routes them to the imaging report
      // template, whose study-type guidance lives in its Findings section.
      // Asserting SOAP guidance for them would require dead, never-read text.
      if (isImagingReportSpecialty(s.id)) continue;
      const text = SPECIALTY_GUIDANCE[s.templateId];
      if (!text || text.trim().length === 0) {
        missing.push(s.templateId);
      }
    }
    expect(missing).toEqual([]);
  });

  it('the ultrasound imaging report carries its own study-type guidance', () => {
    // Coverage for the imaging path: the report template's Findings section
    // holds the study-type routing (venous reflux / DVT / post-ablation / …)
    // in place of a SOAP SPECIALTY_GUIDANCE entry.
    const findings = ULTRASOUND_REPORT_TEMPLATE.sections.find(
      (s) => s.key === 'findings'
    );
    expect(findings?.styleInstructions).toContain('VENOUS REFLUX');
    expect(findings?.styleInstructions).toContain('VENOUS DVT');
    expect(findings?.styleInstructions).toContain('POST-ABLATION');
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

  it('vascular-surgery guidance branches on all five visit types', () => {
    const text = specialtyGuidance('vascular-surgery');
    // Visit-type labels — the SOAP draft is wrong without correct
    // type identification because required sections differ sharply.
    expect(text).toMatch(/OFFICE CONSULTATION/);
    expect(text).toMatch(/ENDOVASCULAR PROCEDURE/);
    expect(text).toMatch(/OPEN VASCULAR PROCEDURE/);
    expect(text).toMatch(/POST-PROCEDURE.*SURVEILLANCE|SURVEILLANCE/);
  });

  it('vascular-surgery office-consult sub-branches by chief-complaint domain', () => {
    const text = specialtyGuidance('vascular-surgery');
    expect(text).toMatch(/VENOUS/);
    expect(text).toMatch(/ARTERIAL/);
    expect(text).toMatch(/AORTIC/);
    expect(text).toMatch(/CAROTID/);
    expect(text).toMatch(/DIALYSIS ACCESS/);
  });

  it('vascular-surgery surfaces the load-bearing clinical scales', () => {
    const text = specialtyGuidance('vascular-surgery');
    // Each of these is a non-substitutable scale the L5 critique uses
    // as an anchor to flag a vascular SOAP as incomplete. Lose any
    // single one and a domain visit silently drops billable detail.
    expect(text).toMatch(/CEAP/);              // venous
    expect(text).toMatch(/Rutherford/);        // arterial PAD
    expect(text).toMatch(/Fontaine/);          // arterial PAD secondary
    expect(text).toMatch(/Ankle-Brachial Index|ABI/);
    expect(text).toMatch(/Toe-Brachial Index|TBI/);
    expect(text).toMatch(/NASCET/);            // carotid stenosis %
    expect(text).toMatch(/5\.5\s*cm|5\.0\s*cm/); // AAA repair threshold
    expect(text).toMatch(/Rule of 6s|Rule of 6/); // AV fistula maturation
    expect(text).toMatch(/endoleak|Type I-V/i);   // EVAR surveillance
  });

  it('vascular-surgery enforces cross-cutting CV-risk-factor optimization', () => {
    const text = specialtyGuidance('vascular-surgery');
    // The "absence is a documented finding" rule applies across all
    // five visit types — the L5 critique flags a vascular SOAP that
    // doesn't mention smoking-cessation / BP / LDL / DM control.
    expect(text).toMatch(/smoking cessation/i);
    expect(text).toMatch(/LDL\s*<\s*70/i);
    expect(text).toMatch(/diabetes control|A1c/i);
    expect(text).toMatch(/antiplatelet/i);
  });
});
