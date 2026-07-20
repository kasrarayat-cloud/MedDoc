"use server";

// ============================================================================
// Patients dashboard — 'use server' action surface (T-M17.2 Phase 3)
// ----------------------------------------------------------------------------
// Only async-function exports allowed here (Next 16). Helpers and types
// live in lib/patients-pagination.ts + lib/patients-query.ts.
// ============================================================================

import prisma from "@meddoc/db";
import { Prisma, type TranscribeVisitStatus } from "@prisma/client";
import { requireSession } from "@/lib/auth";
import { fetchPatientsPage } from "@/lib/patients-query";
import type {
  PatientsCursor,
  LoadMorePatientsResult,
} from "@/lib/patients-pagination";
import {
  C3_PATIENTS_PAGE_SIZE,
  type C3PatientsCursor,
  type C3PatientsPage,
} from "@/lib/c3-list-pagination";
import {
  countTemplateTwinVisibleVisitsByPatient,
  readLatestTemplateTwinVisibleVisitByPatient,
} from "@/lib/template-twin/read-authority";
import { currentClinicalPatientCollectionWhere } from "@/lib/clinical-patient-authority";

export async function loadMorePatientsAction(
  cursor: PatientsCursor,
): Promise<LoadMorePatientsResult> {
  const session = await requireSession();
  return fetchPatientsPage(session.user.practiceId, session.user.id, cursor);
}

// ---------------------------------------------------------------------------
// C3 calm-skin patients list — read-only search + cursor pagination.
// ---------------------------------------------------------------------------
//
// Powers the flag-gated patients list (patients-list-c3.tsx). PURELY
// READ-ONLY: same practice-scoped roster the existing /patients page reads,
// plus an optional case-insensitive name search and a stable (updatedAt desc,
// id desc) cursor so the list scales past the old 100-row client cap without
// rendering everything at once. Per-page visit counts via the same groupBy the
// existing page uses. practiceId comes from the session — never a caller arg.
type C3PatientRaw = {
  id: string;
  name: string;
  dateOfBirth: Date | null;
  updatedAt: Date;
};

export async function searchPatientsAction(
  cursor: C3PatientsCursor | null,
  query: string,
): Promise<C3PatientsPage> {
  const session = await requireSession();
  const actor = {
    userId: session.user.id,
    practiceId: session.user.practiceId,
  };
  const q = query.trim().slice(0, 100);

  let cur: { updatedAt: Date; id: string } | null = null;
  if (cursor) {
    const d = new Date(cursor.updatedAt);
    if (Number.isNaN(d.getTime())) throw new Error("Invalid cursor");
    cur = { updatedAt: d, id: cursor.id };
  }

  const andClauses: Prisma.TranscribeMdPatientWhereInput[] = [];
  if (q) andClauses.push({ name: { contains: q, mode: "insensitive" } });
  if (cur) {
    andClauses.push({
      OR: [
        { updatedAt: { lt: cur.updatedAt } },
        { AND: [{ updatedAt: cur.updatedAt }, { id: { lt: cur.id } }] },
      ],
    });
  }

  const where: Prisma.TranscribeMdPatientWhereInput = {
    ...currentClinicalPatientCollectionWhere({ actor }),
  };
  if (andClauses.length) where.AND = andClauses;

  const rows = (await prisma.transcribeMdPatient.findMany({
    where,
    orderBy: [{ updatedAt: "desc" }, { id: "desc" }],
    take: C3_PATIENTS_PAGE_SIZE + 1,
    select: {
      id: true,
      name: true,
      dateOfBirth: true,
      updatedAt: true,
    },
  })) as C3PatientRaw[];

  const hasMore = rows.length > C3_PATIENTS_PAGE_SIZE;
  const page = hasMore ? rows.slice(0, C3_PATIENTS_PAGE_SIZE) : rows;

  const ids = page.map((p) => p.id);
  type LatestVisit = {
    id: string;
    patientId: string;
    createdAt: Date;
    specialty: string;
    status: TranscribeVisitStatus;
    needsReview: boolean;
    signedAt: Date | null;
  };
  const [latestVisits, counts] = await Promise.all([
    readLatestTemplateTwinVisibleVisitByPatient<LatestVisit>({
      db: prisma,
      actorUserId: session.user.id,
      patientIds: ids,
      scope: { deleted: "active", archived: "active" },
      hydrate: (tx, visitIds) =>
        tx.transcribeVisit.findMany({
          where: {
            id: { in: [...visitIds] },
            userId: session.user.id,
          },
          select: {
            id: true,
            patientId: true,
            createdAt: true,
            specialty: true,
            status: true,
            needsReview: true,
            signedAt: true,
          },
        }) as Promise<LatestVisit[]>,
    }),
    countTemplateTwinVisibleVisitsByPatient({
      db: prisma,
      actorUserId: session.user.id,
      patientIds: ids,
      scope: { deleted: "active", archived: "active" },
    }),
  ]);
  const latestByPatient = new Map(
    latestVisits.map((visit) => [visit.patientId, visit]),
  );
  const countBy = new Map<string, number>(
    counts.map((count) => [count.patientId, count.count]),
  );

  const last = page[page.length - 1];
  const nextCursor: C3PatientsCursor | null =
    hasMore && last
      ? { updatedAt: last.updatedAt.toISOString(), id: last.id }
      : null;

  return {
    rows: page.map((p) => {
      const lv = latestByPatient.get(p.id);
      return {
        id: p.id,
        name: p.name,
        dateOfBirth: p.dateOfBirth
          ? p.dateOfBirth.toISOString().slice(0, 10)
          : null,
        visitCount: countBy.get(p.id) ?? 0,
        lastVisitAt: lv?.createdAt.toISOString() ?? null,
        lastVisitSpecialty: lv?.specialty ?? null,
        lastVisitStatus: lv?.status ?? null,
        lastVisitNeedsReview: lv?.needsReview ?? false,
        lastVisitSignedAt: lv?.signedAt ? lv.signedAt.toISOString() : null,
      };
    }),
    nextCursor,
  };
}
