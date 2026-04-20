// ============================================================================
// Unit tests for T-M13 isLayerComplete
// ============================================================================

import { describe, expect, it } from 'vitest';

import {
  isLayerComplete,
  type LayerSkipState,
  type PipelineLayer,
} from '@/worker/layer-skip';

function emptyState(): LayerSkipState {
  return {
    transcriptRaw: null,
    transcriptText: null,
    speakerMap: null,
    entities: null,
    soapDraft: null,
    critique: null,
    soapFinal: null,
    icdCodes: null,
    cptCodes: null,
    rxDrafts: null,
    referrals: null,
    patientSummary: null,
  };
}

describe('isLayerComplete — all layers false on a fresh visit', () => {
  const layers: PipelineLayer[] = [
    'L1', 'L1b', 'L2', 'L3', 'L4', 'L5', 'L6',
    'L7a', 'L7b', 'L7c', 'L7d', 'L7e',
  ];

  it.each(layers)('%s is incomplete when all columns are null', (layer) => {
    expect(isLayerComplete(emptyState(), layer)).toBe(false);
  });
});

describe('isLayerComplete — per-layer column gating', () => {
  it('L1 and L1b both key off transcriptRaw', () => {
    const s = emptyState();
    expect(isLayerComplete(s, 'L1')).toBe(false);
    expect(isLayerComplete(s, 'L1b')).toBe(false);

    s.transcriptRaw = { results: { utterances: [] } };
    expect(isLayerComplete(s, 'L1')).toBe(true);
    expect(isLayerComplete(s, 'L1b')).toBe(true);
  });

  it('L2 keys off speakerMap', () => {
    const s = emptyState();
    expect(isLayerComplete(s, 'L2')).toBe(false);
    s.speakerMap = { '0': { role: 'doctor', confidence: 0.9, reasoning: '' } };
    expect(isLayerComplete(s, 'L2')).toBe(true);
  });

  it('L3 keys off entities', () => {
    const s = emptyState();
    expect(isLayerComplete(s, 'L3')).toBe(false);
    s.entities = { chief_complaint: null, hpi: null };
    expect(isLayerComplete(s, 'L3')).toBe(true);
  });

  it('L4 requires a non-empty soapDraft string', () => {
    const s = emptyState();
    s.soapDraft = '';
    expect(isLayerComplete(s, 'L4')).toBe(false);
    s.soapDraft = '   \n   ';
    expect(isLayerComplete(s, 'L4')).toBe(false);
    s.soapDraft = '## Subjective\nactual draft';
    expect(isLayerComplete(s, 'L4')).toBe(true);
  });

  it('L5 keys off critique', () => {
    const s = emptyState();
    expect(isLayerComplete(s, 'L5')).toBe(false);
    s.critique = { issues: [], overall_quality: 'high', safe_to_sign_without_review: true };
    expect(isLayerComplete(s, 'L5')).toBe(true);
  });

  it('L6 requires a non-empty soapFinal string', () => {
    const s = emptyState();
    s.soapFinal = '';
    expect(isLayerComplete(s, 'L6')).toBe(false);
    s.soapFinal = 'polished';
    expect(isLayerComplete(s, 'L6')).toBe(true);
  });

  it('L7a/b/c/d/e each gate on their own column independently', () => {
    const s = emptyState();
    s.icdCodes = { codes: [] };
    s.rxDrafts = { prescriptions: [], warnings: [] };
    expect(isLayerComplete(s, 'L7a')).toBe(true);
    expect(isLayerComplete(s, 'L7b')).toBe(false);
    expect(isLayerComplete(s, 'L7c')).toBe(true);
    expect(isLayerComplete(s, 'L7d')).toBe(false);
    expect(isLayerComplete(s, 'L7e')).toBe(false);
  });

  it('patient_summary (L7e) requires non-empty string, not just non-null', () => {
    const s = emptyState();
    s.patientSummary = '';
    expect(isLayerComplete(s, 'L7e')).toBe(false);
    s.patientSummary = 'summary for the patient';
    expect(isLayerComplete(s, 'L7e')).toBe(true);
  });
});

describe('isLayerComplete — resume scenarios', () => {
  it('mid-pipeline-failure state: L1-L3 present, L4 null — skip L1/L2/L3 only', () => {
    const s = emptyState();
    s.transcriptRaw = { results: { utterances: [{ speaker: 0 }] } };
    s.speakerMap = { '0': { role: 'doctor' } };
    s.entities = { chief_complaint: null, hpi: null };

    expect(isLayerComplete(s, 'L1')).toBe(true);
    expect(isLayerComplete(s, 'L2')).toBe(true);
    expect(isLayerComplete(s, 'L3')).toBe(true);
    expect(isLayerComplete(s, 'L4')).toBe(false);
    expect(isLayerComplete(s, 'L5')).toBe(false);
    expect(isLayerComplete(s, 'L6')).toBe(false);
  });

  it('L7 partial-failure state: L7a,c,d persisted; L7b,e cleared by catch', () => {
    const s = emptyState();
    s.icdCodes = { codes: [] };
    s.cptCodes = null;        // cleared by clearAutomationColumn after throw
    s.rxDrafts = { prescriptions: [] };
    s.referrals = { referrals: [] };
    s.patientSummary = null;  // never ran, or cleared

    expect(isLayerComplete(s, 'L7a')).toBe(true);
    expect(isLayerComplete(s, 'L7b')).toBe(false);
    expect(isLayerComplete(s, 'L7c')).toBe(true);
    expect(isLayerComplete(s, 'L7d')).toBe(true);
    expect(isLayerComplete(s, 'L7e')).toBe(false);
  });
});
