// ============================================================================
// Ultrasound imaging-report prompt — structural coverage (no AI spend).
// Proves the report type is a NON-SOAP imaging report with the Tier-1 venous
// frameworks + measurement/laterality discipline, and that it validates
// through the SAME (section-label-driven) structure validator.
// ============================================================================

import { describe, expect, it } from 'vitest';

import { buildUltrasoundSystemPrompt } from '../build-ultrasound-prompt';
import { ULTRASOUND_REPORT_TEMPLATE } from '../ultrasound-report-template';
import { requiredSectionLabels, type ResolvedNoteTemplate } from '../build-soap-prompt';
import { validateSoapStructure } from '../../layers/soap-structure-validator';

const OPTS = {
  specialty: 'ultrasound',
  audioQualityAlert: null,
  interpreterAlert: null,
  specialtyGuidanceText: null,
};

describe('buildUltrasoundSystemPrompt', () => {
  const prompt = buildUltrasoundSystemPrompt(
    ULTRASOUND_REPORT_TEMPLATE as ResolvedNoteTemplate,
    OPTS
  );

  it('is an IMAGING REPORT, not a SOAP note', () => {
    for (const h of ['## Exam', '## Indication', '## Technique', '## Comparison', '## Findings', '## Impression']) {
      expect(prompt).toContain(h);
    }
    // The SOAP scaffold must NOT be present.
    expect(prompt).not.toContain('## Subjective');
    expect(prompt).not.toContain('## Assessment');
    expect(prompt).not.toContain('writing a SOAP note');
    expect(prompt).toContain('IMAGING REPORT');
  });

  it('carries the Tier-1 venous study frameworks accurately', () => {
    expect(prompt).toContain('VENOUS REFLUX');
    expect(prompt).toContain('VENOUS DVT');
    expect(prompt).toContain('POST-ABLATION');
    // Reflux-time conventions (superficial >0.5s, femoropopliteal >1.0s).
    expect(prompt).toContain('> 0.5 s');
    expect(prompt).toContain('> 1.0 s');
    // Segments + measurement units.
    expect(prompt).toMatch(/Common Femoral Vein|CFV/);
    expect(prompt).toMatch(/Great Saphenous Vein|GSV/);
    expect(prompt).toContain('saphenofemoral junction');
    expect(prompt).toContain('EHIT');
    expect(prompt).toContain('diameter (mm)');
  });

  it('reuses the anti-hallucination rules + adds measurement/laterality discipline', () => {
    // Reused verbatim from the SOAP safety layer.
    expect(prompt).toContain('[unclear in recording]');
    // Imaging-specific discipline.
    expect(prompt).toContain('MEASUREMENTS ARE SACRED');
    expect(prompt).toContain('LATERALITY IS SACRED');
    expect(prompt).toContain('Output ONLY the ultrasound report markdown');
  });

  it('validates through the section-label structure validator', () => {
    const labels = requiredSectionLabels(ULTRASOUND_REPORT_TEMPLATE as ResolvedNoteTemplate);
    expect(labels).toEqual(['Exam', 'Indication', 'Technique', 'Comparison', 'Findings', 'Impression']);
    const sampleReport = [
      '## Exam',
      'Venous Duplex Ultrasound — Bilateral Lower Extremities — Reflux',
      '## Indication',
      'Leg heaviness and varicosities.',
      '## Technique',
      'B-mode, color, spectral Doppler; reverse Trendelenburg.',
      '## Comparison',
      'No prior study available for comparison.',
      '## Findings',
      '### Right\nGSV 6.1 mm at SFJ, reflux 3.2 s.',
      '## Impression',
      '1. Incompetent right GSV.',
    ].join('\n\n');
    const v = validateSoapStructure(sampleReport, labels);
    expect(v.ok).toBe(true);
  });
});
