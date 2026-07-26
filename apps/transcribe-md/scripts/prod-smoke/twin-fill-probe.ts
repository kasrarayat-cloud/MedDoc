// ============================================================================
// READ-ONLY fill probe — why a field blocked, without burning a certification.
// ----------------------------------------------------------------------------
// A certification run is ~8 minutes and writes state. This replays the exact
// fill for an already-drafted compiled version using its stored IR, mappings and
// PINNED note, and prints per-field status / value / reason / citations plus the
// validator's verdicts. One L3 call, no writes.
//
//   DATABASE_URL=<qa> npx tsx scripts/prod-smoke/twin-fill-probe.ts [compiledId]
// ============================================================================

import { prisma } from '@meddoc/db';

const say = (s: string) => console.log(`[probe] ${s}`);

async function main() {
  const compiledId = process.argv[2];
  const compiled = await prisma.templateTwinCompiledVersion.findFirst({
    where: compiledId ? { id: compiledId } : { pinnedSyntheticNote: { not: null } },
    orderBy: compiledId ? undefined : { compiledAt: 'desc' },
    select: {
      id: true,
      noteTemplateId: true,
      compiledDocumentIr: true,
      pinnedSyntheticNote: true,
      pinnedSyntheticEntities: true,
      pinnedSyntheticContextText: true,
      sourceArtifact: { select: { practiceId: true } },
      fields: {
        select: {
          fieldId: true,
          originalLabel: true,
          mapping: {
            select: {
              sourceType: true,
              clinicalConcept: true,
              expectedDataType: true,
              polarityBehavior: true,
              temporality: true,
              laterality: true,
              unitPolicy: true,
              approvedSynonyms: true,
              required: true,
              blankPolicy: true,
              unknownPolicy: true,
              practiceDefault: true,
              mappingStatus: true,
            },
          },
        },
      },
    },
  });
  if (!compiled?.pinnedSyntheticNote) throw new Error('no pinned compiled version found');
  say(`compiled=${compiled.id} fields=${compiled.fields.length}`);

  const ENCOUNTER = process.env.PROBE_ENCOUNTER!;
  const user = await prisma.user.findFirst({
    where: { email: { contains: 'qa-' } },
    select: { id: true, practiceId: true },
  });

  const { extractTemplateTwinEntities } = await import('@/worker/layers/03-extract-entities');
  const { projectEncounterFacts } = await import('@/lib/template-twin/encounter-facts');
  const { prepareTemplateTwinFill } = await import('@/lib/template-twin/fill-engine');
  const { SemanticMappingSchema } = await import('@/lib/template-twin/ir');

  // Replay the PINNED extraction when there is one — otherwise the probe would
  // diagnose a different fact set than the run it is explaining.
  const extracted =
    compiled.pinnedSyntheticEntities != null && compiled.pinnedSyntheticContextText != null
      ? {
          entities: compiled.pinnedSyntheticEntities,
          contextText: compiled.pinnedSyntheticContextText,
        }
      : await extractTemplateTwinEntities({
          mode: 'text',
          text: ENCOUNTER,
          practiceId: user!.practiceId,
          userId: user!.id,
          noteTemplateId: compiled.noteTemplateId,
        });
  say(`extraction ${compiled.pinnedSyntheticEntities != null ? 'PINNED' : 'fresh'}`);
  const facts = projectEncounterFacts({
    mode: 'text',
    contextText: extracted.contextText,
    entities: extracted.entities as never,
    asrQuality: 'unknown',
  });
  say(`facts=${facts.length}`);

  const mappings = compiled.fields.map((f: (typeof compiled.fields)[number]) =>
    SemanticMappingSchema.parse({
      fieldId: f.fieldId,
      sourceType: f.mapping!.sourceType,
      clinicalConcept: f.mapping!.clinicalConcept,
      expectedDataType: f.mapping!.expectedDataType,
      polarityBehavior: f.mapping!.polarityBehavior,
      temporality: f.mapping!.temporality,
      laterality: f.mapping!.laterality,
      unitPolicy: f.mapping!.unitPolicy,
      approvedSynonyms: f.mapping!.approvedSynonyms,
      required: f.mapping!.required,
      blankPolicy: f.mapping!.blankPolicy,
      unknownPolicy: f.mapping!.unknownPolicy,
      practiceDefault: f.mapping!.practiceDefault,
      status: String(f.mapping!.mappingStatus).toLowerCase(),
    }),
  );

  const prepared = await prepareTemplateTwinFill({
    compiledVersionId: compiled.id,
    noteTemplateId: compiled.noteTemplateId,
    noteTemplateVersion: 1,
    ir: compiled.compiledDocumentIr as never,
    mappings,
    facts,
    resolverModelVersion: null,
    validationNow: new Date(),
    allowUncertifiedForSyntheticTest: true,
    generatedNote: compiled.pinnedSyntheticNote,
    markerText: '{{one of}}',
  });

  const labelById = new Map(
    compiled.fields.map((f: (typeof compiled.fields)[number]) => [f.fieldId, f.originalLabel]),
  );
  const issues = (prepared.manifest.validation as { issues?: { fieldId: string; code: string }[] })
    .issues ?? [];
  const failing = new Set(issues.map((i) => i.fieldId));
  say(`validation.valid=${(prepared.manifest.validation as { valid: boolean }).valid} issues=${issues.length}`);

  const fields = prepared.manifest.fields as {
    fieldId: string;
    status: string;
    value: unknown;
    reasonCode: string;
    sourceFactIds: string[];
  }[];
  for (const f of fields) {
    if (!failing.has(f.fieldId)) continue;
    const codes = issues.filter((i) => i.fieldId === f.fieldId).map((i) => i.code).join('+');
    say(
      `FAIL ${codes} "${String(labelById.get(f.fieldId)).slice(0, 34)}" ` +
        `status=${f.status} value=${JSON.stringify(f.value)} reason=${f.reasonCode} ` +
        `cites=${f.sourceFactIds.length}`,
    );
    for (const id of f.sourceFactIds) {
      const fact = facts.find((x) => x.factId === id);
      say(
        `      cite ${id.slice(0, 16)} concept=${fact?.concept} lat=${fact?.laterality} ` +
          `num=${fact?.number} unit=${fact?.unit}`,
      );
    }
  }

  // ADDRESSING. The bridge matches a note table row to an IR row by vein label;
  // when that match fails the cell is silently left to the resolver, which
  // cannot address rows at all. Print both sides so the mismatch is visible.
  const { parseMarkdownTables } = await import('@/lib/template-twin/bridge-fill-diag');
  for (const t of parseMarkdownTables(compiled.pinnedSyntheticNote!)) {
    say(`NOTE TABLE header=[${t.header.join(' | ')}] rows=${t.rows.length}`);
    for (const r of t.rows) say(`  note row "${r.label}" -> [${r.cells.join(' | ')}]`);
  }

  // Full picture, compactly: what each field's binding is and how it resolved.
  const irFields = (compiled.compiledDocumentIr as {
    fields: {
      fieldId: string;
      rendererBinding: { bindingType: string; rowLaterality?: string };
    }[];
  }).fields;
  const bindingById = new Map(irFields.map((f) => [f.fieldId, f.rendererBinding]));
  const irCells = irFields.filter((f) => f.rendererBinding.bindingType === 'table_cell');
  say(`IR table cells=${irCells.length}`);
  for (const f of irCells.slice(0, 60)) {
    const b = f.rendererBinding as { rowIndex?: number; rowLaterality?: string; columnIndex?: number };
    const st = fields.find((x) => x.fieldId === f.fieldId);
    say(
      `  ir row=${String(b.rowIndex).padStart(2)} col=${b.columnIndex} lat=${b.rowLaterality} ` +
        `"${String(labelById.get(f.fieldId)).slice(0, 28)}" -> ${st?.status}/${st?.reasonCode}`,
    );
  }
  const byBucket = new Map<string, number>();
  for (const f of fields) {
    const b = bindingById.get(f.fieldId);
    const key = `${b?.bindingType}/${b?.rowLaterality ?? '-'} ${f.status} ${f.reasonCode}`;
    byBucket.set(key, (byBucket.get(key) ?? 0) + 1);
  }
  for (const [key, n] of [...byBucket.entries()].sort()) say(`BUCKET ${n.toString().padStart(3)}  ${key}`);

  const counts = prepared.manifest.counts;
  say(`counts=${JSON.stringify(counts)}`);
}

main()
  .catch((e) => {
    say(`FAILED: ${e instanceof Error ? (e.stack ?? e.message) : String(e)}`);
    process.exitCode = 1;
  })
  .finally(() => prisma.$disconnect());
