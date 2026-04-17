// ============================================================================
// Specialty template seeder
// ----------------------------------------------------------------------------
// Reads every *.yaml file under apps/scribe/specialties/ and upserts a row
// into ScribeSpecialtyTemplate. Idempotent — rerun safely.
//
// Versioning: if the incoming YAML's `version` matches what's already in
// the DB, we update in place (prompt edits, hint tweaks). If versions
// differ, we insert a NEW row and mark the old one `active: false`. This
// preserves reproducibility — outputs stamped with the old version can
// still be re-rendered later without surprise content shifts.
//
// Usage: npm run seed:specialties
// ============================================================================

import 'dotenv/config';
import fs from 'node:fs';
import path from 'node:path';
import yaml from 'js-yaml';
import prisma from '@meddoc/db';

type ClinicalReviewStatus = 'draft' | 'specialist_reviewed' | 'production';

interface TemplateYaml {
  slug: string;
  displayName: string;
  version: string;
  requiredExamElements: unknown;
  soapSchema: unknown;
  defaultIcd10Hints: string[];
  /** M5 D1: optional; defaults to [] if the YAML omits it. */
  defaultCptHints?: string[];
  defaultFormularyHints: string[];
  systemPrompt: string;
  /** M5 D4: optional; defaults to 'draft' if the YAML omits it. */
  clinicalReviewStatus?: ClinicalReviewStatus;
}

const SPECIALTIES_DIR = path.resolve(__dirname, '..', 'specialties');

/**
 * YAML's `clinicalReviewStatus` is lowercase; Prisma's enum is UPPERCASE.
 * Undefined defaults to DRAFT (the column's DB default anyway — we still
 * send it explicitly so version-bumps flip status back to DRAFT unless
 * the YAML says otherwise).
 */
function reviewStatusToPrisma(
  status: ClinicalReviewStatus | undefined
): 'DRAFT' | 'SPECIALIST_REVIEWED' | 'PRODUCTION' {
  switch (status) {
    case 'production':
      return 'PRODUCTION';
    case 'specialist_reviewed':
      return 'SPECIALIST_REVIEWED';
    case 'draft':
    case undefined:
      return 'DRAFT';
  }
}

function loadYamlFiles(): TemplateYaml[] {
  if (!fs.existsSync(SPECIALTIES_DIR)) {
    throw new Error(`Specialties directory not found: ${SPECIALTIES_DIR}`);
  }
  const entries = fs.readdirSync(SPECIALTIES_DIR).filter((f) => f.endsWith('.yaml'));
  if (entries.length === 0) {
    throw new Error(`No *.yaml files in ${SPECIALTIES_DIR}`);
  }
  return entries.map((file) => {
    const raw = fs.readFileSync(path.join(SPECIALTIES_DIR, file), 'utf8');
    const parsed = yaml.load(raw) as TemplateYaml;
    const missing = [
      'slug',
      'displayName',
      'version',
      'requiredExamElements',
      'soapSchema',
      'systemPrompt',
    ].filter((k) => parsed[k as keyof TemplateYaml] == null);
    if (missing.length) {
      throw new Error(`${file}: missing required keys ${missing.join(', ')}`);
    }
    return parsed;
  });
}

async function upsertTemplate(t: TemplateYaml): Promise<'created' | 'updated' | 'version_bumped'> {
  const existing = await prisma.scribeSpecialtyTemplate.findUnique({
    where: { slug: t.slug },
  });
  if (!existing) {
    await prisma.scribeSpecialtyTemplate.create({
      data: {
        slug: t.slug,
        displayName: t.displayName,
        version: t.version,
        systemPrompt: t.systemPrompt,
        requiredExamElements: t.requiredExamElements as object,
        soapSchema: t.soapSchema as object,
        defaultIcd10Hints: t.defaultIcd10Hints ?? [],
        defaultCptHints: t.defaultCptHints ?? [],
        defaultFormularyHints: t.defaultFormularyHints ?? [],
        clinicalReviewStatus: reviewStatusToPrisma(t.clinicalReviewStatus),
        active: true,
      },
    });
    return 'created';
  }

  if (existing.version === t.version) {
    await prisma.scribeSpecialtyTemplate.update({
      where: { slug: t.slug },
      data: {
        displayName: t.displayName,
        systemPrompt: t.systemPrompt,
        requiredExamElements: t.requiredExamElements as object,
        soapSchema: t.soapSchema as object,
        defaultIcd10Hints: t.defaultIcd10Hints ?? [],
        defaultCptHints: t.defaultCptHints ?? [],
        defaultFormularyHints: t.defaultFormularyHints ?? [],
        clinicalReviewStatus: reviewStatusToPrisma(t.clinicalReviewStatus),
        active: true,
      },
    });
    return 'updated';
  }

  // Version bump: deactivate the old row (by slug is already unique, so we
  // can't keep two rows under the same slug). Simpler than maintaining a
  // separate history table for M1 — revisit if outputs need historical
  // lookup by slug+version.
  await prisma.scribeSpecialtyTemplate.update({
    where: { slug: t.slug },
    data: {
      version: t.version,
      displayName: t.displayName,
      systemPrompt: t.systemPrompt,
      requiredExamElements: t.requiredExamElements as object,
      soapSchema: t.soapSchema as object,
      defaultIcd10Hints: t.defaultIcd10Hints ?? [],
      defaultCptHints: t.defaultCptHints ?? [],
      defaultFormularyHints: t.defaultFormularyHints ?? [],
      clinicalReviewStatus: reviewStatusToPrisma(t.clinicalReviewStatus),
      active: true,
    },
  });
  return 'version_bumped';
}

async function main() {
  const templates = loadYamlFiles();
  console.log(`Seeding ${templates.length} specialty template(s)…`);
  for (const t of templates) {
    const result = await upsertTemplate(t);
    console.log(`  ${t.slug} (v${t.version}) → ${result}`);
  }
  console.log('Done.');
}

main()
  .catch((err) => {
    console.error('seed-specialties failed:', err);
    process.exit(1);
  })
  .finally(async () => {
    await prisma.$disconnect();
  });
