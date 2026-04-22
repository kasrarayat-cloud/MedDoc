// Quick harness: pull a template from MinIO and run detectSections on
// its binary. Prints a human-readable table of what each section was
// classified as. No DB writes, no committed output.
//
// Usage: tsx test-section-detect.ts <templateId>

import prisma from '@meddoc/db';

import { downloadTemplate } from '../src/lib/minio';
import { detectSections } from '../src/lib/template-sections';

const KIND_PAD: Record<string, string> = {
  letterhead: 'letterhead        ',
  metadata: 'metadata          ',
  salutation: 'salutation        ',
  clinical_narrative: 'clinical_narrative',
  clinical_table: 'clinical_table    ',
  sub_section: 'sub_section       ',
  signature: 'signature         ',
  disclaimer: 'disclaimer        ',
  boilerplate: 'boilerplate       ',
};

async function main() {
  const templateId = process.argv[2];
  if (!templateId) throw new Error('usage: test-section-detect.ts <templateId>');

  const t = await prisma.transcribeTemplate.findUnique({
    where: { id: templateId },
    select: { id: true, name: true, originalFileName: true, minioKey: true },
  });
  if (!t) throw new Error(`template ${templateId} not found`);

  console.log(`Template: ${t.name} (${t.originalFileName})`);
  console.log(`MinIO:    ${t.minioKey}\n`);

  const buffer = await downloadTemplate(t.minioKey);
  const sections = detectSections(buffer);

  console.log(`Detected ${sections.length} blocks:\n`);
  console.log(
    '   # | contentType        | token            | blocks | tbl | heading / preview'
  );
  console.log(
    '----- +--------------------+------------------+--------+-----+-------------------------'
  );
  sections.forEach((s, idx) => {
    const num = String(idx + 1).padStart(3, ' ');
    const kind = KIND_PAD[s.contentType] ?? s.contentType;
    const token = (s.mappedToken ?? '-').padEnd(16, ' ');
    const blocks = String(s.blockCount).padStart(6, ' ');
    const tbl = s.hasTable ? ' Y ' : '   ';
    const headLabel = s.heading ? s.heading.slice(0, 40) : s.preview.slice(0, 40);
    const preview = s.heading ? s.preview.slice(0, 60) : '';
    console.log(`  ${num} | ${kind} | ${token} | ${blocks} | ${tbl} | ${headLabel}`);
    if (preview) console.log(`                                                              ↳ ${preview}`);
  });

  // Summary stats
  const byType = new Map<string, number>();
  for (const s of sections) {
    byType.set(s.contentType, (byType.get(s.contentType) ?? 0) + 1);
  }
  console.log('\nSummary by contentType:');
  for (const [type, count] of byType) {
    console.log(`  ${type.padEnd(20)} ${count}`);
  }

  const mapped = sections.filter((s) => s.mappedToken).map((s) => s.mappedToken);
  console.log('\nMapped tokens (clinical_narrative):');
  console.log(`  ${mapped.length > 0 ? mapped.join(', ') : '(none)'}`);

  await prisma.$disconnect();
}

main().catch((e) => {
  console.error('detect failed:', e);
  process.exit(1);
});
