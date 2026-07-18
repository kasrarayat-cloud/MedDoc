import {
  execSync,
  spawn,
  type ChildProcessWithoutNullStreams,
} from "node:child_process";

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
  roundTripVerification: {
    verificationContractVersion?: string;
    verified?: boolean;
    packageCheck?: string;
    fieldCheck?: string;
    staticRegionCheck?: string;
    fields?: Array<{
      fieldId?: string;
      occurrences?: number;
      bindingEvidence?: unknown;
    }>;
  } | null;
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

export interface TemplateTwinProviderAtomicityInventory {
  visits: number;
  signedVisits: number;
  completeManifests: number;
  layerRows: number;
  succeededLayers: number;
  notApplicableLayers: number;
  providerExecutions: number;
  providerInvocations: number;
  nonSucceededProviderExecutions: number;
  duplicateProviderIdempotencyKeys: number;
  fillManifests: number;
  outputObjects: number;
  layerCompletionAudits: number;
  completionAudits: number;
}

export interface TemplateTwinProviderProjectionRetryInventory {
  projectionAttemptCount: number;
  manifestAttemptCount: number;
  providerExecutionStatus: string;
  providerInvocationCount: number;
  layerStatus: string;
  layerCompletionAudits: number;
  completionAudits: number;
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

interface QaPsqlSessionResult {
  code: number | null;
  stdout: string;
  stderr: string;
}

interface QaPsqlSession {
  child: ChildProcessWithoutNullStreams;
  result: Promise<QaPsqlSessionResult>;
  stdout(): string;
  stderr(): string;
  exited(): boolean;
}

function openQaPsqlSession(applicationName: string): QaPsqlSession {
  assertNonProdDbName(QA_DB);
  if (!/^qa-template-twin-[a-z0-9-]+$/i.test(applicationName)) {
    throw new Error(
      "Refusing to open an unnamed Template Twin QA SQL session.",
    );
  }
  const command =
    `${QA_COMPOSE} exec -T postgres psql -X -q -v ON_ERROR_STOP=1 ` +
    `-U meddoc -d ${shellQuote(QA_DB)} -A -t`;
  const child = spawn(command, {
    shell: true,
    stdio: ["pipe", "pipe", "pipe"],
  }) as ChildProcessWithoutNullStreams;
  child.stdout.setEncoding("utf8");
  child.stderr.setEncoding("utf8");
  let stdout = "";
  let stderr = "";
  let exited = false;
  child.stdout.on("data", (chunk: string) => {
    stdout += chunk;
  });
  child.stderr.on("data", (chunk: string) => {
    stderr += chunk;
  });
  const result = new Promise<QaPsqlSessionResult>((resolve) => {
    child.once("exit", (code) => {
      exited = true;
      resolve({ code, stdout, stderr });
    });
  });
  child.stdin.write(`SET application_name = ${sqlLiteral(applicationName)};\n`);
  return {
    child,
    result,
    stdout: () => stdout,
    stderr: () => stderr,
    exited: () => exited,
  };
}

async function waitForQaSessionOutput(
  session: QaPsqlSession,
  marker: string,
  timeoutMs = 10_000,
): Promise<void> {
  const deadline = Date.now() + timeoutMs;
  while (Date.now() < deadline) {
    if (session.stdout().includes(marker)) return;
    if (session.exited()) {
      throw new Error(
        `QA SQL session exited before ${marker}: ${session.stderr().slice(0, 800)}`,
      );
    }
    await new Promise((resolve) => setTimeout(resolve, 25));
  }
  throw new Error(`Timed out waiting for QA SQL marker ${marker}.`);
}

async function waitForQaSessionExit(
  session: QaPsqlSession,
  timeoutMs = 10_000,
): Promise<QaPsqlSessionResult> {
  let timer: ReturnType<typeof setTimeout> | undefined;
  try {
    return await Promise.race([
      session.result,
      new Promise<never>((_, reject) => {
        timer = setTimeout(
          () =>
            reject(
              new Error("Timed out waiting for a QA SQL session to exit."),
            ),
          timeoutMs,
        );
      }),
    ]);
  } finally {
    if (timer) clearTimeout(timer);
  }
}

async function rollbackOpenQaPsqlSession(
  session: QaPsqlSession | null,
): Promise<void> {
  if (!session || session.exited()) return;
  if (!session.child.stdin.writableEnded) {
    session.child.stdin.end("ROLLBACK;\n\\q\n");
  } else {
    session.child.kill();
  }
  await waitForQaSessionExit(session).catch(() => {
    session.child.kill();
  });
}

async function waitForQaSessionLock(input: {
  session: QaPsqlSession;
  applicationName: string;
  operation: string;
  timeoutMs?: number;
}): Promise<void> {
  const deadline = Date.now() + (input.timeoutMs ?? 10_000);
  while (Date.now() < deadline) {
    if (input.session.exited()) {
      throw new Error(
        `${input.operation} exited instead of waiting on the concurrent lineage lock: ${input.session
          .stderr()
          .slice(0, 800)}`,
      );
    }
    const waitEvent = psql(`
      SELECT COALESCE((
        SELECT "wait_event_type"
        FROM pg_stat_activity
        WHERE application_name = ${sqlLiteral(input.applicationName)}
        LIMIT 1
      ), 'missing');
    `);
    if (waitEvent === "Lock") return;
    await new Promise((resolve) => setTimeout(resolve, 50));
  }
  throw new Error(
    `${input.operation} never blocked on the concurrent lineage transaction.`,
  );
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
    DO $template_twin_qa_rollout$
    DECLARE
      owning_user TEXT;
      owning_practice TEXT;
      lineage_contracted BOOLEAN;
    BEGIN
      SELECT id, "practiceId"
      INTO owning_user, owning_practice
      FROM users
      WHERE email = ${sqlLiteral(input.email.toLowerCase())};
      IF owning_user IS NULL OR owning_practice IS NULL THEN
        RAISE EXCEPTION 'Synthetic Template Twin QA actor was not found';
      END IF;

      SELECT EXISTS (
        SELECT 1
        FROM template_twin_lineage_migration_progress
        WHERE "operationKey" = 'note_templates_lineage_v1'
          AND phase = 'CONTRACTED'
      ) INTO lineage_contracted;
      IF ${enabledSql} AND NOT lineage_contracted THEN
        RAISE EXCEPTION 'Template Twin lineage migration is not contracted';
      END IF;

      -- Test setup follows the production lock order exactly. The DO block is
      -- one transaction, so neither generation becomes externally visible
      -- until both mutations commit.
      PERFORM 1
      FROM template_twin_rollout_controls
      WHERE id = 'global'
      FOR UPDATE;
      IF NOT FOUND THEN
        RAISE EXCEPTION 'Global Template Twin rollout control is unavailable';
      END IF;
      PERFORM 1
      FROM practices
      WHERE id = owning_practice
      FOR UPDATE;
      IF NOT FOUND THEN
        RAISE EXCEPTION 'Synthetic Template Twin QA practice is unavailable';
      END IF;

      -- The actor row is deliberately taken only after global and practice.
      -- Moving this write above either rollout lock can deadlock a worker that
      -- follows global -> practice -> operation -> actor.
      UPDATE users
      SET "emailVerified" = COALESCE("emailVerified", CURRENT_TIMESTAMP)
      WHERE id = owning_user;

      UPDATE template_twin_rollout_controls
      SET enabled = ${enabledSql},
          generation = generation + 1,
          "updatedAt" = CURRENT_TIMESTAMP
      WHERE id = 'global'
        AND enabled IS DISTINCT FROM ${enabledSql};
      UPDATE practices
      SET "templateTwinEnabled" = ${enabledSql},
          "templateTwinRolloutGeneration" =
            "templateTwinRolloutGeneration" + 1
      WHERE id = owning_practice
        AND "templateTwinEnabled" IS DISTINCT FROM ${enabledSql};
    END
    $template_twin_qa_rollout$;

    SELECT json_build_object(
      'userId', id,
      'practiceId', "practiceId"
    )
    FROM users
    WHERE email = ${sqlLiteral(input.email.toLowerCase())};
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

export function readTemplateTwinQaApprovedMappingsSha256(
  noteTemplateId: string,
): string {
  const value = psqlJson<string | null>(`
    SELECT to_json(certification."approvedMappingsSha256")
    FROM template_twin_compiled_versions compiled
    JOIN template_twin_certifications certification
      ON certification."compiledVersionId" = compiled.id
    WHERE compiled."noteTemplateId" = ${sqlLiteral(noteTemplateId)};
  `);
  if (!value || !/^[a-f0-9]{64}$/.test(value)) {
    throw new Error(
      "The synthetic QA template has no immutable approved mapping version.",
    );
  }
  return value;
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
        'roundTripVerification', f."roundTripVerification",
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

export interface TemplateTwinStagingQaRunState {
  runId: string;
  visitId: string;
  practiceId: string;
  doctorId: string;
  status: string;
  attempt: number;
  fixtureVersion: string;
  pinnedGlobalRolloutGeneration: string;
  pinnedPracticeRolloutGeneration: string;
  visitStatus: string;
}

export interface TemplateTwinStagingQaIdempotencyInventory {
  matchingRuns: number;
  matchingVisits: number;
  matchingFills: number;
  matchingOutputObjects: number;
}

export function readTemplateTwinStagingQaRunByVisit(
  visitId: string,
): TemplateTwinStagingQaRunState | null {
  return psqlJson<TemplateTwinStagingQaRunState | null>(`
    SELECT COALESCE((
      SELECT json_build_object(
        'runId', run.id,
        'visitId', run."visitId",
        'practiceId', run."practiceId",
        'doctorId', run."doctorId",
        'status', run.status,
        'attempt', run.attempt,
        'fixtureVersion', run."fixtureVersion",
        'pinnedGlobalRolloutGeneration', run."pinnedGlobalRolloutGeneration"::text,
        'pinnedPracticeRolloutGeneration', run."pinnedPracticeRolloutGeneration"::text,
        'visitStatus', visit.status
      )
      FROM template_twin_synthetic_qa_runs run
      JOIN transcribe_visits visit ON visit.id = run."visitId"
      WHERE run."visitId" = ${sqlLiteral(visitId)}
    ), 'null'::json);
  `);
}

/**
 * Counts the durable records attributable to one browser admission token.
 * The raw token never enters this helper: it follows the stored request hash
 * from an already-owned synthetic QA run. A byte-for-byte HTTP replay must
 * leave all four counts unchanged.
 */
export function readTemplateTwinStagingQaIdempotencyInventory(
  runId: string,
): TemplateTwinStagingQaIdempotencyInventory {
  return psqlJson<TemplateTwinStagingQaIdempotencyInventory>(`
    WITH target AS (
      SELECT "practiceId", "doctorId", "requestSha256"
      FROM template_twin_synthetic_qa_runs
      WHERE id = ${sqlLiteral(runId)}
    ), matching_runs AS (
      SELECT run.id, run."visitId"
      FROM template_twin_synthetic_qa_runs run
      JOIN target
        ON target."practiceId" = run."practiceId"
       AND target."doctorId" = run."doctorId"
       AND target."requestSha256" = run."requestSha256"
    )
    SELECT json_build_object(
      'matchingRuns', (SELECT count(*) FROM matching_runs),
      'matchingVisits', (
        SELECT count(*)
        FROM transcribe_visits visit
        JOIN matching_runs run ON run."visitId" = visit.id
      ),
      'matchingFills', (
        SELECT count(*)
        FROM template_twin_fill_manifests fill
        JOIN matching_runs run ON run."visitId" = fill."visitId"
      ),
      'matchingOutputObjects', (
        SELECT count(*)
        FROM template_twin_object_ledgers ledger
        JOIN template_twin_fill_manifests fill
          ON fill."outputObjectKey" = ledger."objectKey"
        JOIN matching_runs run ON run."visitId" = fill."visitId"
      )
    );
  `);
}

/** Direct-database tenant backstop for the authenticated staging admission. */
export function assertTemplateTwinStagingQaDatabaseTenantGuard(
  runId: string,
): void {
  const suffix = runId.replace(/[^A-Za-z0-9]/g, "").slice(-16);
  const foreignPracticeId = `qa-template-twin-staging-foreign-${suffix}`;
  expectPsqlRejected(
    `
      BEGIN;
      INSERT INTO practices (id, name, slug, "isActive", "updatedAt")
      VALUES (
        ${sqlLiteral(foreignPracticeId)},
        'Synthetic staging tenant adversary',
        ${sqlLiteral(`qa-tt-staging-foreign-${suffix}`)},
        true,
        CURRENT_TIMESTAMP
      );
      UPDATE template_twin_synthetic_qa_runs
      SET "practiceId" = ${sqlLiteral(foreignPracticeId)}
      WHERE id = ${sqlLiteral(runId)};
      ROLLBACK;
    `,
    // The durable admission is checked before the broader tenant lineage.
    // A copied practice cannot match the admission's immutable tenant.
    "Template Twin synthetic QA run admission mismatch",
  );
}

/**
 * Direct-service-role tampering probes for the staging admission record and
 * its pinned encounter evidence. The QA database is disposable and guarded
 * by assertNonProdDbName; every rejected write is isolated in its own aborted
 * transaction. A before/after snapshot additionally proves that none of the
 * attempted statements left a partial mutation behind.
 */
export function assertTemplateTwinStagingQaDatabaseTamperGuards(
  runId: string,
): void {
  const suffix = runId.replace(/[^A-Za-z0-9]/g, "").slice(-16);
  const foreignPracticeId = `qa-template-twin-visit-foreign-${suffix}`;
  const foreignPatientId = `qa-template-twin-patient-foreign-${suffix}`;
  const invariantSnapshot = (): string =>
    psql(`
      SELECT json_build_object(
        'run', json_build_object(
          'practiceId', run."practiceId",
          'doctorId', run."doctorId",
          'visitId', run."visitId",
          'noteTemplateId', run."noteTemplateId",
          'noteTemplateVersion', run."noteTemplateVersion",
          'requestSha256', run."requestSha256",
          'payloadSha256', run."payloadSha256",
          'mode', run.mode,
          'fixtureVersion', run."fixtureVersion",
          'globalGeneration', run."pinnedGlobalRolloutGeneration"::text,
          'practiceGeneration', run."pinnedPracticeRolloutGeneration"::text,
          'status', run.status,
          'attempt', run.attempt,
          'enqueuedAt', run."enqueuedAt"
        ),
        'visit', json_build_object(
          'userId', visit."userId",
          'patientId', visit."patientId",
          'patientName', visit."patientName",
          'inputMode', visit."inputMode",
          'rawTextInput', visit."rawTextInput",
          'dictationAudioKey', visit."dictationAudioKey",
          'audioMimeType', visit."audioMimeType",
          'audioSizeBytes', visit."audioSizeBytes",
          'noteTemplateId', visit."noteTemplateId",
          'noteTemplateVersion', visit."noteTemplateVersion"
        ),
        'patient', json_build_object(
          'practiceId', patient."practiceId",
          'name', patient.name,
          'externalId', patient."externalId",
          'dateOfBirth', patient."dateOfBirth",
          'mrn', patient.mrn,
          'insurance', patient.insurance,
          'problemList', patient."problemList",
          'weightKg', patient."weightKg",
          'allergies', patient.allergies,
          'deletedAt', patient."deletedAt"
        )
      )
      FROM template_twin_synthetic_qa_runs run
      JOIN transcribe_visits visit ON visit.id = run."visitId"
      JOIN transcribe_md_patients patient ON patient.id = visit."patientId"
      WHERE run.id = ${sqlLiteral(runId)};
    `);

  const before = invariantSnapshot();
  const beforeState = before
    ? (JSON.parse(before) as { run?: { status?: string } })
    : null;
  if (beforeState?.run?.status !== "COMPLETED") {
    throw new Error(
      "Template Twin staging DB tamper probes require one completed synthetic QA run.",
    );
  }

  expectPsqlRejected(
    `
      BEGIN;
      UPDATE template_twin_synthetic_qa_runs
      SET "payloadSha256" =
        CASE WHEN "payloadSha256" = repeat('0', 64)
          THEN repeat('1', 64) ELSE repeat('0', 64) END
      WHERE id = ${sqlLiteral(runId)};
      ROLLBACK;
    `,
    "Template Twin synthetic QA admission identity is immutable",
  );

  expectPsqlRejected(
    `
      BEGIN;
      UPDATE transcribe_visits visit
      SET "rawTextInput" = COALESCE(visit."rawTextInput", '') ||
        ' Synthetic database tamper probe.'
      FROM template_twin_synthetic_qa_runs run
      WHERE run.id = ${sqlLiteral(runId)}
        AND visit.id = run."visitId";
      ROLLBACK;
    `,
    "Template Twin synthetic QA visit provenance is immutable",
  );

  expectPsqlRejected(
    `
      BEGIN;
      INSERT INTO practices (id, name, slug, "isActive", "updatedAt")
      VALUES (
        ${sqlLiteral(foreignPracticeId)},
        'Synthetic staging visit adversary',
        ${sqlLiteral(`qa-tt-visit-foreign-${suffix}`)},
        true,
        CURRENT_TIMESTAMP
      );
      INSERT INTO transcribe_md_patients (
        id, "practiceId", name, "externalId", "updatedAt"
      ) VALUES (
        ${sqlLiteral(foreignPatientId)},
        ${sqlLiteral(foreignPracticeId)},
        'Synthetic Foreign QA Patient',
        'SYNTHETIC-FOREIGN-QA-ONLY',
        CURRENT_TIMESTAMP
      );
      UPDATE transcribe_visits visit
      SET "patientId" = ${sqlLiteral(foreignPatientId)}
      FROM template_twin_synthetic_qa_runs run
      WHERE run.id = ${sqlLiteral(runId)}
        AND visit.id = run."visitId";
      ROLLBACK;
    `,
    "Template Twin synthetic QA visit provenance is immutable",
  );

  expectPsqlRejected(
    `
      BEGIN;
      UPDATE transcribe_visits visit
      SET "dictationAudioKey" =
        'synthetic-qa/tamper-probe/mock-voice.wav',
          "audioMimeType" = 'audio/wav',
          "audioSizeBytes" = 44
      FROM template_twin_synthetic_qa_runs run
      WHERE run.id = ${sqlLiteral(runId)}
        AND visit.id = run."visitId";
      ROLLBACK;
    `,
    "Template Twin synthetic QA visit provenance is immutable",
  );

  expectPsqlRejected(
    `
      BEGIN;
      UPDATE transcribe_md_patients patient
      SET name = 'Synthetic QA identity tamper probe'
      FROM transcribe_visits visit
      JOIN template_twin_synthetic_qa_runs run ON run."visitId" = visit.id
      WHERE run.id = ${sqlLiteral(runId)}
        AND patient.id = visit."patientId";
      ROLLBACK;
    `,
    "Template Twin synthetic QA patient is immutable",
  );

  expectPsqlRejected(
    `
      BEGIN;
      UPDATE transcribe_md_patients patient
      SET mrn = 'SYNTHETIC-TAMPER-PROBE'
      FROM transcribe_visits visit
      JOIN template_twin_synthetic_qa_runs run ON run."visitId" = visit.id
      WHERE run.id = ${sqlLiteral(runId)}
        AND patient.id = visit."patientId";
      ROLLBACK;
    `,
    "Template Twin synthetic QA patient is immutable",
  );

  expectPsqlRejected(
    `
      BEGIN;
      DELETE FROM transcribe_md_patients patient
      USING transcribe_visits visit, template_twin_synthetic_qa_runs run
      WHERE run.id = ${sqlLiteral(runId)}
        AND visit.id = run."visitId"
        AND patient.id = visit."patientId";
      ROLLBACK;
    `,
    "Template Twin synthetic QA patient cannot be deleted",
  );

  assertTemplateTwinStagingQaDatabaseTenantGuard(runId);

  expectPsqlRejected(
    `
      BEGIN;
      UPDATE template_twin_synthetic_qa_runs
      SET attempt = attempt + 2
      WHERE id = ${sqlLiteral(runId)};
      ROLLBACK;
    `,
    "Template Twin synthetic QA attempt is not monotonic",
  );

  expectPsqlRejected(
    `
      BEGIN;
      UPDATE template_twin_synthetic_qa_runs
      SET attempt = attempt - 1
      WHERE id = ${sqlLiteral(runId)};
      ROLLBACK;
    `,
    "Template Twin synthetic QA attempt is not monotonic",
  );

  expectPsqlRejected(
    `
      BEGIN;
      UPDATE template_twin_synthetic_qa_runs
      SET status = 'PENDING_ENQUEUE', "enqueuedAt" = NULL
      WHERE id = ${sqlLiteral(runId)};
      ROLLBACK;
    `,
    "Template Twin synthetic QA queue transition is invalid",
  );

  const after = invariantSnapshot();
  if (after !== before) {
    throw new Error(
      "A rejected Template Twin staging database tamper changed immutable QA state.",
    );
  }
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

export function readTemplateTwinProviderAtomicityInventory(
  visitIds: readonly string[],
): TemplateTwinProviderAtomicityInventory {
  if (
    visitIds.length === 0 ||
    visitIds.some((visitId) => !/^[A-Za-z0-9_-]{8,128}$/u.test(visitId))
  ) {
    throw new Error(
      "Provider atomicity inventory requires synthetic visit IDs.",
    );
  }
  const ids = visitIds.map(sqlLiteral).join(", ");
  return psqlJson(`
    WITH selected_visits AS (
      SELECT id FROM transcribe_visits WHERE id IN (${ids})
    ), selected_manifests AS (
      SELECT manifest.*
      FROM visit_automation_manifests manifest
      JOIN selected_visits visit ON visit.id = manifest."visitId"
    ), selected_layers AS (
      SELECT layer.*
      FROM visit_automation_layers layer
      JOIN selected_manifests manifest ON manifest.id = layer."manifestId"
    ), selected_executions AS (
      SELECT execution.*
      FROM visit_automation_provider_executions execution
      JOIN selected_manifests manifest ON manifest.id = execution."manifestId"
    ), duplicate_keys AS (
      SELECT "idempotencyKey"
      FROM selected_executions
      GROUP BY "idempotencyKey"
      HAVING count(*) > 1
    )
    SELECT json_build_object(
      'visits', (SELECT count(*)::int FROM selected_visits),
      'signedVisits', (SELECT count(*)::int FROM transcribe_visits visit JOIN selected_visits selected ON selected.id = visit.id WHERE visit.status = 'SIGNED'),
      'completeManifests', (SELECT count(*)::int FROM selected_manifests WHERE status = 'COMPLETE'),
      'layerRows', (SELECT count(*)::int FROM selected_layers),
      'succeededLayers', (SELECT count(*)::int FROM selected_layers WHERE status = 'SUCCEEDED'),
      'notApplicableLayers', (SELECT count(*)::int FROM selected_layers WHERE status = 'NOT_APPLICABLE'),
      'providerExecutions', (SELECT count(*)::int FROM selected_executions),
      'providerInvocations', (SELECT COALESCE(sum("invocationCount"), 0)::int FROM selected_executions),
      'nonSucceededProviderExecutions', (SELECT count(*)::int FROM selected_executions WHERE status <> 'SUCCEEDED'),
      'duplicateProviderIdempotencyKeys', (SELECT count(*)::int FROM duplicate_keys),
      'fillManifests', (SELECT count(*)::int FROM template_twin_fill_manifests fill JOIN selected_visits visit ON visit.id = fill."visitId"),
      'outputObjects', (
        SELECT count(*)::int
        FROM template_twin_object_ledgers ledger
        JOIN template_twin_fill_manifests fill ON fill.id = ledger."claimId"
        JOIN selected_visits visit ON visit.id = fill."visitId"
        WHERE ledger."claimType" = 'fill_manifest'
      ),
      'layerCompletionAudits', (
        SELECT count(*)::int
        FROM template_twin_audit_outbox audit
        JOIN selected_visits visit ON visit.id = audit."targetId"
        WHERE audit."targetType" = 'VisitAutomationLayer'
          AND audit.action = 'VISIT_AUTOMATION_COMPLETED'
      ),
      'completionAudits', (
        SELECT count(*)::int
        FROM template_twin_audit_outbox audit
        JOIN selected_visits visit ON visit.id = audit."targetId"
        WHERE audit."targetType" = 'TranscribeVisit'
          AND audit.action = 'VISIT_AUTOMATION_COMPLETED'
          AND audit."eventKey" LIKE 'visit-automation:completed:%'
      )
    );
  `);
}

/**
 * Installs a disposable, visit-scoped fault at the atomic layer audit insert.
 * A PostgreSQL sequence is intentionally used as the test latch because
 * nextval() is not rolled back: the first three complete projection
 * transactions receive 40001, exhausting the hard retry ceiling, while the
 * BullMQ job retry's fourth projection can commit. The provider result was
 * already committed before this boundary and therefore must be reused.
 */
export function installTemplateTwinProviderProjectionRetryFault(
  visitId: string,
): void {
  if (!/^[A-Za-z0-9_-]{8,128}$/u.test(visitId)) {
    throw new Error("Projection fault injection requires a synthetic visit ID.");
  }
  psql(`
    DROP TRIGGER IF EXISTS qa_tt_provider_projection_retry_fault
      ON template_twin_audit_outbox;
    DROP FUNCTION IF EXISTS qa_tt_provider_projection_retry_fault();
    DROP SEQUENCE IF EXISTS qa_tt_provider_projection_retry_fault_seq;
    CREATE SEQUENCE qa_tt_provider_projection_retry_fault_seq START 1;
    CREATE FUNCTION qa_tt_provider_projection_retry_fault()
    RETURNS trigger AS $body$
    BEGIN
      IF NEW."targetId" = ${sqlLiteral(visitId)}
        AND NEW."targetType" = 'VisitAutomationLayer'
        AND NEW.action = 'VISIT_AUTOMATION_COMPLETED'
        AND NEW.metadata->>'layerId' = 'icd_coding'
        AND nextval('qa_tt_provider_projection_retry_fault_seq') <= 3 THEN
        RAISE EXCEPTION 'synthetic provider projection retry fault'
          USING ERRCODE = '40001';
      END IF;
      RETURN NEW;
    END;
    $body$ LANGUAGE plpgsql;
    CREATE TRIGGER qa_tt_provider_projection_retry_fault
      BEFORE INSERT ON template_twin_audit_outbox
      FOR EACH ROW EXECUTE FUNCTION qa_tt_provider_projection_retry_fault();
  `);
}

export function readTemplateTwinProviderProjectionRetryInventory(
  visitId: string,
): TemplateTwinProviderProjectionRetryInventory {
  if (!/^[A-Za-z0-9_-]{8,128}$/u.test(visitId)) {
    throw new Error("Projection retry inventory requires a synthetic visit ID.");
  }
  return psqlJson<TemplateTwinProviderProjectionRetryInventory>(`
    WITH target_manifest AS (
      SELECT * FROM visit_automation_manifests WHERE "visitId" = ${sqlLiteral(visitId)}
    ), target_layer AS (
      SELECT layer.*
      FROM visit_automation_layers layer
      JOIN target_manifest manifest ON manifest.id = layer."manifestId"
      WHERE layer."layerId" = 'icd_coding'
    ), target_execution AS (
      SELECT execution.*
      FROM visit_automation_provider_executions execution
      JOIN target_layer layer ON layer.id = execution."automationLayerId"
    )
    SELECT json_build_object(
      'projectionAttemptCount', (
        SELECT last_value::int
        FROM qa_tt_provider_projection_retry_fault_seq
      ),
      'manifestAttemptCount', (
        SELECT "attemptCount" FROM target_manifest
      ),
      'providerExecutionStatus', (
        SELECT status::text FROM target_execution
      ),
      'providerInvocationCount', (
        SELECT "invocationCount" FROM target_execution
      ),
      'layerStatus', (
        SELECT status::text FROM target_layer
      ),
      'layerCompletionAudits', (
        SELECT count(*)::int
        FROM template_twin_audit_outbox
        WHERE "targetId" = ${sqlLiteral(visitId)}
          AND "targetType" = 'VisitAutomationLayer'
          AND action = 'VISIT_AUTOMATION_COMPLETED'
          AND metadata->>'layerId' = 'icd_coding'
      ),
      'completionAudits', (
        SELECT count(*)::int
        FROM template_twin_audit_outbox
        WHERE "targetId" = ${sqlLiteral(visitId)}
          AND "targetType" = 'TranscribeVisit'
          AND action = 'VISIT_AUTOMATION_COMPLETED'
          AND "eventKey" LIKE 'visit-automation:completed:%'
      )
    );
  `);
}

export function removeTemplateTwinProviderProjectionRetryFault(): void {
  psql(`
    DROP TRIGGER IF EXISTS qa_tt_provider_projection_retry_fault
      ON template_twin_audit_outbox;
    DROP FUNCTION IF EXISTS qa_tt_provider_projection_retry_fault();
    DROP SEQUENCE IF EXISTS qa_tt_provider_projection_retry_fault_seq;
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
  const foreignTemplateId = `qa-template-twin-template-${suffix}`;
  const foreignCompiledId = `qa-template-twin-compiled-${suffix}`;
  const foreignLineageId = `qa-template-twin-lineage-${suffix}`;

  const foreignTemplateOwnerSetup = `
      INSERT INTO practices (id, name, slug, "isActive", "updatedAt")
      VALUES (
        ${sqlLiteral(foreignPracticeId)},
        'Synthetic foreign lineage practice',
        ${sqlLiteral(`qa-template-twin-lineage-${suffix}`)},
        true,
        CURRENT_TIMESTAMP
      );
      INSERT INTO users (
        id, email, name, "passwordHash", role, "isActive", "practiceId", "updatedAt"
      ) VALUES (
        ${sqlLiteral(foreignReviewerId)},
        ${sqlLiteral(`${foreignReviewerId}@synthetic.test`)},
        'Synthetic Foreign Template Owner',
        'synthetic-not-a-real-password-hash',
        'DOCTOR',
        true,
        ${sqlLiteral(foreignPracticeId)},
        CURRENT_TIMESTAMP
      );
      INSERT INTO note_templates (
        id, "doctorId", name, "encounterType", "specialtyBaseline", sections,
        "styleProfile", version, status, "isSystemDefault", "lineageId",
        "parentVersionId", "templateKind", "versionDescription", "createdAt", "updatedAt"
      )
      SELECT
        ${sqlLiteral(foreignTemplateId)}, ${sqlLiteral(foreignReviewerId)},
        'Synthetic cross-tenant lineage probe', n."encounterType",
        n."specialtyBaseline", n.sections, n."styleProfile", 1, 'draft', false,
        ${sqlLiteral(foreignLineageId)}, NULL, 'template_twin_docx',
        'Synthetic database tenant guard probe', CURRENT_TIMESTAMP, CURRENT_TIMESTAMP
      FROM template_twin_fill_manifests f
      JOIN note_templates n ON n.id = f."noteTemplateId"
      WHERE f.id = ${sqlLiteral(input.fillManifestId)};
  `;

  expectPsqlRejected(
    `
      BEGIN;
      ${foreignTemplateOwnerSetup}
      INSERT INTO template_twin_compiled_versions (
        id, "sourceArtifactId", "noteTemplateId", "compilerVersion",
        "irSchemaVersion", "compiledDocumentIr", "unsupportedElements",
        "structureSha256", "staticContentSha256", "certificationStatus",
        "blockingUnsupportedCount"
      )
      SELECT
        ${sqlLiteral(foreignCompiledId)}, c."sourceArtifactId",
        ${sqlLiteral(foreignTemplateId)}, c."compilerVersion" || '-tenant-probe',
        c."irSchemaVersion", c."compiledDocumentIr", c."unsupportedElements",
        c."structureSha256", c."staticContentSha256", 'NEEDS_CONFIRMATION',
        c."blockingUnsupportedCount"
      FROM template_twin_fill_manifests f
      JOIN template_twin_compiled_versions c ON c.id = f."compiledVersionId"
      WHERE f.id = ${sqlLiteral(input.fillManifestId)};
      ROLLBACK;
    `,
    "Template Twin compiled tenant lineage mismatch",
  );

  expectPsqlRejected(
    `
      BEGIN;
      ${foreignTemplateOwnerSetup}
      UPDATE template_twin_compiled_versions c
      SET "noteTemplateId" = ${sqlLiteral(foreignTemplateId)}
      WHERE c."noteTemplateId" = ${sqlLiteral(input.foreignNoteTemplateId)};
      ROLLBACK;
    `,
    "Template Twin compiled tenant lineage mismatch",
  );

  expectPsqlRejected(
    `
      BEGIN;
      ${foreignTemplateOwnerSetup}
      UPDATE note_templates n
      SET "doctorId" = ${sqlLiteral(foreignReviewerId)}
      FROM template_twin_fill_manifests f
      WHERE f.id = ${sqlLiteral(input.fillManifestId)}
        AND n.id = f."noteTemplateId";
      ROLLBACK;
    `,
    "Template Twin NoteTemplate owner tenant mismatch",
  );

  expectPsqlRejected(
    `
      BEGIN;
      INSERT INTO practices (id, name, slug, "isActive", "updatedAt")
      VALUES (
        ${sqlLiteral(foreignPracticeId)},
        'Synthetic foreign reassignment practice',
        ${sqlLiteral(`qa-template-twin-reassignment-${suffix}`)},
        true,
        CURRENT_TIMESTAMP
      );
      UPDATE users owner
      SET "practiceId" = ${sqlLiteral(foreignPracticeId)}
      FROM note_templates n
      JOIN template_twin_fill_manifests f ON f."noteTemplateId" = n.id
      WHERE f.id = ${sqlLiteral(input.fillManifestId)}
        AND owner.id = n."doctorId";
      ROLLBACK;
    `,
    "Template Twin owner practice reassignment mismatch",
  );

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

interface QaConcurrentLineageState {
  ownerPracticeId: string | null;
  sourcePracticeId: string | null;
  compiledCount: number;
  lineageMismatchCount: number;
}

/**
 * Live PostgreSQL sessions prove both serialization directions for the
 * cross-table compiled/source/template-owner invariant. The first race holds
 * an owner reassignment open and requires compilation to wait, re-read, and
 * reject. The reverse race holds a valid compilation open and requires owner
 * reassignment to wait, re-read, and reject. pg_stat_activity supplies the
 * synchronization oracle; elapsed-time sleeps are never treated as proof.
 */
export async function assertTemplateTwinQaConcurrentCompiledOwnerGuard(input: {
  fillManifestId: string;
}): Promise<void> {
  assertNonProdDbName(QA_DB);
  const suffix = input.fillManifestId.replace(/[^A-Za-z0-9]/g, "").slice(-16);
  const foreignPracticeId = `qa-template-twin-race-practice-${suffix}`;
  const ownerFirstOwnerId = `qa-template-twin-owner-first-owner-${suffix}`;
  const ownerFirstTemplateId = `qa-template-twin-owner-first-template-${suffix}`;
  const ownerFirstCompiledId = `qa-template-twin-owner-first-compiled-${suffix}`;
  const ownerFirstLineageId = `qa-template-twin-owner-first-lineage-${suffix}`;
  const compiledFirstOwnerId = `qa-template-twin-compiled-first-owner-${suffix}`;
  const compiledFirstTemplateId = `qa-template-twin-compiled-first-template-${suffix}`;
  const compiledFirstCompiledId = `qa-template-twin-compiled-first-compiled-${suffix}`;
  const compiledFirstLineageId = `qa-template-twin-compiled-first-lineage-${suffix}`;
  const repeatableReadCompiledId = `qa-template-twin-repeatable-read-compiled-${suffix}`;
  const serializableCompiledId = `qa-template-twin-serializable-compiled-${suffix}`;
  const ownerFirstOwnerSessionName = `qa-template-twin-owner-first-owner-${suffix}`;
  const ownerFirstCompiledSessionName = `qa-template-twin-owner-first-compiled-${suffix}`;
  const compiledFirstCompiledSessionName = `qa-template-twin-compiled-first-compiled-${suffix}`;
  const compiledFirstOwnerSessionName = `qa-template-twin-compiled-first-owner-${suffix}`;

  const compiledInsertSql = (compiled: {
    compiledVersionId: string;
    noteTemplateId: string;
    compilerSuffix: string;
  }): string => `
    INSERT INTO template_twin_compiled_versions (
      id, "sourceArtifactId", "noteTemplateId", "compilerVersion",
      "irSchemaVersion", "compiledDocumentIr", "unsupportedElements",
      "structureSha256", "staticContentSha256", "certificationStatus",
      "blockingUnsupportedCount"
    )
    SELECT
      ${sqlLiteral(compiled.compiledVersionId)}, c."sourceArtifactId",
      ${sqlLiteral(compiled.noteTemplateId)}, c."compilerVersion" || ${sqlLiteral(compiled.compilerSuffix)},
      c."irSchemaVersion", c."compiledDocumentIr", c."unsupportedElements",
      c."structureSha256", c."staticContentSha256", 'NEEDS_CONFIRMATION',
      c."blockingUnsupportedCount"
    FROM template_twin_fill_manifests f
    JOIN template_twin_compiled_versions c ON c.id = f."compiledVersionId"
    WHERE f.id = ${sqlLiteral(input.fillManifestId)};
  `;

  let ownerFirstOwnerSession: QaPsqlSession | null = null;
  let ownerFirstCompiledSession: QaPsqlSession | null = null;
  let compiledFirstCompiledSession: QaPsqlSession | null = null;
  let compiledFirstOwnerSession: QaPsqlSession | null = null;
  try {
    psql(`
      BEGIN;
      INSERT INTO practices (id, name, slug, "isActive", "updatedAt")
      VALUES (
        ${sqlLiteral(foreignPracticeId)},
        'Synthetic concurrent owner practice',
        ${sqlLiteral(`qa-template-twin-race-${suffix}`)},
        true,
        CURRENT_TIMESTAMP
      );
      INSERT INTO users (
        id, email, name, "passwordHash", role, "isActive", "practiceId", "updatedAt"
      )
      SELECT
        fixture.owner_id,
        fixture.email,
        fixture.owner_name,
        'synthetic-not-a-real-password-hash',
        'DOCTOR',
        true,
        f."practiceId",
        CURRENT_TIMESTAMP
      FROM template_twin_fill_manifests f
      CROSS JOIN (
        VALUES
          (
            ${sqlLiteral(ownerFirstOwnerId)},
            ${sqlLiteral(`${ownerFirstOwnerId}@synthetic.test`)},
            'Synthetic Owner-First Template Owner'
          ),
          (
            ${sqlLiteral(compiledFirstOwnerId)},
            ${sqlLiteral(`${compiledFirstOwnerId}@synthetic.test`)},
            'Synthetic Compiled-First Template Owner'
          )
      ) AS fixture(owner_id, email, owner_name)
      WHERE f.id = ${sqlLiteral(input.fillManifestId)};
      INSERT INTO note_templates (
        id, "doctorId", name, "encounterType", "specialtyBaseline", sections,
        "styleProfile", version, status, "isSystemDefault", "lineageId",
        "parentVersionId", "templateKind", "versionDescription", "createdAt", "updatedAt"
      )
      SELECT
        fixture.template_id, fixture.owner_id, fixture.template_name,
        n."encounterType", n."specialtyBaseline", n.sections,
        n."styleProfile", 1, 'draft', false, fixture.lineage_id, NULL,
        'template_twin_docx', 'Synthetic two-session tenant guard probe',
        CURRENT_TIMESTAMP, CURRENT_TIMESTAMP
      FROM template_twin_fill_manifests f
      JOIN note_templates n ON n.id = f."noteTemplateId"
      CROSS JOIN (
        VALUES
          (
            ${sqlLiteral(ownerFirstTemplateId)},
            ${sqlLiteral(ownerFirstOwnerId)},
            ${sqlLiteral(ownerFirstLineageId)},
            'Synthetic owner-first lineage probe'
          ),
          (
            ${sqlLiteral(compiledFirstTemplateId)},
            ${sqlLiteral(compiledFirstOwnerId)},
            ${sqlLiteral(compiledFirstLineageId)},
            'Synthetic compiled-first lineage probe'
          )
      ) AS fixture(template_id, owner_id, lineage_id, template_name)
      WHERE f.id = ${sqlLiteral(input.fillManifestId)};
      COMMIT;
    `);

    // Snapshot-retaining isolation levels are deliberately unsupported for
    // cross-table lineage mutations. An advisory-lock wait cannot refresh a
    // REPEATABLE READ/SERIALIZABLE snapshot, so every trigger fails before it
    // takes the shared gate. This also makes mixed-isolation callers lose
    // closed instead of validating stale ownership.
    expectPsqlRejected(
      `
        BEGIN ISOLATION LEVEL REPEATABLE READ;
        ${compiledInsertSql({
          compiledVersionId: repeatableReadCompiledId,
          noteTemplateId: ownerFirstTemplateId,
          compilerSuffix: "-repeatable-read-tenant-probe",
        })}
        COMMIT;
      `,
      "Template Twin tenant lineage writes require READ COMMITTED isolation",
    );
    expectPsqlRejected(
      `
        BEGIN ISOLATION LEVEL SERIALIZABLE;
        ${compiledInsertSql({
          compiledVersionId: serializableCompiledId,
          noteTemplateId: ownerFirstTemplateId,
          compilerSuffix: "-serializable-tenant-probe",
        })}
        COMMIT;
      `,
      "Template Twin tenant lineage writes require READ COMMITTED isolation",
    );
    expectPsqlRejected(
      `
        BEGIN ISOLATION LEVEL REPEATABLE READ;
        UPDATE note_templates
        SET "doctorId" = ${sqlLiteral(compiledFirstOwnerId)}
        WHERE id = ${sqlLiteral(ownerFirstTemplateId)};
        COMMIT;
      `,
      "Template Twin tenant lineage writes require READ COMMITTED isolation",
    );
    expectPsqlRejected(
      `
        BEGIN ISOLATION LEVEL REPEATABLE READ;
        UPDATE users
        SET "practiceId" = ${sqlLiteral(foreignPracticeId)}
        WHERE id = ${sqlLiteral(ownerFirstOwnerId)};
        COMMIT;
      `,
      "Template Twin tenant lineage writes require READ COMMITTED isolation",
    );

    ownerFirstOwnerSession = openQaPsqlSession(ownerFirstOwnerSessionName);
    ownerFirstOwnerSession.child.stdin.write(`
      BEGIN;
      UPDATE users
      SET "practiceId" = ${sqlLiteral(foreignPracticeId)}
      WHERE id = ${sqlLiteral(ownerFirstOwnerId)};
      \\echo TEMPLATE_TWIN_OWNER_FIRST_REASSIGNMENT_STAGED
    `);
    await waitForQaSessionOutput(
      ownerFirstOwnerSession,
      "TEMPLATE_TWIN_OWNER_FIRST_REASSIGNMENT_STAGED",
    );

    ownerFirstCompiledSession = openQaPsqlSession(
      ownerFirstCompiledSessionName,
    );
    ownerFirstCompiledSession.child.stdin.end(`
      BEGIN;
      ${compiledInsertSql({
        compiledVersionId: ownerFirstCompiledId,
        noteTemplateId: ownerFirstTemplateId,
        compilerSuffix: "-owner-first-tenant-probe",
      })}
      COMMIT;
      \\echo TEMPLATE_TWIN_OWNER_FIRST_COMPILED_COMMITTED
      \\q
    `);

    await waitForQaSessionLock({
      session: ownerFirstCompiledSession,
      applicationName: ownerFirstCompiledSessionName,
      operation: "Owner-first concurrent compilation",
    });

    ownerFirstOwnerSession.child.stdin.end(`
      COMMIT;
      \\echo TEMPLATE_TWIN_OWNER_FIRST_REASSIGNMENT_COMMITTED
      \\q
    `);
    const ownerFirstOwnerResult = await waitForQaSessionExit(
      ownerFirstOwnerSession,
    );
    if (
      ownerFirstOwnerResult.code !== 0 ||
      !ownerFirstOwnerResult.stdout.includes(
        "TEMPLATE_TWIN_OWNER_FIRST_REASSIGNMENT_COMMITTED",
      )
    ) {
      throw new Error(
        `Owner-first reassignment did not commit cleanly: ${ownerFirstOwnerResult.stderr.slice(0, 800)}`,
      );
    }

    const ownerFirstCompiledResult = await waitForQaSessionExit(
      ownerFirstCompiledSession,
    );
    if (
      ownerFirstCompiledResult.code === 0 ||
      !ownerFirstCompiledResult.stderr.includes(
        "Template Twin compiled tenant lineage mismatch",
      )
    ) {
      throw new Error(
        `Owner-first compilation was not rejected after reassignment committed: ${ownerFirstCompiledResult.stderr.slice(0, 800)}`,
      );
    }

    const ownerFirstState = psqlJson<QaConcurrentLineageState>(`
      SELECT json_build_object(
        'ownerPracticeId', (
          SELECT "practiceId" FROM users
          WHERE id = ${sqlLiteral(ownerFirstOwnerId)}
        ),
        'sourcePracticeId', (
          SELECT "practiceId" FROM template_twin_fill_manifests
          WHERE id = ${sqlLiteral(input.fillManifestId)}
        ),
        'compiledCount', (
          SELECT count(*) FROM template_twin_compiled_versions
          WHERE id = ${sqlLiteral(ownerFirstCompiledId)}
        ),
        'lineageMismatchCount', (
          SELECT count(*)
          FROM template_twin_compiled_versions c
          JOIN template_twin_source_artifacts s ON s.id = c."sourceArtifactId"
          JOIN note_templates n ON n.id = c."noteTemplateId"
          LEFT JOIN users owner ON owner.id = n."doctorId"
          WHERE c.id = ${sqlLiteral(ownerFirstCompiledId)}
            AND (
              owner."practiceId" IS NULL
              OR owner."practiceId" <> s."practiceId"
            )
        )
      )::text;
    `);
    if (
      ownerFirstState.ownerPracticeId !== foreignPracticeId ||
      ownerFirstState.sourcePracticeId === null ||
      ownerFirstState.compiledCount !== 0 ||
      ownerFirstState.lineageMismatchCount !== 0
    ) {
      throw new Error(
        `Owner-first race left unexpected lineage state: ${JSON.stringify(ownerFirstState)}`,
      );
    }

    compiledFirstCompiledSession = openQaPsqlSession(
      compiledFirstCompiledSessionName,
    );
    compiledFirstCompiledSession.child.stdin.write(`
      BEGIN;
      ${compiledInsertSql({
        compiledVersionId: compiledFirstCompiledId,
        noteTemplateId: compiledFirstTemplateId,
        compilerSuffix: "-compiled-first-tenant-probe",
      })}
      \\echo TEMPLATE_TWIN_COMPILED_FIRST_INSERT_STAGED
    `);
    await waitForQaSessionOutput(
      compiledFirstCompiledSession,
      "TEMPLATE_TWIN_COMPILED_FIRST_INSERT_STAGED",
    );

    compiledFirstOwnerSession = openQaPsqlSession(
      compiledFirstOwnerSessionName,
    );
    compiledFirstOwnerSession.child.stdin.end(`
      BEGIN;
      UPDATE users
      SET "practiceId" = ${sqlLiteral(foreignPracticeId)}
      WHERE id = ${sqlLiteral(compiledFirstOwnerId)};
      COMMIT;
      \\echo TEMPLATE_TWIN_COMPILED_FIRST_OWNER_REASSIGNED
      \\q
    `);
    await waitForQaSessionLock({
      session: compiledFirstOwnerSession,
      applicationName: compiledFirstOwnerSessionName,
      operation: "Compiled-first concurrent owner reassignment",
    });

    compiledFirstCompiledSession.child.stdin.end(`
      COMMIT;
      \\echo TEMPLATE_TWIN_COMPILED_FIRST_COMMITTED
      \\q
    `);
    const compiledFirstCompiledResult = await waitForQaSessionExit(
      compiledFirstCompiledSession,
    );
    if (
      compiledFirstCompiledResult.code !== 0 ||
      !compiledFirstCompiledResult.stdout.includes(
        "TEMPLATE_TWIN_COMPILED_FIRST_COMMITTED",
      )
    ) {
      throw new Error(
        `Compiled-first compilation did not commit cleanly: ${compiledFirstCompiledResult.stderr.slice(0, 800)}`,
      );
    }

    const compiledFirstOwnerResult = await waitForQaSessionExit(
      compiledFirstOwnerSession,
    );
    if (
      compiledFirstOwnerResult.code === 0 ||
      !compiledFirstOwnerResult.stderr.includes(
        "Template Twin owner practice reassignment mismatch",
      )
    ) {
      throw new Error(
        `Compiled-first owner reassignment was not rejected after compilation committed: ${compiledFirstOwnerResult.stderr.slice(0, 800)}`,
      );
    }

    const compiledFirstState = psqlJson<QaConcurrentLineageState>(`
      SELECT json_build_object(
        'ownerPracticeId', (
          SELECT "practiceId" FROM users
          WHERE id = ${sqlLiteral(compiledFirstOwnerId)}
        ),
        'sourcePracticeId', (
          SELECT "practiceId" FROM template_twin_fill_manifests
          WHERE id = ${sqlLiteral(input.fillManifestId)}
        ),
        'compiledCount', (
          SELECT count(*) FROM template_twin_compiled_versions
          WHERE id = ${sqlLiteral(compiledFirstCompiledId)}
        ),
        'lineageMismatchCount', (
          SELECT count(*)
          FROM template_twin_compiled_versions c
          JOIN template_twin_source_artifacts s ON s.id = c."sourceArtifactId"
          JOIN note_templates n ON n.id = c."noteTemplateId"
          LEFT JOIN users owner ON owner.id = n."doctorId"
          WHERE c.id = ${sqlLiteral(compiledFirstCompiledId)}
            AND (
              owner."practiceId" IS NULL
              OR owner."practiceId" <> s."practiceId"
            )
        )
      )::text;
    `);
    if (
      compiledFirstState.ownerPracticeId === null ||
      compiledFirstState.ownerPracticeId !==
        compiledFirstState.sourcePracticeId ||
      compiledFirstState.compiledCount !== 1 ||
      compiledFirstState.lineageMismatchCount !== 0
    ) {
      throw new Error(
        `Compiled-first race left unexpected lineage state: ${JSON.stringify(compiledFirstState)}`,
      );
    }
  } finally {
    await rollbackOpenQaPsqlSession(ownerFirstOwnerSession);
    await rollbackOpenQaPsqlSession(ownerFirstCompiledSession);
    await rollbackOpenQaPsqlSession(compiledFirstCompiledSession);
    await rollbackOpenQaPsqlSession(compiledFirstOwnerSession);
    psql(`
      BEGIN;
      DELETE FROM template_twin_compiled_versions
      WHERE id IN (
        ${sqlLiteral(ownerFirstCompiledId)},
        ${sqlLiteral(compiledFirstCompiledId)},
        ${sqlLiteral(repeatableReadCompiledId)},
        ${sqlLiteral(serializableCompiledId)}
      );
      DELETE FROM note_templates
      WHERE id IN (
        ${sqlLiteral(ownerFirstTemplateId)},
        ${sqlLiteral(compiledFirstTemplateId)}
      );
      DELETE FROM users
      WHERE id IN (
        ${sqlLiteral(ownerFirstOwnerId)},
        ${sqlLiteral(compiledFirstOwnerId)}
      );
      DELETE FROM practices WHERE id = ${sqlLiteral(foreignPracticeId)};
      COMMIT;
    `);
    const cleanupCount = psql(`
      SELECT
        (SELECT count(*) FROM template_twin_compiled_versions
         WHERE id IN (
           ${sqlLiteral(ownerFirstCompiledId)},
           ${sqlLiteral(compiledFirstCompiledId)},
           ${sqlLiteral(repeatableReadCompiledId)},
           ${sqlLiteral(serializableCompiledId)}
         ))
        +
        (SELECT count(*) FROM note_templates
         WHERE id IN (
           ${sqlLiteral(ownerFirstTemplateId)},
           ${sqlLiteral(compiledFirstTemplateId)}
         ))
        +
        (SELECT count(*) FROM users
         WHERE id IN (
           ${sqlLiteral(ownerFirstOwnerId)},
           ${sqlLiteral(compiledFirstOwnerId)}
         ))
        +
        (SELECT count(*) FROM practices
         WHERE id = ${sqlLiteral(foreignPracticeId)});
    `);
    if (cleanupCount !== "0") {
      throw new Error(
        `Template Twin concurrent-lineage fixtures were not fully cleaned: ${cleanupCount}`,
      );
    }
  }
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
