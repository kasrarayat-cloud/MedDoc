#!/usr/bin/env tsx

import { PrismaPg } from "@prisma/adapter-pg";
import { PrismaClient } from "@prisma/client";
import { createHash } from "node:crypto";
import { readFileSync } from "node:fs";
import path from "node:path";
import { spawnSync } from "node:child_process";
import { fileURLToPath } from "node:url";

import { assertNonProdDatabase } from "../src/db-guard";

const databaseUrl =
  process.env.TEMPLATE_TWIN_SCHEMA_TEST_DATABASE_URL ??
  process.env.DATABASE_URL;
assertNonProdDatabase(databaseUrl);
if (!databaseUrl) {
  throw new Error("A disposable contracted schema test database is required.");
}

const root = path.resolve(
  path.dirname(fileURLToPath(import.meta.url)),
  "../../..",
);
const schemaPath = path.join(root, "packages/db/prisma/schema.prisma");
const configPath = path.join(root, "packages/db/prisma.config.ts");
const prismaCli = path.join(root, "node_modules/.bin/prisma");

const sha256 = (value: string | Buffer): string =>
  createHash("sha256").update(value).digest("hex");

const prisma = new PrismaClient({
  adapter: new PrismaPg({ connectionString: databaseUrl, max: 1 }),
});

interface ContractState {
  phase: string;
  columnNotNull: boolean;
  transitionTriggerPresent: boolean;
  lineageIndexValid: boolean;
  templateKindIndexValid: boolean;
}

async function main(): Promise<void> {
  const [state] = await prisma.$queryRaw<ContractState[]>`
     SELECT
       progress.phase,
       attribute.attnotnull AS "columnNotNull",
       EXISTS (
         SELECT 1
         FROM pg_trigger
         WHERE tgrelid = 'note_templates'::regclass
           AND tgname = 'note_templates_lineage_transition_guard'
           AND NOT tgisinternal
       ) AS "transitionTriggerPresent",
       COALESCE(lineage_index.indisvalid AND lineage_index.indisready, false)
         AS "lineageIndexValid",
       COALESCE(kind_index.indisvalid AND kind_index.indisready, false)
         AS "templateKindIndexValid"
     FROM "template_twin_lineage_migration_progress" AS progress
     JOIN pg_attribute AS attribute
       ON attribute.attrelid = 'note_templates'::regclass
      AND attribute.attname = 'lineageId'
      AND NOT attribute.attisdropped
     LEFT JOIN pg_index AS lineage_index
       ON lineage_index.indexrelid =
          to_regclass('"note_templates_lineageId_version_key"')
     LEFT JOIN pg_index AS kind_index
       ON kind_index.indexrelid =
          to_regclass('"note_templates_doctorId_templateKind_status_idx"')
     WHERE progress."operationKey" = 'note_templates_lineage_v1'`;

  if (
    state?.phase !== "CONTRACTED" ||
    !state.columnNotNull ||
    state.transitionTriggerPresent ||
    !state.lineageIndexValid ||
    !state.templateKindIndexValid
  ) {
    throw new Error("Template Twin lineage schema is not fully contracted.");
  }

  const diff = spawnSync(
    prismaCli,
    [
      "migrate",
      "diff",
      "--from-config-datasource",
      "--to-schema",
      schemaPath,
      "--script",
      "--exit-code",
      "--config",
      configPath,
    ],
    {
      cwd: root,
      encoding: "utf8",
      env: { ...process.env, DATABASE_URL: databaseUrl },
      timeout: 120_000,
    },
  );

  const stdout = diff.stdout ?? "";
  const stderr = diff.stderr ?? "";
  if (diff.error || diff.signal || diff.status !== 0) {
    throw new Error(
      `Contracted Prisma schema drift detected (status=${String(diff.status)}, signal=${String(diff.signal)}, stdoutSha256=${sha256(stdout)}, stderrSha256=${sha256(stderr)}).`,
    );
  }

  process.stdout.write(
    `${JSON.stringify({
      profile: "template-twin-contracted-schema-drift-v1",
      synthetic: true,
      phase: state.phase,
      columnNotNull: state.columnNotNull,
      transitionTriggerPresent: state.transitionTriggerPresent,
      lineageIndexValid: state.lineageIndexValid,
      templateKindIndexValid: state.templateKindIndexValid,
      schemaSha256: sha256(readFileSync(schemaPath)),
      diffStdoutSha256: sha256(stdout),
      diffStderrSha256: sha256(stderr),
      result: "passed",
    })}\n`,
  );
}

void main()
  .catch((error: unknown) => {
    process.stderr.write(
      `${error instanceof Error ? (error.stack ?? error.message) : String(error)}\n`,
    );
    process.exitCode = 1;
  })
  .finally(async () => prisma.$disconnect());
