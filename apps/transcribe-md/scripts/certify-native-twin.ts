// ============================================================================
// Certify a native DOCX Template Twin through the REAL production path.
// ----------------------------------------------------------------------------
// One-shot ruled-act tooling (SLICE-0 #317): drafts a committed .docx into a
// practice and runs the SAME auto-certify path the production worker uses
// (runAutoCertifyTwin) — plan the mappings, run the LIVE L3/L4 synthetic
// round-trip self-test, certify + activate iff 0 fields decline and the proof
// passes. It certifies NOTHING on its own; it drives the sanctioned lifecycle
// and reports the outcome. A declined field or a failed proof leaves a
// NEEDS_CONFIRMATION draft and names the reason — it never half-certifies.
//
// Env:  DOCX_PATH  ACTOR_USER  ACTOR_EMAIL  ACTOR_PRACTICE
// Run inside transcribe-md-worker (has DATABASE_URL, the @/* alias, the image
// code) via scripts/run-ruled-mutation.sh --in transcribe-md-worker.
// ============================================================================
import { readFileSync } from 'node:fs';
import { createHash } from 'node:crypto';

import { createTemplateTwinDraft } from '@/lib/template-twin/create-draft';
import { runAutoCertifyTwin } from '@/worker/auto-certify-twin-job';
import prisma from '@meddoc/db';

function req(name: string): string {
  const v = process.env[name];
  if (!v) throw new Error(`missing env ${name}`);
  return v;
}

async function main() {
  const docxPath = req('DOCX_PATH');
  const actor = {
    userId: req('ACTOR_USER'),
    userEmail: req('ACTOR_EMAIL'),
    practiceId: req('ACTOR_PRACTICE'),
  };
  const source = new Uint8Array(readFileSync(docxPath));
  const sha = createHash('sha256').update(source).digest('hex');
  console.log(`[certify-twin] source ${docxPath} bytes=${source.byteLength} sha256=${sha}`);
  console.log(`[certify-twin] actor user=${actor.userId} practice=${actor.practiceId}`);

  const draft = await createTemplateTwinDraft({ source, actor });
  console.log(`[certify-twin] DRAFT created: noteTemplateId=${draft.noteTemplateId} sourceSha=${draft.sourceSha256}`);

  const result = await runAutoCertifyTwin({
    noteTemplateId: draft.noteTemplateId,
    userId: actor.userId,
    userEmail: actor.userEmail,
    practiceId: actor.practiceId,
  });
  console.log(`[certify-twin] auto-certify RESULT: ${JSON.stringify(result)}`);

  // Report the resulting state for the judgement.
  const nt = await prisma.noteTemplate.findUnique({
    where: { id: draft.noteTemplateId },
    select: {
      id: true,
      name: true,
      status: true,
      templateTwinCompiledVersion: { select: { certificationStatus: true } },
    },
  });
  console.log(`[certify-twin] template now: ${JSON.stringify(nt)}`);
  const active = await prisma.noteTemplate.findMany({
    where: { practiceId: actor.practiceId, status: 'active' },
    select: { id: true, name: true },
  });
  console.log(`[certify-twin] ACTIVE templates in practice: ${JSON.stringify(active)}`);
  console.log(`[certify-twin] DONE — status=${(result as any).status ?? 'unknown'} noteTemplateId=${draft.noteTemplateId}`);
}

main().catch((e) => {
  console.error('[certify-twin] FAILED:', e?.stack ?? e?.message ?? e);
  process.exit(1);
});
