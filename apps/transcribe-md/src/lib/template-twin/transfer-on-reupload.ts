// ============================================================================
// UPLOAD-AND-CERTIFIED · S3 — TRANSFER-BY-IDENTITY ON RE-UPLOAD.
// ----------------------------------------------------------------------------
// When a doctor re-uploads a form for a slot (doctorId, encounterType) that
// ALREADY has a certified twin, the prior certified dispositions carry across to
// the new draft BY FIELD IDENTITY — `fieldId` (survives a byte-identical
// re-upload) or `w:tag` (survives an edit/rename), the #274 primitive — so the
// doctor is not re-asked for the rows a machine can pair to an already-approved
// one. The remainder (unmatched rows) go through the ordinary auto-confirm class
// rules at certification time.
//
// ⚠️ IT COMPOSES THE #274 PRIMITIVES, IT DOES NOT REINVENT THEM. `planTransfer`
// (the pure fieldId|tag bijection matcher) and `applyCertifiedTransfer` (the
// idempotent writer) are the ruled engine; `readCertified` is the ONE
// tenant-checked read. This module only resolves the prior version and composes
// them onto the just-minted draft.
//
// ⚠️ visit_metadata IS NEVER TRANSFERRED-AS-CERTIFIED — RULING #247. A control
// that prints a value from the patient record (a name, a DOB) requires a human
// to have seen THIS form's control; a machine identity-match is not that human
// act. So record-derived / visit_metadata rows are dropped from the transfer and
// reproposed, which lands them in the doctor's confirm list every time — exactly
// "confirm ... any record-derived or visit_metadata row". Clinical (extraction /
// manual) dispositions transfer; identity dispositions do not.
//
// ⚠️ FAIL-SAFE. A transfer failure must NEVER fail the upload: the twin already
// compiled and its mappings were freshly proposed, so the worst case is the
// pre-S3 behaviour — the doctor re-confirms. The caller wraps this and continues.
// ============================================================================
import { prisma } from '@meddoc/db';

import { applyCertifiedTransfer, readCertified } from './ingest';
import { planReuploadTransfer } from './ingest-plan';
import type { TemplateDocIR } from './ir';

export interface TransferOnReuploadInput {
  /** The just-minted draft (attached to the new NoteTemplate). */
  newNoteTemplateId: string;
  doctorId: string;
  encounterType: string | null;
  practiceId: string;
}

export interface TransferOnReuploadResult {
  /** The prior certified compiled version the dispositions came from. */
  fromCompiledVersionId: string;
  transferred: number;
  reproposed: number;
}

/**
 * Resolve the newest OTHER compiled version for this slot whose twin is
 * CERTIFIED — the source of the transfer. Tenant-scoped by construction (the
 * doctorId + practiceId filter), newest lineage first, never the new draft
 * itself. Returns null when the slot has no prior certified twin (a first
 * upload, or only PDF-native certs).
 */
export async function resolvePriorCertifiedTwinVersion(input: {
  doctorId: string;
  encounterType: string | null;
  practiceId: string;
  excludeNoteTemplateId: string;
}): Promise<{ compiledVersionId: string; noteTemplateId: string } | null> {
  const priors = await prisma.noteTemplate.findMany({
    where: {
      practiceId: input.practiceId,
      doctorId: input.doctorId,
      encounterType: input.encounterType,
      NOT: { id: input.excludeNoteTemplateId },
    },
    select: {
      id: true,
      templateTwinCompiledVersion: {
        select: { id: true, certificationStatus: true },
      },
    },
    orderBy: [{ version: 'desc' }, { createdAt: 'desc' }],
  });
  for (const p of priors) {
    const cv = p.templateTwinCompiledVersion;
    if (cv && cv.certificationStatus === 'CERTIFIED') {
      return { compiledVersionId: cv.id, noteTemplateId: p.id };
    }
  }
  return null;
}

/** Read the just-minted draft's compiled IR — the transfer TARGET. */
async function readTargetIr(newNoteTemplateId: string, practiceId: string): Promise<TemplateDocIR | null> {
  const row = await prisma.templateTwinCompiledVersion.findUnique({
    where: { noteTemplateId: newNoteTemplateId },
    select: { practiceId: true, compiledDocumentIr: true },
  });
  if (!row || row.practiceId !== practiceId) return null;
  return row.compiledDocumentIr as unknown as TemplateDocIR;
}

/**
 * Carry a slot's prior certified clinical dispositions onto the just-minted
 * draft by fieldId|tag identity. Returns null when there is no prior certified
 * twin (nothing to transfer). Throws only on a genuine invariant break in the
 * apply step; the caller treats ANY failure as "no transfer" and proceeds.
 */
export async function transferCertifiedDispositionsOnReupload(
  input: TransferOnReuploadInput,
): Promise<TransferOnReuploadResult | null> {
  const prior = await resolvePriorCertifiedTwinVersion({
    doctorId: input.doctorId,
    encounterType: input.encounterType,
    practiceId: input.practiceId,
    excludeNoteTemplateId: input.newNoteTemplateId,
  });
  if (!prior) return null;

  const target = await readTargetIr(input.newNoteTemplateId, input.practiceId);
  if (!target || target.fields.length === 0) return null;

  // The ONE tenant-checked read; the pure planner drops record-derived rows
  // (#247) and matches the clinical remainder by fieldId|tag (#274).
  const source = await readCertified(prior.compiledVersionId, input.practiceId, null);
  if (source.certified.size === 0) return null;

  const plan = planReuploadTransfer({
    target,
    sourceIr: source.ir,
    certified: source.certified,
  });
  const transferred = await applyCertifiedTransfer({
    noteTemplateId: input.newNoteTemplateId,
    practiceId: input.practiceId,
    plan,
  });

  return {
    fromCompiledVersionId: prior.compiledVersionId,
    transferred,
    reproposed: plan.reproposed.length,
  };
}
