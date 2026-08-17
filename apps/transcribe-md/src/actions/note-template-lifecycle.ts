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
import { isTenantOwnedArtifactKey } from '@/lib/template-twin/storage';
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
  let existing: {
    id: string;
    status: string;
    version: number;
    sourceObjectKey: string | null;
    sourceSha256: string | null;
  } | null = null;
  if (inputId) {
    existing = await prisma.noteTemplate.findFirst({
      where: { id: inputId, doctorId },
      // ⚠️ THE SOURCE REF IS SELECTED SERVER-SIDE, AND DELIBERATELY NOT ROUND-
      // TRIPPED THROUGH THE CLIENT. `getNoteTemplateForEditAction` still does
      // NOT return it, on purpose: sending a storage key to the browser so it
      // can hand it back would widen the untrusted surface for no benefit, when
      // the server already has the row. An edit preserves the ref from HERE.
      select: {
        id: true,
        status: true,
        version: true,
        sourceObjectKey: true,
        sourceSha256: true,
      },
    });
    if (!existing) {
      return { ok: false, error: "That template doesn't exist or isn't yours to edit." };
    }
  }

  // ── THE SOURCE REF, RESOLVED AND VALIDATED BEFORE ANY WRITE ──────────────
  //
  // ⚠️ IT IS VALIDATED HERE, ABOVE THE `try`, BECAUSE THE `catch` BELOW IS BARE.
  // Every throw inside that block becomes "Could not save the template just now
  // — please try again", which is indistinguishable from a transient database
  // error for the doctor AND for whoever debugs it. A refusal to trust a
  // storage key is a SECURITY decision and must say so in its own words.
  //
  // ⚠️ AN EDIT PRESERVES THE EXISTING REF AND IGNORES THE CLIENT'S.
  // The governing rule: an edit must never silently destroy or fabricate the
  // source ref. Update-in-place preserves it because Prisma leaves unnamed
  // fields alone — but a version bump CREATES A NEW ROW, and a new row with no
  // source columns is exactly the silent destruction: the doctor edits a
  // section, a version is minted, and the only pointer to their letterhead is
  // gone. So the prior row's ref is carried forward explicitly, from the server,
  // and the client cannot influence it on an edit.
  //
  // It is ORIGIN provenance, not a claim the current sections still match the
  // file byte-for-byte. The doctor edited the parsed text; the file it was
  // parsed from is unchanged.
  let sourceRef: { objectKey: string; sha256: string } | null = null;
  // ⚠️ NEW UPLOAD, not merely 'has a source'. A version bump CARRIES the ref
  // forward (see below), so keying compile-on-upload off `sourceRef` alone
  // would re-compile the same bytes on every subsequent edit — a fresh twin
  // lineage per keystroke-save, none of them asked for. The twin is compiled
  // once, for the request that actually brought the file.
  let isNewUpload = false;
  if (existing) {
    sourceRef =
      existing.sourceObjectKey && existing.sourceSha256
        ? { objectKey: existing.sourceObjectKey, sha256: existing.sourceSha256 }
        : null;
  } else if (parsed.data.source) {
    const claimed = parsed.data.source;
    // ⚠️ THE KEY IS CLIENT-SUPPLIED. Without this, a doctor who edited the
    // payload could point their template at ANOTHER PRACTICE'S file, and the
    // twin/native-export path would later read it.
    if (
      !isTenantOwnedArtifactKey({
        objectKey: claimed.objectKey,
        practiceId: session.user.practiceId,
        kind: 'upload',
      })
    ) {
      return {
        ok: false,
        error:
          'That upload reference is not valid for your practice. Re-upload the ' +
          'file and try again.',
      };
    }
    sourceRef = { objectKey: claimed.objectKey, sha256: claimed.sha256 };
    isNewUpload = true;
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
      // Annotated, not inferred: a bare `const status = …` has a WIDENING
      // literal type, so `{ …, status }` below infers the property as plain
      // `string` and the action's declared `status: 'draft' | 'active'` no
      // longer accepts it. The annotation pins the union; the runtime value is
      // unchanged.
      const status: 'draft' | 'active' = activate ? 'active' : 'draft';
      if (existing && existing.status !== 'active') {
        // draft / inactive → update in place (not a live row)
        // ⚠️ `sourceObjectKey` / `sourceSha256` ARE ABSENT FROM `data` ON
        // PURPOSE, AND THAT IS PRESERVATION RATHER THAN OVERSIGHT. Prisma
        // leaves unnamed fields untouched, so an in-place edit keeps the ref.
        // Naming them here with `sourceRef` would be equivalent today and would
        // become a silent NULLing the moment somebody spread a partial object
        // into it — the omission is the safer shape, so it is documented as a
        // decision instead of read as a gap.
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
          // Carried forward on a version bump, set once on a new template, and
          // NULL when there is no file — never invented. See the block above.
          sourceObjectKey: sourceRef?.objectKey ?? null,
          sourceSha256: sourceRef?.sha256 ?? null,
        },
        select: { id: true },
      });
      return { id: created.id, status };
    });

    // ── RC-2 (#106(b)) — COMPILE ON UPLOAD. THE DOOR. ─────────────────────
    //
    // ⚠️ THIS IS THE WHOLE ITEM. The twin compiler has existed and worked for
    // months; its ONLY caller was `template-twin-certify.ts`, reached from
    // `NativeTemplateManager`, which renders **null** in production because
    // `NEXT_PUBLIC_SETTINGS_SIMPLE_ROW=true`. So prod holds zero compiled
    // versions — not because the gate refused, but because nothing could knock.
    // AGENTS.md records the symptom ("there is therefore no door in"); this is
    // the door.
    //
    // It ATTACHES to the template just written rather than minting one, so the
    // doctor ends up with their template, not their template and a shadow.
    //
    // ⚠️ IT CAN NEVER FAIL THE SAVE. Same contract as the PDF carry-forward
    // below: the transaction is already committed, the doctor's note format is
    // already theirs, and the twin is a PARKED capability. A compile failure
    // must cost a log line, never the doctor's upload. But it is NOT
    // fire-and-forget — it is awaited and its outcome recorded, because a side
    // effect nothing reads back is a comment (AGENTS.md, the fire-and-forget
    // rule), and `attemptedTwinCompile` is what the reachability test asserts.
    let twinCompile: 'skipped' | 'compiled' | 'failed' = 'skipped';
    if (isNewUpload && sourceRef) {
      try {
        const [{ createTemplateTwinDraft }, { createTemplateTwinArtifactStore }] =
          await Promise.all([
            import('@/lib/template-twin/create-draft'),
            import('@/lib/template-twin/storage'),
          ]);
        const store = createTemplateTwinArtifactStore();
        // ⚠️ THE DIGEST IS REQUIRED BY THE READ, AND THAT IS THE POINT OF
        // HAVING STORED IT. A key alone cannot prove the object still holds
        // what was uploaded; `readUploadArtifact` verifies against this and
        // refuses a mismatch, so the twin can never be compiled from bytes
        // that are not the doctor's file.
        const bytes = await store.readUploadArtifact({
          objectKey: sourceRef.objectKey,
          practiceId: session.user.practiceId,
          expectedSha256: sourceRef.sha256,
        });
        const compiled = await createTemplateTwinDraft({
          source: new Uint8Array(bytes),
          actor: {
            userId: doctorId,
            userEmail: session.user.email,
            practiceId: session.user.practiceId,
          },
          attachToNoteTemplateId: result.id,
        });
        twinCompile = 'compiled';

        // ── RULING #124 — AUTO-CERTIFY. ──────────────────────────────────
        //
        // The doctor's job is upload then run visits. When the twin compiles
        // with ZERO blocking elements the model's proposals are confirmed and
        // the template certifies itself — no sitting, no eighty clicks.
        //
        // ⚠️ ENQUEUED, NEVER AWAITED. Certification runs a live model
        // generation for its round-trip proof; awaiting it here would make an
        // upload hang on a generation, and a slow model would read to the
        // doctor as a broken upload. The row shows "Preparing your format…"
        // until the worker finishes.
        //
        // ⚠️ GATED ON blockingUnsupportedCount === 0 — the ruling's own
        // condition. A template with blocking elements cannot be reproduced
        // faithfully, so it must NOT auto-certify; it stays in needs-review
        // where the doctor is told why.
        //
        // ⚠️ AND FAIL-SAFE, like the compile above it. An enqueue failure must
        // never fail the upload: the template is saved and the twin compiled,
        // so the worst case is the pre-#124 behaviour — a template awaiting
        // manual confirmation, which the manual screen still serves.
        if (compiled.blockingUnsupportedCount === 0) {
          try {
            const { enqueueAutoCertifyTwin } = await import('@/lib/queue');
            await enqueueAutoCertifyTwin({
              noteTemplateId: result.id,
              userId: doctorId,
              userEmail: session.user.email,
              practiceId: session.user.practiceId,
            });
            console.info(
              `[template-twin:auto-certify] template=${result.id} ENQUEUED ` +
                `(fields=${compiled.fieldCount}, blocking=0)`,
            );
          } catch (enqueueError) {
            console.warn(
              `[template-twin:auto-certify] template=${result.id} enqueue FAILED — ` +
                'the template is saved and compiled; it awaits manual confirmation: ' +
                `${enqueueError instanceof Error ? enqueueError.message : String(enqueueError)}`,
            );
          }
        } else {
          console.info(
            `[template-twin:auto-certify] template=${result.id} SKIPPED ` +
              `(blocking=${compiled.blockingUnsupportedCount})`,
          );
        }
        console.info(
          `[template-twin:compile-on-upload] template=${result.id} ` +
            `fields=${compiled.fieldCount} blocking=${compiled.blockingUnsupportedCount} ` +
            `fallbackMappings=${compiled.usedFallbackMappings}`,
        );
      } catch (error) {
        // Loud, and non-fatal. The `.docx` itself is already kept (RC-2 part 1),
        // so a failed compile loses nothing that was not already recoverable —
        // which is precisely why part 1 had to land before this.
        twinCompile = 'failed';
        console.warn(
          `[template-twin:compile-on-upload] template=${result.id} FAILED — ` +
            'the upload is saved and the source .docx is kept; the twin was not ' +
            `compiled: ${error instanceof Error ? error.message : String(error)}`,
        );
      }
    }

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
    select: {
      name: true,
      encounterType: true,
      sections: true,
      styleProfile: true,
      specialtyBaseline: true,
      sourceObjectKey: true,
      sourceSha256: true,
    },
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
      // ── RC-2 (#106(b)) — THE DUPLICATE CARRIES THE SAME SOURCE REF ────────
      //
      // ⚠️ SHARED ORIGIN: TWO ROWS, ONE FILE. The choice is between recording
      // the provenance that is TRUE and recording none, and a duplicate's
      // origin genuinely IS the file the original was parsed from — the doctor
      // copied a template to diverge from it, they did not acquire a new
      // document. Writing NULL here would DESTROY provenance the copy has
      // legitimately earned; minting anything else would FABRICATE one it has
      // not. Neither is available under the governing rule.
      //
      // Safe because the object is IMMUTABLE and CONTENT-ADDRESSED — its sha is
      // in its own key — so two rows referencing it cannot disagree about what
      // it contains, and nothing is double-stored.
      //
      // ⚠️ CONSEQUENCE THE REAPER MUST HONOUR, STATED HERE BECAUSE THIS IS
      // WHERE THE SECOND REFERENCE IS CREATED: an unreferenced-object sweep
      // must COUNT references, never assume one. Deleting the object when the
      // first row goes would silently strip the letterhead from the copy.
      sourceObjectKey: row.sourceObjectKey,
      sourceSha256: row.sourceSha256,
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
