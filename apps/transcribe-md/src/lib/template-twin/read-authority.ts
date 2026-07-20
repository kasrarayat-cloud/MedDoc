import { Prisma } from "@prisma/client";
import {
  runSerializableTransactionWithRetry,
  type TransactionHost,
} from "@/lib/db/transaction-retry";

/**
 * Stable, PHI-free denial for a generic read that discovered durable
 * Template Twin provenance but could not bind it to the caller's current
 * physician account and practice.
 */
export class TemplateTwinVisitReadAuthorityError extends Error {
  readonly code = "TEMPLATE_TWIN_VISIT_READ_NOT_AUTHORIZED" as const;

  constructor() {
    super("The requested visit is not available.");
    this.name = "TemplateTwinVisitReadAuthorityError";
  }
}

export interface TemplateTwinVisitReadQueryClient {
  $queryRaw<T>(query: Prisma.Sql): Promise<T>;
}

interface TemplateTwinVisitReadRow {
  visitId: string;
  isTemplateTwin: boolean;
  isSyntheticTemplateTwin: boolean;
  isInternalPreCertification: boolean;
  authorized: boolean;
  practiceId: string | null;
  templateTwinEnabled: boolean | null;
}

export interface TemplateTwinVisitReadDecision {
  visitId: string;
  isTemplateTwin: boolean;
  /** Synthetic QA is never inferred from a label or environment flag. */
  isSyntheticTemplateTwin: boolean;
  /** Null for ordinary visits so stale JWT tenant data is never promoted. */
  practiceId: string | null;
  /** Current practice flag. Reads remain allowed when this is false. */
  templateTwinEnabled: boolean | null;
}

export type TemplateTwinVisitSqlAlias = "visit" | "v" | "v2";

/**
 * Query-native correlated SQL form of the generic read boundary. This is used
 * by raw rollups/exports where Prisma cannot express cross-row identity
 * equality. `visitAlias` is a closed code-owned union, never request input.
 */
export function templateTwinVisitReadVisibilitySql(input: {
  actorUserId: string;
  visitAlias: TemplateTwinVisitSqlAlias;
}): Prisma.Sql {
  const visit = Prisma.raw(input.visitAlias);
  return Prisma.sql`
    (
      (
        NOT EXISTS (
          SELECT 1
          FROM "note_templates" provenance_template
          WHERE provenance_template."id" = ${visit}."noteTemplateId"
            AND provenance_template."templateKind" = 'template_twin_docx'
        )
        AND NOT EXISTS (
          SELECT 1
          FROM "template_twin_compiled_versions" provenance_compiled
          WHERE provenance_compiled."noteTemplateId" = ${visit}."noteTemplateId"
        )
        AND NOT EXISTS (
          SELECT 1 FROM "template_twin_fill_manifests" provenance_fill
          WHERE provenance_fill."visitId" = ${visit}."id"
        )
        AND NOT EXISTS (
          SELECT 1 FROM "template_twin_synthetic_qa_runs" provenance_run
          WHERE provenance_run."visitId" = ${visit}."id"
        )
        AND NOT EXISTS (
          SELECT 1 FROM "template_twin_synthetic_qa_admissions" provenance_admission
          WHERE provenance_admission."visitId" = ${visit}."id"
        )
        AND NOT EXISTS (
          SELECT 1 FROM "template_twin_provider_executions" provenance_execution
          WHERE provenance_execution."visitId" = ${visit}."id"
        )
        AND EXISTS (
          SELECT 1
          FROM "users" ordinary_actor
          JOIN "practices" ordinary_practice
            ON ordinary_practice."id" = ordinary_actor."practiceId"
          JOIN "transcribe_md_patients" ordinary_patient
            ON ordinary_patient."id" = ${visit}."patientId"
          WHERE ordinary_actor."id" = ${input.actorUserId}
            AND ${visit}."userId" = ordinary_actor."id"
            AND ordinary_actor."role" = 'DOCTOR'::"UserRole"
            AND ordinary_actor."isActive" = TRUE
            AND ordinary_actor."deactivatedAt" IS NULL
            AND ordinary_actor."suspendedAt" IS NULL
            AND ordinary_actor."softDeletedAt" IS NULL
            AND 'TRANSCRIBE_MD'::"Product" = ANY(ordinary_actor."products")
            AND ordinary_practice."isActive" = TRUE
            AND ordinary_patient."practiceId" = ordinary_practice."id"
            AND ordinary_patient."externalId" IS DISTINCT FROM 'SYNTHETIC-QA-ONLY'
        )
      )
      OR EXISTS (
        SELECT 1
        FROM "users" current_actor
        JOIN "practices" current_practice
          ON current_practice."id" = current_actor."practiceId"
        JOIN "transcribe_md_patients" current_patient
          ON current_patient."id" = ${visit}."patientId"
        JOIN "note_templates" current_template
          ON current_template."id" = ${visit}."noteTemplateId"
        JOIN "template_twin_compiled_versions" current_compiled
          ON current_compiled."noteTemplateId" = current_template."id"
        JOIN "template_twin_source_artifacts" current_source
          ON current_source."id" = current_compiled."sourceArtifactId"
        WHERE current_actor."id" = ${input.actorUserId}
          AND ${visit}."userId" = current_actor."id"
          AND current_actor."role" = 'DOCTOR'::"UserRole"
          AND current_actor."isActive" = TRUE
          AND current_actor."deactivatedAt" IS NULL
          AND current_actor."suspendedAt" IS NULL
          AND current_actor."softDeletedAt" IS NULL
          AND 'TRANSCRIBE_MD'::"Product" = ANY(current_actor."products")
          AND current_practice."isActive" = TRUE
          AND current_patient."practiceId" = current_practice."id"
          AND current_patient."externalId" IS DISTINCT FROM 'SYNTHETIC-QA-ONLY'
          AND current_template."doctorId" = current_actor."id"
          AND current_template."templateKind" = 'template_twin_docx'
          AND ${visit}."noteTemplateVersion" IS NOT NULL
          AND current_template."version" = ${visit}."noteTemplateVersion"
          AND (
            SELECT COUNT(*)
            FROM "template_twin_compiled_versions" compiled_count
            WHERE compiled_count."noteTemplateId" = current_template."id"
          ) = 1
          AND current_source."practiceId" = current_practice."id"
          AND NOT EXISTS (
            SELECT 1
            FROM "template_twin_fill_manifests" fill
            LEFT JOIN "template_twin_compiled_versions" fill_compiled
              ON fill_compiled."id" = fill."compiledVersionId"
            LEFT JOIN "template_twin_source_artifacts" fill_source
              ON fill_source."id" = fill_compiled."sourceArtifactId"
            WHERE fill."visitId" = ${visit}."id"
              AND (
                fill."practiceId" IS DISTINCT FROM current_practice."id"
                OR fill."noteTemplateId" IS DISTINCT FROM current_template."id"
                OR fill."noteTemplateVersion" IS DISTINCT FROM ${visit}."noteTemplateVersion"
                OR fill_compiled."id" IS DISTINCT FROM current_compiled."id"
                OR fill_compiled."noteTemplateId" IS DISTINCT FROM current_template."id"
                OR fill_source."id" IS DISTINCT FROM current_source."id"
                OR fill_source."practiceId" IS DISTINCT FROM current_practice."id"
              )
          )
          AND NOT EXISTS (
            SELECT 1 FROM "template_twin_synthetic_qa_runs" run
            WHERE run."visitId" = ${visit}."id"
          )
          AND NOT EXISTS (
            SELECT 1 FROM "template_twin_synthetic_qa_admissions" admission
            WHERE admission."visitId" = ${visit}."id"
          )
          AND NOT EXISTS (
            SELECT 1
            FROM "template_twin_provider_executions" execution
            LEFT JOIN "template_twin_compiled_versions" execution_compiled
              ON execution_compiled."id" = execution."compiledVersionId"
            LEFT JOIN "template_twin_source_artifacts" execution_source
              ON execution_source."id" = execution."sourceArtifactId"
            WHERE execution."visitId" = ${visit}."id"
              AND (
                execution."practiceId" IS DISTINCT FROM current_practice."id"
                OR execution."actorUserId" IS DISTINCT FROM current_actor."id"
                OR execution."providerMode" IS DISTINCT FROM 'LIVE'
                OR execution."syntheticAdmissionId" IS NOT NULL
                OR execution."noteTemplateId" IS DISTINCT FROM current_template."id"
                OR execution."noteTemplateVersion" IS DISTINCT FROM ${visit}."noteTemplateVersion"
                OR execution_compiled."id" IS DISTINCT FROM current_compiled."id"
                OR execution_compiled."noteTemplateId" IS DISTINCT FROM current_template."id"
                OR execution_source."id" IS DISTINCT FROM current_source."id"
                OR execution_source."practiceId" IS DISTINCT FROM current_practice."id"
              )
          )
      )
    )
  `;
}

export interface TemplateTwinVisibleVisitIdentity {
  id: string;
  createdAt: Date;
}

export type TemplateTwinVisitDateColumn =
  | "createdAt"
  | "updatedAt"
  | "deletedAt";

export interface TemplateTwinVisibleVisitScope {
  patientId?: string;
  patientIds?: readonly string[];
  deleted?: "active" | "deleted" | "any";
  archived?: "active" | "archived" | "any";
  statuses?: readonly string[];
  needsReview?: boolean;
  signed?: "signed" | "unsigned" | "any";
  signedAtGte?: Date;
  createdAtGte?: Date;
  draftedInSeconds?: "present" | "any";
  /** Patient name, legacy patient name, or chief complaint. */
  search?: string;
}

export interface TemplateTwinVisibleVisitCursor {
  value: Date;
  id: string;
}

export interface TemplateTwinVisibleVisitPageQuery {
  scope?: TemplateTwinVisibleVisitScope;
  orderBy?: TemplateTwinVisitDateColumn;
  direction?: "asc" | "desc";
  cursor?: TemplateTwinVisibleVisitCursor;
  skip?: number;
  take: number;
}

export interface TemplateTwinVisibleVisitAggregate {
  count: number;
  maxCreatedAt: Date | null;
  avgDraftedInSeconds: number | null;
}

export interface TemplateTwinVisibleVisitPatientCount {
  patientId: string;
  count: number;
}

export interface TemplateTwinVisibleVisitPatientLatest extends TemplateTwinVisibleVisitIdentity {
  patientId: string;
}

const MAX_TEMPLATE_TWIN_VISIBLE_VISIT_PAGE = 256;

function templateTwinVisibleVisitScopeSql(
  scope: TemplateTwinVisibleVisitScope | undefined,
): Prisma.Sql {
  if (!scope) return Prisma.empty;
  const predicates: Prisma.Sql[] = [];
  if (scope.patientId !== undefined) {
    predicates.push(Prisma.sql`visit."patientId" = ${scope.patientId}`);
  }
  if (scope.patientIds !== undefined) {
    predicates.push(
      scope.patientIds.length === 0
        ? Prisma.sql`FALSE`
        : Prisma.sql`visit."patientId" IN (${Prisma.join(scope.patientIds)})`,
    );
  }
  if (scope.deleted === "active") {
    predicates.push(Prisma.sql`visit."deletedAt" IS NULL`);
  } else if (scope.deleted === "deleted") {
    predicates.push(Prisma.sql`visit."deletedAt" IS NOT NULL`);
  }
  if (scope.archived === "active") {
    predicates.push(Prisma.sql`visit."archivedAt" IS NULL`);
  } else if (scope.archived === "archived") {
    predicates.push(Prisma.sql`visit."archivedAt" IS NOT NULL`);
  }
  if (scope.statuses !== undefined) {
    predicates.push(
      scope.statuses.length === 0
        ? Prisma.sql`FALSE`
        : Prisma.sql`visit."status"::text IN (${Prisma.join(scope.statuses)})`,
    );
  }
  if (scope.needsReview !== undefined) {
    predicates.push(Prisma.sql`visit."needsReview" = ${scope.needsReview}`);
  }
  if (scope.signed === "signed") {
    predicates.push(Prisma.sql`visit."signedAt" IS NOT NULL`);
  } else if (scope.signed === "unsigned") {
    predicates.push(Prisma.sql`visit."signedAt" IS NULL`);
  }
  if (scope.signedAtGte !== undefined) {
    predicates.push(Prisma.sql`visit."signedAt" >= ${scope.signedAtGte}`);
  }
  if (scope.createdAtGte !== undefined) {
    predicates.push(Prisma.sql`visit."createdAt" >= ${scope.createdAtGte}`);
  }
  if (scope.draftedInSeconds === "present") {
    predicates.push(Prisma.sql`visit."draftedInSeconds" IS NOT NULL`);
  }
  if (scope.search !== undefined && scope.search.length > 0) {
    // Prisma `contains` treats SQL wildcard characters as literal input.
    // Keep that behavior when compiling the query-native equivalent.
    const literal = scope.search
      .replaceAll("!", "!!")
      .replaceAll("%", "!%")
      .replaceAll("_", "!_");
    const pattern = `%${literal}%`;
    predicates.push(Prisma.sql`
      (
        patient."name" ILIKE ${pattern} ESCAPE '!'
        OR visit."patientName" ILIKE ${pattern} ESCAPE '!'
        OR visit."chiefComplaint" ILIKE ${pattern} ESCAPE '!'
      )
    `);
  }
  return predicates.length === 0
    ? Prisma.empty
    : Prisma.sql`AND ${Prisma.join(predicates, " AND ")}`;
}

function templateTwinVisitOrderColumn(
  column: TemplateTwinVisitDateColumn,
): Prisma.Sql {
  switch (column) {
    case "updatedAt":
      return Prisma.sql`visit."updatedAt"`;
    case "deletedAt":
      return Prisma.sql`visit."deletedAt"`;
    case "createdAt":
    default:
      return Prisma.sql`visit."createdAt"`;
  }
}

function assertBoundedVisitPage(input: { take: number; skip?: number }): void {
  if (
    !Number.isInteger(input.take) ||
    input.take < 1 ||
    input.take > MAX_TEMPLATE_TWIN_VISIBLE_VISIT_PAGE
  ) {
    throw new RangeError(
      `take must be an integer between 1 and ${MAX_TEMPLATE_TWIN_VISIBLE_VISIT_PAGE}.`,
    );
  }
  if (
    input.skip !== undefined &&
    (!Number.isInteger(input.skip) || input.skip < 0)
  ) {
    throw new RangeError("skip must be a non-negative integer.");
  }
}

function assertBoundedPatientIds(patientIds: readonly string[]): void {
  if (patientIds.length > MAX_TEMPLATE_TWIN_VISIBLE_VISIT_PAGE) {
    throw new RangeError(
      `patientIds must contain at most ${MAX_TEMPLATE_TWIN_VISIBLE_VISIT_PAGE} entries.`,
    );
  }
}

/**
 * Exact bounded identifier page. Caller scope, ordering, cursor, offset, and
 * limit are all applied by PostgreSQL after the correlated current-authority
 * predicate. Only non-PHI identities leave this statement.
 */
export async function listTemplateTwinVisibleVisitPage(input: {
  db: TemplateTwinVisitReadQueryClient;
  actorUserId: string;
  query: TemplateTwinVisibleVisitPageQuery;
}): Promise<TemplateTwinVisibleVisitIdentity[]> {
  assertBoundedVisitPage(input.query);
  if (
    input.query.orderBy === "deletedAt" &&
    input.query.scope?.deleted !== "deleted"
  ) {
    throw new RangeError(
      'deletedAt ordering requires scope.deleted to be "deleted".',
    );
  }
  const visibility = templateTwinVisitReadVisibilitySql({
    actorUserId: input.actorUserId,
    visitAlias: "visit",
  });
  const scope = templateTwinVisibleVisitScopeSql(input.query.scope);
  const orderColumn = templateTwinVisitOrderColumn(
    input.query.orderBy ?? "createdAt",
  );
  const direction = input.query.direction ?? "desc";
  const orderOperator = direction === "desc" ? Prisma.sql`<` : Prisma.sql`>`;
  const orderDirection =
    direction === "desc" ? Prisma.sql`DESC` : Prisma.sql`ASC`;
  const cursor = input.query.cursor
    ? Prisma.sql`
        AND (
          ${orderColumn} ${orderOperator} ${input.query.cursor.value}
          OR (
            ${orderColumn} = ${input.query.cursor.value}
            AND visit."id" ${orderOperator} ${input.query.cursor.id}
          )
        )
      `
    : Prisma.empty;
  const offset =
    input.query.skip === undefined
      ? Prisma.empty
      : Prisma.sql`OFFSET ${input.query.skip}`;
  return input.db.$queryRaw<TemplateTwinVisibleVisitIdentity[]>(Prisma.sql`
    SELECT visit."id", visit."createdAt"
    FROM "transcribe_visits" visit
    JOIN "transcribe_md_patients" patient
      ON patient."id" = visit."patientId"
    WHERE visit."userId" = ${input.actorUserId}
      AND patient."externalId" IS DISTINCT FROM 'SYNTHETIC-QA-ONLY'
      ${scope}
      ${cursor}
      AND ${visibility}
    ORDER BY ${orderColumn} ${orderDirection}, visit."id" ${orderDirection}
    LIMIT ${input.query.take}
    ${offset}
  `);
}

/** Exact aggregate over the same query-native current-authority boundary. */
export async function aggregateTemplateTwinVisibleVisits(input: {
  db: TemplateTwinVisitReadQueryClient;
  actorUserId: string;
  scope?: TemplateTwinVisibleVisitScope;
}): Promise<TemplateTwinVisibleVisitAggregate> {
  const visibility = templateTwinVisitReadVisibilitySql({
    actorUserId: input.actorUserId,
    visitAlias: "visit",
  });
  const scope = templateTwinVisibleVisitScopeSql(input.scope);
  const [row] = await input.db.$queryRaw<TemplateTwinVisibleVisitAggregate[]>(
    Prisma.sql`
      SELECT
        COUNT(*)::integer AS "count",
        MAX(visit."createdAt") AS "maxCreatedAt",
        AVG(visit."draftedInSeconds")::double precision AS "avgDraftedInSeconds"
      FROM "transcribe_visits" visit
      JOIN "transcribe_md_patients" patient
        ON patient."id" = visit."patientId"
      WHERE visit."userId" = ${input.actorUserId}
        AND patient."externalId" IS DISTINCT FROM 'SYNTHETIC-QA-ONLY'
        ${scope}
        AND ${visibility}
    `,
  );
  return row ?? { count: 0, maxCreatedAt: null, avgDraftedInSeconds: null };
}

/** Exact active-visit counts for a bounded, already-authorized patient page. */
export async function countTemplateTwinVisibleVisitsByPatient(input: {
  db: TemplateTwinVisitReadQueryClient;
  actorUserId: string;
  patientIds: readonly string[];
  scope?: Omit<TemplateTwinVisibleVisitScope, "patientId" | "patientIds">;
}): Promise<TemplateTwinVisibleVisitPatientCount[]> {
  assertBoundedPatientIds(input.patientIds);
  if (input.patientIds.length === 0) return [];
  const visibility = templateTwinVisitReadVisibilitySql({
    actorUserId: input.actorUserId,
    visitAlias: "visit",
  });
  const scope = templateTwinVisibleVisitScopeSql({
    ...input.scope,
    patientIds: input.patientIds,
  });
  return input.db.$queryRaw<TemplateTwinVisibleVisitPatientCount[]>(Prisma.sql`
    SELECT visit."patientId", COUNT(*)::integer AS "count"
    FROM "transcribe_visits" visit
    JOIN "transcribe_md_patients" patient
      ON patient."id" = visit."patientId"
    WHERE visit."userId" = ${input.actorUserId}
      AND patient."externalId" IS DISTINCT FROM 'SYNTHETIC-QA-ONLY'
      ${scope}
      AND ${visibility}
    GROUP BY visit."patientId"
  `);
}

/** One exact latest visible identity for each patient in a bounded page. */
export async function listLatestTemplateTwinVisibleVisitByPatient(input: {
  db: TemplateTwinVisitReadQueryClient;
  actorUserId: string;
  patientIds: readonly string[];
  scope?: Omit<TemplateTwinVisibleVisitScope, "patientId" | "patientIds">;
}): Promise<TemplateTwinVisibleVisitPatientLatest[]> {
  assertBoundedPatientIds(input.patientIds);
  if (input.patientIds.length === 0) return [];
  const visibility = templateTwinVisitReadVisibilitySql({
    actorUserId: input.actorUserId,
    visitAlias: "visit",
  });
  const scope = templateTwinVisibleVisitScopeSql({
    ...input.scope,
    patientIds: input.patientIds,
  });
  return input.db.$queryRaw<TemplateTwinVisibleVisitPatientLatest[]>(Prisma.sql`
    SELECT DISTINCT ON (visit."patientId")
      visit."id", visit."patientId", visit."createdAt"
    FROM "transcribe_visits" visit
    JOIN "transcribe_md_patients" patient
      ON patient."id" = visit."patientId"
    WHERE visit."userId" = ${input.actorUserId}
      AND patient."externalId" IS DISTINCT FROM 'SYNTHETIC-QA-ONLY'
      ${scope}
      AND ${visibility}
    ORDER BY visit."patientId" ASC, visit."createdAt" DESC, visit."id" DESC
  `);
}

/**
 * Hydrate one bounded exact page inside a serializable snapshot, then run the
 * same classifier again before any row leaves the transaction. The callback
 * must only read rows whose ids it receives.
 */
export async function readTemplateTwinVisibleVisitPage<
  T extends { id: string },
>(input: {
  db: TransactionHost;
  actorUserId: string;
  query: TemplateTwinVisibleVisitPageQuery;
  hydrate: (
    tx: Prisma.TransactionClient,
    visitIds: readonly string[],
  ) => Promise<readonly T[]>;
}): Promise<T[]> {
  return runSerializableTransactionWithRetry({
    prisma: input.db,
    operation: "template_twin_visible_visit_page",
    isolationLevel: Prisma.TransactionIsolationLevel.Serializable,
    transaction: async (tx) => {
      const identities = await listTemplateTwinVisibleVisitPage({
        db: tx,
        actorUserId: input.actorUserId,
        query: input.query,
      });
      if (identities.length === 0) return [];
      const rows = await input.hydrate(
        tx,
        identities.map((identity) => identity.id),
      );
      const visible = await filterTemplateTwinVisitReadRows({
        db: tx,
        actorUserId: input.actorUserId,
        rows,
      });
      const rowById = new Map(visible.map((row) => [row.id, row]));
      if (
        rowById.size !== identities.length ||
        visible.length !== identities.length
      ) {
        throw new TemplateTwinVisitReadAuthorityError();
      }
      return identities.map((identity) => {
        const row = rowById.get(identity.id);
        if (!row) throw new TemplateTwinVisitReadAuthorityError();
        return row;
      });
    },
  });
}

/** Serializable bounded hydration for the latest visible visit per patient. */
export async function readLatestTemplateTwinVisibleVisitByPatient<
  T extends { id: string },
>(input: {
  db: TransactionHost;
  actorUserId: string;
  patientIds: readonly string[];
  scope?: Omit<TemplateTwinVisibleVisitScope, "patientId" | "patientIds">;
  hydrate: (
    tx: Prisma.TransactionClient,
    visitIds: readonly string[],
  ) => Promise<readonly T[]>;
}): Promise<T[]> {
  assertBoundedPatientIds(input.patientIds);
  if (input.patientIds.length === 0) return [];
  return runSerializableTransactionWithRetry({
    prisma: input.db,
    operation: "template_twin_latest_visible_visit_by_patient",
    isolationLevel: Prisma.TransactionIsolationLevel.Serializable,
    transaction: async (tx) => {
      const identities = await listLatestTemplateTwinVisibleVisitByPatient({
        db: tx,
        actorUserId: input.actorUserId,
        patientIds: input.patientIds,
        scope: input.scope,
      });
      if (identities.length === 0) return [];
      const rows = await input.hydrate(
        tx,
        identities.map((identity) => identity.id),
      );
      const visible = await filterTemplateTwinVisitReadRows({
        db: tx,
        actorUserId: input.actorUserId,
        rows,
      });
      const rowById = new Map(visible.map((row) => [row.id, row]));
      if (
        rowById.size !== identities.length ||
        visible.length !== identities.length
      ) {
        throw new TemplateTwinVisitReadAuthorityError();
      }
      return identities.map((identity) => {
        const row = rowById.get(identity.id);
        if (!row) throw new TemplateTwinVisitReadAuthorityError();
        return row;
      });
    },
  });
}

/**
 * Exact, query-native identifier census for archive/export jobs. This avoids
 * both projecting object keys before authority and compiling an unbounded
 * Prisma OR over the physician's visit history.
 */
export async function listTemplateTwinVisibleVisitIdentities(input: {
  db: TemplateTwinVisitReadQueryClient;
  actorUserId: string;
  patientId?: string;
  activeOnly?: boolean;
}): Promise<TemplateTwinVisibleVisitIdentity[]> {
  const visibility = templateTwinVisitReadVisibilitySql({
    actorUserId: input.actorUserId,
    visitAlias: "visit",
  });
  const patientScope = input.patientId
    ? Prisma.sql`AND visit."patientId" = ${input.patientId}`
    : Prisma.empty;
  const activeScope = input.activeOnly
    ? Prisma.sql`
        AND visit."deletedAt" IS NULL
        AND visit."archivedAt" IS NULL
      `
    : Prisma.empty;
  return input.db.$queryRaw<TemplateTwinVisibleVisitIdentity[]>(Prisma.sql`
    SELECT visit."id", visit."createdAt"
    FROM "transcribe_visits" visit
    JOIN "transcribe_md_patients" patient
      ON patient."id" = visit."patientId"
    WHERE visit."userId" = ${input.actorUserId}
      AND patient."externalId" IS DISTINCT FROM 'SYNTHETIC-QA-ONLY'
      ${patientScope}
      ${activeScope}
      AND ${visibility}
    ORDER BY visit."createdAt" ASC, visit."id" ASC
  `);
}

/**
 * One-statement durable-provenance classifier and current-physician read
 * boundary. The statement deliberately does not consult rollout: an owning
 * physician may still read the underlying clinical record after rollout is
 * revoked, while callers use `templateTwinEnabled` to suppress Twin-only UI.
 *
 * A stale JWT/user id is only a hint for both ordinary and Twin visits: the
 * current database row must still be an active DOCTOR with the TRANSCRIBE_MD
 * product, the practice must remain active, and the patient must remain in
 * that current practice. Twin reads additionally bind every tenant-bearing
 * provenance row. Structurally inconsistent provenance is denied rather than
 * interpreted as ordinary.
 */
export async function inspectTemplateTwinVisitReads(input: {
  db: TemplateTwinVisitReadQueryClient;
  visitIds: readonly string[];
  actorUserId: string;
}): Promise<TemplateTwinVisitReadDecision[]> {
  const visitIds = [...new Set(input.visitIds.filter((id) => id.length > 0))];
  if (visitIds.length === 0) return [];

  const rows = await input.db.$queryRaw<TemplateTwinVisitReadRow[]>(Prisma.sql`
    WITH scoped AS (
      SELECT
        visit."id" AS "visitId",
        visit."userId" AS "visitUserId",
        visit."patientId" AS "patientId",
        scoped_patient."id" AS "scopedPatientId",
        scoped_patient."practiceId" AS "patientPracticeId",
        scoped_patient."externalId" AS "patientExternalId",
        visit."noteTemplateId" AS "noteTemplateId",
        visit."noteTemplateVersion" AS "noteTemplateVersion",
        template."id" AS "templateId",
        template."doctorId" AS "templateDoctorId",
        template."templateKind" AS "templateKind",
        template."version" AS "templateVersion",
        actor."id" AS "actorId",
        actor."practiceId" AS "practiceId",
        actor."role"::text AS "actorRole",
        actor."isActive" AS "actorIsActive",
        actor."deactivatedAt" AS "actorDeactivatedAt",
        actor."suspendedAt" AS "actorSuspendedAt",
        actor."softDeletedAt" AS "actorSoftDeletedAt",
        actor."products" AS "actorProducts",
        practice."isActive" AS "practiceIsActive",
        practice."templateTwinEnabled" AS "templateTwinEnabled"
      FROM "transcribe_visits" visit
      LEFT JOIN "note_templates" template
        ON template."id" = visit."noteTemplateId"
      LEFT JOIN "transcribe_md_patients" scoped_patient
        ON scoped_patient."id" = visit."patientId"
      LEFT JOIN "users" actor
        ON actor."id" = visit."userId"
      LEFT JOIN "practices" practice
        ON practice."id" = actor."practiceId"
      WHERE visit."userId" = ${input.actorUserId}
        AND visit."id" IN (${Prisma.join(visitIds)})
    ), classified AS (
      SELECT scoped.*,
        COALESCE((
          COALESCE(scoped."templateKind" = 'template_twin_docx', FALSE)
          OR EXISTS (
            SELECT 1
            FROM "template_twin_compiled_versions" compiled_provenance
            WHERE compiled_provenance."noteTemplateId" = scoped."noteTemplateId"
          )
          OR COALESCE(scoped."patientExternalId" = 'SYNTHETIC-QA-ONLY', FALSE)
          OR EXISTS (
            SELECT 1 FROM "template_twin_fill_manifests" fill
            WHERE fill."visitId" = scoped."visitId"
          )
          OR EXISTS (
            SELECT 1 FROM "template_twin_synthetic_qa_runs" run
            WHERE run."visitId" = scoped."visitId"
          )
          OR EXISTS (
            SELECT 1 FROM "template_twin_synthetic_qa_admissions" admission
            WHERE admission."visitId" = scoped."visitId"
          )
          OR EXISTS (
            SELECT 1 FROM "template_twin_provider_executions" execution
            WHERE execution."visitId" = scoped."visitId"
          )
        ), FALSE) AS "isTemplateTwin",
        COALESCE((
          EXISTS (
            SELECT 1 FROM "template_twin_synthetic_qa_runs" run
            WHERE run."visitId" = scoped."visitId"
          )
          OR COALESCE(scoped."patientExternalId" = 'SYNTHETIC-QA-ONLY', FALSE)
          OR EXISTS (
            SELECT 1 FROM "template_twin_synthetic_qa_admissions" admission
            WHERE admission."visitId" = scoped."visitId"
          )
          OR EXISTS (
            SELECT 1 FROM "template_twin_provider_executions" execution
            WHERE execution."visitId" = scoped."visitId"
              AND (
                execution."syntheticAdmissionId" IS NOT NULL
                OR execution."providerMode" <> 'LIVE'
              )
          )
        ), FALSE) AS "isSyntheticTemplateTwin",
        (
          EXISTS (
            SELECT 1
            FROM "template_twin_synthetic_qa_admissions" admission
            WHERE admission."visitId" = scoped."visitId"
              AND admission."preCertificationVoiceEvidence" = TRUE
          )
          OR EXISTS (
            SELECT 1
            FROM "template_twin_provider_executions" execution
            JOIN "template_twin_synthetic_qa_admissions" admission
              ON admission."id" = execution."syntheticAdmissionId"
            WHERE execution."visitId" = scoped."visitId"
              AND admission."preCertificationVoiceEvidence" = TRUE
          )
        ) AS "isInternalPreCertification"
      FROM scoped
    )
    SELECT
      classified."visitId",
      classified."isTemplateTwin",
      classified."isSyntheticTemplateTwin",
      classified."isInternalPreCertification",
      classified."practiceId",
      classified."templateTwinEnabled",
      CASE
        WHEN NOT classified."isTemplateTwin" THEN (
          classified."actorId" = ${input.actorUserId}
          AND classified."visitUserId" = classified."actorId"
          AND classified."actorRole" = 'DOCTOR'
          AND classified."actorIsActive" = TRUE
          AND classified."actorDeactivatedAt" IS NULL
          AND classified."actorSuspendedAt" IS NULL
          AND classified."actorSoftDeletedAt" IS NULL
          AND 'TRANSCRIBE_MD'::"Product" = ANY(classified."actorProducts")
          AND classified."practiceId" IS NOT NULL
          AND classified."practiceIsActive" = TRUE
          AND classified."scopedPatientId" IS NOT NULL
          AND classified."patientPracticeId" = classified."practiceId"
          AND classified."patientExternalId" IS DISTINCT FROM 'SYNTHETIC-QA-ONLY'
        )
        ELSE (
          NOT classified."isInternalPreCertification"
          AND
          classified."actorId" = ${input.actorUserId}
          AND classified."actorRole" = 'DOCTOR'
          AND classified."actorIsActive" = TRUE
          AND classified."actorDeactivatedAt" IS NULL
          AND classified."actorSuspendedAt" IS NULL
          AND classified."actorSoftDeletedAt" IS NULL
          AND 'TRANSCRIBE_MD'::"Product" = ANY(classified."actorProducts")
          AND classified."practiceId" IS NOT NULL
          AND classified."practiceIsActive" = TRUE
          AND classified."templateId" IS NOT NULL
          AND classified."templateKind" = 'template_twin_docx'
          AND classified."templateDoctorId" = ${input.actorUserId}
          AND classified."noteTemplateVersion" IS NOT NULL
          AND classified."templateVersion" = classified."noteTemplateVersion"
          AND (
            SELECT COUNT(*)
            FROM "template_twin_compiled_versions" compiled_count
            WHERE compiled_count."noteTemplateId" = classified."templateId"
          ) = 1
          AND EXISTS (
            SELECT 1
            FROM "template_twin_compiled_versions" compiled
            JOIN "template_twin_source_artifacts" source
              ON source."id" = compiled."sourceArtifactId"
            WHERE compiled."noteTemplateId" = classified."templateId"
              AND source."practiceId" = classified."practiceId"
          )
          AND EXISTS (
            SELECT 1
            FROM "transcribe_md_patients" patient
            WHERE patient."id" = classified."patientId"
              AND patient."practiceId" = classified."practiceId"
          )
          AND NOT EXISTS (
            SELECT 1
            FROM "template_twin_fill_manifests" fill
            LEFT JOIN "template_twin_compiled_versions" compiled
              ON compiled."id" = fill."compiledVersionId"
            LEFT JOIN "template_twin_source_artifacts" source
              ON source."id" = compiled."sourceArtifactId"
            WHERE fill."visitId" = classified."visitId"
              AND (
                fill."practiceId" IS DISTINCT FROM classified."practiceId"
                OR fill."noteTemplateId" IS DISTINCT FROM classified."templateId"
                OR fill."noteTemplateVersion" IS DISTINCT FROM classified."noteTemplateVersion"
                OR compiled."id" IS NULL
                OR compiled."noteTemplateId" IS DISTINCT FROM classified."templateId"
                OR source."id" IS NULL
                OR source."practiceId" IS DISTINCT FROM classified."practiceId"
              )
          )
          AND NOT EXISTS (
            SELECT 1
            FROM "template_twin_synthetic_qa_runs" run
            LEFT JOIN "template_twin_synthetic_qa_admissions" run_admission
              ON run_admission."id" = run."admissionId"
            LEFT JOIN "template_twin_synthetic_qa_admissions" run_parent
              ON run_parent."id" = run_admission."parentAdmissionId"
            WHERE run."visitId" = classified."visitId"
              AND (
                run."practiceId" IS DISTINCT FROM classified."practiceId"
                OR run."doctorId" IS DISTINCT FROM ${input.actorUserId}
                OR run."noteTemplateId" IS DISTINCT FROM classified."templateId"
                OR run."noteTemplateVersion" IS DISTINCT FROM classified."noteTemplateVersion"
                OR run_admission."id" IS NULL
                OR run_admission."visitId" IS DISTINCT FROM classified."visitId"
                OR run_admission."practiceId" IS DISTINCT FROM classified."practiceId"
                OR run_admission."actorId" IS DISTINCT FROM ${input.actorUserId}
                OR run_admission."noteTemplateId" IS DISTINCT FROM classified."templateId"
                OR run_admission."noteTemplateVersion" IS DISTINCT FROM classified."noteTemplateVersion"
                OR run_parent."id" IS NULL
                OR run_parent."practiceId" IS DISTINCT FROM classified."practiceId"
                OR run_parent."actorId" IS DISTINCT FROM ${input.actorUserId}
                OR run_parent."noteTemplateId" IS DISTINCT FROM classified."templateId"
                OR run_parent."noteTemplateVersion" IS DISTINCT FROM classified."noteTemplateVersion"
                OR run_parent."visitId" IS NOT NULL
              )
          )
          AND NOT EXISTS (
            SELECT 1
            FROM "template_twin_synthetic_qa_admissions" admission
            LEFT JOIN "template_twin_synthetic_qa_admissions" parent
              ON parent."id" = admission."parentAdmissionId"
            WHERE admission."visitId" = classified."visitId"
              AND (
                admission."practiceId" IS DISTINCT FROM classified."practiceId"
                OR admission."actorId" IS DISTINCT FROM ${input.actorUserId}
                OR admission."noteTemplateId" IS DISTINCT FROM classified."templateId"
                OR admission."noteTemplateVersion" IS DISTINCT FROM classified."noteTemplateVersion"
                OR admission."purpose" IS DISTINCT FROM 'VISIT'
                OR parent."id" IS NULL
                OR parent."practiceId" IS DISTINCT FROM classified."practiceId"
                OR parent."actorId" IS DISTINCT FROM ${input.actorUserId}
                OR parent."noteTemplateId" IS DISTINCT FROM classified."templateId"
                OR parent."noteTemplateVersion" IS DISTINCT FROM classified."noteTemplateVersion"
                OR parent."purpose" IS DISTINCT FROM 'UPLOAD'
                OR parent."visitId" IS NOT NULL
              )
          )
          AND NOT EXISTS (
            SELECT 1
            FROM "template_twin_provider_executions" execution
            LEFT JOIN "template_twin_synthetic_qa_admissions" execution_admission
              ON execution_admission."id" = execution."syntheticAdmissionId"
            LEFT JOIN "template_twin_compiled_versions" execution_compiled
              ON execution_compiled."id" = execution."compiledVersionId"
            LEFT JOIN "template_twin_source_artifacts" execution_source
              ON execution_source."id" = execution."sourceArtifactId"
            WHERE execution."visitId" = classified."visitId"
              AND (
                execution."practiceId" IS DISTINCT FROM classified."practiceId"
                OR execution."actorUserId" IS DISTINCT FROM ${input.actorUserId}
                OR execution."noteTemplateId" IS DISTINCT FROM classified."templateId"
                OR execution."noteTemplateVersion" IS DISTINCT FROM classified."noteTemplateVersion"
                OR execution_compiled."id" IS NULL
                OR execution_compiled."noteTemplateId" IS DISTINCT FROM classified."templateId"
                OR execution_source."id" IS NULL
                OR execution_source."id" IS DISTINCT FROM execution_compiled."sourceArtifactId"
                OR execution_source."practiceId" IS DISTINCT FROM classified."practiceId"
                OR (
                  execution."providerMode" = 'LIVE'
                  AND execution."syntheticAdmissionId" IS NOT NULL
                )
                OR (
                  execution."providerMode" <> 'LIVE'
                  AND execution."syntheticAdmissionId" IS NULL
                )
                OR (
                  execution."syntheticAdmissionId" IS NOT NULL
                  AND (
                    execution_admission."id" IS NULL
                    OR execution_admission."visitId" IS DISTINCT FROM classified."visitId"
                    OR execution_admission."practiceId" IS DISTINCT FROM classified."practiceId"
                    OR execution_admission."actorId" IS DISTINCT FROM ${input.actorUserId}
                    OR execution_admission."noteTemplateId" IS DISTINCT FROM classified."templateId"
                    OR execution_admission."noteTemplateVersion" IS DISTINCT FROM classified."noteTemplateVersion"
                  )
                )
              )
          )
        )
      END AS "authorized"
    FROM classified
  `);

  const decisions: TemplateTwinVisitReadDecision[] = [];
  for (const row of rows) {
    if (!row.authorized) {
      continue;
    }
    decisions.push({
      visitId: row.visitId,
      isTemplateTwin: row.isTemplateTwin,
      isSyntheticTemplateTwin: row.isSyntheticTemplateTwin,
      practiceId: row.isTemplateTwin ? row.practiceId : null,
      templateTwinEnabled: row.isTemplateTwin ? row.templateTwinEnabled : null,
    });
  }
  return decisions;
}

/**
 * Final response filter for bounded visit lists. Unauthorized or internally
 * inconsistent rows are suppressed; ordinary rows require the same exact
 * current physician, product, practice, and patient-tenant authority.
 */
export async function filterTemplateTwinVisitReadRows<
  T extends { id: string },
>(input: {
  db: TemplateTwinVisitReadQueryClient;
  rows: readonly T[];
  actorUserId: string;
}): Promise<T[]> {
  if (input.rows.length === 0) return [];
  const decisions = await inspectTemplateTwinVisitReads({
    db: input.db,
    visitIds: input.rows.map((row) => row.id),
    actorUserId: input.actorUserId,
  });
  const allowed = new Set(decisions.map((decision) => decision.visitId));
  return input.rows.filter((row) => allowed.has(row.id));
}

/** Single-visit form used at detail/read response boundaries. */
export async function requireTemplateTwinVisitReadAuthority(input: {
  db: TemplateTwinVisitReadQueryClient;
  visitId: string;
  actorUserId: string;
  /** Used by the final required-audit transaction to reject tenant drift. */
  expectedPracticeId?: string;
  /** Final audit claims must still describe a durable Twin visit. */
  requireTemplateTwin?: boolean;
}): Promise<TemplateTwinVisitReadDecision> {
  const [decision] = await inspectTemplateTwinVisitReads({
    db: input.db,
    visitIds: [input.visitId],
    actorUserId: input.actorUserId,
  });
  if (!decision) {
    throw new TemplateTwinVisitReadAuthorityError();
  }
  if (input.requireTemplateTwin && !decision.isTemplateTwin) {
    throw new TemplateTwinVisitReadAuthorityError();
  }
  if (
    input.expectedPracticeId !== undefined &&
    decision.practiceId !== input.expectedPracticeId
  ) {
    throw new TemplateTwinVisitReadAuthorityError();
  }
  return decision;
}

/**
 * Final locked recheck for high-frequency Twin reads that are covered by an
 * enclosing page-view audit and should not manufacture one audit row per poll.
 * Lock order matches the release-critical audit/final-claim order.
 */
export async function reassertTemplateTwinVisitReadAuthority(input: {
  db: TransactionHost;
  visitId: string;
  actorUserId: string;
  expectedPracticeId: string;
}): Promise<TemplateTwinVisitReadDecision> {
  return runSerializableTransactionWithRetry({
    prisma: input.db,
    operation: "template_twin_visit_read_authority",
    isolationLevel: Prisma.TransactionIsolationLevel.Serializable,
    context: {
      visitId: input.visitId,
      practiceId: input.expectedPracticeId,
    },
    transaction: async (tx) => {
      const practices = await tx.$queryRaw<Array<{ id: string }>>(Prisma.sql`
        SELECT "id"
        FROM "practices"
        WHERE "id" = ${input.expectedPracticeId}
          AND "isActive" = TRUE
        FOR KEY SHARE
      `);
      const actors = await tx.$queryRaw<Array<{ id: string }>>(Prisma.sql`
        SELECT "id"
        FROM "users"
        WHERE "id" = ${input.actorUserId}
          AND "practiceId" = ${input.expectedPracticeId}
          AND "role" = 'DOCTOR'::"UserRole"
          AND "isActive" = TRUE
          AND "deactivatedAt" IS NULL
          AND "suspendedAt" IS NULL
          AND "softDeletedAt" IS NULL
          AND 'TRANSCRIBE_MD'::"Product" = ANY("products")
        FOR SHARE
      `);
      const visits = await tx.$queryRaw<Array<{ id: string }>>(Prisma.sql`
        SELECT "id"
        FROM "transcribe_visits"
        WHERE "id" = ${input.visitId}
          AND "userId" = ${input.actorUserId}
        FOR SHARE
      `);
      if (
        practices.length !== 1 ||
        actors.length !== 1 ||
        visits.length !== 1
      ) {
        throw new TemplateTwinVisitReadAuthorityError();
      }
      const decision = await requireTemplateTwinVisitReadAuthority({
        db: tx,
        visitId: input.visitId,
        actorUserId: input.actorUserId,
        expectedPracticeId: input.expectedPracticeId,
        requireTemplateTwin: true,
      });
      return decision;
    },
  });
}
