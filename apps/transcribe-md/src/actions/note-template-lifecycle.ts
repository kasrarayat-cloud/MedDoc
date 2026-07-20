"use server";

import { randomUUID } from "node:crypto";

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

import { revalidatePath } from "next/cache";

import prisma from "@meddoc/db";
import { requireSession } from "@/lib/auth";
import { applyPhiGate } from "@/lib/note-template-parse/phi-gate";
import {
  claimCurrentLegacyNoteTemplateProviderActor,
  LegacyNoteTemplateProviderAuthorityError,
  type LegacyNoteTemplateProviderAuthorityClaim,
} from "@/lib/note-template-parse/parse-note-to-template";
import {
  hasLocallyUnsafeReviewedTemplateContent,
  REVIEWED_TEMPLATE_PRIVACY_REJECTION,
} from "@/lib/note-template-parse/reviewed-template-safety";
import {
  ReviewedTemplateSchema,
  normalizeReviewedTemplate,
  friendlyValidationError,
} from "@/lib/note-template-persist/reviewed-template";
import { rowToReviewModel } from "@/lib/note-template-persist/read";
import { canonicalSha256 } from "@/lib/template-twin/canonical";
import type { TemplateReviewModel } from "@/lib/note-template-persist/types";
import type { Prisma } from "@prisma/client";

export type SaveTemplateResult =
  | { ok: true; id: string; status: "draft" | "active"; flags: string[] }
  | { ok: false; error: string };

export type SimpleResult =
  | { ok: true; id?: string }
  | { ok: false; error: string };

const LEGACY_TEMPLATE_AUTHORITY_DENIAL =
  "Current physician access could not be confirmed. No template data was returned or changed.";

async function claimCurrentLegacyTemplateLifecycleActor(
  actorUserId: string,
): Promise<LegacyNoteTemplateProviderAuthorityClaim | null> {
  try {
    return await claimCurrentLegacyNoteTemplateProviderActor({ actorUserId });
  } catch (error) {
    if (error instanceof LegacyNoteTemplateProviderAuthorityError) return null;
    throw error;
  }
}

function currentLegacyTemplateAuthorityWhere(
  actor: LegacyNoteTemplateProviderAuthorityClaim,
): Prisma.NoteTemplateWhereInput {
  return {
    doctorId: actor.actorUserId,
    doctor: {
      is: {
        id: actor.actorUserId,
        practiceId: actor.practiceId,
        role: "DOCTOR",
        isActive: true,
        deactivatedAt: null,
        suspendedAt: null,
        softDeletedAt: null,
        products: { has: "TRANSCRIBE_MD" },
        practice: {
          is: { id: actor.practiceId, isActive: true },
        },
      },
    },
  };
}

/**
 * Canonical mutation lock order: active exact practice, then exact current
 * physician. Every template row lock/write follows these locks in the same
 * transaction, so suspension, transfer, product revocation, and practice
 * deactivation cannot race a final mutation.
 */
async function lockAndAssertCurrentLegacyTemplateActor(input: {
  tx: Prisma.TransactionClient;
  actor: LegacyNoteTemplateProviderAuthorityClaim;
}): Promise<void> {
  const practices = await input.tx.$queryRaw<Array<{ id: string }>>`
    SELECT practice."id"
    FROM "practices" practice
    WHERE practice."id" = ${input.actor.practiceId}
      AND practice."isActive" = TRUE
    FOR UPDATE
  `;
  if (practices.length !== 1 || practices[0]?.id !== input.actor.practiceId) {
    throw new LegacyNoteTemplateProviderAuthorityError();
  }

  const actors = await input.tx.$queryRaw<Array<{ id: string }>>`
    SELECT actor."id"
    FROM "users" actor
    WHERE actor."id" = ${input.actor.actorUserId}
      AND actor."practiceId" = ${input.actor.practiceId}
      AND actor."role" = 'DOCTOR'::"UserRole"
      AND actor."isActive" = TRUE
      AND actor."deactivatedAt" IS NULL
      AND actor."suspendedAt" IS NULL
      AND actor."softDeletedAt" IS NULL
      AND 'TRANSCRIBE_MD'::"Product" = ANY(actor."products")
    FOR UPDATE
  `;
  if (actors.length !== 1 || actors[0]?.id !== input.actor.actorUserId) {
    throw new LegacyNoteTemplateProviderAuthorityError();
  }
}

function bridgeTemplateExclusion(): {
  templateKind: { not: "template_twin_docx" };
  templateTwinCompiledVersion: { is: null };
} {
  // Generic note-template lifecycle writes never own Template Twin rows.
  // Runtime enablement changes availability, not mutation authority: only the
  // certified Twin lifecycle may activate/deactivate/retire those versions.
  return {
    templateKind: { not: "template_twin_docx" },
    templateTwinCompiledVersion: { is: null },
  };
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
  activate: boolean,
): Promise<SaveTemplateResult> {
  const session = await requireSession();
  const actor = await claimCurrentLegacyTemplateLifecycleActor(session.user.id);
  if (!actor) return { ok: false, error: LEGACY_TEMPLATE_AUTHORITY_DENIAL };
  const doctorId = actor.actorUserId;

  const parsed = ReviewedTemplateSchema.safeParse(rawInput);
  if (!parsed.success) {
    // Friendly, field-named message — never leak a raw Zod "Too big …".
    return { ok: false, error: friendlyValidationError(parsed.error) };
  }

  const { draft } = normalizeReviewedTemplate(parsed.data);

  // The legacy structured-template lifecycle owns blank structure only.
  // Apply the same deterministic local boundary as preview so a preview
  // privacy denial can never be bypassed by Save or Save & activate.
  if (hasLocallyUnsafeReviewedTemplateContent(draft)) {
    return { ok: false, error: REVIEWED_TEMPLATE_PRIVACY_REJECTION };
  }

  // Deterministic PHI re-scrub over the doctor's edits (regex layer; no LLM
  // call). Structural-field PHI → reject; default-text PHI → scrubbed + flagged.
  const gate = applyPhiGate(draft, [], [], false);
  if (gate.rejected) return { ok: false, error: gate.reason };

  const cleanSections = gate.template
    .sections as unknown as Prisma.InputJsonValue;
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
      where: {
        id: inputId,
        ...currentLegacyTemplateAuthorityWhere(actor),
        ...bridgeTemplateExclusion(),
      },
      select: {
        id: true,
        status: true,
        version: true,
        lineageId: true,
        templateKind: true,
      },
    });
    if (!existing) {
      return {
        ok: false,
        error: "That template doesn't exist or isn't yours to edit.",
      };
    }
    if (existing.templateKind === "template_twin_docx") {
      return {
        ok: false,
        error:
          "Original Word templates must be revised through Template Twin certification.",
      };
    }
  }

  try {
    const result = await prisma.$transaction(
      async (tx: Prisma.TransactionClient) => {
        await lockAndAssertCurrentLegacyTemplateActor({ tx, actor });

        // 1. Lock and reassert the exact source before any slot mutation. When
        //    the source itself is active, clearing the active slot changes its
        //    status; doing this lock afterward would compare against the stale
        //    admitted `active` status and make every active-row edit roll back.
        if (existing) {
          const locked = await tx.$queryRaw<Array<{ id: string }>>`
          SELECT template."id"
          FROM "note_templates" template
          WHERE template."id" = ${existing.id}
            AND template."doctorId" = ${doctorId}
            AND template."templateKind" <> 'template_twin_docx'
            AND NOT EXISTS (
              SELECT 1
              FROM "template_twin_compiled_versions" compiled
              WHERE compiled."noteTemplateId" = template."id"
            )
            AND template."status" = ${existing.status}
            AND template."version" = ${existing.version}
            AND template."lineageId" IS NOT DISTINCT FROM ${existing.lineageId}
          FOR UPDATE
        `;
          if (locked.length !== 1 || locked[0]?.id !== existing.id) {
            throw new Error("generic template authority changed");
          }
        }

        // 2. If activating, CLEAR the active slot first (deactivate prior active
        //    for this doctor+encounterType) so the partial-unique index holds
        //    when we set the new row active. This also supersedes the live row
        //    when an active template is being re-activated as a new version.
        if (activate) {
          await tx.noteTemplate.updateMany({
            where: {
              ...currentLegacyTemplateAuthorityWhere(actor),
              encounterType,
              status: "active",
              ...bridgeTemplateExclusion(),
            },
            data: { status: "inactive" },
          });
        }

        // 3. Write the target row.
        const status = activate ? "active" : "draft";
        if (existing && existing.status !== "active") {
          // draft / inactive → update in place (not a live row)
          const updated = await tx.noteTemplate.updateMany({
            where: {
              id: existing.id,
              ...currentLegacyTemplateAuthorityWhere(actor),
              status: existing.status,
              version: existing.version,
              ...bridgeTemplateExclusion(),
            },
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
          });
          if (updated.count !== 1) {
            throw new Error("generic template authority changed");
          }
          return { id: existing.id, status };
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
          WHERE "id" = ${existing.id}
            AND "doctorId" = ${doctorId}
            AND "templateKind" <> 'template_twin_docx'
            AND NOT EXISTS (
              SELECT 1
              FROM "template_twin_compiled_versions" compiled
              WHERE compiled."noteTemplateId" = "note_templates"."id"
            )
            AND "lineageId" IS NULL
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
      },
    );

    revalidatePath("/settings");
    return { ok: true, id: result.id, status: result.status, flags };
  } catch (error) {
    if (error instanceof LegacyNoteTemplateProviderAuthorityError) {
      return { ok: false, error: LEGACY_TEMPLATE_AUTHORITY_DENIAL };
    }
    // e.g. a concurrent-activation race tripping the partial-unique index.
    return {
      ok: false,
      error: "Could not save the template just now — please try again.",
    };
  }
}

/** Activate an existing (owned) template, superseding the prior active for its
 *  encounterType. Transactional + doctor-scoped. */
export async function activateNoteTemplateAction(
  id: string,
): Promise<SimpleResult> {
  const session = await requireSession();
  const actor = await claimCurrentLegacyTemplateLifecycleActor(session.user.id);
  if (!actor) return { ok: false, error: LEGACY_TEMPLATE_AUTHORITY_DENIAL };
  const doctorId = actor.actorUserId;

  const row = await prisma.noteTemplate.findFirst({
    where: {
      id,
      ...currentLegacyTemplateAuthorityWhere(actor),
      ...bridgeTemplateExclusion(),
    },
    select: {
      id: true,
      name: true,
      encounterType: true,
      sections: true,
      styleProfile: true,
      templateKind: true,
    },
  });
  if (!row)
    return { ok: false, error: "That template doesn't exist or isn't yours." };
  if (row.templateKind === "template_twin_docx") {
    return {
      ok: false,
      error: "Template Twin activation requires a verified certification.",
    };
  }
  if (
    hasLocallyUnsafeReviewedTemplateContent({
      name: row.name,
      encounterType: row.encounterType,
      sections: row.sections,
      styleProfile: row.styleProfile,
    })
  ) {
    return { ok: false, error: REVIEWED_TEMPLATE_PRIVACY_REJECTION };
  }

  try {
    const outcome = await prisma.$transaction(
      async (tx: Prisma.TransactionClient) => {
        await lockAndAssertCurrentLegacyTemplateActor({ tx, actor });
        const locked = await tx.$queryRaw<
          Array<{
            id: string;
            name: string;
            encounterType: string | null;
            sections: Prisma.JsonValue;
            styleProfile: Prisma.JsonValue | null;
          }>
        >`
          SELECT
            template."id", template."name", template."encounterType",
            template."sections", template."styleProfile"
          FROM "note_templates" template
          WHERE template."id" = ${id}
            AND template."doctorId" = ${doctorId}
            AND template."templateKind" <> 'template_twin_docx'
            AND NOT EXISTS (
              SELECT 1
              FROM "template_twin_compiled_versions" compiled
              WHERE compiled."noteTemplateId" = template."id"
            )
          FOR UPDATE
        `;
        const current = locked[0];
        if (locked.length !== 1 || !current || current.id !== id) {
          throw new Error("generic template authority changed");
        }
        if (
          hasLocallyUnsafeReviewedTemplateContent({
            name: current.name,
            encounterType: current.encounterType,
            sections: current.sections,
            styleProfile: current.styleProfile,
          })
        ) {
          return { privacyRejected: true as const };
        }

        // Deactivate the prior active for this slot FIRST (index-safe ordering),
        // excluding the target so re-activating an already-active row is a no-op.
        await tx.noteTemplate.updateMany({
          where: {
            ...currentLegacyTemplateAuthorityWhere(actor),
            encounterType: current.encounterType,
            status: "active",
            NOT: { id },
            ...bridgeTemplateExclusion(),
          },
          data: { status: "inactive" },
        });
        const activated = await tx.noteTemplate.updateMany({
          where: {
            id,
            ...currentLegacyTemplateAuthorityWhere(actor),
            ...bridgeTemplateExclusion(),
          },
          data: { status: "active" },
        });
        if (activated.count !== 1) {
          throw new Error("generic template authority changed");
        }
        return { privacyRejected: false as const };
      },
    );
    if (outcome.privacyRejected) {
      return { ok: false, error: REVIEWED_TEMPLATE_PRIVACY_REJECTION };
    }
    revalidatePath("/settings");
    return { ok: true, id };
  } catch (error) {
    if (error instanceof LegacyNoteTemplateProviderAuthorityError) {
      return { ok: false, error: LEGACY_TEMPLATE_AUTHORITY_DENIAL };
    }
    return {
      ok: false,
      error: "Could not activate the template — please try again.",
    };
  }
}

/** Duplicate an owned template as a fresh DRAFT (version 1, not active). */
export async function duplicateNoteTemplateAction(
  id: string,
): Promise<SimpleResult> {
  const session = await requireSession();
  const actor = await claimCurrentLegacyTemplateLifecycleActor(session.user.id);
  if (!actor) return { ok: false, error: LEGACY_TEMPLATE_AUTHORITY_DENIAL };
  const doctorId = actor.actorUserId;

  const row = await prisma.noteTemplate.findFirst({
    where: {
      id,
      ...currentLegacyTemplateAuthorityWhere(actor),
      ...bridgeTemplateExclusion(),
    },
    select: {
      id: true,
      name: true,
      encounterType: true,
      sections: true,
      styleProfile: true,
      specialtyBaseline: true,
      templateKind: true,
      version: true,
      updatedAt: true,
    },
  });
  if (!row)
    return { ok: false, error: "That template doesn't exist or isn't yours." };
  if (row.templateKind === "template_twin_docx") {
    return {
      ok: false,
      error:
        "Create a new Template Twin version from the certification workspace.",
    };
  }

  const sourceSha256 = canonicalSha256({
    id: row.id,
    name: row.name,
    encounterType: row.encounterType,
    sections: row.sections,
    styleProfile: row.styleProfile,
    specialtyBaseline: row.specialtyBaseline,
    version: row.version,
    updatedAtEpochMs: row.updatedAt.getTime(),
  });
  let created: { id: string };
  try {
    created = await prisma.$transaction(
      async (tx: Prisma.TransactionClient) => {
        await lockAndAssertCurrentLegacyTemplateActor({ tx, actor });
        const locked = await tx.$queryRaw<
          Array<{
            id: string;
            name: string;
            encounterType: string | null;
            sections: Prisma.JsonValue;
            styleProfile: Prisma.JsonValue | null;
            specialtyBaseline: string | null;
            version: number;
            updatedAt: Date;
          }>
        >`
          SELECT
            template."id", template."name", template."encounterType",
            template."sections", template."styleProfile",
            template."specialtyBaseline", template."version",
            template."updatedAt"
          FROM "note_templates" template
          WHERE template."id" = ${row.id}
            AND template."doctorId" = ${doctorId}
            AND template."templateKind" <> 'template_twin_docx'
            AND NOT EXISTS (
              SELECT 1
              FROM "template_twin_compiled_versions" compiled
              WHERE compiled."noteTemplateId" = template."id"
            )
            AND template."version" = ${row.version}
            AND template."updatedAt" = ${row.updatedAt}
          FOR UPDATE
        `;
        const current = locked[0];
        if (
          locked.length !== 1 ||
          !current ||
          canonicalSha256({
            id: current.id,
            name: current.name,
            encounterType: current.encounterType,
            sections: current.sections,
            styleProfile: current.styleProfile,
            specialtyBaseline: current.specialtyBaseline,
            version: current.version,
            updatedAtEpochMs: current.updatedAt.getTime(),
          }) !== sourceSha256
        ) {
          throw new Error("generic template authority changed");
        }
        return tx.noteTemplate.create({
          data: {
            doctorId,
            name: `${current.name} (copy)`.slice(0, 120),
            encounterType: current.encounterType,
            sections: current.sections as Prisma.InputJsonValue,
            styleProfile: (current.styleProfile ?? undefined) as
              | Prisma.InputJsonValue
              | undefined,
            specialtyBaseline: current.specialtyBaseline,
            version: 1,
            status: "draft",
            isSystemDefault: false,
            // A duplicate is a fresh lineage, not a version of the source row.
            lineageId: randomUUID(),
          },
          select: { id: true },
        });
      },
    );
  } catch (error) {
    if (error instanceof LegacyNoteTemplateProviderAuthorityError) {
      return { ok: false, error: LEGACY_TEMPLATE_AUTHORITY_DENIAL };
    }
    return { ok: false, error: "Could not duplicate the template just now." };
  }
  revalidatePath("/settings");
  return { ok: true, id: created.id };
}

/** Delete an owned template (any status). Scoped deleteMany — can never reach
 *  another doctor's row or the system default (doctorId IS NULL). */
export async function deleteNoteTemplateAction(
  id: string,
): Promise<SimpleResult> {
  const session = await requireSession();
  const actor = await claimCurrentLegacyTemplateLifecycleActor(session.user.id);
  if (!actor) return { ok: false, error: LEGACY_TEMPLATE_AUTHORITY_DENIAL };
  const row = await prisma.noteTemplate.findFirst({
    where: {
      id,
      ...currentLegacyTemplateAuthorityWhere(actor),
      ...bridgeTemplateExclusion(),
    },
    select: { templateKind: true },
  });
  if (!row)
    return { ok: false, error: "That template doesn't exist or isn't yours." };
  if (row.templateKind === "template_twin_docx") {
    return {
      ok: false,
      error:
        "Template Twin versions are immutable; retire or supersede this version instead.",
    };
  }
  let res: { count: number };
  try {
    res = await prisma.$transaction(async (tx: Prisma.TransactionClient) => {
      await lockAndAssertCurrentLegacyTemplateActor({ tx, actor });
      return tx.noteTemplate.deleteMany({
        where: {
          id,
          ...currentLegacyTemplateAuthorityWhere(actor),
          ...bridgeTemplateExclusion(),
        },
      });
    });
  } catch (error) {
    if (error instanceof LegacyNoteTemplateProviderAuthorityError) {
      return { ok: false, error: LEGACY_TEMPLATE_AUTHORITY_DENIAL };
    }
    return { ok: false, error: "Could not delete the template just now." };
  }
  if (res.count === 0)
    return { ok: false, error: "Could not delete the template just now." };
  revalidatePath("/settings");
  return { ok: true };
}

/** Load an owned template into the review-editor model (for the Edit flow). */
export async function getNoteTemplateForEditAction(
  id: string,
): Promise<
  { ok: true; template: TemplateReviewModel } | { ok: false; error: string }
> {
  const session = await requireSession();
  const actor = await claimCurrentLegacyTemplateLifecycleActor(session.user.id);
  if (!actor) return { ok: false, error: LEGACY_TEMPLATE_AUTHORITY_DENIAL };
  const row = await prisma.noteTemplate.findFirst({
    where: {
      id,
      ...currentLegacyTemplateAuthorityWhere(actor),
      ...bridgeTemplateExclusion(),
    },
    select: {
      id: true,
      name: true,
      encounterType: true,
      sections: true,
      styleProfile: true,
      templateKind: true,
    },
  });
  if (!row)
    return { ok: false, error: "That template doesn't exist or isn't yours." };
  if (row.templateKind === "template_twin_docx") {
    return {
      ok: false,
      error: "Open this version in the Template Twin certification workspace.",
    };
  }
  return { ok: true, template: rowToReviewModel(row) };
}
