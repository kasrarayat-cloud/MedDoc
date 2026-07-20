// ============================================================================
// /api/patients/[id] — read, update, soft-delete (T-M17.2 Phase 2 Commit 4)
// ----------------------------------------------------------------------------
// All three handlers 404 on mismatched practiceId (anti-enumeration,
// matches the pattern used by /api/visits/[id]/retry).
//
// Soft-delete is idempotent: DELETE on an already-deleted patient
// returns 200 without touching the row again, so repeated calls from
// a flaky client are harmless. Hard delete is intentionally not
// exposed — the DB FK from transcribe_visits uses ON DELETE RESTRICT,
// so a hard drop while visits exist would fail anyway.
// ============================================================================

import { z } from "zod";
import { NextResponse } from "next/server";

import prisma from "@meddoc/db";
import { Prisma } from "@prisma/client";

import { apiError, withApiHandler } from "@/lib/api-error";
import { getSession } from "@/lib/auth";
import { ProblemListSchema } from "@/lib/problem-list";
import { RATE_LIMITS, rateLimitOr429 } from "@/lib/rate-limit";
import { logAudit } from "@/lib/audit";
import {
  isTemplateTwinSyntheticQaPatient,
  TEMPLATE_TWIN_SYNTHETIC_QA_PATIENT_EXTERNAL_ID,
} from "@/lib/template-twin/synthetic-qa-patient";
import { aggregateTemplateTwinVisibleVisits } from "@/lib/template-twin/read-authority";
import {
  ClinicalPatientAuthorityError,
  currentClinicalPatientWhere,
  lockAndReadCurrentClinicalPatient,
  type CurrentClinicalPatientActor,
} from "@/lib/clinical-patient-authority";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

async function loadPatientForSession(
  id: string,
  actor: CurrentClinicalPatientActor,
) {
  const patient = await prisma.transcribeMdPatient.findFirst({
    where: currentClinicalPatientWhere({ actor, patientId: id }),
    select: {
      id: true,
      practiceId: true,
      name: true,
      dateOfBirth: true,
      externalId: true,
      mrn: true,
      insurance: true,
      problemList: true,
      deletedAt: true,
      createdAt: true,
      updatedAt: true,
    },
  });
  if (!patient || isTemplateTwinSyntheticQaPatient(patient)) {
    return null;
  }
  return patient;
}

export const GET = withApiHandler<{ id: string }>(
  "api:patients:get",
  async (_req, { params }) => {
    const session = await getSession();
    if (!session) return apiError("unauthorized", 401);

    const blocked = rateLimitOr429(RATE_LIMITS.PATIENT_READ, session.user.id);
    if (blocked) return blocked;

    const { id } = await params;
    const actor = {
      userId: session.user.id,
      practiceId: session.user.practiceId,
    };
    const patient = await loadPatientForSession(id, actor);
    if (!patient) return apiError("not found", 404);

    // Attach visit count + last-visit-at so the detail page doesn't
    // need a second round-trip.
    const aggregate = await aggregateTemplateTwinVisibleVisits({
      db: prisma,
      actorUserId: session.user.id,
      scope: {
        patientId: patient.id,
        deleted: "active",
        archived: "active",
      },
    });

    // Round 3 PR-C — §164.312(b) PHI-read audit (A05-P0-004).
    void logAudit({
      action: "VIEWED_PATIENT_FILE",
      targetId: patient.id,
      targetType: "TranscribeMdPatient",
      metadata: { source: "api:GET /api/patients/[id]" },
    });

    return NextResponse.json({
      patient: {
        id: patient.id,
        name: patient.name,
        dateOfBirth: patient.dateOfBirth,
        externalId: patient.externalId,
        mrn: patient.mrn,
        insurance: patient.insurance,
        problemList: patient.problemList,
        createdAt: patient.createdAt,
        updatedAt: patient.updatedAt,
        visitCount: aggregate.count,
        lastVisitAt: aggregate.maxCreatedAt,
      },
    });
  },
);

const UpdateBodySchema = z.object({
  name: z.string().trim().min(1).max(200).optional(),
  /** Pass null to clear a previously-set DOB (e.g. typo correction);
   *  pass a string to set/update it; omit to leave unchanged. */
  dateOfBirth: z
    .union([
      z
        .string()
        .min(1)
        .refine((s) => !Number.isNaN(Date.parse(s)), {
          message: "Invalid date",
        }),
      z.null(),
    ])
    .optional(),
  externalId: z
    .union([z.string().trim().max(100), z.null()])
    .optional()
    .transform((v) => {
      if (v === undefined) return undefined;
      if (v === null) return null;
      return v.length === 0 ? null : v;
    }),
  mrn: z
    .union([z.string().trim().max(50), z.null()])
    .optional()
    .transform((v) => {
      if (v === undefined) return undefined;
      if (v === null) return null;
      return v.length === 0 ? null : v;
    }),
  insurance: z
    .union([z.string().trim().max(200), z.null()])
    .optional()
    .transform((v) => {
      if (v === undefined) return undefined;
      if (v === null) return null;
      return v.length === 0 ? null : v;
    }),
  /** Full-array replace. Caller sends the complete post-edit list;
   *  server treats it as truth. `null` clears the list. */
  problemList: z.union([ProblemListSchema, z.null()]).optional(),
});

export const PATCH = withApiHandler<{ id: string }>(
  "api:patients:update",
  async (req, { params }) => {
    const session = await getSession();
    if (!session) return apiError("unauthorized", 401);

    const blocked = rateLimitOr429(RATE_LIMITS.PATIENT_OPS, session.user.id);
    if (blocked) return blocked;

    const { id } = await params;
    let body: unknown;
    try {
      body = await req.json();
    } catch {
      return apiError("invalid JSON body", 400);
    }
    const parsed = UpdateBodySchema.safeParse(body);
    if (!parsed.success) {
      const first = parsed.error.issues[0];
      const field = first?.path.join(".") || "_form";
      return NextResponse.json(
        { error: first?.message || "invalid payload", field },
        { status: 400 },
      );
    }
    if (
      parsed.data.externalId === TEMPLATE_TWIN_SYNTHETIC_QA_PATIENT_EXTERNAL_ID
    ) {
      return apiError("invalid external ID", 400);
    }

    // Build the update payload from only the fields the caller sent.
    // Touching every field on every PATCH would also bump updatedAt
    // spuriously and would mask "what changed?" in audit logs later.
    const data: {
      name?: string;
      dateOfBirth?: Date | null;
      externalId?: string | null;
      mrn?: string | null;
      insurance?: string | null;
      problemList?: Prisma.NullableJsonNullValueInput | Prisma.InputJsonValue;
    } = {};
    if (parsed.data.name !== undefined) data.name = parsed.data.name;
    if (parsed.data.dateOfBirth !== undefined) {
      data.dateOfBirth =
        parsed.data.dateOfBirth === null
          ? null
          : new Date(parsed.data.dateOfBirth);
    }
    if (parsed.data.externalId !== undefined) {
      data.externalId = parsed.data.externalId;
    }
    if (parsed.data.mrn !== undefined) data.mrn = parsed.data.mrn;
    if (parsed.data.insurance !== undefined) {
      data.insurance = parsed.data.insurance;
    }
    if (parsed.data.problemList !== undefined) {
      data.problemList =
        parsed.data.problemList === null
          ? Prisma.DbNull
          : parsed.data.problemList;
    }

    if (Object.keys(data).length === 0) {
      return NextResponse.json(
        { error: "No fields to update.", field: "_form" },
        { status: 400 },
      );
    }

    const actor = {
      userId: session.user.id,
      practiceId: session.user.practiceId,
    };
    try {
      const updated = await prisma.$transaction(
        async (tx: Prisma.TransactionClient) => {
          const existing = await lockAndReadCurrentClinicalPatient({
            tx,
            actor,
            patientId: id,
          });
          if (!existing) return null;

          const write = await tx.transcribeMdPatient.updateMany({
            where: {
              ...currentClinicalPatientWhere({ actor, patientId: id }),
              updatedAt: existing.updatedAt,
            },
            data,
          });
          if (write.count !== 1) return null;

          return tx.transcribeMdPatient.findFirst({
            where: currentClinicalPatientWhere({ actor, patientId: id }),
            select: {
              id: true,
              name: true,
              dateOfBirth: true,
              externalId: true,
              mrn: true,
              insurance: true,
              problemList: true,
              updatedAt: true,
            },
          });
        },
      );
      if (!updated) return apiError("not found", 404);

      void logAudit({
        action: "TM_PATIENT_UPDATED",
        targetType: "TranscribeMdPatient",
        targetId: updated.id,
        metadata: {
          changedFields: Object.keys(data),
        },
      });

      return NextResponse.json({ patient: updated });
    } catch (error) {
      if (error instanceof ClinicalPatientAuthorityError) {
        return apiError("not found", 404);
      }
      throw error;
    }
  },
);

export const DELETE = withApiHandler<{ id: string }>(
  "api:patients:delete",
  async (_req, { params }) => {
    const session = await getSession();
    if (!session) return apiError("unauthorized", 401);

    const blocked = rateLimitOr429(RATE_LIMITS.PATIENT_OPS, session.user.id);
    if (blocked) return blocked;

    const { id } = await params;
    const actor = {
      userId: session.user.id,
      practiceId: session.user.practiceId,
    };
    try {
      const result = await prisma.$transaction(
        async (tx: Prisma.TransactionClient) => {
          // includeDeleted:true preserves idempotent repeated DELETE while the
          // same actor/practice/reserved-marker authority is still current.
          const existing = await lockAndReadCurrentClinicalPatient({
            tx,
            actor,
            patientId: id,
            includeDeleted: true,
          });
          if (!existing) return null;
          if (existing.deletedAt !== null) {
            return { kind: "already-deleted" as const, id: existing.id };
          }

          const write = await tx.transcribeMdPatient.updateMany({
            where: {
              ...currentClinicalPatientWhere({ actor, patientId: id }),
              updatedAt: existing.updatedAt,
            },
            data: { deletedAt: new Date() },
          });
          return write.count === 1
            ? { kind: "deleted" as const, id: existing.id }
            : null;
        },
      );
      if (!result) return apiError("not found", 404);
      if (result.kind === "already-deleted") {
        return NextResponse.json({ ok: true, alreadyDeleted: true });
      }

      void logAudit({
        action: "TM_PATIENT_DELETED",
        targetType: "TranscribeMdPatient",
        targetId: result.id,
        metadata: { mode: "soft" },
      });

      return NextResponse.json({ ok: true });
    } catch (error) {
      if (error instanceof ClinicalPatientAuthorityError) {
        return apiError("not found", 404);
      }
      throw error;
    }
  },
);
