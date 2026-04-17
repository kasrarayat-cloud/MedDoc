// ============================================================================
// M6 — Pure extractors for task + problem-list derivation
// ----------------------------------------------------------------------------
// Lock the heuristic extraction behavior. The Sign orchestrator calls
// these, then ships results to the MedDoc Pro internal endpoints.
// Tests live in the meddoc-pro vitest harness because that's where all
// scribe-adjacent unit tests already run.
// ============================================================================

import { describe, it, expect } from 'vitest';
import type { SoapNote } from '@meddoc/types';
import {
  extractTasksFromSoap,
  extractProblemLinesFromSoap,
  todayYmd,
} from '../../../scribe/src/server/push/extractors';

const baseSoap: SoapNote = {
  confidence: 'medium',
  subjective: { chief_complaint: 'Hypertension follow-up.' },
  objective: { vitals: 'BP 148/92.' },
  assessment: [
    {
      icd10_candidate: 'I10',
      description: 'Essential hypertension.',
      evidence_quote: 'BP 148 over 92',
      confidence: 'high',
    },
  ],
  plan: {
    follow_up: 'See back in 6 weeks for BP check.',
    diagnostics: 'BMP and A1c today.',
    medications: 'Increase lisinopril to 20 mg daily.',
  },
  missing_required_elements: [],
  ambiguities: [],
};

describe('extractTasksFromSoap', () => {
  it('creates one task per actionable plan key (follow_up + diagnostics)', () => {
    const tasks = extractTasksFromSoap(baseSoap, 'Jane Doe');
    const titles = tasks.map((t) => t.title);
    expect(titles).toEqual(
      expect.arrayContaining([
        'Schedule follow-up for Jane Doe',
        'Order diagnostics for Jane Doe',
      ])
    );
    // medications is NOT an actionable key — Rx pushes its own rows.
    expect(titles).not.toContain('Schedule medications for Jane Doe');
  });

  it('caps at 5 tasks even when plan has many actionable sections', () => {
    const busy: SoapNote = {
      ...baseSoap,
      plan: {
        follow_up: 'x',
        diagnostics: 'x',
        counseling: 'x',
        physical_therapy: 'x',
        imaging: 'x',
        procedures_in_clinic: 'x',
      },
    };
    expect(extractTasksFromSoap(busy, 'Jane Doe')).toHaveLength(5);
  });

  it('returns an empty array when plan has no actionable keys', () => {
    const quiet: SoapNote = {
      ...baseSoap,
      plan: { medications: 'Continue current regimen.' },
    };
    expect(extractTasksFromSoap(quiet, 'Jane Doe')).toEqual([]);
  });

  it('assigns sequential sourceItemIndex values (composite unique)', () => {
    const tasks = extractTasksFromSoap(baseSoap, 'Jane Doe');
    const indexes = tasks.map((t) => t.sourceItemIndex);
    expect(new Set(indexes).size).toBe(indexes.length);
    expect(indexes.every((i) => Number.isInteger(i) && i >= 0)).toBe(true);
  });

  it('adds an URGENT task at the top when requires_immediate_follow_up is set', () => {
    const psychSoap: SoapNote = {
      ...baseSoap,
      plan: { follow_up: 'Follow up in 3 days.' },
      requires_immediate_follow_up: true,
    };
    const tasks = extractTasksFromSoap(psychSoap, 'Jane Doe');
    expect(tasks[0].title).toContain('URGENT safety follow-up');
    // Still within the 5-task cap after the unshift.
    expect(tasks.length).toBeLessThanOrEqual(5);
  });

  it('truncates descriptions to protect the internal-API max-length', () => {
    const huge: SoapNote = {
      ...baseSoap,
      plan: { follow_up: 'x'.repeat(3000) },
    };
    const t = extractTasksFromSoap(huge, 'Jane Doe')[0];
    expect((t.description ?? '').length).toBeLessThanOrEqual(2000);
  });
});

describe('extractProblemLinesFromSoap', () => {
  it('formats each assessment item with code, description, provenance', () => {
    const lines = extractProblemLinesFromSoap(baseSoap, 'v_abc', '2026-04-17');
    expect(lines).toHaveLength(1);
    expect(lines[0]).toBe(
      'Essential hypertension. (I10) — from Scribe visit v_abc on 2026-04-17'
    );
  });

  it('returns an empty array when there are no assessment items', () => {
    const empty: SoapNote = { ...baseSoap, assessment: [] };
    expect(extractProblemLinesFromSoap(empty, 'v1', '2026-04-17')).toEqual([]);
  });

  it('normalises whitespace in descriptions so duplicates can dedupe', () => {
    const weird: SoapNote = {
      ...baseSoap,
      assessment: [
        {
          icd10_candidate: 'I10',
          description: '  Essential   hypertension.\n  ',
          evidence_quote: 'q',
          confidence: 'medium',
        },
      ],
    };
    const lines = extractProblemLinesFromSoap(weird, 'v1', '2026-04-17');
    expect(lines[0]).toBe(
      'Essential hypertension. (I10) — from Scribe visit v1 on 2026-04-17'
    );
  });
});

describe('todayYmd', () => {
  it('produces a stable 10-char yyyy-mm-dd string', () => {
    const fixed = new Date('2026-04-17T14:05:00Z');
    expect(todayYmd(fixed)).toBe('2026-04-17');
  });
});
