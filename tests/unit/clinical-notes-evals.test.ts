// ============================================================================
// Clinical Notes eval cases — structural validation
// ----------------------------------------------------------------------------
// Runs in CI. Does NOT hit OpenAI. Asserts that the eval-cases file at
// tests/evals/clinical-notes-phrasings.ts is well-formed so a broken case
// can't ship unnoticed (the real eval run is `npm run eval:clinical-notes`,
// which needs an API key and is triggered manually / nightly).
// ============================================================================

import { describe, it, expect } from 'vitest';

import {
  NOTE_EVAL_CASES,
  SAMPLE_NOTE,
  type NoteEvalCase,
} from '@/../tests/evals/clinical-notes-phrasings';
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

describe('Clinical Notes eval cases — structural validation', () => {
  it('has a non-empty set of cases', () => {
    expect(NOTE_EVAL_CASES.length).toBeGreaterThan(0);
  });

  it('SAMPLE_NOTE contains every section the cases reference as target_section', () => {
    const targets = new Set(
      NOTE_EVAL_CASES.map((c) => c.expected.target_section).filter(
        (t): t is string => !!t
      )
    );
    for (const target of targets) {
      expect(SAMPLE_NOTE, `SAMPLE_NOTE missing section: ${target}`).toContain(target);
    }
  });

  it('every case has a unique, stable ID', () => {
    const seen = new Set<string>();
    for (const c of NOTE_EVAL_CASES) {
      expect(c.id).toMatch(/^[a-z0-9-]+$/);
      expect(seen.has(c.id), `duplicate id: ${c.id}`).toBe(false);
      seen.add(c.id);
    }
  });

  it('every case has non-empty instruction and description', () => {
    for (const c of NOTE_EVAL_CASES) {
      expect(c.instruction.trim().length, `${c.id}: empty instruction`).toBeGreaterThan(0);
      expect(c.description.trim().length, `${c.id}: empty description`).toBeGreaterThan(0);
    }
  });

  it('every case expects a valid operation and confidence', () => {
    for (const c of NOTE_EVAL_CASES) {
      expect(VALID_OPERATIONS.has(c.expected.operation), `${c.id}: invalid operation`).toBe(true);
      expect(VALID_CONFIDENCE.has(c.expected.confidence), `${c.id}: invalid confidence`).toBe(true);
    }
  });

  it('replace cases specify replacement_text; blank/unclear cases do not', () => {
    for (const c of NOTE_EVAL_CASES) {
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

  it('unclear cases expect low confidence (the short-circuit path)', () => {
    for (const c of NOTE_EVAL_CASES) {
      if (c.expected.operation === 'unclear') {
        expect(c.expected.confidence, `${c.id}: unclear case must set confidence=low`).toBe('low');
      }
    }
  });

  it('coverage: clinical-note suite covers the operations doctors actually use', () => {
    // Clinical notes don't typically use fill_field (no labeled input fields
    // like a patient profile), so we don't require that one. But we DO want
    // coverage of the operations doctors hit on real notes.
    const coveredOps = new Set(NOTE_EVAL_CASES.map((c: NoteEvalCase) => c.expected.operation));
    for (const op of ['replace', 'blank', 'generate', 'partial_edit', 'unclear'] as EditOperation[]) {
      expect(coveredOps.has(op), `no eval case covers operation=${op}`).toBe(true);
    }
  });
});
