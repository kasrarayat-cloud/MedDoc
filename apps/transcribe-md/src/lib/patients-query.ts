// ============================================================================
// Patients dashboard — SQL + keyset pagination (T-M17.2 Phase 3 Commit 7)
// ----------------------------------------------------------------------------
// Kept out of the 'use server' action file so the internal helper
// (`fetchPatientsPage(practiceId, cursor)`) isn't reachable from the
// client as a callable action — practiceId would then be a
// caller-controlled argument, bypassing session scoping.
//
// The server component calls `fetchPatientsPage` directly with the
// authed practiceId; the `loadMorePatientsAction` in actions/patients.ts
// calls it after its own requireSession() gate.
// ============================================================================

import prisma from "@meddoc/db";
import { Prisma } from "@prisma/client";
import {
  PATIENTS_PAGE_SIZE,
  type PatientsCursor,
  type PatientListItem,
  type LoadMorePatientsResult,
} from "@/lib/patients-pagination";
import { templateTwinVisitReadVisibilitySql } from "@/lib/template-twin/read-authority";
import { currentClinicalPatientReadAuthoritySql } from "@/lib/clinical-patient-authority";

interface RawRow {
  id: string;
  name: string;
  dateOfBirth: Date | null;
  externalId: string | null;
  visitCount: number;
  lastVisitAt: Date | null;
  lastVisitSpecialty: string | null;
}

async function fetchRows(
  practiceId: string,
  actorUserId: string,
  cursor: PatientsCursor | null,
): Promise<RawRow[]> {
  const take = PATIENTS_PAGE_SIZE + 1;
  const visibleV = templateTwinVisitReadVisibilitySql({
    actorUserId,
    visitAlias: "v",
  });
  const visibleV2 = templateTwinVisitReadVisibilitySql({
    actorUserId,
    visitAlias: "v2",
  });
  const patientAuthority = currentClinicalPatientReadAuthoritySql({
    actor: { userId: actorUserId, practiceId },
    patientAlias: "p",
  });

  if (cursor === null) {
    return prisma.$queryRaw(Prisma.sql`
      SELECT
        p.id,
        p.name,
        p."dateOfBirth",
        p."externalId",
        COUNT(v.id)::int AS "visitCount",
        MAX(v."createdAt") AS "lastVisitAt",
        (
          SELECT v2.specialty
          FROM transcribe_visits v2
          WHERE v2."patientId" = p.id
            AND v2."deletedAt" IS NULL
            AND v2."archivedAt" IS NULL
            AND ${visibleV2}
          ORDER BY v2."createdAt" DESC
          LIMIT 1
        ) AS "lastVisitSpecialty"
      FROM transcribe_md_patients p
      LEFT JOIN transcribe_visits v ON v."patientId" = p.id
        AND v."deletedAt" IS NULL
        AND v."archivedAt" IS NULL
        AND ${visibleV}
      WHERE ${patientAuthority}
      GROUP BY p.id
      ORDER BY MAX(v."createdAt") DESC NULLS LAST, p.id DESC
      LIMIT ${take}
    `) as Promise<RawRow[]>;
  }

  if (cursor.lastVisitAt === null) {
    // Cursor anchored in the "no visits yet" tail — only null-
    // lastVisitAt rows with a smaller id remain.
    return prisma.$queryRaw(Prisma.sql`
      SELECT
        p.id,
        p.name,
        p."dateOfBirth",
        p."externalId",
        COUNT(v.id)::int AS "visitCount",
        MAX(v."createdAt") AS "lastVisitAt",
        (
          SELECT v2.specialty
          FROM transcribe_visits v2
          WHERE v2."patientId" = p.id
            AND v2."deletedAt" IS NULL
            AND v2."archivedAt" IS NULL
            AND ${visibleV2}
          ORDER BY v2."createdAt" DESC
          LIMIT 1
        ) AS "lastVisitSpecialty"
      FROM transcribe_md_patients p
      LEFT JOIN transcribe_visits v ON v."patientId" = p.id
        AND v."deletedAt" IS NULL
        AND v."archivedAt" IS NULL
        AND ${visibleV}
      WHERE ${patientAuthority}
        AND p.id < ${cursor.id}
      GROUP BY p.id
      HAVING MAX(v."createdAt") IS NULL
      ORDER BY p.id DESC
      LIMIT ${take}
    `) as Promise<RawRow[]>;
  }

  // Cursor anchored on a row with visits. Next-page candidates:
  //   (a) earlier in the same stratum — lastVisitAt < cursor, or
  //       tied on lastVisitAt with smaller id, or
  //   (b) any null-lastVisitAt row (those come AFTER non-null rows).
  const cursorDate = new Date(cursor.lastVisitAt);
  return prisma.$queryRaw(Prisma.sql`
    SELECT
      p.id,
      p.name,
      p."dateOfBirth",
      p."externalId",
      COUNT(v.id)::int AS "visitCount",
      MAX(v."createdAt") AS "lastVisitAt",
      (
        SELECT v2.specialty
        FROM transcribe_visits v2
        WHERE v2."patientId" = p.id
          AND v2."deletedAt" IS NULL
          AND v2."archivedAt" IS NULL
          AND ${visibleV2}
        ORDER BY v2."createdAt" DESC
        LIMIT 1
      ) AS "lastVisitSpecialty"
    FROM transcribe_md_patients p
    LEFT JOIN transcribe_visits v ON v."patientId" = p.id
      AND v."deletedAt" IS NULL
      AND v."archivedAt" IS NULL
      AND ${visibleV}
    WHERE ${patientAuthority}
    GROUP BY p.id
    HAVING
      MAX(v."createdAt") IS NULL
      OR MAX(v."createdAt") < ${cursorDate}
      OR (MAX(v."createdAt") = ${cursorDate} AND p.id < ${cursor.id})
    ORDER BY MAX(v."createdAt") DESC NULLS LAST, p.id DESC
    LIMIT ${take}
  `) as Promise<RawRow[]>;
}

export async function fetchPatientsPage(
  practiceId: string,
  actorUserId: string,
  cursor: PatientsCursor | null,
): Promise<LoadMorePatientsResult> {
  const rows = await fetchRows(practiceId, actorUserId, cursor);
  const hasMore = rows.length > PATIENTS_PAGE_SIZE;
  const page = hasMore ? rows.slice(0, PATIENTS_PAGE_SIZE) : rows;
  const items: PatientListItem[] = page.map((r) => ({
    id: r.id,
    name: r.name,
    dateOfBirth: r.dateOfBirth,
    externalId: r.externalId,
    visitCount: r.visitCount,
    lastVisitAt: r.lastVisitAt,
    lastVisitSpecialty: r.lastVisitSpecialty,
  }));
  const last = page[page.length - 1];
  const nextCursor: PatientsCursor | null =
    hasMore && last
      ? {
          lastVisitAt: last.lastVisitAt ? last.lastVisitAt.toISOString() : null,
          id: last.id,
        }
      : null;
  return { patients: items, nextCursor };
}
