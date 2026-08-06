// ============================================================================
// Durable PDF-native certification — carry a cert forward across template-id
// rotation (feat/pdf-native-durable-cert). Server-only. Deterministic; PHI-safe.
//
// Root cause it cures: editing/re-uploading an ACTIVE note format mints a NEW
// template row id (note-template-lifecycle.ts) and flips the old to `inactive`.
// The PDF-native cert (canvas + anchors, keyed to the OLD id) is then orphaned →
// the export silently falls back to the styled generator. A doctor re-uploading
// the SAME form must never lose native export.
//
// The cure: when a template becomes active, look for a prior CERTIFIED template
// for the same (doctorId, encounterType) whose STRUCTURE SIGNATURE matches. If
// found and the new template's labels still fully anchor against that prior
// canvas, re-key the cert to the new id automatically (copy the canvas, re-extract
// anchors under the NEW template's keys, copy the signatures). If the structure
// changed materially — a label added/removed/renamed so it no longer anchors —
// mark the new template "pending preview": it stays uncertified (styled fallback)
// until the doctor re-runs the one-time preview/certify against the new form.
//
// SCOPE / ASSUMPTION: the save/activate flow parses labels but does NOT retain the
// re-uploaded PDF bytes, so this path has no NEW canvas to hash — it keys on LABEL
// identity (structureHash) and reuses the prior canvas. That is exactly right for
// the proven root cause (re-activation / rename / text-only edit mints a new id
// while the underlying form is unchanged). A genuinely DIFFERENT form that keeps
// every label byte-for-byte (e.g. new letterhead, same fields) is the one case
// this can't detect from labels alone; the certify/preview path (which DOES have
// the bytes + records pdfNativeCanvasHash, verified at export) is the authority
// there. Follow-up: thread the raw PDF through save to hash the new canvas here.
// ============================================================================
import prisma from '@meddoc/db';
import { getDocumentProxy } from 'unpdf';

import { extractPdfAnchors } from './anchors';
import { anchorSpecsFor } from './certify';
import { getTemplateCanvas, putTemplateCanvas } from './store';
import { templateStructureHash } from './hash';
import type { PdfFillAnchor } from './fill-engine';
import type {
  NoteTemplateSection,
  NoteTemplateHeaderField,
} from '@/worker/note-templates/system-default-template';

export type CarryForwardResult =
  | { carried: true; fromTemplateId: string; anchors: number }
  | {
      carried: false;
      reason:
        | 'already_certified'
        | 'no_template'
        | 'no_prior_cert'
        | 'structure_changed'
        | 'anchors_missing'
        | 'no_canvas';
    };

const sp = (v: unknown): Record<string, unknown> => (v ?? {}) as Record<string, unknown>;

async function markPendingPreview(
  templateId: string,
  styleProfile: Record<string, unknown>
): Promise<void> {
  await prisma.noteTemplate.update({
    where: { id: templateId },
    data: { styleProfile: { ...styleProfile, pdfNativePendingPreview: true } as never },
  });
}

/**
 * Try to carry a prior PDF-native cert forward onto `newTemplateId`. Idempotent:
 * a no-op when the template is already certified or when there is no prior cert
 * to inherit (a net-new PDF template certifies through the normal certify path).
 */
export async function carryForwardPdfCertification(input: {
  doctorId: string;
  encounterType: string | null;
  newTemplateId: string;
}): Promise<CarryForwardResult> {
  // ⚠️ ITS OWN PREDICATE, not the caller's scope inherited by habit. Callers
  // pass a template they just created or already verified — so `doctorId` here
  // is a no-op on every real path and a refusal on the one that matters. T5's
  // rule: a read does not borrow the authorisation of the read above it.
  const row = await prisma.noteTemplate.findFirst({
    where: { id: input.newTemplateId, doctorId: input.doctorId },
    select: { sections: true, styleProfile: true },
  });
  if (!row) return { carried: false, reason: 'no_template' };
  const styleProfile = sp(row.styleProfile);
  if (styleProfile.pdfNativeCertified === true) {
    return { carried: false, reason: 'already_certified' };
  }

  const sections = (row.sections as unknown as NoteTemplateSection[]) ?? [];
  const headerFields = (styleProfile.headerFields as NoteTemplateHeaderField[]) ?? [];
  const newStructure = templateStructureHash(sections, headerFields);

  // Prior CERTIFIED templates for the same slot, newest lineage first.
  const priors = await prisma.noteTemplate.findMany({
    where: {
      doctorId: input.doctorId,
      encounterType: input.encounterType,
      NOT: { id: input.newTemplateId },
    },
    select: { id: true, styleProfile: true },
    orderBy: [{ version: 'desc' }, { createdAt: 'desc' }],
  });
  type PriorRow = { id: string; styleProfile: unknown };
  const certifiedPriors = (priors as PriorRow[]).filter(
    (p) => sp(p.styleProfile).pdfNativeCertified === true
  );
  if (certifiedPriors.length === 0) return { carried: false, reason: 'no_prior_cert' };

  // Same form ⇒ same structure signature.
  const prior = certifiedPriors.find(
    (p) => sp(p.styleProfile).pdfNativeStructureHash === newStructure
  );
  if (!prior) {
    await markPendingPreview(input.newTemplateId, styleProfile);
    return { carried: false, reason: 'structure_changed' };
  }

  const canvas = await getTemplateCanvas(prior.id);
  if (!canvas) {
    await markPendingPreview(input.newTemplateId, styleProfile);
    return { carried: false, reason: 'no_canvas' };
  }

  // Re-extract anchors under the NEW template's keys against the prior canvas.
  // getDocumentProxy detaches its input buffer → give it its own copy.
  const specs = anchorSpecsFor(sections, headerFields);
  const anchors: PdfFillAnchor[] = await extractPdfAnchors(
    (await getDocumentProxy(new Uint8Array(canvas).slice())) as never,
    specs
  );
  const anchored = new Set(anchors.map((a) => a.key));
  const missing = specs.filter((s) => !anchored.has(s.key));
  if (missing.length > 0) {
    await markPendingPreview(input.newTemplateId, styleProfile);
    return { carried: false, reason: 'anchors_missing' };
  }

  const priorSp = sp(prior.styleProfile);
  await putTemplateCanvas(input.newTemplateId, canvas);
  await prisma.noteTemplate.update({
    where: { id: input.newTemplateId },
    data: {
      styleProfile: {
        ...styleProfile,
        pdfNativeAnchors: anchors as unknown,
        pdfNativeCertified: true,
        pdfNativeCanvasHash: priorSp.pdfNativeCanvasHash ?? null,
        pdfNativeStructureHash: newStructure,
        pdfNativePendingPreview: false,
        pdfNativeCarriedFrom: prior.id,
        // Carry the form's signature style forward too (form-only exports).
        ...(priorSp.formSignature ? { formSignature: priorSp.formSignature } : {}),
      } as never,
    },
  });
  return { carried: true, fromTemplateId: prior.id, anchors: anchors.length };
}
