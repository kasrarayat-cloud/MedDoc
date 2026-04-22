// E2E download-side test — mimics GET /api/visits/:id/export/template-docx
// without going through HTTP/auth. Reads the visit's filledTemplate
// JSON, prefers the template's injectedMinioKey when set, runs
// fillTemplate, writes /host/visit-filled.docx.
//
// Usage: tsx test-visit-template-download.ts <visitId>

import { writeFileSync } from 'node:fs';

import prisma from '@meddoc/db';

import { downloadTemplate } from '../src/lib/minio';
import { fillTemplate } from '../src/lib/template-docx-generator';

async function main() {
  const visitId = process.argv[2];
  if (!visitId) throw new Error('usage: test-visit-template-download.ts <visitId>');

  // Raw SQL so we work against the db-migrate container's stale
  // prisma client (which may predate `injectedMinioKey`).
  const rows = (await prisma.$queryRaw`
    SELECT v."filledTemplate", v."templateId",
           t.name         AS template_name,
           t."minioKey"   AS template_minio_key,
           t."injectedMinioKey" AS template_injected_minio_key
      FROM transcribe_visits v
      JOIN transcribe_templates t ON t.id = v."templateId"
     WHERE v.id = ${visitId}
  `) as Array<{
    filledTemplate: string | null;
    templateId: string;
    template_name: string;
    template_minio_key: string;
    template_injected_minio_key: string | null;
  }>;

  if (rows.length === 0) throw new Error('visit + template join failed');
  const v = rows[0];
  if (!v.filledTemplate) throw new Error('visit has no filledTemplate');

  const filled = JSON.parse(v.filledTemplate) as Record<string, string>;
  console.log(`Visit ${visitId}`);
  console.log(`  template:        ${v.template_name}`);
  console.log(`  minioKey:        ${v.template_minio_key}`);
  console.log(`  injectedMinioKey: ${v.template_injected_minio_key ?? '(null — legacy token-fill)'}`);
  console.log(`  filledTemplate keys: [${Object.keys(filled).join(', ')}]`);

  const keyToUse = v.template_injected_minio_key ?? v.template_minio_key;
  console.log(`  → fetching MinIO key: ${keyToUse}`);

  const templateBuf = await downloadTemplate(keyToUse);
  const out = fillTemplate(templateBuf, filled);
  console.log(`  → fillTemplate produced ${out.length} bytes`);

  writeFileSync('/host/visit-filled.docx', out);
  console.log('  → wrote /host/visit-filled.docx');

  await prisma.$disconnect();
}

main().catch((e) => {
  console.error('FAILED:', e);
  process.exit(1);
});
