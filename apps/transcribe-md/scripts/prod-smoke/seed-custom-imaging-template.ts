// ============================================================================
// A CUSTOM imaging template on the smoke fixture — the path that regressed.
// ----------------------------------------------------------------------------
// The anchored-verifier provenance work was smoked against a doctor with NO
// custom template, so it resolved the BUILT-IN ultrasound template — the one
// that carries `provenance` declarations, and the one path that was never
// broken. Zero flags, and the fix looked proven. A real clinician on their own
// uploaded form got ten flags forty minutes later.
//
// So the smoke needs a template shaped like the one that actually failed:
//   * `provenance` on NO section (an uploaded form never declares it)
//   * `defaultText` on EVERY section, FINDINGS included
//   * it DECLARES the cross-step sections (PROCEDURES / E&M, PATIENT SUMMARY),
//     which is what let a template's own claim beat PIPELINE_SECTION_POLICY
//
// Smoke-fixture only: refuses to run against anything but the synthetic
// account, and the cleaner already removes note_templates it owns.
//
//   DATABASE_URL=... npx tsx scripts/prod-smoke/seed-custom-imaging-template.ts
// ============================================================================

import { prisma } from '@meddoc/db';

import { SMOKE_EMAIL, assertIsSmokeFixture } from './smoke-account';

/** Mirrors the production form's section set — labels and shape, no content. */
const SECTIONS = [
  {
    key: 'exam_metadata',
    label: 'Exam Metadata',
    order: 0,
    formatHint: 'prose',
    styleInstructions: 'Study type, laterality, indications.',
    defaultText: 'Referring physician: [not documented]. Machine: [not documented].',
    defaultTextMode: 'omit_unless_supported',
  },
  {
    key: 'technique',
    label: 'TECHNIQUE',
    order: 1,
    formatHint: 'prose',
    styleInstructions: 'The standing scan protocol.',
    defaultText:
      'A duplex Doppler color flow ultrasound study was performed in the upright position with and without manual augmentation of flow and Valsalva maneuver.',
    defaultTextMode: 'omit_unless_supported',
  },
  {
    key: 'findings',
    label: 'FINDINGS',
    order: 2,
    formatHint: 'prose',
    styleInstructions: 'Per-leg venous findings with measurements.',
    defaultText: '| Vein | Diameter (mm) | Reflux time (s) |',
    defaultTextMode: 'omit_unless_supported',
  },
  {
    key: 'impression',
    label: 'IMPRESSION',
    order: 3,
    formatHint: 'numbered',
    styleInstructions: 'Numbered impressions.',
    defaultText: 'Clinical correlation with the above findings is required.',
    defaultTextMode: 'omit_unless_supported',
  },
  {
    key: 'procedures_em',
    label: 'PROCEDURES / E&M',
    order: 4,
    formatHint: 'prose',
    styleInstructions: 'Written by the coding step.',
    defaultText: '[not documented]',
    defaultTextMode: 'omit_unless_supported',
  },
  {
    key: 'patient_education',
    label: 'PATIENT SUMMARY',
    order: 5,
    formatHint: 'prose',
    styleInstructions: 'Written by the patient-summary step.',
    defaultText: 'What we found',
    defaultTextMode: 'omit_unless_supported',
  },
];

const TEMPLATE_NAME = 'Smoke Venous Duplex Report (synthetic custom form)';

async function main() {
  const user = await prisma.user.findUnique({
    where: { email: SMOKE_EMAIL },
    include: { practice: { select: { slug: true } } },
  });
  if (!user) throw new Error('no smoke fixture on this database');
  assertIsSmokeFixture({ email: user.email, practice: { slug: user.practice.slug } });

  // Idempotent: one template, replaced in place.
  const existing = await prisma.noteTemplate.findFirst({
    where: { doctorId: user.id, name: TEMPLATE_NAME },
    select: { id: true },
  });

  const data = {
    doctorId: user.id,
    name: TEMPLATE_NAME,
    // Null so it resolves for the imaging encounter the way the real one does.
    encounterType: null,
    sections: SECTIONS as never,
    status: 'active',
    isSystemDefault: false,
  };

  const row = existing
    ? await prisma.noteTemplate.update({ where: { id: existing.id }, data })
    : await prisma.noteTemplate.create({ data });

  // Any OTHER active template of the smoke doctor's would race this one.
  await prisma.noteTemplate.updateMany({
    where: { doctorId: user.id, status: 'active', NOT: { id: row.id } },
    data: { status: 'inactive' },
  });

  const hasProvenance = SECTIONS.some((s) => 'provenance' in s);
  console.log(`[smoke-template] ${existing ? 'updated' : 'created'} ${row.id}`);
  console.log(
    `[smoke-template] sections=${SECTIONS.length} provenanceDeclared=${hasProvenance} ` +
      `(false is the point — it is what an uploaded form looks like)`
  );
}

main()
  .then(async () => {
    await prisma.$disconnect();
    process.exit(0);
  })
  .catch(async (err) => {
    console.error(`[smoke-template] FAILED: ${err instanceof Error ? err.stack : String(err)}`);
    await prisma.$disconnect();
    process.exit(1);
  });
