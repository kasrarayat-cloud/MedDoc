'use server';

// ============================================================================
// Patients dashboard — 'use server' action surface (T-M17.2 Phase 3)
// ----------------------------------------------------------------------------
// Only async-function exports allowed here (Next 16). Helpers and types
// live in lib/patients-pagination.ts + lib/patients-query.ts.
// ============================================================================

import { requireSession } from '@/lib/auth';
import { fetchPatientsPage } from '@/lib/patients-query';
import type {
  PatientsCursor,
  LoadMorePatientsResult,
} from '@/lib/patients-pagination';

export async function loadMorePatientsAction(
  cursor: PatientsCursor
): Promise<LoadMorePatientsResult> {
  const session = await requireSession();
  return fetchPatientsPage(session.user.practiceId, cursor);
}
