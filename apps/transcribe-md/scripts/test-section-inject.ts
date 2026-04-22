// Ad-hoc harness — pull a template from MinIO, run injectTokens on
// its binary, print a summary of what changed, and write the injected
// .docx to /host/template-injected.docx so we can unzip + diff the
// XML manually.
//
// Usage: tsx test-section-inject.ts <templateId>

import { writeFileSync } from 'node:fs';

import prisma from '@meddoc/db';

import { downloadTemplate } from '../src/lib/minio';
import { detectSections } from '../src/lib/template-sections';
import { injectTokens } from '../src/lib/template-inject';

async function main() {
  const templateId = process.argv[2];
  if (!templateId) throw new Error('usage: test-section-inject.ts <templateId>');

  const t = await prisma.transcribeTemplate.findUnique({
    where: { id: templateId },
    select: { id: true, name: true, minioKey: true },
  });
  if (!t) throw new Error(`template ${templateId} not found`);

  const original = await downloadTemplate(t.minioKey);
  const beforeSections = detectSections(original);
  const clinical = beforeSections.filter(
    (s) => s.contentType === 'clinical_narrative' && s.mappedToken
  );

  console.log(`Template:           ${t.name}`);
  console.log(`Original bytes:     ${original.length}`);
  console.log(`Clinical sections:  ${clinical.length}`);
  for (const s of clinical) {
    const tag = s.headingHasInlineContent ? 'inline' : 'separate-body';
    console.log(`  • ${String(s.mappedToken).padEnd(16)} ${tag.padEnd(14)} ${s.heading}`);
  }
  console.log('');

  const result = injectTokens(original);
  console.log(`Injected bytes:     ${result.injected.length}`);
  console.log(`Tokens written:     ${result.tokensInjected.join(', ')}`);
  console.log(`Tokens skipped:     ${result.tokensSkipped.join(', ') || '(none)'}`);
  console.log('');

  // Verify the injected binary re-parses cleanly and docxtemplater
  // token extraction would pick up the new placeholders.
  const afterSections = detectSections(result.injected);
  const afterClinical = afterSections.filter(
    (s) => s.contentType === 'clinical_narrative'
  );
  console.log(`After-detect clinical sections: ${afterClinical.length}`);
  for (const s of afterClinical) {
    console.log(
      `  • ${String(s.mappedToken).padEnd(16)} ${String(s.heading).slice(0, 40).padEnd(40)} preview="${s.preview.slice(0, 40)}"`
    );
  }

  writeFileSync('/host/template-injected.docx', result.injected);
  console.log('\nWrote /host/template-injected.docx');

  await prisma.$disconnect();
}

main().catch((e) => {
  console.error('inject failed:', e);
  process.exit(1);
});
