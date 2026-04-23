// ============================================================================
// Problem list shape (Gate 1 schema comment, Gate 7 UI).
// ----------------------------------------------------------------------------
// TranscribeMdPatient.problemList is a Json? column. The client UI, the
// server PATCH validator, and any future rendering code all read from
// this file so they can't drift.
// ============================================================================

import { z } from 'zod';

export const ProblemStatusValues = ['active', 'resolved', 'chronic'] as const;
export type ProblemStatus = (typeof ProblemStatusValues)[number];

export const ProblemListItemSchema = z.object({
  condition: z.string().trim().min(1).max(200),
  status: z.enum(ProblemStatusValues),
  icd10: z
    .string()
    .trim()
    .max(20)
    .optional()
    .transform((v) => (v && v.length > 0 ? v : undefined)),
});

export type ProblemListItem = z.infer<typeof ProblemListItemSchema>;

/** Cap at 50 — a reasonable guardrail that still covers complex
 *  comorbid patients. Prevents a runaway client from posting 10MB
 *  of JSON. */
export const ProblemListSchema = z.array(ProblemListItemSchema).max(50);

/** Safe parse a value coming from JSONB — returns [] on any shape
 *  mismatch so a corrupted row doesn't crash the page. */
export function parseProblemList(raw: unknown): ProblemListItem[] {
  if (!Array.isArray(raw)) return [];
  const parsed = ProblemListSchema.safeParse(raw);
  return parsed.success ? parsed.data : [];
}

export function statusLabel(status: ProblemStatus): string {
  switch (status) {
    case 'active':
      return 'Active';
    case 'resolved':
      return 'Resolved';
    case 'chronic':
      return 'Chronic';
  }
}

/** Chip tone mapping for the patient header problem list display. */
export function statusTone(status: ProblemStatus): 'amber' | 'mint' | 'accent' {
  switch (status) {
    case 'active':
      return 'amber';
    case 'resolved':
      return 'mint';
    case 'chronic':
      return 'accent';
  }
}
