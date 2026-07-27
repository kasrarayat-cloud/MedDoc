// ============================================================================
// LIVE round-trip: a manual-classified mapping written, then read back through
// the real read path. The static test proves the chain is wired; this proves the
// database honours it. Together they are the check that would have caught the
// missing column before two certification runs were burned.
// ============================================================================

import { prisma } from '@meddoc/db';

const say = (s: string) => console.log(`[rt] ${s}`);

async function main() {
  const mapping = await prisma.templateTwinSemanticMapping.findFirst({
    select: { id: true, sourceType: true, fieldDefinitionId: true },
  });
  if (!mapping) throw new Error('no mappings on this database');

  const before = mapping.sourceType;
  say(`chose mapping ${mapping.id} (sourceType=${before})`);

  try {
    // WRITE — exactly the column updateTemplateTwinMappings now sets.
    await prisma.templateTwinSemanticMapping.update({
      where: { id: mapping.id },
      data: { sourceType: 'manual' },
    });

    // READ — through a fresh query, as loadOwnedCompilation does.
    const back = await prisma.templateTwinSemanticMapping.findUniqueOrThrow({
      where: { id: mapping.id },
      select: { sourceType: true },
    });
    say(`read back sourceType=${back.sourceType}`);

    // And through the schema parse the read path applies.
    const { SemanticMappingSchema } = await import('@/lib/template-twin/ir');
    const parsed = SemanticMappingSchema.parse({
      // The parse only has to prove sourceType survives; the id shape is
      // checked by the schema and is not what this proof is about.
      fieldId: `ttf_${'a'.repeat(24)}`,
      sourceType: back.sourceType,
      clinicalConcept: null,
      expectedDataType: 'single_select',
      polarityBehavior: 'value_only',
      temporality: 'current',
      laterality: 'optional',
      unitPolicy: 'not_applicable',
      approvedSynonyms: [],
      required: false,
      blankPolicy: 'blank',
      unknownPolicy: 'blank',
      practiceDefault: null,
      status: 'certified',
    });
    say(`parsed sourceType=${parsed.sourceType}`);

    const ok = back.sourceType === 'manual' && parsed.sourceType === 'manual';
    say(`ROUNDTRIP ${ok ? 'PASS' : 'FAIL'} — wrote manual, read manual: ${ok}`);
    if (!ok) process.exitCode = 1;
  } finally {
    await prisma.templateTwinSemanticMapping.update({
      where: { id: mapping.id },
      data: { sourceType: before },
    });
    say(`restored sourceType=${before}`);
  }
}

main()
  .catch((e) => { say(`FAILED: ${e instanceof Error ? e.stack : String(e)}`); process.exitCode = 1; })
  .finally(() => prisma.$disconnect());
