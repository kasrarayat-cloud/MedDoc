"use server";

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

import prisma from "@meddoc/db";
import { getSession } from "@/lib/auth";
import { logAudit } from "@/lib/audit";
import { resolveWarning, mapWorkerSeverity } from "@/lib/rx-warnings";

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
const DEV_PREVIEW_VISIT_ID = "dev-preview";

export async function recordOverride(
  input: RecordOverrideInput,
): Promise<RecordOverrideResult> {
  try {
    // ── 0. Validate input shape before any auth/DB work ──
    const trimmedReason = (input.reason ?? "").trim();
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
      return { ok: false, error: "Missing warning metadata." };
    }
    if (
      typeof input.rxLineNumber !== "number" ||
      !Number.isFinite(input.rxLineNumber)
    ) {
      return { ok: false, error: "Invalid Rx line number." };
    }

    // ── 1. Dev preview short-circuit (no auth, no DB write) ──
    if (input.visitId === DEV_PREVIEW_VISIT_ID) {
      return { ok: true, auditId: "dev-preview-audit" };
    }

    // ── 2. Auth + visit ownership check ──
    const session = await getSession();
    if (!session) {
      return { ok: false, error: "Not signed in." };
    }

    type VisitRow = {
      userId: string;
      rxDrafts: unknown;
      templateTwinSyntheticQaRun?: { id: string } | null;
    } | null;
    const visit: VisitRow = await prisma.transcribeVisit.findUnique({
      where: { id: input.visitId },
      select: {
        userId: true,
        rxDrafts: true,
        templateTwinSyntheticQaRun: { select: { id: true } },
      },
    });
    if (!visit || visit.userId !== session.user.id) {
      return { ok: false, error: "Visit not found." };
    }
    // Staging facts and warnings are immutable outputs of the bounded mock
    // pipeline. A generic override would create an unpinned clinical mutation
    // outside the synthetic run's rollout/attempt contract.
    if (visit.templateTwinSyntheticQaRun) {
      return { ok: false, error: "Visit not found." };
    }

    // ── 2.5 Correlate the override to a REAL warning ──
    // fix/rx-override-gate-correlation: the client supplies warningId +
    // severity, but they MUST NOT be trusted verbatim into a clinical-safety
    // audit row. Resolve the submitted warningId against the visit's persisted
    // rxDrafts.warnings[]; reject if it names no real warning, or if the
    // claimed severity doesn't match the warning's server-derived severity.
    // This is what stops a caller minting fabricated 'critical' override rows
    // (distinct bogus warningIds) to inflate the sign-gate's count.
    const warning = resolveWarning(visit.rxDrafts, input.warningId);
    if (!warning) {
      return {
        ok: false,
        error: "That warning is not on this visit.",
      };
    }
    if (input.severity !== mapWorkerSeverity(warning.severity)) {
      return {
        ok: false,
        error: "Warning severity does not match this visit.",
      };
    }

    // ── 3. Write audit row ──
    // Round 3 PR-E (A09-P0-001) — idempotent on (visitId, warningId).
    // Same warning re-clicked or network-retried produces the SAME
    // audit row (the original one), not a new dupe that would inflate
    // the sign-gate's distinct-warning count and let an actual
    // unanswered warning slip through. The compound unique key is
    // enforced at the DB layer; we catch P2002 instead of using upsert
    // so we PRESERVE the original `overriddenAt` + `reason` (audit-
    // trail integrity) rather than overwrite with the second-click
    // data.
    type CreatedRow = { id: string };
    let created: CreatedRow;
    try {
      created = await prisma.rxWarningOverride.create({
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
    } catch (err: unknown) {
      // P2002 = Prisma unique-constraint violation. Treat as
      // idempotent: fetch the existing row and return its id. Any
      // other error re-throws into the outer try/catch.
      // eslint-disable-next-line @typescript-eslint/no-explicit-any
      const code = (err as any)?.code;
      if (code !== "P2002") throw err;
      const existing = await prisma.rxWarningOverride.findUnique({
        where: {
          rx_warning_overrides_visit_warning_unique: {
            visitId: input.visitId,
            warningId: input.warningId,
          },
        },
        select: { id: true },
      });
      if (!existing) {
        return {
          ok: false,
          error: "Override write conflicted; please retry.",
        };
      }
      created = existing;
    }

    // HIPAA audit row. The domain-specific `rx_warning_overrides`
    // table is the clinical-safety record; `audit_logs` is the
    // platform-wide record. Both are written — compliance tooling
    // can query either.
    void logAudit({
      action: "RX_OVERRIDE_RECORDED",
      targetType: "TranscribeVisit",
      targetId: input.visitId,
      metadata: {
        warningId: input.warningId,
        rxLineNumber: input.rxLineNumber,
        severity: input.severity,
        // headline + reason are doctor-authored and pass the 10-char
        // minimum; they're PHI-adjacent (may quote drug names) —
        // record their LENGTHS only, not their contents.
        headlineLength: input.headline.length,
        reasonLength: trimmedReason.length,
      },
    });

    return { ok: true, auditId: created.id };
  } catch (err) {
    console.error("[rx-warning-audit] recordOverride failed:", err);
    return {
      ok: false,
      error: "Could not record override. Please try again.",
    };
  }
}
