// T-M24.smart backfill — run the injector on an existing
// transcribe_templates row that was uploaded BEFORE the auto-inject
// path went live, and set its injectedMinioKey. One-off tool: the
// upload endpoint now handles this automatically at upload time.
//
// Usage: tsx backfill-template-injection.ts <templateId>

import { randomUUID } from 'node:crypto';

import prisma from '@meddoc/db';

import {
  buildTemplateObjectKey,
  downloadTemplate,
  putTemplate,
} from '../src/lib/minio';
import { injectTokens } from '../src/lib/template-inject';

async function main() {
  const templateId = process.argv[2];
  if (!templateId) throw new Error('usage: backfill-template-injection.ts <templateId>');

  // Raw SQL to dodge the db-migrate container's stale prisma client.
  const rows = (await prisma.$queryRaw`
    SELECT id, "userId", name, "minioKey", "injectedMinioKey", tokens
      FROM transcribe_templates
     WHERE id = ${templateId}
       AND "deletedAt" IS NULL
  `) as Array<{
    id: string;
    userId: string;
    name: string;
    minioKey: string;
    injectedMinioKey: string | null;
    tokens: string[];
  }>;
  if (rows.length === 0) throw new Error(`template ${templateId} not found`);
  const t = rows[0];

  console.log(`Template: ${t.name}`);
  console.log(`  user:           ${t.userId}`);
  console.log(`  minioKey:       ${t.minioKey}`);
  console.log(`  injectedMinioKey (before): ${t.injectedMinioKey ?? '(null)'}`);
  console.log(`  hand tokens:    [${t.tokens.join(', ')}]`);

  if (t.tokens.length > 0) {
    console.log('\n→ template already has hand-written tokens; skipping auto-injection.');
    await prisma.$disconnect();
    return;
  }

  const original = await downloadTemplate(t.minioKey);
  const result = injectTokens(original);
  console.log(`\n→ injected tokens: [${result.tokensInjected.join(', ')}]`);
  if (result.tokensInjected.length === 0) {
    console.log('  no clinical sections detected — nothing to inject.');
    await prisma.$disconnect();
    return;
  }

  const newKey = buildTemplateObjectKey(t.userId, `${randomUUID()}-injected`);
  await putTemplate(newKey, result.injected);
  console.log(`→ uploaded injected variant to: ${newKey}`);

  await prisma.$executeRaw`
    UPDATE transcribe_templates
       SET "injectedMinioKey" = ${newKey}
     WHERE id = ${t.id}
  `;
  console.log('→ updated transcribe_templates row ✓');

  await prisma.$disconnect();
}

main().catch((e) => {
  console.error('backfill failed:', e);
  process.exit(1);
});
