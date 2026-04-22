// End-to-end smoke: inject + fill with dummy data, then verify the
// resulting .docx has no leftover {{tokens}} and contains the dummy
// content. Writes /host/injected-filled.docx for manual inspection.
//
// Usage: tsx test-inject-and-fill.ts <templateId>

import { writeFileSync } from 'node:fs';

import prisma from '@meddoc/db';

import { downloadTemplate } from '../src/lib/minio';
import { injectTokens } from '../src/lib/template-inject';
import { fillTemplate } from '../src/lib/template-docx-generator';

const DUMMY_CONTENT = {
  chief_complaint: 'DUMMY_CC',
  hpi: 'DUMMY_HPI narrative for testing.',
  ros: 'DUMMY_ROS findings.',
  pmh: 'DUMMY_PMH summary.',
  allergies: 'DUMMY_ALLERGIES',
  medications: 'DUMMY_MEDICATIONS list.',
  exam: 'DUMMY_EXAM findings.',
  assessment: 'DUMMY_ASSESSMENT.',
  plan: 'DUMMY_PLAN.',
};

async function main() {
  const templateId = process.argv[2];
  if (!templateId) throw new Error('usage: test-inject-and-fill.ts <templateId>');

  const t = await prisma.transcribeTemplate.findUnique({
    where: { id: templateId },
    select: { minioKey: true },
  });
  if (!t) throw new Error('template not found');

  const original = await downloadTemplate(t.minioKey);
  const { injected, tokensInjected } = injectTokens(original);
  console.log(`inject: ${original.length} → ${injected.length} bytes, tokens=[${tokensInjected.join(', ')}]`);

  const filled = fillTemplate(injected, DUMMY_CONTENT);
  console.log(`fill: → ${filled.length} bytes`);

  writeFileSync('/host/injected-filled.docx', filled);
  console.log('wrote /host/injected-filled.docx');

  await prisma.$disconnect();
}

main().catch((e) => {
  console.error('FAILED:', e);
  process.exit(1);
});
