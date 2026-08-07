'use server';

// ============================================================================
// Note-format customization — Phase 2b: template lifecycle server actions
// ----------------------------------------------------------------------------
// Save (draft) · activate (transactional supersede) · duplicate · delete ·
// get-for-edit. Every action is DOCTOR-SCOPED: it resolves doctorId from the
// session and every read/write is constrained to that doctor's own rows. A
// doctor can never see, edit, or activate another doctor's template, nor touch
// the system default (doctorId IS NULL).
//
// SAFETY POSTURE:
//   - The reviewed template is re-run through the DETERMINISTIC PHI gate
//     (regex layer, no LLM) on every save — defense-in-depth over doctor edits.
//   - styleProfile is persisted as { tense, tone, abbreviations, contextDefaults }
//     only; the immutable safety preamble/guardrails are NEVER stored on a
//     custom row (sourced from the canonical default at generation time).
//     contextDefaults is per-doctor context-field picks, not a safety field.
//   - Activation supersede is done in ONE transaction, deactivating the prior
//     active BEFORE setting the new one active, so the partial-unique index
//     (one active per doctor+encounterType) is satisfied at every step and
//     there is never a window with two-active or zero-active.
//   - Editing an ACTIVE template never mutates the live row — it creates a new
//     version (preserve history / audit trail).
// ============================================================================

import { revalidatePath } from 'next/cache';

import prisma from '@meddoc/db';
import { requireSession } from '@/lib/auth';
import { applyPhiGate } from '@/lib/note-template-parse/phi-gate';
import {
  ReviewedTemplateSchema,
  normalizeReviewedTemplate,
  friendlyValidationError,
} from '@/lib/note-template-persist/reviewed-template';
import { rowToReviewModel } from '@/lib/note-template-persist/read';
import type { TemplateReviewModel } from '@/lib/note-template-persist/types';
import type { Prisma } from '@prisma/client';

export type SaveTemplateResult =
  | { ok: true; id: string; status: 'draft' | 'active'; flags: string[] }
  | { ok: false; error: string };

export type SimpleResult =
  | { ok: true; id?: string }
  | { ok: false; error: string };

/**
 * Validate + persist a reviewed template. `activate` decides whether it goes
 * live (active, superseding the prior one) or is stored as a draft.
 *
 * Editing rules:
 *   - new (no id)                  → create version 1
 *   - editing a draft/inactive row → update in place
 *   - editing an ACTIVE row        → create a NEW version (live row untouched
 *                                     until/unless the new version is activated)
 */
export async function saveNoteTemplateAction(
  rawInput: unknown,
  activate: boolean
): Promise<SaveTemplateResult> {
  const session = await requireSession();
  const doctorId = session.user.id;

  const parsed = ReviewedTemplateSchema.safeParse(rawInput);
  if (!parsed.success) {
    // Friendly, field-named message — never leak a raw Zod "Too big …".
    return { ok: false, error: friendlyValidationError(parsed.error) };
  }

  const { draft } = normalizeReviewedTemplate(parsed.data);

  // Deterministic PHI re-scrub over the doctor's edits (regex layer; no LLM
  // call). Structural-field PHI → reject; default-text PHI → scrubbed + flagged.
  const gate = applyPhiGate(draft, [], [], false);
  if (gate.rejected) return { ok: false, error: gate.reason };

  const cleanSections = gate.template.sections as unknown as Prisma.InputJsonValue;
  const styleProfile = {
    tense: gate.template.styleProfile.tense,
    tone: gate.template.styleProfile.tone,
    abbreviations: gate.template.styleProfile.abbreviations,
    // feat/template-context-defaults: per-doctor context-field picks (never a
    // safety field; validated at generation against the template's own
    // options). Null when unset.
    contextDefaults: gate.template.styleProfile.contextDefaults ?? null,
    // feat/template-header-fields: labeled header/short fields (labels only) for
    // the styled export, and the form-only export preference. Export-only —
    // note-gen ignores them.
    headerFields: gate.template.styleProfile.headerFields ?? null,
    formOnlyExport: gate.template.styleProfile.formOnlyExport ?? false,
    // NOTE: this rebuild intentionally omits the certify-derived durable fields
    // (pdfNative* + formSignature). Editing an ACTIVE row creates a new version
    // whose cert is then re-keyed by carryForwardPdfCertification (which copies
    // formSignature forward) — so an active form-only template keeps its DD:/DT:
    // lines. A draft edit drops them until the next certify. Consistent with the
    // pre-existing pdfNative* drop-and-carry-forward behavior.
  } as unknown as Prisma.InputJsonValue;
  const flags = gate.flags;

  const { name, encounterType } = gate.template;
  const inputId = parsed.data.id ?? null;

  // Ownership pre-check (scoped) so we never create a version off another
  // doctor's row, and so we know the existing status/version.
  let existing: { id: string; status: string; version: number } | null = null;
  if (inputId) {
    existing = await prisma.noteTemplate.findFirst({
      where: { id: inputId, doctorId },
      select: { id: true, status: true, version: true },
    });
    if (!existing) {
      return { ok: false, error: "That template doesn't exist or isn't yours to edit." };
    }
  }

  try {
    const result = await prisma.$transaction(async (tx: Prisma.TransactionClient) => {
      // 1. If activating, CLEAR the active slot first (deactivate prior active
      //    for this doctor+encounterType) so the partial-unique index holds
      //    when we set the new row active. This also supersedes the live row
      //    when an active template is being re-activated as a new version.
      if (activate) {
        await tx.noteTemplate.updateMany({
          where: { doctorId, encounterType, status: 'active' },
          data: { status: 'inactive' },
        });
      }

      // 2. Write the target row.
      const status = activate ? 'active' : 'draft';
      if (existing && existing.status !== 'active') {
        // draft / inactive → update in place (not a live row)
        const updated = await tx.noteTemplate.update({
          where: { id: existing.id },
          data: { name, encounterType, sections: cleanSections, styleProfile, status },
          select: { id: true },
        });
        return { id: updated.id, status };
      }
      // new, OR editing an active row → new version (history preserved)
      const created = await tx.noteTemplate.create({
        data: {
          doctorId,
          // T7 — the biconditional `note_templates_practice_iff_doctor` pairs these
          // two. tsc cannot see it: the shared prisma client is `any`.
          practiceId: session.user.practiceId,
          name,
          encounterType,
          sections: cleanSections,
          styleProfile,
          version: existing ? existing.version + 1 : 1,
          status,
          isSystemDefault: false,
        },
        select: { id: true },
      });
      return { id: created.id, status };
    });

    // Durable PDF-native cert — a re-upload/re-activation of the SAME flat-PDF
    // form mints a new id; carry a prior cert forward so native export never
    // silently drops to styled. Fail-safe: wrapped so it can never FAIL the save
    // (the tx is already committed); on a hit it adds a MinIO GET + parse.
    if (activate && result.status === 'active') {
      try {
        const { carryForwardPdfCertification } = await import('@/lib/pdf-native/carry-forward');
        const cf = await carryForwardPdfCertification({
          doctorId,
          encounterType: encounterType ?? null,
          newTemplateId: result.id,
        });
        console.info(
          cf.carried
            ? `[note-template] carried PDF-native cert ${cf.fromTemplateId} → ${result.id} (${cf.anchors} anchors)`
            : `[note-template] no PDF-native cert carry-forward for ${result.id}: ${cf.reason}`
        );
      } catch (e) {
        console.error(
          '[note-template] cert carry-forward failed (non-fatal):',
          e instanceof Error ? e.message : e
        );
      }
    }

    revalidatePath('/settings');
    return { ok: true, id: result.id, status: result.status, flags };
  } catch {
    // e.g. a concurrent-activation race tripping the partial-unique index.
    return {
      ok: false,
      error: 'Could not save the template just now — please try again.',
    };
  }
}

/** Activate an existing (owned) template, superseding the prior active for its
 *  encounterType. Transactional + doctor-scoped. */
export async function activateNoteTemplateAction(id: string): Promise<SimpleResult> {
  const session = await requireSession();
  const doctorId = session.user.id;

  const row = await prisma.noteTemplate.findFirst({
    where: { id, doctorId },
    select: { id: true, encounterType: true },
  });
  if (!row) return { ok: false, error: "That template doesn't exist or isn't yours." };

  try {
    await prisma.$transaction(async (tx: Prisma.TransactionClient) => {
      // Deactivate the prior active for this slot FIRST (index-safe ordering),
      // excluding the target so re-activating an already-active row is a no-op.
      await tx.noteTemplate.updateMany({
        where: { doctorId, encounterType: row.encounterType, status: 'active', NOT: { id } },
        data: { status: 'inactive' },
      });
      await tx.noteTemplate.update({ where: { id }, data: { status: 'active' } });
    });

    // Durable PDF-native cert carry-forward (see saveNoteTemplateAction). Safe.
    try {
      const { carryForwardPdfCertification } = await import('@/lib/pdf-native/carry-forward');
      const cf = await carryForwardPdfCertification({
        doctorId,
        encounterType: row.encounterType ?? null,
        newTemplateId: id,
      });
      console.info(
        cf.carried
          ? `[note-template] carried PDF-native cert ${cf.fromTemplateId} → ${id} (${cf.anchors} anchors)`
          : `[note-template] no PDF-native cert carry-forward for ${id}: ${cf.reason}`
      );
    } catch (e) {
      console.error(
        '[note-template] cert carry-forward failed (non-fatal):',
        e instanceof Error ? e.message : e
      );
    }

    revalidatePath('/settings');
    return { ok: true, id };
  } catch {
    return { ok: false, error: 'Could not activate the template — please try again.' };
  }
}

/** Duplicate an owned template as a fresh DRAFT (version 1, not active). */
export async function duplicateNoteTemplateAction(id: string): Promise<SimpleResult> {
  const session = await requireSession();
  const doctorId = session.user.id;

  const row = await prisma.noteTemplate.findFirst({
    where: { id, doctorId },
    select: { name: true, encounterType: true, sections: true, styleProfile: true, specialtyBaseline: true },
  });
  if (!row) return { ok: false, error: "That template doesn't exist or isn't yours." };

  const created = await prisma.noteTemplate.create({
    data: {
      doctorId,
      // T7 — the biconditional `note_templates_practice_iff_doctor` pairs these
      // two. tsc cannot see it: the shared prisma client is `any`.
      practiceId: session.user.practiceId,
      name: `${row.name} (copy)`.slice(0, 120),
      encounterType: row.encounterType,
      sections: row.sections as Prisma.InputJsonValue,
      styleProfile: (row.styleProfile ?? undefined) as Prisma.InputJsonValue | undefined,
      specialtyBaseline: row.specialtyBaseline,
      version: 1,
      status: 'draft',
      isSystemDefault: false,
    },
    select: { id: true },
  });
  revalidatePath('/settings');
  return { ok: true, id: created.id };
}

/** Delete an owned template (any status). Scoped deleteMany — can never reach
 *  another doctor's row or the system default (doctorId IS NULL). */
export async function deleteNoteTemplateAction(id: string): Promise<SimpleResult> {
  const session = await requireSession();
  const doctorId = session.user.id;
  const res = await prisma.noteTemplate.deleteMany({ where: { id, doctorId } });
  if (res.count === 0) return { ok: false, error: "That template doesn't exist or isn't yours." };
  revalidatePath('/settings');
  return { ok: true };
}

/** Load an owned template into the review-editor model (for the Edit flow). */
export async function getNoteTemplateForEditAction(
  id: string
): Promise<{ ok: true; template: TemplateReviewModel } | { ok: false; error: string }> {
  const session = await requireSession();
  const doctorId = session.user.id;
  const row = await prisma.noteTemplate.findFirst({
    where: { id, doctorId },
    select: { id: true, name: true, encounterType: true, sections: true, styleProfile: true },
  });
  if (!row) return { ok: false, error: "That template doesn't exist or isn't yours." };
  return { ok: true, template: rowToReviewModel(row) };
}
