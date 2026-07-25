// ============================================================================
// Template-Twin native-DOCX probe — exercises the twin pipeline end to end
// against a REAL .docx, with NEXT_PUBLIC_TEMPLATE_NATIVE_DOCX forced ON.
// ----------------------------------------------------------------------------
// Run against the ISOLATED QA STACK only. The twin flag is OFF in production
// and must stay off: the path is not end-to-end functional (see the verdict
// this script prints), and enabling it would route real DOCX exports through
// it.
//
//   DATABASE_URL=<qa> npx tsx scripts/prod-smoke/twin-probe.ts "<file.docx>"
//
// Prints each stage and the VERBATIM error on the first failure — the point is
// the error text, not a pass/fail.
// ============================================================================

process.env.NEXT_PUBLIC_TEMPLATE_NATIVE_DOCX = 'true';

import { readFileSync } from 'node:fs';

import { prisma } from '@meddoc/db';

async function main() {
  const file = process.argv[2];
  const bytes = new Uint8Array(readFileSync(file));
  console.log(`[twin] source: ${file} (${bytes.length} bytes)`);

  const user = await prisma.user.findFirst({
    where: { email: { contains: 'qa-' } },
    select: { id: true, practiceId: true, email: true },
  });
  if (!user) throw new Error('no QA user found on this database');
  console.log(`[twin] actor: ${user.email}`);
  // The twin actor carries userEmail as well as the ids — it lands in the
  // TEMPLATE_TWIN_* audit rows, which is why it is required rather than derived.
  const actor = { userId: user.id, userEmail: user.email, practiceId: user.practiceId };

  const { createTemplateTwinDraft } = await import('@/lib/template-twin/create-draft');

  let noteTemplateId: string;
  try {
    const created = await createTemplateTwinDraft({
      source: bytes,
      actor,
    });
    noteTemplateId = created.noteTemplateId;
    console.log(`[twin] STAGE 1 createTemplateTwinDraft: OK noteTemplateId=${noteTemplateId}`);
  } catch (err) {
    console.log('[twin] STAGE 1 createTemplateTwinDraft: FAILED');
    console.log('[twin] VERBATIM:', err instanceof Error ? err.stack ?? err.message : String(err));
    return;
  }

  // What did the bridge actually produce? This is the documented root cause:
  // the twin NoteTemplate is seeded from the SYSTEM DEFAULT SOAP sections
  // rather than the docx's own {{one of}} + table structure.
  const tmpl = await prisma.noteTemplate.findUnique({
    where: { id: noteTemplateId },
    select: { name: true, sections: true, status: true },
  });
  const secs = (tmpl?.sections as unknown as { heading?: string }[]) ?? [];
  console.log(`[twin] STAGE 2 bridged NoteTemplate: status=${tmpl?.status} sections=${secs.length}`);
  console.log(`[twin]   headings: ${secs.map((s) => s.heading).join(' | ')}`);

  const compiled = await prisma.templateTwinCompiledVersion.findFirst({
    where: { noteTemplateId },
    select: { id: true, certificationStatus: true },
  });
  console.log(
    `[twin] STAGE 3 compiled version: ${compiled ? `${compiled.id} status=${compiled.certificationStatus}` : 'NONE'}`
  );

  if (compiled) {
    const fields = await prisma.templateTwinFieldDefinition.count({
      where: { compiledVersionId: compiled.id },
    });
    console.log(`[twin] STAGE 4 extracted field definitions: ${fields}`);
  }
}

main()
  .catch((err) => {
    console.log('[twin] UNCAUGHT VERBATIM:', err instanceof Error ? err.stack ?? err.message : String(err));
    process.exitCode = 1;
  })
  .finally(() => prisma.$disconnect());
