// ============================================================================
// RULING C (2026-09-15) — RE-DERIVE the owner's Colonoscopy_Operative_Template.pdf
// under REGISTRY-3 (#323) + the #324 affordance amendment, AUTO-CERTIFY through the
// REAL path, and ACTIVATE it as the operative note (superseding the prior active,
// KEPT). ONE-SHOT RULED ACT — runs inside transcribe-md-worker via
// scripts/run-ruled-mutation.sh --in transcribe-md-worker (ruling #262).
// ----------------------------------------------------------------------------
// WHY A NEW TEMPLATE ROW, NOT AN IN-PLACE RE-CERTIFY:
//   #324 changes the AFFORDANCE at COMPILE time and REGISTRY-3 changes the mapping
//   at PROPOSE time, so a faithful re-derivation must re-run compile→propose — a
//   NEW compiled version. TemplateTwinCompiledVersion.noteTemplateId is @unique
//   (one-to-one), so a fresh compiled version cannot attach to the prior template;
//   the real upload path mints a new template VERSION. This reproduces that path:
//     1 · mint a new note_template, COPYING the prior's structural fields (name,
//         sections, styleProfile.headerFields, sourceObjectKey/Sha);
//     2 · createTemplateTwinDraft(attachTo=new id) — #324/#325 controls, REGISTRY-3 map;
//     3 · certifyPdfTemplate(new id, ORIGINAL PDF BYTES) — the AUTHORITATIVE pdf-native
//         cert (canvas + anchors + pdfNativeCertified from the bytes). NOT the
//         label-only carryForwardPdfCertification, which refuses on anchors_missing;

//     4 · AUTO-CONFIRM the model's clinical proposals (the REAL auto path); CONFIRM
//         the record-derived (visit_metadata) headers as the ruled human act (#247
//         declines them for a human, and RULING C is that authorisation — exactly as
//         #319 did). ⚠️ ANY OTHER decline ABORTS: it means REGISTRY-3 did not map a
//         clinical field, which is the acceptance signal, not something to paper over;
//     5 · the REAL synthetic round-trip, then certifyAndActivate (activates the new
//         template, flips the prior active → inactive, KEPT).
//
// It PRINTS the model's own proposal (evidence REGISTRY-3 now maps the colon note),
// certifies NOTHING if the round-trip or the lifecycle gate refuses, and reports the
// before/after template + twin + pdf-native state for the judgement.
//
// Args (positional; docker exec forwards args, not env):
//   npx tsx scripts/certify-colon-323.ts <userId> <userEmail> <practiceId> <priorTemplateId>
// where <priorTemplateId> is the currently-active colon operative note whose source
// PDF + structure are the re-derivation input (superseded by this act, kept).
// ============================================================================
import { randomUUID } from 'node:crypto';

import { createTemplateTwinDraft } from '@/lib/template-twin/create-draft';
import { createTemplateTwinArtifactStore } from '@/lib/template-twin/storage';
import { certifyPdfTemplate } from '@/lib/pdf-native/certify';
import { readTemplateTwinWorkspace } from '@/lib/template-twin/workspace-read';
import {
  updateTemplateTwinMappings,
  certifyAndActivateTemplateTwin,
} from '@/lib/template-twin/certification-lifecycle';
import { runTemplateTwinSyntheticTest } from '@/lib/template-twin/synthetic-test';
import { planAutoConfirm } from '@/lib/template-twin/auto-certify-eligibility';
import { extractTemplateTwinEntities } from '@/worker/layers/03-extract-entities';
import { createEphemeralVisitNoteGenerator } from '@/worker/template-twin-note-generator';
import { deriveVerificationEncounter } from '@/lib/template-twin/verification-encounter';
import type { SemanticMapping } from '@/lib/template-twin/ir';
import prisma from '@meddoc/db';

const L = '[323]';

async function ownerTemplates(practiceId: string) {
  return prisma.noteTemplate.findMany({
    where: { practiceId },
    select: {
      id: true,
      name: true,
      status: true,
      encounterType: true,
      styleProfile: true,
      templateTwinCompiledVersion: { select: { certificationStatus: true } },
    },
    orderBy: { createdAt: 'asc' },
  });
}

/** styleProfile with the PDF-native CERT STATE stripped, so carryForward re-derives
 *  it rather than seeing `already_certified`. headerFields / formSignature stay —
 *  headerFields is what the structure hash keys on. */
function styleProfileForFreshDraft(sp: Record<string, unknown>): Record<string, unknown> {
  const {
    pdfNativeCertified: _a,
    pdfNativeAnchors: _b,
    pdfNativeCanvasHash: _c,
    pdfNativeStructureHash: _d,
    pdfNativePendingPreview: _e,
    pdfNativeCarriedFrom: _f,
    ...rest
  } = sp;
  return rest;
}

async function main() {
  const [userId, userEmail, practiceId, priorTemplateId, mode] = process.argv.slice(2);
  if (!userId || !userEmail || !practiceId || !priorTemplateId) {
    throw new Error(
      'usage: certify-colon-323.ts <userId> <userEmail> <practiceId> <priorTemplateId> [inspect]',
    );
  }
  // `inspect` — mint, re-derive, LOG the model proposal + auto-confirm plan, then
  // ROLL BACK (delete the draft mint). Nothing is certified, activated, or
  // superseded. The rehearsal that lets a human read the REGISTRY-3 mapping under
  // the deployed code BEFORE the irreversible act runs for real.
  const inspectOnly = mode === 'inspect';
  const actor = { userId, userEmail, practiceId };

  // ── 0 · read the prior active template (source PDF + structure to copy) ──────
  const prior = await prisma.noteTemplate.findFirst({
    where: { id: priorTemplateId, doctorId: userId, practiceId },
    select: {
      id: true,
      name: true,
      encounterType: true,
      sections: true,
      styleProfile: true,
      specialtyBaseline: true,
      sourceObjectKey: true,
      sourceSha256: true,
      status: true,
    },
  });
  if (!prior) throw new Error(`prior template ${priorTemplateId} not found for this doctor`);
  if (!prior.sourceObjectKey || !prior.sourceSha256) {
    throw new Error(`prior template ${priorTemplateId} has no source PDF (sourceObjectKey/Sha)`);
  }
  const priorSp = (prior.styleProfile ?? {}) as Record<string, unknown>;
  console.log(`${L} PRIOR ${prior.id} "${prior.name}" status=${prior.status} enc=${prior.encounterType}`);
  console.log(`${L} PRIOR source objectKey=${prior.sourceObjectKey} sha=${String(prior.sourceSha256).slice(0, 12)} pdfNativeCertified=${priorSp.pdfNativeCertified}`);

  console.log(`${L} BEFORE — practice templates:`);
  for (const t of await ownerTemplates(practiceId)) {
    const sp = (t.styleProfile ?? {}) as Record<string, unknown>;
    console.log(`    ${t.id} "${t.name}" status=${t.status} cert=${t.templateTwinCompiledVersion?.certificationStatus ?? 'none'} pdfNative=${sp.pdfNativeCertified === true}`);
  }

  // ── 1 · fetch the ORIGINAL PDF bytes (verified against the stored digest) ────
  const store = createTemplateTwinArtifactStore();
  const pdfBytes = await store.readUploadArtifact({
    practiceId,
    objectKey: prior.sourceObjectKey,
    expectedSha256: prior.sourceSha256,
  });
  console.log(`${L} fetched original PDF bytes=${pdfBytes.byteLength}`);

  // ── 2 · MINT a new note_template, COPYING the prior's structural fields ──────
  const newTemplateId = randomUUID();
  await prisma.noteTemplate.create({
    data: {
      id: newTemplateId,
      doctorId: userId,
      practiceId,
      name: prior.name,
      encounterType: prior.encounterType,
      sections: prior.sections as never,
      styleProfile: styleProfileForFreshDraft(priorSp) as never,
      specialtyBaseline: prior.specialtyBaseline,
      version: 1,
      status: 'draft',
      isSystemDefault: false,
      sourceObjectKey: prior.sourceObjectKey,
      sourceSha256: prior.sourceSha256,
    },
  });
  console.log(`${L} MINTED ${newTemplateId} (draft, structural copy of ${prior.id})`);

  // ── 3 · re-derive the twin under #324 + REGISTRY-3, attached to the mint ─────
  const draft = await createTemplateTwinDraft({
    source: new Uint8Array(pdfBytes),
    actor,
    attachToNoteTemplateId: newTemplateId,
  });
  console.log(`${L} DRAFT twin attached: fields=${draft.fieldCount} blocking=${draft.blockingUnsupportedCount} fallbackMappings=${draft.usedFallbackMappings}`);
  if (draft.blockingUnsupportedCount > 0) {
    throw new Error(`re-derivation has ${draft.blockingUnsupportedCount} blocking unsupported elements — cannot certify`);
  }

  // ── 5 · read + LOG the model's own proposal (evidence REGISTRY-3 maps) ───────
  const ws = await readTemplateTwinWorkspace({ noteTemplateId: newTemplateId, doctorId: userId, practiceId });
  if (!ws) throw new Error('workspace_not_found after draft');
  console.log(`${L} MODEL PROPOSAL under REGISTRY-3 (${ws.fields.length} fields):`);
  for (const { field, mapping } of ws.fields) {
    console.log(`    ${JSON.stringify(field.originalLabel)} -> ${mapping.clinicalConcept} [src=${mapping.sourceType} status=${mapping.status}]`);
  }

  // ── 6 · plan the auto-confirm; CONFIRM the record-derived headers (ruled) ────
  const plan = planAutoConfirm(ws);
  const declinedVisitMeta: string[] = [];
  const declinedOther: Array<{ label: string; reason: string }> = [];
  for (const d of plan.declined) {
    const f = ws.fields.find(({ field }) => (field.originalLabel ?? '(unnamed field)') === d.label);
    if (f && f.mapping.sourceType === 'visit_metadata') declinedVisitMeta.push(d.label);
    else declinedOther.push(d);
  }
  console.log(`${L} auto-confirm: confirmed=${plan.mappings.filter((m) => m.status === 'certified').length} declined_visitMetadata=${declinedVisitMeta.length} declined_other=${declinedOther.length}`);
  console.log(`${L}   record-derived headers to confirm as the ruled act: ${JSON.stringify(declinedVisitMeta)}`);
  if (declinedOther.length > 0) {
    // ⚠️ A non-record-derived decline means the model did NOT map a clinical field
    // under REGISTRY-3 — the acceptance signal. ABORT rather than paper over it.
    // In inspect mode the mint is rolled back first so a failed rehearsal leaves
    // no draft behind.
    if (inspectOnly) {
      await prisma.noteTemplate.delete({ where: { id: newTemplateId } });
      console.log(`${L} INSPECT rolled back the mint ${newTemplateId}`);
    }
    throw new Error(`REGISTRY-3 INCOMPLETE — clinical field(s) declined by the auto path: ${JSON.stringify(declinedOther)}`);
  }

  // ── INSPECT rehearsal ends here: roll back the mint, certify NOTHING ─────────
  if (inspectOnly) {
    await prisma.noteTemplate.delete({ where: { id: newTemplateId } }); // cascade: compiled version + fields + mappings
    console.log(`${L} INSPECT complete — proposal above; mint ${newTemplateId} rolled back. Nothing certified/activated/superseded.`);
    return;
  }

  // ── 4 · set up the PDF-native cert on the mint from the ORIGINAL PDF BYTES ────
  // ⚠️ NOT carryForwardPdfCertification: that re-keys the PRIOR canvas by LABEL
  // identity (no bytes) and REFUSES on any spec that does not re-anchor
  // ("anchors_missing") — which the owner's form hits, because the prior was itself
  // certified from bytes, not carried. `certifyPdfTemplate` is the AUTHORITY (it has
  // the bytes): it re-derives the header fields + anchors from the PDF, stores the
  // canvas, and sets pdfNativeCertified. S2-4 re-derives the actual fill anchors from
  // the twin at export, so the stored anchors need only be non-empty (the gate).
  const pdfCert = await certifyPdfTemplate({
    templateId: newTemplateId,
    pdfBytes: Buffer.from(pdfBytes),
    doctorId: userId,
  });
  console.log(`${L} pdf-native certify: anchors=${pdfCert.anchors.length} missing=${pdfCert.missing.length}`);
  if (pdfCert.anchors.length === 0) {
    throw new Error('pdf-native certify found NO anchors — the form is not a fillable flat PDF; refusing to certify a template whose export would silently fall back to styled');
  }

  // Confirm the visit_metadata headers by keeping their (deterministic, label-derived)
  // concept and marking status certified — the #247 human confirm, authorised here.
  const byFieldId = new Map(plan.mappings.map((m) => [m.fieldId, m] as const));
  const finalMappings: SemanticMapping[] = ws.fields.map(({ field, mapping }) => {
    const planned = byFieldId.get(mapping.fieldId) ?? mapping;
    if (planned.status === 'certified') return planned;
    // Still unconfirmed → a record-derived header. Confirm it (keep the concept).
    if (mapping.sourceType === 'visit_metadata' && mapping.clinicalConcept) {
      return { ...mapping, status: 'certified' } as unknown as SemanticMapping;
    }
    return planned;
  });
  const stillUnconfirmed = finalMappings.filter((m) => m.status !== 'certified');
  if (stillUnconfirmed.length > 0) {
    throw new Error(`refusing to certify: ${stillUnconfirmed.length} mapping(s) not confirmed`);
  }

  await updateTemplateTwinMappings({
    noteTemplateId: newTemplateId,
    actor,
    expectedMappingsSha256: ws.mappingsSha256,
    mappings: finalMappings,
  });
  console.log(`${L} mappings confirmed (${finalMappings.length} fields)`);

  // ── 7 · the REAL synthetic round-trip (live L3 + fill from THIS form) ────────
  const persisted = await readTemplateTwinWorkspace({ noteTemplateId: newTemplateId, doctorId: userId, practiceId });
  if (!persisted) throw new Error('reread_failed after update');
  await runTemplateTwinSyntheticTest({
    noteTemplateId: newTemplateId,
    actor,
    expectedMappingsSha256: persisted.mappingsSha256,
    deriveEncounter: () =>
      deriveVerificationEncounter(
        persisted.fields.map(({ field, mapping }) => ({
          originalLabel: field.originalLabel,
          clinicalConcept: mapping.clinicalConcept,
        })),
      ),
    encounterMode: 'dictation',
    extractEntities: extractTemplateTwinEntities,
    generateNote: createEphemeralVisitNoteGenerator({ specialty: persisted.template.encounterType ?? 'General' }),
  });
  console.log(`${L} synthetic round-trip PASSED`);

  // ── 8 · certify + activate (supersedes the prior active, kept) ───────────────
  const reread = await readTemplateTwinWorkspace({ noteTemplateId: newTemplateId, doctorId: userId, practiceId });
  if (!reread) throw new Error('reread_failed before certify');
  await certifyAndActivateTemplateTwin({
    noteTemplateId: newTemplateId,
    actor,
    expectedMappingsSha256: reread.mappingsSha256,
  });
  console.log(`${L} CERTIFIED + ACTIVATED ${newTemplateId}`);

  // ── 9 · verify the end state ─────────────────────────────────────────────────
  console.log(`${L} AFTER — practice templates:`);
  for (const t of await ownerTemplates(practiceId)) {
    const sp = (t.styleProfile ?? {}) as Record<string, unknown>;
    console.log(`    ${t.id} "${t.name}" status=${t.status} cert=${t.templateTwinCompiledVersion?.certificationStatus ?? 'none'} pdfNative=${sp.pdfNativeCertified === true}`);
  }
  const priorAfter = await prisma.noteTemplate.findUnique({
    where: { id: prior.id },
    select: { id: true, status: true },
  });
  console.log(`${L} PRIOR ${prior.id} now status=${priorAfter?.status} (must be 'inactive', kept)`);
  console.log(`${L} DONE newTemplateId=${newTemplateId}`);
}

main().catch((e) => {
  console.error(`${L} FAILED:`, e?.stack ?? e?.message ?? e);
  process.exit(1);
});
