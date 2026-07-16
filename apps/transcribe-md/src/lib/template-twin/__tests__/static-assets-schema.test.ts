import { readFileSync } from 'node:fs';
import path from 'node:path';

import { describe, expect, it } from 'vitest';

const ROOT = path.resolve(__dirname, '../../../../../..');
const schema = readFileSync(
  path.join(ROOT, 'packages/db/prisma/schema.prisma'),
  'utf8',
);
const migration = readFileSync(
  path.join(
    ROOT,
    'packages/db/prisma/migrations/20260716190000_template_twin_placeholder_assets_v1/migration.sql',
  ),
  'utf8',
);
const sourcePhi = readFileSync(
  path.join(
    ROOT,
    'apps/transcribe-md/src/lib/template-twin/source-phi.ts',
  ),
  'utf8',
);
const createDraft = readFileSync(
  path.join(
    ROOT,
    'apps/transcribe-md/src/lib/template-twin/create-draft.ts',
  ),
  'utf8',
);
const certificationLifecycle = readFileSync(
  path.join(
    ROOT,
    'apps/transcribe-md/src/lib/template-twin/certification-lifecycle.ts',
  ),
  'utf8',
);
const staticAssets = readFileSync(
  path.join(
    ROOT,
    'apps/transcribe-md/src/lib/template-twin/static-assets.ts',
  ),
  'utf8',
);
const postgresRevocationProof = readFileSync(
  path.join(
    ROOT,
    'packages/db/scripts/template-twin-static-asset-revocation-pg-test.ts',
  ),
  'utf8',
);

describe('Template Twin intent and static-asset database contract', () => {
  it('stores byte-exact practice-scoped inspection evidence and append-only decisions', () => {
    expect(schema).toContain('model TemplateTwinStaticAsset {');
    expect(schema).toMatch(/@@unique\(\[practiceId, sha256\]\)/);
    expect(schema).toContain('model TemplateTwinStaticAssetDecision {');
    expect(schema).toContain('model TemplateTwinStaticAssetReviewReceipt {');
    expect(schema).toContain('inspectionEvidenceSha256');
    expect(schema).toMatch(/@@unique\(\[assetId, version\]\)/);
    expect(migration).toContain('template_twin_static_asset_identity_immutable');
    expect(migration).toContain('template_twin_static_asset_decision_immutable');
    expect(migration).toContain('template_twin_apply_static_asset_decision');
    expect(migration).toContain("NEW.\"decision\" = 'REVOKED'");
    expect(migration).toContain(
      'template_twin_static_asset_creator_tenant_guard',
    );
    expect(migration).toContain('TT_STATIC_ASSET_ADMIN_TENANT_INVALID');
    expect(migration).toContain('TT_STATIC_ASSET_EVIDENCE_MISMATCH');
    expect(migration).toContain('TEMPLATE_TWIN_STATIC_ASSET_SUMMARY_MANAGED');
    expect(migration).toContain(
      'template_twin_static_asset_review_receipt_guard',
    );
    expect(migration).toContain('NEW."consumedAt" IS NOT NULL');
    expect(migration).toContain(
      'NEW."consumedAt" IS DISTINCT FROM CURRENT_TIMESTAMP',
    );
    expect(migration).toContain(
      'receipt_scanner_version IS DISTINCT FROM asset_scanner_version',
    );
    expect(migration).toContain(
      'receipt_global_generation IS DISTINCT FROM global_generation',
    );
    expect(migration).toContain(
      'receipt_consumed_at > receipt_expires_at',
    );
    expect(migration).toContain(
      'template_twin_static_asset_review_receipts_tokenSha256_key',
    );
    expect(schema).toContain(
      '@unique(map: "template_twin_static_asset_decisions_auditEventKey_key")',
    );
    expect(schema).toContain(
      'map: "template_twin_static_asset_decisions_auditEventKey_fkey"',
    );
    expect(migration).toContain('TT_STATIC_ASSET_AUDIT_OUTBOX_INVALID');
    expect(migration).toContain(
      'outbox."metadata"->>\'decisionId\' = NEW."id"',
    );
    expect(migration).toContain(
      'outbox."status" = \'PENDING\'',
    );
    expect(staticAssets).toContain(
      'lockTemplateTwinRolloutForFinalClaim({',
    );
    expect(staticAssets).toContain(
      'UPDATE "template_twin_static_asset_review_receipts"',
    );
  });

  it('keeps field intent append-only and binds test, certification, and fill provenance', () => {
    expect(schema).toContain('model TemplateTwinFieldIntentDecision {');
    expect(schema).toMatch(/fieldDefinitionId\s+String\s+@unique/);
    expect(schema).toContain('latestTestFieldIntentsSha256');
    expect(schema).toContain('approvedFieldIntentsSha256');
    expect(schema).toContain('fieldIntentsSha256');
    expect(migration).toContain('template_twin_field_intent_immutable');
    expect(migration).toContain(
      'TT_FIELD_INTENT_NEW_TEMPLATE_VERSION_REQUIRED',
    );
    expect(migration).toContain('NEW."version" <> 1');
    expect(migration).toContain('n."status" = \'draft\'');
    expect(migration).toContain('template_twin_certifications');
    expect(migration).toContain('TT_FIELD_INTENT_PHYSICIAN_TENANT_INVALID');
  });

  it('persists immutable custom-example results and permits only one-way physician acknowledgement', () => {
    expect(schema).toContain('model TemplateTwinCustomExampleExecution {');
    expect(schema).toContain('approvedCustomExampleProofSha256');
    expect(schema).toContain('TEMPLATE_TWIN_CUSTOM_EXAMPLE_EXECUTED');
    expect(schema).toContain('TEMPLATE_TWIN_CUSTOM_EXAMPLE_ACKNOWLEDGED');
    expect(migration).toContain('template_twin_custom_example_execution_guard');
    expect(migration).toContain('TEMPLATE_TWIN_CUSTOM_EXAMPLE_IMMUTABLE');
    expect(migration).toContain('TT_CUSTOM_EXAMPLE_ACK_MUST_BE_SEPARATE');
    expect(migration).toContain('TT_CUSTOM_EXAMPLE_PHYSICIAN_TENANT_INVALID');
    expect(migration).toContain(
      'template_twin_certification_custom_example_proof_guard',
    );
    expect(migration).toContain(
      "to_jsonb(NEW) - 'acknowledgedById' - 'acknowledgedAt'",
    );
    expect(certificationLifecycle).toContain(
      'assertTemplateTwinCustomExamplesReadyForCertification',
    );
  });

  it('uses bounded migration locks and a durable audit outbox for every asset decision class', () => {
    expect(migration).toContain("SET LOCAL lock_timeout = '2s'");
    expect(migration).toContain("SET LOCAL statement_timeout = '30s'");
    for (const action of [
      'TEMPLATE_TWIN_STATIC_ASSET_APPROVED',
      'TEMPLATE_TWIN_STATIC_ASSET_REJECTED',
      'TEMPLATE_TWIN_STATIC_ASSET_REVOKED',
      'TEMPLATE_TWIN_STATIC_ASSET_USED',
    ]) {
      expect(schema).toContain(action);
      expect(migration).toContain(action);
    }
    for (const prefix of ['approved', 'rejected', 'revoked']) {
      const outboxAt = staticAssets.indexOf(
        `eventKey: auditEventKey`,
        staticAssets.indexOf(`static-asset-${prefix}:`),
      );
      const decisionAt = staticAssets.indexOf(
        'templateTwinStaticAssetDecision.create',
        outboxAt,
      );
      expect(outboxAt).toBeGreaterThan(-1);
      expect(decisionAt).toBeGreaterThan(outboxAt);
    }
  });

  it('maps every intentionally shortened Prisma name to the migration and avoids PostgreSQL truncation', () => {
    const mappedNames = [
      'template_twin_custom_example_practiceId_fkey',
      'template_twin_custom_example_compiledVersionId_fkey',
      'template_twin_custom_example_fieldDefinitionId_fkey',
      'template_twin_custom_example_fieldIntentDecisionId_fkey',
      'template_twin_custom_example_executedById_fkey',
      'template_twin_custom_example_acknowledgedById_fkey',
      'template_twin_custom_example_batch_field_kind_id_key',
      'template_twin_custom_example_compiled_executed_idx',
      'template_twin_custom_example_intent_executed_idx',
      'template_twin_custom_example_practice_executed_idx',
      'tt_static_asset_receipt_practice_reviewer_expiry_idx',
    ];
    expect(mappedNames).toHaveLength(11);
    for (const name of mappedNames) {
      expect(Buffer.byteLength(name, 'utf8')).toBeLessThanOrEqual(63);
      expect(schema).toContain(`map: "${name}"`);
      expect(migration).toContain(`"${name}"`);
    }
    expect(migration).not.toContain(
      'template_twin_static_asset_review_receipts_practice_reviewer_expiry_idx',
    );
  });

  it('does not retain the former environment digest authorization path', () => {
    expect(sourcePhi).not.toContain(
      'TEMPLATE_TWIN_APPROVED_STATIC_ASSETS_BY_PRACTICE_JSON',
    );
    expect(sourcePhi).not.toContain(
      'TEMPLATE_TWIN_APPROVED_STATIC_ASSET_SHA256',
    );
    expect(sourcePhi).toContain('resolveApprovedTemplateTwinStaticAssets');
  });

  it('revalidates approvals before source claim and certification and audits every accepted use', () => {
    expect(createDraft).toContain(
      'lockAndAssertTemplateTwinStaticAssetBindingsCurrent({',
    );
    expect(createDraft).toContain('TEMPLATE_TWIN_STATIC_ASSET_USED');
    expect(createDraft).toContain('binding.decisionId');
    expect(certificationLifecycle).toContain(
      'lockAndAssertTemplateTwinStaticAssetBindingsCurrent({',
    );
    expect(staticAssets).toContain('ORDER BY asset."id"');
    expect(staticAssets).toContain('FOR SHARE');
    expect(postgresRevocationProof).toContain(
      'databaseObservedBlocking: true',
    );
    expect(postgresRevocationProof).toContain(
      'lockAndAssertTemplateTwinStaticAssetBindingsCurrent',
    );
    expect(postgresRevocationProof).not.toContain('setTimeout(');
  });
});
