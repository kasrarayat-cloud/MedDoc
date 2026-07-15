import { execSync } from "node:child_process";

import { assertNonProdDbName } from "@meddoc/db/guard";

import type {
  SemanticMapping,
  TemplateTwinFillManifest,
} from "../../../src/lib/template-twin/ir";
import { templateTwinMappingsSha256 } from "../../../src/lib/template-twin/mapping-hash";
import { QA_COMPOSE, QA_DB } from "./qa-compose";

const TEMPLATE_BUCKET =
  process.env.E2E_TEMPLATE_TWIN_BUCKET ?? "transcribe-md-template-artifacts-qa";

export interface TemplateTwinQaField {
  fieldId: string;
  originalLabel: string;
  fieldKind: string;
  mapping: SemanticMapping;
}

export interface TemplateTwinQaFillState {
  id: string;
  status: string;
  manifestVersion: number;
  fillManifest: TemplateTwinFillManifest;
  manifestSha256: string;
  soapVersion: number | null;
  soapSha256: string | null;
  outputObjectKey: string | null;
  outputVersionId: string | null;
  outputEtag: string | null;
  outputSha256: string | null;
  outputSizeBytes: number | null;
  roundTripVerified: boolean;
  visitStatus: string;
  currentSoapVersion: number;
  currentSoapFinal: string | null;
  noteTemplateId: string | null;
  noteTemplateVersion: number | null;
}

export interface TemplateTwinQaInventory {
  sourceArtifacts: number;
  compiledVersions: number;
  fieldDefinitions: number;
  certifications: number;
  fills: number;
  reviewDecisions: number;
  objectLedgerRows: number;
  auditOutboxRows: number;
}

function shellQuote(value: string): string {
  return `'${value.replaceAll("'", `'"'"'`)}'`;
}

function sqlLiteral(value: string): string {
  return `'${value.replaceAll("'", "''")}'`;
}

function assertSyntheticEmail(email: string): void {
  if (
    !/^qa-template-twin-e2e-[a-z0-9-]+@(example|synthetic)\.test$/i.test(email)
  ) {
    throw new Error(
      "Template Twin QA helpers accept only qa-template-twin-e2e-* @example.test/@synthetic.test identities.",
    );
  }
}

function psql(sql: string): string {
  assertNonProdDbName(QA_DB);
  return execSync(
    `${QA_COMPOSE} exec -T postgres psql -X -q -v ON_ERROR_STOP=1 -U meddoc -d ${shellQuote(QA_DB)} -A -t -c ${shellQuote(sql)}`,
    {
      encoding: "utf8",
      stdio: ["ignore", "pipe", "pipe"],
      maxBuffer: 4 * 1024 * 1024,
    },
  ).trim();
}

function psqlJson<T>(sql: string): T {
  const output = psql(sql);
  if (!output) throw new Error("QA database returned no JSON row.");
  return JSON.parse(output) as T;
}

function expectPsqlRejected(sql: string, expectedError: string): void {
  assertNonProdDbName(QA_DB);
  try {
    execSync(
      `${QA_COMPOSE} exec -T postgres psql -X -q -v ON_ERROR_STOP=1 -U meddoc -d ${shellQuote(QA_DB)} -c ${shellQuote(sql)}`,
      {
        encoding: "utf8",
        stdio: ["ignore", "pipe", "pipe"],
        maxBuffer: 1024 * 1024,
      },
    );
  } catch (error) {
    const stderr =
      error && typeof error === "object" && "stderr" in error
        ? String((error as { stderr?: unknown }).stderr ?? "")
        : "";
    if (stderr.includes(expectedError)) return;
    throw new Error(
      `QA database rejected the adversarial write for an unexpected reason: ${stderr.slice(0, 800)}`,
    );
  }
  throw new Error(
    `QA database accepted an adversarial Template Twin write that should have failed: ${expectedError}`,
  );
}

export function setTemplateTwinQaPractice(input: {
  email: string;
  enabled: boolean;
}): { userId: string; practiceId: string } {
  assertSyntheticEmail(input.email);
  const enabledSql = input.enabled ? "true" : "false";
  return psqlJson(`
    WITH verified AS (
      UPDATE users
      SET "emailVerified" = COALESCE("emailVerified", CURRENT_TIMESTAMP)
      WHERE email = ${sqlLiteral(input.email.toLowerCase())}
      RETURNING id, "practiceId"
    ), enabled AS (
      UPDATE practices p
      SET "templateTwinEnabled" = ${enabledSql}
      FROM verified v
      WHERE p.id = v."practiceId"
      RETURNING p.id
    )
    SELECT json_build_object(
      'userId', v.id,
      'practiceId', v."practiceId"
    )
    FROM verified v
    JOIN enabled e ON e.id = v."practiceId";
  `);
}

export function readTemplateTwinQaFields(noteTemplateId: string): {
  fields: TemplateTwinQaField[];
  mappingsSha256: string;
} {
  const rows = psqlJson<
    Array<{
      fieldId: string;
      originalLabel: string;
      fieldKind: string;
      clinicalConcept: string | null;
      expectedDataType: SemanticMapping["expectedDataType"];
      polarityBehavior: SemanticMapping["polarityBehavior"];
      temporality: SemanticMapping["temporality"];
      laterality: SemanticMapping["laterality"];
      unitPolicy: SemanticMapping["unitPolicy"];
      approvedSynonyms: string[];
      required: boolean;
      blankPolicy: SemanticMapping["blankPolicy"];
      unknownPolicy: SemanticMapping["unknownPolicy"];
      practiceDefault: string | null;
      status: SemanticMapping["status"];
    }>
  >(`
    SELECT COALESCE(json_agg(json_build_object(
      'fieldId', f."fieldId",
      'originalLabel', f."originalLabel",
      'fieldKind', f."fieldKind",
      'clinicalConcept', m."clinicalConcept",
      'expectedDataType', m."expectedDataType",
      'polarityBehavior', m."polarityBehavior",
      'temporality', m.temporality,
      'laterality', m.laterality,
      'unitPolicy', m."unitPolicy",
      'approvedSynonyms', m."approvedSynonyms",
      'required', m.required,
      'blankPolicy', m."blankPolicy",
      'unknownPolicy', m."unknownPolicy",
      'practiceDefault', m."practiceDefault",
      'status', lower(m."mappingStatus"::text)
    ) ORDER BY f."displayOrder"), '[]'::json)
    FROM template_twin_compiled_versions c
    JOIN template_twin_field_definitions f
      ON f."compiledVersionId" = c.id
    JOIN template_twin_semantic_mappings m
      ON m."fieldDefinitionId" = f.id
    WHERE c."noteTemplateId" = ${sqlLiteral(noteTemplateId)};
  `);

  const fields: TemplateTwinQaField[] = rows.map((row) => ({
    fieldId: row.fieldId,
    originalLabel: row.originalLabel,
    fieldKind: row.fieldKind,
    mapping: {
      fieldId: row.fieldId,
      clinicalConcept: row.clinicalConcept,
      expectedDataType: row.expectedDataType,
      polarityBehavior: row.polarityBehavior,
      temporality: row.temporality,
      laterality: row.laterality,
      unitPolicy: row.unitPolicy,
      approvedSynonyms: row.approvedSynonyms,
      required: row.required,
      blankPolicy: row.blankPolicy,
      unknownPolicy: row.unknownPolicy,
      practiceDefault: row.practiceDefault,
      status: row.status,
    },
  }));
  return {
    fields,
    mappingsSha256: templateTwinMappingsSha256(
      fields.map((field) => field.mapping),
    ),
  };
}

export function readTemplateTwinQaFill(
  visitId: string,
): TemplateTwinQaFillState | null {
  return psqlJson<TemplateTwinQaFillState | null>(`
    SELECT COALESCE((
      SELECT json_build_object(
        'id', f.id,
        'status', f.status,
        'manifestVersion', f."manifestVersion",
        'fillManifest', f."fillManifest",
        'manifestSha256', f."manifestSha256",
        'soapVersion', f."soapVersion",
        'soapSha256', f."soapSha256",
        'outputObjectKey', f."outputObjectKey",
        'outputVersionId', f."outputVersionId",
        'outputEtag', f."outputEtag",
        'outputSha256', f."outputSha256",
        'outputSizeBytes', f."outputSizeBytes",
        'roundTripVerified', f."roundTripVerified",
        'visitStatus', v.status,
        'currentSoapVersion', v."soapVersion",
        'currentSoapFinal', v."soapFinal",
        'noteTemplateId', v."noteTemplateId",
        'noteTemplateVersion', v."noteTemplateVersion"
      )
      FROM transcribe_visits v
      JOIN template_twin_fill_manifests f ON f."visitId" = v.id
      WHERE v.id = ${sqlLiteral(visitId)}
    ), 'null'::json);
  `);
}

export function readTemplateTwinQaInventory(
  practiceId: string,
): TemplateTwinQaInventory {
  return psqlJson(`
    SELECT json_build_object(
      'sourceArtifacts', (SELECT count(*) FROM template_twin_source_artifacts WHERE "practiceId" = ${sqlLiteral(practiceId)}),
      'compiledVersions', (SELECT count(*) FROM template_twin_compiled_versions c JOIN template_twin_source_artifacts s ON s.id = c."sourceArtifactId" WHERE s."practiceId" = ${sqlLiteral(practiceId)}),
      'fieldDefinitions', (SELECT count(*) FROM template_twin_field_definitions f JOIN template_twin_compiled_versions c ON c.id = f."compiledVersionId" JOIN template_twin_source_artifacts s ON s.id = c."sourceArtifactId" WHERE s."practiceId" = ${sqlLiteral(practiceId)}),
      'certifications', (SELECT count(*) FROM template_twin_certifications cert JOIN template_twin_compiled_versions c ON c.id = cert."compiledVersionId" JOIN template_twin_source_artifacts s ON s.id = c."sourceArtifactId" WHERE s."practiceId" = ${sqlLiteral(practiceId)}),
      'fills', (SELECT count(*) FROM template_twin_fill_manifests WHERE "practiceId" = ${sqlLiteral(practiceId)}),
      'reviewDecisions', (SELECT count(*) FROM template_twin_review_decisions r JOIN template_twin_fill_manifests f ON f.id = r."fillManifestId" WHERE f."practiceId" = ${sqlLiteral(practiceId)}),
      'objectLedgerRows', (SELECT count(*) FROM template_twin_object_ledgers WHERE "practiceId" = ${sqlLiteral(practiceId)}),
      'auditOutboxRows', (SELECT count(*) FROM template_twin_audit_outbox WHERE "practiceId" = ${sqlLiteral(practiceId)})
    );
  `);
}

/**
 * Direct-database adversarial checks against the migrated QA schema. Each
 * statement runs inside an uncommitted transaction; the expected trigger
 * error aborts the transaction, so no test mutation survives. If a trigger is
 * absent, the SQL succeeds and the helper fails the E2E explicitly.
 */
export function assertTemplateTwinQaDatabaseGuards(input: {
  fillManifestId: string;
  foreignNoteTemplateId: string;
}): void {
  const suffix = input.fillManifestId.replace(/[^A-Za-z0-9]/g, "").slice(-16);
  const foreignPracticeId = `qa-template-twin-foreign-${suffix}`;
  const foreignReviewerId = `qa-template-twin-reviewer-${suffix}`;
  expectPsqlRejected(
    `
      BEGIN;
      INSERT INTO practices (id, name, slug, "isActive", "updatedAt")
      VALUES (
        ${sqlLiteral(foreignPracticeId)},
        'Synthetic foreign practice',
        ${sqlLiteral(`qa-template-twin-foreign-${suffix}`)},
        true,
        CURRENT_TIMESTAMP
      );
      UPDATE template_twin_fill_manifests
      SET "practiceId" = ${sqlLiteral(foreignPracticeId)}
      WHERE id = ${sqlLiteral(input.fillManifestId)};
      ROLLBACK;
    `,
    "Template Twin fill tenant or lineage mismatch",
  );

  expectPsqlRejected(
    `
      BEGIN;
      UPDATE template_twin_fill_manifests
      SET "outputObjectKey" = ${sqlLiteral(`practices/${foreignPracticeId}/template-twin/outputs/synthetic/wrong.docx`)}
      WHERE id = ${sqlLiteral(input.fillManifestId)};
      ROLLBACK;
    `,
    "Template Twin output key tenant lineage mismatch",
  );

  expectPsqlRejected(
    `
      BEGIN;
      UPDATE template_twin_fill_manifests
      SET "outputObjectKey" =
        'practices/' || "practiceId" || '/template-twin/outputs/' || "visitId" || '/' ||
        CASE WHEN "manifestSha256" = repeat('0', 64) THEN repeat('1', 64) ELSE repeat('0', 64) END ||
        '/tampered/' || "outputSha256" || '.docx'
      WHERE id = ${sqlLiteral(input.fillManifestId)};
      ROLLBACK;
    `,
    "Template Twin output key manifest hash mismatch",
  );

  expectPsqlRejected(
    `
      BEGIN;
      UPDATE template_twin_fill_manifests
      SET "outputSha256" =
        CASE WHEN "outputSha256" = repeat('0', 64) THEN repeat('1', 64) ELSE repeat('0', 64) END
      WHERE id = ${sqlLiteral(input.fillManifestId)};
      ROLLBACK;
    `,
    "Template Twin output key content hash mismatch",
  );

  expectPsqlRejected(
    `
      BEGIN;
      UPDATE template_twin_object_ledgers
      SET "sha256" =
        CASE WHEN "sha256" = repeat('0', 64) THEN repeat('1', 64) ELSE repeat('0', 64) END
      WHERE "claimType" = 'fill_manifest'
        AND "claimId" = ${sqlLiteral(input.fillManifestId)}
        AND "objectKey" = (
          SELECT "outputObjectKey" FROM template_twin_fill_manifests
          WHERE id = ${sqlLiteral(input.fillManifestId)}
        );
      ROLLBACK;
    `,
    "Template Twin object ledger claim integrity mismatch",
  );

  expectPsqlRejected(
    `
      BEGIN;
      UPDATE template_twin_object_ledgers
      SET "state" = 'WRITTEN_UNCLAIMED', "claimType" = NULL, "claimId" = NULL
      WHERE "claimType" = 'fill_manifest'
        AND "claimId" = ${sqlLiteral(input.fillManifestId)}
        AND "objectKey" = (
          SELECT "outputObjectKey" FROM template_twin_fill_manifests
          WHERE id = ${sqlLiteral(input.fillManifestId)}
        );
      ROLLBACK;
    `,
    "Template Twin object ledger claim ownership missing",
  );

  // A same-tenant active physician is a valid reviewer. This transaction is
  // always rolled back; its purpose is to prove the positive side of the DB
  // invariant before exercising the cross-tenant rejection below.
  psql(`
    BEGIN;
    UPDATE template_twin_fill_manifests f
    SET "reviewedById" = u.id,
        "reviewedAt" = CURRENT_TIMESTAMP,
        "reviewedManifestVersion" = f."manifestVersion",
        "reviewedManifestSha256" = f."manifestSha256"
    FROM transcribe_visits v
    JOIN users u ON u.id = v."userId"
    WHERE f.id = ${sqlLiteral(input.fillManifestId)}
      AND v.id = f."visitId"
      AND u.role = 'DOCTOR'
      AND u."isActive" = true;
    ROLLBACK;
  `);

  expectPsqlRejected(
    `
      BEGIN;
      INSERT INTO practices (id, name, slug, "isActive", "updatedAt")
      VALUES (
        ${sqlLiteral(foreignPracticeId)},
        'Synthetic foreign reviewer practice',
        ${sqlLiteral(`qa-template-twin-reviewer-${suffix}`)},
        true,
        CURRENT_TIMESTAMP
      );
      INSERT INTO users (
        id, email, name, "passwordHash", role, "isActive", "practiceId", "updatedAt"
      ) VALUES (
        ${sqlLiteral(foreignReviewerId)},
        ${sqlLiteral(`${foreignReviewerId}@synthetic.test`)},
        'Synthetic Foreign Reviewer',
        'synthetic-not-a-real-password-hash',
        'DOCTOR',
        true,
        ${sqlLiteral(foreignPracticeId)},
        CURRENT_TIMESTAMP
      );
      UPDATE template_twin_fill_manifests f
      SET "reviewedById" = ${sqlLiteral(foreignReviewerId)},
          "reviewedAt" = CURRENT_TIMESTAMP,
          "reviewedManifestVersion" = f."manifestVersion",
          "reviewedManifestSha256" = f."manifestSha256"
      WHERE f.id = ${sqlLiteral(input.fillManifestId)}
      ;
      ROLLBACK;
    `,
    "Template Twin fill reviewer tenant mismatch",
  );

  expectPsqlRejected(
    `
      BEGIN;
      UPDATE template_twin_review_decisions r
      SET "fieldDefinitionId" = foreign_field.id,
          "fieldId" = foreign_field."fieldId"
      FROM (
        SELECT f.id, f."fieldId"
        FROM template_twin_field_definitions f
        JOIN template_twin_compiled_versions c
          ON c.id = f."compiledVersionId"
        WHERE c."noteTemplateId" = ${sqlLiteral(input.foreignNoteTemplateId)}
        ORDER BY f."displayOrder"
        LIMIT 1
      ) foreign_field
      WHERE r."fillManifestId" = ${sqlLiteral(input.fillManifestId)};
      ROLLBACK;
    `,
    "Template Twin review field lineage mismatch",
  );
}

/** QA-only fault injection used to exercise the public retry/worker boundary. */
export function markTemplateTwinQaVisitFailed(visitId: string): void {
  psql(`
    UPDATE transcribe_visits
    SET status = 'FAILED',
        "failureCategory" = 'transient',
        "processingFinishedAt" = CURRENT_TIMESTAMP
    WHERE id = ${sqlLiteral(visitId)};
  `);
}

/**
 * Delete only the exact immutable synthetic QA version pinned by the fill.
 * A later version at the same key must never satisfy a version-bound read.
 */
export function removeTemplateTwinQaObjectVersion(
  objectKey: string,
  objectVersionId: string,
): void {
  if (
    !/^practices\/[A-Za-z0-9_-]+\/template-twin\/outputs\/[A-Za-z0-9_-]+\/[a-f0-9]{64}\/[A-Za-z0-9_-]+\/[a-f0-9]{64}\.docx$/.test(
      objectKey,
    )
  ) {
    throw new Error(
      "Refusing to replace an object outside a synthetic Template Twin output key.",
    );
  }
  if (!objectVersionId.trim() || /[\s'"\\]/.test(objectVersionId)) {
    throw new Error("Refusing to remove an invalid synthetic object version.");
  }
  const target = `qa/${TEMPLATE_BUCKET}/${objectKey}`;
  const minioCommand = [
    "export MC_CONFIG_DIR=/tmp/template-twin-e2e-mc",
    "mc alias set qa http://127.0.0.1:9000 qa_minio qa_minio_pw >/dev/null",
    `mc rm --force --version-id ${shellQuote(objectVersionId)} ${shellQuote(target)} >/dev/null`,
  ].join(" && ");
  execSync(`${QA_COMPOSE} exec -T minio sh -c ${shellQuote(minioCommand)}`, {
    stdio: ["ignore", "pipe", "pipe"],
    maxBuffer: 1024 * 1024,
  });
}
