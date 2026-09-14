// ============================================================================
// UPLOAD-AND-CERTIFIED · S2-4 — load the certified twin's fields + a visit's
// resolved values for the pdf-native fill (owner ruling #322). Server-only.
// ----------------------------------------------------------------------------
// The twin decides the values; this reads them. Two loaders:
//   • loadCertifiedTwinFields — the compiled twin's field list (id, label,
//     order), for anchor derivation. Used by BOTH the visit export and the
//     settings preview, so they place the same fields on the same page.
//   • loadCertifiedTwinExportData — the above PLUS the visit's VERIFIED fill
//     manifest resolutions, for the real export.
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

import { FieldResolutionSchema, type FieldResolution } from '@/lib/template-twin/ir';
import type { TwinAnchorField } from './twin-anchor-derivation';

/** The compiled twin's fields for a note template, or null when the template's
 *  compiled twin is not CERTIFIED. Ordered by displayOrder (reading order). */
export async function loadCertifiedTwinFields(
  noteTemplateId: string,
  practiceId: string,
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

export interface TwinExportData {
  fields: TwinAnchorField[];
  resolutions: FieldResolution[];
}

/** The certified twin's fields + a visit's VERIFIED resolutions, or null when
 *  the template's twin is not certified OR the visit has no verified manifest
 *  (→ the caller keeps the note-heading fill / styled fallback). */
export async function loadCertifiedTwinExportData(
  visitId: string,
  noteTemplateId: string,
  practiceId: string,
): Promise<TwinExportData | null> {
  const fields = await loadCertifiedTwinFields(noteTemplateId, practiceId);
  if (!fields) return null;

  // Signed → the frozen manifest by pointer; unsigned → the visit's verified
  // manifest. NULL on a signed visit that froze none: the answer is styled.
  const visit = await prisma.transcribeVisit.findFirst({
    where: { id: visitId, practiceId, deletedAt: null },
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
    select: { fillManifest: true },
    orderBy: isSigned ? undefined : { createdAt: 'desc' },
  });
  if (!manifestRow?.fillManifest) return null;

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

  return { fields, resolutions };
}
