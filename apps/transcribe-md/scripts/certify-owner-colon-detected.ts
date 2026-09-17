// ============================================================================
// SLICE D ACCEPTANCE (#326, owner directive 2026-09-17) — run the owner's
// Colonoscopy_Operative_Template.pdf through the ONE-PIPELINE detect→map→certify,
// mapping each detected box by TRANSFER-BY-IDENTITY from his CERTIFIED colon twin
// (every transferred concept is one his twin approved — REFUSE otherwise), then
// emit the sample-filled preview PDF for his eyeball. ONE-SHOT RULED ACT — runs in
// transcribe-md-worker via scripts/run-ruled-mutation.sh --in transcribe-md-worker
// (ruling #262). The worker is on the `converter` network for the detector sidecar.
//
// It mints a DRAFT detected-form template on his practice (NOT active — no cutover;
// the real-visit acceptance selects it), certifies it (synthetic proof + fidelity),
// writes the sample PDF to /tmp, and prints the before/after for the judgement.
// Certifies NOTHING if a LABELED box has no approved twin concept (it REFUSES).
//
// Args (positional; docker exec forwards args, not env):
//   npx tsx scripts/certify-owner-colon-detected.ts <userId> <userEmail> <practiceId> <pdfPath>
// ============================================================================
import { randomUUID } from 'node:crypto';
import { readFileSync, writeFileSync } from 'node:fs';

import { exitCleanly } from './lib/exit-cleanly';

import prisma from '@meddoc/db';
import {
  detectFormFields,
  groupDetectedFields,
  transferFromTwin,
  persistDetectedForm,
  type TwinApprovedField,
  type StoredDetectedForm,
} from '@/lib/form-fill';
import { certifyDetectedForm } from '@/lib/form-fill/certify-detected-form';
import { previewDetectedForm } from '@/lib/form-fill/preview-detected';
import { canvasHash } from '@/lib/pdf-native/hash';

const L = '[colon-detected]';
const SAMPLE_OUT = '/tmp/colon-detected-sample.pdf';

async function ownerColonTwin(practiceId: string) {
  return prisma.templateTwinCompiledVersion.findFirst({
    where: {
      practiceId,
      certificationStatus: 'CERTIFIED',
      noteTemplate: { name: { contains: 'Colon' } },
    },
    orderBy: { compiledAt: 'desc' },
    select: { id: true, noteTemplate: { select: { id: true, name: true } } },
  });
}

async function main(): Promise<void> {
  const [userId, userEmail, practiceId, pdfPath] = process.argv.slice(2);
  if (!userId || !userEmail || !practiceId || !pdfPath) {
    throw new Error('args: <userId> <userEmail> <practiceId> <pdfPath>');
  }
  const actor = { userId, userEmail, practiceId };

  // ── 1 · his CERTIFIED colon twin → the approved label→concept set ──────────
  const twinComp = await ownerColonTwin(practiceId);
  if (!twinComp) throw new Error('no CERTIFIED colonoscopy twin for this practice');
  console.log(`${L} twin compiled=${twinComp.id} template="${twinComp.noteTemplate?.name}"`);

  const defs = await prisma.templateTwinFieldDefinition.findMany({
    where: { compiledVersionId: twinComp.id, practiceId },
    orderBy: { displayOrder: 'asc' },
    select: {
      originalLabel: true,
      displayOrder: true,
      mapping: { select: { clinicalConcept: true } },
    },
  });
  const twin: TwinApprovedField[] = defs.map((d) => ({
    originalLabel: d.originalLabel ?? '',
    concept: d.mapping?.clinicalConcept ?? null,
    displayOrder: d.displayOrder,
  }));
  console.log(`${L} twin approved fields=${twin.length} concepts=${new Set(twin.map((t) => t.concept).filter(Boolean)).size}`);

  // ── 2 · detect the owner's colon PDF ───────────────────────────────────────
  const pdf = readFileSync(pdfPath);
  const detected = await detectFormFields(new Uint8Array(pdf));
  const grouped = groupDetectedFields(detected);
  console.log(`${L} detected model=${detected.detector.model} boxes=${detected.pages.reduce((n, p) => n + p.boxes.length, 0)} grouped=${grouped.length}`);

  // ── 3 · TRANSFER-BY-IDENTITY (approved-only, refuse otherwise) ─────────────
  const { fields, unmappedLabeled, excludedUnlabeled } = transferFromTwin(grouped, twin);
  console.log(`${L} transfer: mapped=${fields.filter((f) => f.concept).length} unmappedLabeled=${unmappedLabeled.length} excludedUnlabeled=${excludedUnlabeled.length}`);
  for (const f of fields) console.log(`${L}   ${(f.concept ?? 'NULL').padEnd(32)} ${JSON.stringify(f.label)}`);
  if (excludedUnlabeled.length > 0) console.log(`${L} excluded (unlabeled, not filled): ${excludedUnlabeled.map((e) => `p${e.page}`).join(', ')}`);
  if (unmappedLabeled.length > 0) {
    console.log(`${L} REFUSE — labeled boxes with NO approved twin concept: ${unmappedLabeled.map((u) => JSON.stringify(u.label)).join(', ')}`);
    throw new Error('refusing: a labeled box has no approved twin concept (never guessed)');
  }

  // ── 4 · mint a DRAFT template + persist the detected form ──────────────────
  const templateId = randomUUID();
  const sections = fields
    .filter((f) => f.headerKey === null && f.concept)
    .map((f) => ({ key: f.id, label: f.label.replace(/[:*_]+$/g, '').trim() || f.id }));
  const headerFields = fields
    .filter((f) => f.headerKey !== null)
    .map((f, i) => ({ key: f.headerKey as string, label: f.label, order: i + 1 }));
  await prisma.noteTemplate.create({
    data: {
      id: templateId,
      doctorId: userId,
      practiceId,
      name: 'Colonoscopy Operative Note (detected · #326)',
      encounterType: null,
      sections: sections as never,
      styleProfile: { headerFields } as never,
      specialtyBaseline: null,
      version: 1,
      status: 'draft',
      isSystemDefault: false,
    },
  });
  const canvas = Buffer.from(pdf);
  const form: StoredDetectedForm = {
    model: detected.model,
    detector: detected.detector,
    canvasHash: canvasHash(canvas),
    pageCount: detected.pages.length,
    fields,
  };
  await persistDetectedForm({ templateId, doctorId: userId, form, canvas });
  console.log(`${L} minted DRAFT templateId=${templateId} (status=draft — NOT active, no cutover)`);

  // ── 5 · certify (synthetic proof + pixel fidelity) ─────────────────────────
  const cert = await certifyDetectedForm({ templateId, actor });
  console.log(`${L} CERTIFIED fields=${cert.fieldCount} filled=${cert.filledCount} policyBlank=${cert.policyBlankCount} fidelityPages=${cert.fidelity.pages} dpi=${cert.fidelity.dpi}`);

  // ── 6 · the SAMPLE-VALUE PREVIEW PDF (synthetic, PHI-free) ──────────────────
  const preview = await previewDetectedForm({ templateId, actor });
  writeFileSync(SAMPLE_OUT, Buffer.from(preview.pdf));
  console.log(`${L} SAMPLE written ${SAMPLE_OUT} bytes=${preview.pdf.length} filled=${preview.filledCount}/${preview.fieldCount}`);
  console.log(`${L} DONE templateId=${templateId}`);
}

main()
  .then(() => exitCleanly(0))
  .catch((e) => {
    console.error(`${L} FAILED:`, e?.stack ?? e?.message ?? e);
    exitCleanly(1);
  });
