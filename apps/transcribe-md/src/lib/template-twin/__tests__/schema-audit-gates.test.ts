import { readFileSync } from 'node:fs';
import path from 'node:path';

import { describe, expect, it } from 'vitest';

const ROOT = path.resolve(__dirname, '../../../../../..');
const schema = readFileSync(
  path.join(ROOT, 'packages/db/prisma/schema.prisma'),
  'utf8',
);
const migrationPath = path.join(
  ROOT,
  'packages/db/prisma/migrations/20260715203000_template_twin_audit_gates_v1/migration.sql',
);

function modelBody(model: string): string {
  const match = schema.match(new RegExp(`model ${model} \\{([\\s\\S]*?)\\n\\}`, 'm'));
  if (!match?.[1]) throw new Error(`Missing Prisma model ${model}`);
  return match[1];
}

describe('Template Twin audit-gate schema contract', () => {
  it('persists a default-off practice rollout flag and template version description', () => {
    expect(modelBody('Practice')).toMatch(
      /templateTwinEnabled\s+Boolean\s+@default\(false\)/,
    );
    expect(modelBody('NoteTemplate')).toMatch(/versionDescription\s+String\?/);
  });

  it('binds every fill manifest to an exact SOAP version and SHA-256', () => {
    const fill = modelBody('TemplateTwinFillManifest');
    expect(fill).toMatch(/soapVersion\s+Int\?/);
    expect(fill).toMatch(/soapSha256\s+String\?\s+@db\.Char\(64\)/);
    expect(fill).toMatch(/reviewedById\s+String\?/);
    expect(fill).toMatch(/reviewedManifestVersion\s+Int\?/);
    expect(fill).toMatch(
      /reviewedManifestSha256\s+String\?\s+@db\.Char\(64\)/,
    );
    expect(fill).toMatch(/outputVersionId\s+String\?/);
    expect(fill).toMatch(/outputEtag\s+String\?/);
  });

  it('persists field-level test waivers with physician provenance', () => {
    const waiver = modelBody('TemplateTwinFieldTestWaiver');
    expect(waiver).toMatch(/fieldDefinitionId\s+String/);
    expect(waiver).toMatch(/mappingsSha256\s+String\s+@db\.Char\(64\)/);
    expect(waiver).toMatch(/waivedById\s+String/);
    expect(waiver).toMatch(/reason\s+String/);
    expect(waiver).toMatch(/@@unique\(\[compiledVersionId, fieldId, mappingsSha256\]\)/);
  });

  it('adds durable object and critical-audit ledgers', () => {
    expect(modelBody('TemplateTwinObjectLedger')).toMatch(/objectKey\s+String\s+@unique/);
    expect(modelBody('TemplateTwinObjectLedger')).toMatch(
      /objectVersionId\s+String\?/,
    );
    expect(modelBody('TemplateTwinObjectLedger')).toMatch(/objectEtag\s+String\?/);
    expect(modelBody('TemplateTwinObjectLedger')).toMatch(
      /state\s+TemplateTwinObjectLedgerState/,
    );
    expect(modelBody('TemplateTwinAuditOutbox')).toMatch(/eventKey\s+String\s+@unique/);
    expect(modelBody('TemplateTwinAuditOutbox')).toMatch(/action\s+AuditAction/);
  });

  it('ships database tenant-consistency and immutable-waiver enforcement', () => {
    const migration = readFileSync(migrationPath, 'utf8');
    expect(migration).toContain('template_twin_assert_fill_tenant_consistency');
    expect(migration).toContain('template_twin_assert_review_lineage_consistency');
    expect(migration).toContain('template_twin_waivers_immutable_after_certification');
    expect(migration).toContain('template_twin_object_ledgers');
    expect(migration).toContain('template_twin_audit_outbox');
    expect(migration).toContain('template_twin_fill_review_current_manifest');
    expect(migration).toMatch(
      /"validationStatus" <> 'accepted'[\s\S]*?"objectVersionId" IS NOT NULL[\s\S]*?"objectEtag" IS NOT NULL/,
    );
    expect(migration).toMatch(
      /"state" <> 'INTENT'[\s\S]*?"objectVersionId" IS NOT NULL[\s\S]*?"objectEtag" IS NOT NULL/,
    );
  });

  it('binds reviewers and rendered outputs to exact tenant-owned lineage', () => {
    const migration = readFileSync(migrationPath, 'utf8');
    expect(migration).toContain(
      'Template Twin fill reviewer tenant mismatch',
    );
    expect(migration).toMatch(
      /WHERE u\."id" = NEW\."reviewedById"[\s\S]*?u\."role" = 'DOCTOR'[\s\S]*?u\."isActive" = true[\s\S]*?reviewer_practice <> NEW\."practiceId"/,
    );
    expect(migration).toContain(
      "output_key_parts[6] <> NEW.\"manifestSha256\"",
    );
    expect(migration).toContain(
      "output_key_parts[8] <> (NEW.\"outputSha256\" || '.docx')",
    );
    expect(migration).toContain(
      'Template Twin object ledger claim integrity mismatch',
    );
    expect(migration).toContain(
      'Template Twin object ledger claim provider identity mismatch',
    );
    expect(migration).toContain(
      'Template Twin object ledger claim ownership missing',
    );
    expect(migration).toContain('template_twin_assert_fill_output_ledger');
    expect(migration).toMatch(
      /CREATE CONSTRAINT TRIGGER template_twin_fill_output_ledger_consistency[\s\S]*?DEFERRABLE INITIALLY DEFERRED/,
    );
    expect(migration).toMatch(
      /l\."objectKey" = NEW\."outputObjectKey"[\s\S]*?l\."sha256" = NEW\."outputSha256"[\s\S]*?l\."sizeBytes" = NEW\."outputSizeBytes"[\s\S]*?l\."claimType" = 'fill_manifest'[\s\S]*?l\."claimId" = NEW\."id"/,
    );
    expect(migration).toMatch(
      /l\."objectVersionId" = NEW\."outputVersionId"[\s\S]*?l\."objectEtag" = NEW\."outputEtag"/,
    );
  });
});
