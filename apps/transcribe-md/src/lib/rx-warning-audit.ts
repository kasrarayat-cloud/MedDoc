'use server';

// ============================================================================
// Rx warning override audit (DESIGN_SPEC §4.1 critical · override audit).
// ----------------------------------------------------------------------------
// A doctor can sign past a critical Rx warning only via the
// <OverrideConfirmModal> — which submits a typed reason through this
// action. One row per override in `rx_warning_overrides`.
//
// Contract: returns a discriminated union so the caller never has to
// catch. All failure paths (unauth, bad input, not-your-visit,
// transient DB) resolve to `{ ok: false, error }` with a copy-ready
// message. Nothing throws.
//
// Dev preview route (/dev/rx-warnings) passes visitId="dev-preview"
// so the modal flow can be exercised without writing to the DB; this
// action short-circuits for that sentinel.
// ============================================================================

import prisma from '@meddoc/db';
import { getSession } from '@/lib/auth';

export interface RecordOverrideInput {
  visitId: string;
  warningId: string;
  rxLineNumber: number;
  severity: string;
  headline: string;
  reason: string;
}

export type RecordOverrideResult =
  | { ok: true; auditId: string }
  | { ok: false; error: string };

const REASON_MIN = 10;
const REASON_MAX = 500;
const DEV_PREVIEW_VISIT_ID = 'dev-preview';

export async function recordOverride(
  input: RecordOverrideInput
): Promise<RecordOverrideResult> {
  try {
    // ── 0. Validate input shape before any auth/DB work ──
    const trimmedReason = (input.reason ?? '').trim();
    if (trimmedReason.length < REASON_MIN) {
      return {
        ok: false,
        error: `Reason must be at least ${REASON_MIN} characters.`,
      };
    }
    if (input.reason.length > REASON_MAX) {
      return {
        ok: false,
        error: `Reason cannot exceed ${REASON_MAX} characters.`,
      };
    }
    if (!input.warningId || !input.headline || !input.severity) {
      return { ok: false, error: 'Missing warning metadata.' };
    }
    if (
      typeof input.rxLineNumber !== 'number' ||
      !Number.isFinite(input.rxLineNumber)
    ) {
      return { ok: false, error: 'Invalid Rx line number.' };
    }

    // ── 1. Dev preview short-circuit (no auth, no DB write) ──
    if (input.visitId === DEV_PREVIEW_VISIT_ID) {
      return { ok: true, auditId: 'dev-preview-audit' };
    }

    // ── 2. Auth + visit ownership check ──
    const session = await getSession();
    if (!session) {
      return { ok: false, error: 'Not signed in.' };
    }

    type VisitRow = { userId: string } | null;
    const visit: VisitRow = await prisma.transcribeVisit.findUnique({
      where: { id: input.visitId },
      select: { userId: true },
    });
    if (!visit || visit.userId !== session.user.id) {
      return { ok: false, error: 'Visit not found.' };
    }

    // ── 3. Write audit row ──
    type CreatedRow = { id: string };
    const created: CreatedRow = await prisma.rxWarningOverride.create({
      data: {
        visitId: input.visitId,
        rxLineNumber: input.rxLineNumber,
        warningId: input.warningId,
        severity: input.severity,
        headline: input.headline,
        reason: trimmedReason,
        overriddenBy: session.user.id,
      },
      select: { id: true },
    });

    return { ok: true, auditId: created.id };
  } catch (err) {
    console.error('[rx-warning-audit] recordOverride failed:', err);
    return {
      ok: false,
      error: 'Could not record override. Please try again.',
    };
  }
}
