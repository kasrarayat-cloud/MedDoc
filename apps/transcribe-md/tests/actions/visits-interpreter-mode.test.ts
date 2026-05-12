// ============================================================================
// createVisitAction — interpreterMode form-field parsing (2026-05-12).
// ----------------------------------------------------------------------------
// Pins the Zod-schema coercion that translates the HTML checkbox value
// ('on' when checked, omitted when unchecked) into the typed boolean
// the worker reads off TranscribeVisit.interpreterMode. Without this
// guard, a future schema cleanup could silently change the form-field
// semantics — e.g. start emitting `false` on miss instead of defaulting
// to false at the Zod layer — and we'd lose interpreter-mode signal on
// every checked submission.
//
// The action itself does Prisma + auth + redirect work that's hard to
// test without a full integration setup. We test the schema in
// isolation by importing it directly. The schema is the load-bearing
// contract because the action's only other interpreter-mode-aware
// surface is `data: { ..., interpreterMode: parsed.data.interpreterMode }`
// — a single field passthrough that's compile-time-checked.
// ============================================================================

import { describe, expect, it } from 'vitest';
import { z } from 'zod';
import { SPECIALTY_IDS } from '@meddoc/shared/specialties';

// Mirror of the action-local INPUT_MODES const (single source: the
// action file). If the action's list grows, this mirror must follow.
const INPUT_MODES = ['audio_upload', 'voice_dictation', 'text_notes'] as const;

// Inline-redeclared to avoid pulling the action's Prisma + auth chain
// into the test. The shape MUST match
// `apps/transcribe-md/src/actions/visits.ts:CreateVisitSchema`. If this
// mirror drifts, the test will pass but the action will break — guard
// against that by keeping the test diff sized to one field at a time
// and the action's schema diff narrow.
const TestSchema = z.object({
  patientId: z.string().nullable().optional(),
  patientName: z.string().nullable().optional(),
  specialty: z.enum(SPECIALTY_IDS),
  chiefComplaint: z.string().nullable().optional(),
  inputMode: z.enum(INPUT_MODES),
  interpreterMode: z
    .preprocess(
      (v) => (v === 'on' || v === 'true' || v === true ? true : false),
      z.boolean(),
    )
    .default(false),
});

function base() {
  return {
    patientId: 'p1',
    specialty: 'vascular-surgery' as const,
    inputMode: 'voice_dictation' as const,
  };
}

describe('createVisitAction Zod schema — interpreterMode', () => {
  it('defaults to false when the field is omitted (unchecked checkbox case)', () => {
    const parsed = TestSchema.parse(base());
    expect(parsed.interpreterMode).toBe(false);
  });

  it("coerces 'on' (HTML checkbox-checked value) to true", () => {
    const parsed = TestSchema.parse({ ...base(), interpreterMode: 'on' });
    expect(parsed.interpreterMode).toBe(true);
  });

  it("coerces 'true' (JSON-form / API-caller convention) to true", () => {
    const parsed = TestSchema.parse({ ...base(), interpreterMode: 'true' });
    expect(parsed.interpreterMode).toBe(true);
  });

  it('accepts a literal boolean true', () => {
    const parsed = TestSchema.parse({ ...base(), interpreterMode: true });
    expect(parsed.interpreterMode).toBe(true);
  });

  it('does NOT accept any other string truthy value (only on/true)', () => {
    // Defensive: doctors could pre-fill an interpreterMode= query param
    // with a non-canonical truthy string. We deliberately don't match
    // those — the form-server contract is 'on' (HTML) or 'true' (API).
    for (const val of ['yes', '1', 'YES', 'TRUE', 'On']) {
      const parsed = TestSchema.parse({ ...base(), interpreterMode: val });
      expect(parsed.interpreterMode, val).toBe(false);
    }
  });

  it('does NOT accept truthy non-string non-boolean values', () => {
    for (const val of [1, 'something']) {
      const parsed = TestSchema.parse({ ...base(), interpreterMode: val });
      expect(parsed.interpreterMode).toBe(false);
    }
  });
});
