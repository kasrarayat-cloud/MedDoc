// ============================================================================
// UPLOAD-AND-CERTIFIED · S2-4 — load the certified twin's fields + a visit's
// resolved values for the pdf-native fill (owner ruling #322). Server-only.
// ----------------------------------------------------------------------------
// The twin decides the values; this reads them. Two loaders:
//   • loadCertifiedTwinFields — the compiled twin's field list (id, label,
//     order), for anchor derivation. Used by BOTH the visit export and the
//     settings preview, so they place the same fields on the same page.
//   • loadVisitTwinResolutions — a visit's VERIFIED fill-manifest resolutions,
//     for the real export (kept separate so the caller can tell "no certified
//     twin" from "certified twin, no manifest").
//
// Both return null unless the template's compiled twin is CERTIFIED — S2-4's
// twin-driven fill fires only for a certified twin; an uncertified or non-twin
// template keeps the pre-S2-4 note-heading fill (backward-compatible).
//
// ⚠️ A SIGNED VISIT RESOLVES ITS MANIFEST BY POINTER, never by lookup — the same
// rule loadNativeTemplateDocxForVisit follows (ruling 2(b)): the signature froze
// `frozenFillManifestId`, and a manifest that landed afterwards is unreachable
// by construction. Tenancy is per-PRACTICE, not per-user (F5-f ruling 2).
// ============================================================================
import prisma from '@meddoc/db';

import { visitByIdScope, type PracticeId } from '@/lib/practice-scope';
import { FieldResolutionSchema, type FieldResolution } from '@/lib/template-twin/ir';
import { manifestMatchesDocument } from '@/lib/template-twin/note-identity';
import type { TwinAnchorField } from './twin-anchor-derivation';

/** The compiled twin's fields for a note template, or null when the template's
 *  compiled twin is not CERTIFIED. Ordered by displayOrder (reading order). */
export async function loadCertifiedTwinFields(
  noteTemplateId: string,
  practiceId: PracticeId,
): Promise<TwinAnchorField[] | null> {
  const compiled = await prisma.templateTwinCompiledVersion.findFirst({
    where: { noteTemplateId, practiceId, certificationStatus: 'CERTIFIED' },
    select: { id: true },
  });
  if (!compiled) return null;

  const defs = await prisma.templateTwinFieldDefinition.findMany({
    where: { compiledVersionId: compiled.id, practiceId },
    select: { fieldId: true, originalLabel: true, displayOrder: true },
    orderBy: { displayOrder: 'asc' },
  });
  if (defs.length === 0) return null;

  return defs.map((d) => ({
    fieldId: d.fieldId,
    label: d.originalLabel ?? '',
    displayOrder: d.displayOrder,
  }));
}

/** A visit's VERIFIED + FRESH twin resolutions, or null when the visit has no
 *  usable manifest (→ the caller falls back to the STYLED render, exactly as the
 *  DOCX export does — a certified-twin template never reverts to note-heading).
 *  Independent of the field list so the caller can distinguish "no certified
 *  twin" (loadCertifiedTwinFields === null) from "certified twin, no manifest". */
export async function loadVisitTwinResolutions(
  visitId: string,
  practiceId: PracticeId,
): Promise<FieldResolution[] | null> {
  // Signed → the frozen manifest by pointer; unsigned → the visit's verified
  // manifest. NULL on a signed visit that froze none: the answer is styled.
  // Practice-scoped through the sanctioned accessor (src/lib/practice-scope.ts),
  // which also asserts a non-empty practice — the same guard nativePdfExport uses.
  const visit = await prisma.transcribeVisit.findFirst({
    where: { ...visitByIdScope(visitId, practiceId), deletedAt: null },
    select: { status: true, frozenFillManifestId: true },
  });
  if (!visit) return null;
  const isSigned = visit.status === 'SIGNED';
  if (isSigned && !visit.frozenFillManifestId) return null;

  const manifestRow = await prisma.templateTwinFillManifest.findFirst({
    where: {
      visitId,
      ...(isSigned ? { id: visit.frozenFillManifestId! } : {}),
      visit: { practiceId, deletedAt: null },
      status: 'VERIFIED',
      roundTripVerified: true,
    },
    select: {
      fillManifest: true,
      noteSha256: true,
      overridesSha256: true,
      visit: { select: { soapFinal: true } },
    },
    orderBy: isSigned ? undefined : { createdAt: 'desc' },
  });
  if (!manifestRow?.fillManifest) return null;

  // ⚠️ FRESHNESS GOVERNS THE UNSIGNED RECORD; THE POINTER GOVERNS THE SIGNED ONE
  // (F24-S5, mirrored from loadNativeTemplateDocxForVisit). A VERIFIED manifest
  // stays VERIFIED after the doctor edits the note or a control override — so
  // for an UNSIGNED visit, serving those bytes could draw STALE clinical values
  // on the doctor's page. Re-derive freshness from the note + overrides here,
  // exactly as the DOCX export does, so the PDF and Word answer identically. A
  // signed visit resolved by pointer skips it (the signature froze the pair).
  if (!isSigned) {
    const currentOverrides = await prisma.templateTwinFieldOverride.findMany({
      where: { visitId, practiceId },
      select: { fieldId: true, selectedOptionOrdinal: true, overrideKind: true, insertedText: true },
    });
    const freshness = manifestMatchesDocument({
      manifestNoteSha256: manifestRow.noteSha256,
      manifestOverridesSha256: manifestRow.overridesSha256,
      soapFinal: manifestRow.visit?.soapFinal,
      currentOverrides,
    });
    if (!freshness.ok) return null; // note/overrides moved → styled fallback, not stale bytes
  }

  const rawFields = (manifestRow.fillManifest as { fields?: unknown }).fields;
  if (!Array.isArray(rawFields)) return null;

  // Parse each resolution defensively — the manifest was schema-written by the
  // twin, but a malformed entry must never draw onto the doctor's page. An
  // entry that fails validation is simply dropped (its region stays blank),
  // never coerced.
  const resolutions: FieldResolution[] = [];
  for (const raw of rawFields) {
    const parsed = FieldResolutionSchema.safeParse(raw);
    if (parsed.success) resolutions.push(parsed.data);
  }
  if (resolutions.length === 0) return null;

  return resolutions;
}
