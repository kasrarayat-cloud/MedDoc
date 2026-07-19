#!/usr/bin/env tsx

import { readFileSync } from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

import { PrismaPg } from "@prisma/adapter-pg";
import { PrismaClient } from "@prisma/client";

import { assertNonProdDatabase } from "../src/db-guard";

const databaseUrl = process.env.TEMPLATE_TWIN_SCHEMA_TEST_DATABASE_URL ??
  process.env.DATABASE_URL;
assertNonProdDatabase(databaseUrl);
if (!databaseUrl) {
  throw new Error("A disposable placeholder schema test database is required.");
}

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "../../..");
const schema = readFileSync(path.join(root, "packages/db/prisma/schema.prisma"), "utf8");
const migration = readFileSync(
  path.join(
    root,
    "packages/db/prisma/migrations/20260716190000_template_twin_placeholder_assets_v1/migration.sql",
  ),
  "utf8",
);

const mappedConstraints = [
  "template_twin_custom_example_practiceId_fkey",
  "template_twin_custom_example_compiledVersionId_fkey",
  "template_twin_custom_example_fieldDefinitionId_fkey",
  "template_twin_custom_example_fieldIntentDecisionId_fkey",
  "template_twin_custom_example_executedById_fkey",
  "template_twin_custom_example_acknowledgedById_fkey",
] as const;
const mappedIndexes = [
  "template_twin_custom_example_batch_field_kind_id_key",
  "template_twin_custom_example_compiled_executed_idx",
  "template_twin_custom_example_intent_executed_idx",
  "template_twin_custom_example_practice_executed_idx",
  "tt_static_asset_receipt_practice_reviewer_expiry_idx",
] as const;
const auditConstraint =
  "template_twin_static_asset_decisions_auditEventKey_fkey";
const auditIndex =
  "template_twin_static_asset_decisions_auditEventKey_key";

for (const name of [...mappedConstraints, ...mappedIndexes]) {
  if (Buffer.byteLength(name, "utf8") > 63) {
    throw new Error(`Mapped PostgreSQL name exceeds 63 bytes: ${name}`);
  }
  if (!schema.includes(`map: "${name}"`) || !migration.includes(`"${name}"`)) {
    throw new Error(`Schema and migration do not share mapped name: ${name}`);
  }
}

const prisma = new PrismaClient({
  adapter: new PrismaPg({ connectionString: databaseUrl, max: 1 }),
});

async function main(): Promise<void> {
  const constraints = await prisma.$queryRawUnsafe<Array<{ name: string }>>(
    `SELECT conname AS "name"
     FROM pg_constraint
     WHERE conrelid IN (
       'template_twin_custom_example_executions'::regclass,
       'template_twin_static_asset_decisions'::regclass
     )`,
  );
  const indexes = await prisma.$queryRawUnsafe<Array<{ name: string }>>(
    `SELECT indexname AS "name"
     FROM pg_indexes
     WHERE schemaname = current_schema()
       AND tablename IN (
         'template_twin_custom_example_executions',
         'template_twin_static_asset_review_receipts',
         'template_twin_static_asset_decisions'
       )`,
  );
  const constraintNames = new Set(constraints.map(({ name }) => name));
  const indexNames = new Set(indexes.map(({ name }) => name));
  for (const name of [...mappedConstraints, auditConstraint]) {
    if (!constraintNames.has(name)) {
      throw new Error(`Applied database is missing mapped constraint: ${name}`);
    }
  }
  for (const name of [...mappedIndexes, auditIndex]) {
    if (!indexNames.has(name)) {
      throw new Error(`Applied database is missing mapped index: ${name}`);
    }
  }
  const [auditColumn] = await prisma.$queryRawUnsafe<
    Array<{ nullable: string; dataType: string }>
  >(
    `SELECT is_nullable AS "nullable", data_type AS "dataType"
     FROM information_schema.columns
     WHERE table_schema = current_schema()
       AND table_name = 'template_twin_static_asset_decisions'
       AND column_name = 'auditEventKey'`,
  );
  if (auditColumn?.nullable !== "NO" || auditColumn.dataType !== "text") {
    throw new Error("Decision auditEventKey is not a required text identity.");
  }
  process.stdout.write(
    `${JSON.stringify({
      profile: "template-twin-placeholder-schema-drift-v1",
      synthetic: true,
      mappedPhysicalNames: mappedConstraints.length + mappedIndexes.length,
      decisionAuditForeignKey: true,
      decisionAuditUniqueIndex: true,
      receiptIndexNameBytes: Buffer.byteLength(mappedIndexes[4], "utf8"),
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
