// ============================================================================
// Extractors — turn signed outputs into push-request inputs (M6)
// ----------------------------------------------------------------------------
// The Sign orchestrator calls these to derive tasks + problem-list lines
// from the SOAP output. Kept heuristic + small in M6 — a future milestone
// could upgrade to a dedicated LLM extraction. Pure functions, unit-tested.
// ============================================================================

import type { SoapNote, CreateTaskItem } from '@meddoc/types';

/**
 * Heuristic task extraction (M6 D10): we don't auto-schedule anything;
 * instead we create one Task per actionable plan section so the clinician
 * has a CRM reminder to actually do it (call the lab, book the follow-up,
 * etc.). Cap at 5 tasks so one chatty plan doesn't swamp the task list.
 *
 * Referrals are NOT covered here — they push separately as Documents.
 */
const ACTIONABLE_PLAN_KEYS = [
  'follow_up',
  'diagnostics',
  'counseling',
  'physical_therapy',
  'imaging',
  'procedures_in_clinic',
] as const;

const MAX_TASKS = 5;

export function extractTasksFromSoap(
  soap: SoapNote,
  patientDisplayName: string
): CreateTaskItem[] {
  const items: CreateTaskItem[] = [];
  let idx = 0;

  for (const key of ACTIONABLE_PLAN_KEYS) {
    if (items.length >= MAX_TASKS) break;
    const value = soap.plan[key];
    if (typeof value !== 'string' || !value.trim()) continue;

    let title: string;
    switch (key) {
      case 'follow_up':
        title = `Schedule follow-up for ${patientDisplayName}`;
        break;
      case 'diagnostics':
        title = `Order diagnostics for ${patientDisplayName}`;
        break;
      case 'counseling':
        title = `Patient counseling / education — ${patientDisplayName}`;
        break;
      case 'physical_therapy':
        title = `Refer / coordinate PT for ${patientDisplayName}`;
        break;
      case 'imaging':
        title = `Order imaging for ${patientDisplayName}`;
        break;
      case 'procedures_in_clinic':
        title = `Schedule in-clinic procedure for ${patientDisplayName}`;
        break;
    }

    items.push({
      title,
      description: value.trim().slice(0, 2000),
      sourceItemIndex: idx,
    });
    idx += 1;
  }

  // If the generator surfaced a safety flag, ALWAYS land an immediate
  // follow-up task at the top of the list (psych SAFETY CLAUSE, etc.).
  // It replaces or supplements the follow_up task — separate index so
  // composite-unique idempotency stays clean.
  if (soap.requires_immediate_follow_up) {
    items.unshift({
      title: `URGENT safety follow-up for ${patientDisplayName}`,
      description:
        'SOAP flagged requires_immediate_follow_up. Review safety plan and ' +
        'confirm next contact per visit notes.',
      sourceItemIndex: idx,
    });
    // Keep total <= MAX_TASKS even after the unshift.
    if (items.length > MAX_TASKS) items.pop();
  }

  return items;
}

/**
 * Build the `problemLines` payload for the problem-list PATCH — one line
 * per SOAP assessment item. Format matches how Patient.briefHistory
 * renders in MedDoc Pro's PatientDetailClient (bulleted single-string
 * list). Idempotency is exact-string match on the MedDoc Pro side.
 */
export function extractProblemLinesFromSoap(
  soap: SoapNote,
  visitId: string,
  today: string // "yyyy-mm-dd"
): string[] {
  return soap.assessment.map((a) => {
    const desc = a.description.trim().replace(/\s+/g, ' ');
    const code = a.icd10_candidate.trim();
    return `${desc} (${code}) — from Scribe visit ${visitId} on ${today}`;
  });
}

/** Short ymd for M6 push notes. Wraps new Date so tests can stub if needed. */
export function todayYmd(now: Date = new Date()): string {
  return now.toISOString().slice(0, 10);
}
