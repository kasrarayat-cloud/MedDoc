// ============================================================================
// Doc Editor eval cases — structural validation
// ----------------------------------------------------------------------------
// Runs in CI. Does NOT hit OpenAI. Just asserts that the eval-cases file at
// tests/evals/doc-editor-phrasings.ts is well-formed so a broken case can't
// ship unnoticed (the real eval run is `npm run eval:doc-editor`, which
// needs an API key and is triggered manually / nightly).
// ============================================================================

import { describe, it, expect } from 'vitest';

import { EVAL_CASES, SAMPLE_DOC, type EvalCase } from '@/../tests/evals/doc-editor-phrasings';
import type { EditOperation } from '@/lib/ai-service';

const VALID_OPERATIONS = new Set<EditOperation>([
  'replace',
  'blank',
  'generate',
  'partial_edit',
  'fill_field',
  'unclear',
]);

const VALID_CONFIDENCE = new Set(['high', 'medium', 'low']);

describe('Doc Editor eval cases — structural validation', () => {
  it('has a non-empty set of cases', () => {
    expect(EVAL_CASES.length).toBeGreaterThan(0);
  });

  it('SAMPLE_DOC contains every section the cases reference as target_section', () => {
    // Sanity: if a case targets "BRIEF HISTORY", the sample doc should have
    // that label so the parser has something to match. Stops us from
    // authoring eval cases against sections the doc doesn't declare.
    const targets = new Set(
      EVAL_CASES.map((c) => c.expected.target_section).filter(
        (t): t is string => !!t
      )
    );
    for (const target of targets) {
      expect(SAMPLE_DOC, `SAMPLE_DOC missing section: ${target}`).toContain(target);
    }
  });

  it('every case has a unique, stable ID', () => {
    const seen = new Set<string>();
    for (const c of EVAL_CASES) {
      expect(c.id).toMatch(/^[a-z0-9-]+$/);
      expect(seen.has(c.id), `duplicate id: ${c.id}`).toBe(false);
      seen.add(c.id);
    }
  });

  it('every case has non-empty instruction and description', () => {
    for (const c of EVAL_CASES) {
      expect(c.instruction.trim().length, `${c.id}: empty instruction`).toBeGreaterThan(0);
      expect(c.description.trim().length, `${c.id}: empty description`).toBeGreaterThan(0);
    }
  });

  it('every case expects a valid operation and confidence', () => {
    for (const c of EVAL_CASES) {
      expect(VALID_OPERATIONS.has(c.expected.operation), `${c.id}: invalid operation`).toBe(true);
      expect(VALID_CONFIDENCE.has(c.expected.confidence), `${c.id}: invalid confidence`).toBe(true);
    }
  });

  it('replace cases specify replacement_text; blank/unclear cases do not', () => {
    for (const c of EVAL_CASES) {
      if (c.expected.operation === 'replace') {
        expect(c.expected.replacement_text, `${c.id}: replace case must specify replacement_text`).toBeDefined();
      }
      if (c.expected.operation === 'blank' || c.expected.operation === 'unclear') {
        expect(
          c.expected.replacement_text,
          `${c.id}: ${c.expected.operation} case must not specify replacement_text`
        ).toBeUndefined();
      }
    }
  });

  it('fill_field cases specify fill_fields', () => {
    for (const c of EVAL_CASES) {
      if (c.expected.operation === 'fill_field') {
        expect(c.expected.fill_fields, `${c.id}: fill_field case must specify fill_fields`).toBeDefined();
        expect(c.expected.fill_fields!.length, `${c.id}: fill_fields must be non-empty`).toBeGreaterThan(0);
      }
    }
  });

  it('unclear cases expect low confidence (they are the short-circuit cases)', () => {
    for (const c of EVAL_CASES) {
      if (c.expected.operation === 'unclear') {
        expect(c.expected.confidence, `${c.id}: unclear case must set confidence=low`).toBe('low');
      }
    }
  });

  it('coverage: at least one case per operation type', () => {
    const coveredOps = new Set(EVAL_CASES.map((c: EvalCase) => c.expected.operation));
    for (const op of VALID_OPERATIONS) {
      expect(coveredOps.has(op), `no eval case covers operation=${op}`).toBe(true);
    }
  });
});
