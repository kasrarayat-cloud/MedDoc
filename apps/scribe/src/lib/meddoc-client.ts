// ============================================================================
// apps/scribe — typed client for MedDoc Pro's internal API
// ----------------------------------------------------------------------------
// Wraps the shared SCRIBE_SERVICE_TOKEN + internal URL so workers and
// route handlers don't re-implement the bearer/auth boilerplate. Every
// response is Zod-validated before it's returned to the caller — the
// network shape is the single source of truth from packages/types.
//
// Current callers:
//   - server/workers/pipeline/draft-rx.ts  (M4 — fetchClinicalSafety)
// ============================================================================

import {
  ClinicalSafetyResponseSchema,
  type ClinicalSafetyResponse,
} from '@meddoc/types';

function getInternalUrl(): string {
  return process.env.MEDDOC_PRO_INTERNAL_URL?.trim() || 'http://meddoc-pro:3000';
}

function getServiceToken(): string {
  const token = process.env.SCRIBE_SERVICE_TOKEN;
  if (!token) {
    throw new Error('SCRIBE_SERVICE_TOKEN is not set.');
  }
  return token;
}

/**
 * Fetch a patient's active medications + allergies from MedDoc Pro.
 * Used by the Rx drafter to flag interactions / duplicates / allergy
 * conflicts in the generated prescription warnings[] (spec §11 item 4,
 * M4 D4 — LLM-only check).
 */
export async function fetchClinicalSafety(
  patientId: string
): Promise<ClinicalSafetyResponse> {
  const url = `${getInternalUrl()}/api/internal/patients/${patientId}/clinical-safety`;
  const resp = await fetch(url, {
    method: 'GET',
    headers: {
      Authorization: `Bearer ${getServiceToken()}`,
      Accept: 'application/json',
    },
    // Internal-only hop — never cache on this path.
    cache: 'no-store',
  });
  if (!resp.ok) {
    const text = await resp.text().catch(() => '');
    throw new Error(
      `MedDoc Pro /clinical-safety returned ${resp.status}: ${text.slice(0, 300)}`
    );
  }
  const raw = (await resp.json()) as unknown;
  const parsed = ClinicalSafetyResponseSchema.safeParse(raw);
  if (!parsed.success) {
    throw new Error(
      `Clinical-safety response failed schema validation: ${JSON.stringify(parsed.error.issues)}`
    );
  }
  return parsed.data;
}
