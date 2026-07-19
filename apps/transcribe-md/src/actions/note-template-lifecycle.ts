'use server';

import { randomUUID } from 'node:crypto';

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
import { templateTwinRuntimeEnabled } from '@/lib/runtime-protocol';

export type SaveTemplateResult =
  | { ok: true; id: string; status: 'draft' | 'active'; flags: string[] }
  | { ok: false; error: string };

export type SimpleResult =
  | { ok: true; id?: string }
  | { ok: false; error: string };

function bridgeTemplateExclusion():
  | { templateKind: { not: 'template_twin_docx' } }
  | Record<string, never> {
  return !templateTwinRuntimeEnabled(process.env)
    ? { templateKind: { not: 'template_twin_docx' } }
    : {};
}

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
  } as unknown as Prisma.InputJsonValue;
  const flags = gate.flags;

  const { name, encounterType } = gate.template;
  const inputId = parsed.data.id ?? null;

  // Ownership pre-check (scoped) so we never create a version off another
  // doctor's row, and so we know the existing status/version.
  let existing: {
    id: string;
    status: string;
    version: number;
    // Nullable only during the online expand/backfill deployment window. The
    // final schema is NOT NULL; pre-existing rows safely self-root at their id.
    lineageId: string | null;
    templateKind: string;
  } | null = null;
  if (inputId) {
    existing = await prisma.noteTemplate.findFirst({
      where: { id: inputId, doctorId, ...bridgeTemplateExclusion() },
      select: {
        id: true,
        status: true,
        version: true,
        lineageId: true,
        templateKind: true,
      },
    });
    if (!existing) {
      return { ok: false, error: "That template doesn't exist or isn't yours to edit." };
    }
    if (existing.templateKind === 'template_twin_docx') {
      return {
        ok: false,
        error: 'Original Word templates must be revised through Template Twin certification.',
      };
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
          where: {
            doctorId,
            encounterType,
            status: 'active',
            ...bridgeTemplateExclusion(),
          },
          data: { status: 'inactive' },
        });
      }

      // 2. Write the target row.
      const status = activate ? 'active' : 'draft';
      if (existing && existing.status !== 'active') {
        // draft / inactive → update in place (not a live row)
        const updated = await tx.noteTemplate.update({
          where: { id: existing.id },
          data: {
            name,
            encounterType,
            sections: cleanSections,
            styleProfile,
            status,
            // Transition compatibility: touching a pre-expand generic row also
            // completes its deterministic self-root lineage in this bounded
            // single-row write.
            lineageId: existing.lineageId ?? existing.id,
          },
          select: { id: true },
        });
        return { id: updated.id, status };
      }
      // new, OR editing an active row → new version (history preserved)
      const lineageId = existing?.lineageId ?? existing?.id ?? randomUUID();
      if (existing && existing.lineageId === null) {
        // Parent and child must enter the same lineage. The cursor backfill uses
        // the identical self-root value, so this is race-safe and idempotent.
        // Raw SQL is intentional during the expand window: schema.prisma models
        // the final non-null shape, so the generated Prisma filter type cannot
        // express the transitional `lineageId IS NULL` predicate.
        await tx.$executeRaw`
          UPDATE "note_templates"
          SET "lineageId" = ${lineageId}
          WHERE "id" = ${existing.id} AND "lineageId" IS NULL
        `;
      }
      const created = await tx.noteTemplate.create({
        data: {
          doctorId,
          name,
          encounterType,
          sections: cleanSections,
          styleProfile,
          version: existing ? existing.version + 1 : 1,
          status,
          isSystemDefault: false,
          // Explicit in every new application write; the online migration's
          // insert trigger remains only as mixed-version defense in depth.
          lineageId,
          ...(existing ? { parentVersionId: existing.id } : {}),
        },
        select: { id: true },
      });
      return { id: created.id, status };
    });

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
    where: { id, doctorId, ...bridgeTemplateExclusion() },
    select: { id: true, encounterType: true, templateKind: true },
  });
  if (!row) return { ok: false, error: "That template doesn't exist or isn't yours." };
  if (row.templateKind === 'template_twin_docx') {
    return {
      ok: false,
      error: 'Template Twin activation requires a verified certification.',
    };
  }

  try {
    await prisma.$transaction(async (tx: Prisma.TransactionClient) => {
      // Deactivate the prior active for this slot FIRST (index-safe ordering),
      // excluding the target so re-activating an already-active row is a no-op.
      await tx.noteTemplate.updateMany({
        where: {
          doctorId,
          encounterType: row.encounterType,
          status: 'active',
          NOT: { id },
          ...bridgeTemplateExclusion(),
        },
        data: { status: 'inactive' },
      });
      await tx.noteTemplate.update({ where: { id }, data: { status: 'active' } });
    });
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
    where: { id, doctorId, ...bridgeTemplateExclusion() },
    select: {
      name: true,
      encounterType: true,
      sections: true,
      styleProfile: true,
      specialtyBaseline: true,
      templateKind: true,
    },
  });
  if (!row) return { ok: false, error: "That template doesn't exist or isn't yours." };
  if (row.templateKind === 'template_twin_docx') {
    return {
      ok: false,
      error: 'Create a new Template Twin version from the certification workspace.',
    };
  }

  const created = await prisma.noteTemplate.create({
    data: {
      doctorId,
      name: `${row.name} (copy)`.slice(0, 120),
      encounterType: row.encounterType,
      sections: row.sections as Prisma.InputJsonValue,
      styleProfile: (row.styleProfile ?? undefined) as Prisma.InputJsonValue | undefined,
      specialtyBaseline: row.specialtyBaseline,
      version: 1,
      status: 'draft',
      isSystemDefault: false,
      // A duplicate is a fresh lineage, not a version of the source row.
      lineageId: randomUUID(),
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
  const row = await prisma.noteTemplate.findFirst({
    where: { id, doctorId, ...bridgeTemplateExclusion() },
    select: { templateKind: true },
  });
  if (!row) return { ok: false, error: "That template doesn't exist or isn't yours." };
  if (row.templateKind === 'template_twin_docx') {
    return {
      ok: false,
      error: 'Template Twin versions are immutable; retire or supersede this version instead.',
    };
  }
  const res = await prisma.noteTemplate.deleteMany({
    where: { id, doctorId, ...bridgeTemplateExclusion() },
  });
  if (res.count === 0) return { ok: false, error: 'Could not delete the template just now.' };
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
    where: { id, doctorId, ...bridgeTemplateExclusion() },
    select: {
      id: true,
      name: true,
      encounterType: true,
      sections: true,
      styleProfile: true,
      templateKind: true,
    },
  });
  if (!row) return { ok: false, error: "That template doesn't exist or isn't yours." };
  if (row.templateKind === 'template_twin_docx') {
    return {
      ok: false,
      error: 'Open this version in the Template Twin certification workspace.',
    };
  }
  return { ok: true, template: rowToReviewModel(row) };
}
