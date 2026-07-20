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
// so an authenticated physician can exercise the modal flow without a
// warning write. The sentinel is never an authentication bypass.
// ============================================================================

import prisma from "@meddoc/db";
import { Prisma, TranscribeVisitStatus } from "@prisma/client";
import { getSession } from "@/lib/auth";
import { logAudit } from "@/lib/audit";
import { resolveWarning, mapWorkerSeverity } from "@/lib/rx-warnings";
import { currentClinicalVisitActorWhere } from "@/lib/clinical-visit-authority";
import { canonicalSha256 } from "@/lib/template-twin/canonical";
import { TEMPLATE_TWIN_DURABLE_VISIT_EXCLUSION_WHERE } from "@/lib/template-twin/durable-visit-exclusion";
import {
  hasDurableTemplateTwinClinicalMutationProvenance,
  enqueueTemplateTwinClinicalMutationAudit,
  loadTemplateTwinClinicalMutationAdmissionTarget,
  lockAndAssertOrdinaryClinicalMutation,
  lockAndAssertTemplateTwinClinicalMutation,
  pinTemplateTwinClinicalMutation,
  TEMPLATE_TWIN_CLINICAL_MUTATION_PROVENANCE_SELECT,
  TemplateTwinClinicalMutationAuthorizationError,
  type TemplateTwinClinicalMutationClaim,
} from "@/lib/template-twin/visit-mutation-authority";

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
    // Server Actions are direct request surfaces. Authenticate before input
    // handling or the development sentinel so every branch shares the exact
    // physician process/Host/current-session boundary in getSession().
    const session = await getSession();
    if (!session) {
      return { ok: false, error: "Not signed in." };
    }

    // ── 0. Validate bounded input shape before clinical DB work ──
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

    // ── 1. Authenticated dev preview short-circuit (no warning DB write) ──
    if (input.visitId === DEV_PREVIEW_VISIT_ID) {
      return { ok: true, auditId: "dev-preview-audit" };
    }

    // ── 2. Visit ownership check ──
    // Gate from identifiers and immutable lineage before selecting persisted
    // medication warnings. This prevents a revoked Twin physician from using
    // the generic action as a clinical-data read surface.
    const authorityTarget =
      await loadTemplateTwinClinicalMutationAdmissionTarget({
        visitId: input.visitId,
        actorUserId: session.user.id,
      });
    if (!authorityTarget || authorityTarget.userId !== session.user.id) {
      return { ok: false, error: "Visit not found." };
    }
    if (authorityTarget.templateTwinSyntheticQaRun) {
      return { ok: false, error: "Visit not found." };
    }
    let templateTwinMutationClaim: TemplateTwinClinicalMutationClaim | null =
      null;
    try {
      templateTwinMutationClaim = await pinTemplateTwinClinicalMutation({
        visitId: input.visitId,
        actorUserId: session.user.id,
        admittedVisitUpdatedAt: authorityTarget.updatedAt,
        provenance: authorityTarget,
      });
    } catch (error) {
      if (error instanceof TemplateTwinClinicalMutationAuthorizationError) {
        return { ok: false, error: "Visit not found." };
      }
      throw error;
    }

    const visit = await prisma.transcribeVisit.findUnique({
      where: {
        id: input.visitId,
        ...currentClinicalVisitActorWhere(session.user.id),
        updatedAt: authorityTarget.updatedAt,
        ...(templateTwinMutationClaim
          ? {}
          : TEMPLATE_TWIN_DURABLE_VISIT_EXCLUSION_WHERE),
      },
      select: {
        userId: true,
        updatedAt: true,
        rxDrafts: true,
        status: true,
        deletedAt: true,
        archivedAt: true,
        signedAt: true,
        ...TEMPLATE_TWIN_CLINICAL_MUTATION_PROVENANCE_SELECT,
      },
    });
    if (!visit || visit.userId !== session.user.id) {
      return { ok: false, error: "Visit not found." };
    }
    if (
      Boolean(templateTwinMutationClaim) !==
      hasDurableTemplateTwinClinicalMutationProvenance(visit)
    ) {
      return { ok: false, error: "The visit changed. Reload and try again." };
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
    let created: CreatedRow | null;
    if (templateTwinMutationClaim) {
      try {
        created = await prisma.$transaction(
          async (tx: Prisma.TransactionClient) => {
            const locked = await lockAndAssertTemplateTwinClinicalMutation({
              tx,
              claim: templateTwinMutationClaim,
            });
            const lockedWarning = resolveWarning(
              locked.rxDrafts,
              input.warningId,
            );
            if (
              locked.status !== TranscribeVisitStatus.READY ||
              locked.deletedAt !== null ||
              locked.archivedAt !== null ||
              locked.signedAt !== null ||
              locked.updatedAt.getTime() !== visit.updatedAt.getTime() ||
              canonicalSha256(locked.rxDrafts ?? null) !==
                canonicalSha256(visit.rxDrafts ?? null) ||
              !lockedWarning ||
              input.severity !== mapWorkerSeverity(lockedWarning.severity)
            ) {
              return null;
            }
            const persisted = await persistRxWarningOverride({
              client: tx,
              visitId: input.visitId,
              warningId: input.warningId,
              rxLineNumber: input.rxLineNumber,
              severity: input.severity,
              headline: input.headline,
              reason: trimmedReason,
              actorUserId: session.user.id,
            });
            if (!persisted) return null;
            await enqueueTemplateTwinClinicalMutationAudit({
              tx,
              claim: templateTwinMutationClaim,
              operation: "rx_warning_override",
              action: "RX_OVERRIDE_RECORDED",
              discriminator: input.warningId,
              metadata: {
                warningId: input.warningId,
                rxLineNumber: input.rxLineNumber,
                severity: input.severity,
              },
            });
            return persisted;
          },
        );
      } catch (error) {
        if (error instanceof TemplateTwinClinicalMutationAuthorizationError) {
          return {
            ok: false,
            error: "Template Twin authorization changed. Reload and try again.",
          };
        }
        throw error;
      }
      if (!created) {
        return {
          ok: false,
          error: "The visit warnings changed. Reload and try again.",
        };
      }
    } else {
      try {
        created = await prisma.$transaction(
          async (tx: Prisma.TransactionClient) => {
            await lockAndAssertOrdinaryClinicalMutation({
              tx,
              visitId: input.visitId,
              actorUserId: session.user.id,
              admittedVisitUpdatedAt: authorityTarget.updatedAt,
              admittedPatientId: authorityTarget.patientId,
              admittedNoteTemplateId: authorityTarget.noteTemplateId,
            });
            const locked = await tx.transcribeVisit.findUnique({
              where: {
                id: input.visitId,
                AND: [currentClinicalVisitActorWhere(session.user.id)],
              },
              select: {
                status: true,
                deletedAt: true,
                archivedAt: true,
                signedAt: true,
                updatedAt: true,
                rxDrafts: true,
              },
            });
            const lockedWarning = locked
              ? resolveWarning(locked.rxDrafts, input.warningId)
              : null;
            if (
              !locked ||
              locked.status !== TranscribeVisitStatus.READY ||
              locked.deletedAt !== null ||
              locked.archivedAt !== null ||
              locked.signedAt !== null ||
              locked.updatedAt.getTime() !== visit.updatedAt.getTime() ||
              canonicalSha256(locked.rxDrafts ?? null) !==
                canonicalSha256(visit.rxDrafts ?? null) ||
              !lockedWarning ||
              input.severity !== mapWorkerSeverity(lockedWarning.severity)
            ) {
              return null;
            }
            return persistRxWarningOverride({
              client: tx,
              visitId: input.visitId,
              warningId: input.warningId,
              rxLineNumber: input.rxLineNumber,
              severity: input.severity,
              headline: input.headline,
              reason: trimmedReason,
              actorUserId: session.user.id,
            });
          },
        );
      } catch (error) {
        if (error instanceof TemplateTwinClinicalMutationAuthorizationError) {
          return {
            ok: false,
            error: "The visit changed. Reload and try again.",
          };
        }
        throw error;
      }
      if (!created) {
        return {
          ok: false,
          error: "Override write conflicted; please retry.",
        };
      }
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

type RxWarningOverrideClient = Pick<
  Prisma.TransactionClient,
  "rxWarningOverride"
>;

async function persistRxWarningOverride(input: {
  client: RxWarningOverrideClient;
  visitId: string;
  warningId: string;
  rxLineNumber: number;
  severity: string;
  headline: string;
  reason: string;
  actorUserId: string;
}): Promise<{ id: string } | null> {
  try {
    return await input.client.rxWarningOverride.create({
      data: {
        visitId: input.visitId,
        rxLineNumber: input.rxLineNumber,
        warningId: input.warningId,
        severity: input.severity,
        headline: input.headline,
        reason: input.reason,
        overriddenBy: input.actorUserId,
      },
      select: { id: true },
    });
  } catch (error: unknown) {
    // Preserve the first immutable audit row under a retry/double-click.
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    if ((error as any)?.code !== "P2002") throw error;
    return input.client.rxWarningOverride.findUnique({
      where: {
        rx_warning_overrides_visit_warning_unique: {
          visitId: input.visitId,
          warningId: input.warningId,
        },
      },
      select: { id: true },
    });
  }
}
