'use server';

// ============================================================================
// Template Twin — CONFIRM THE FIELD MAPPINGS.
// ----------------------------------------------------------------------------
// ⚠️ ITS OWN FILE, DELIBERATELY. This lives beside `template-twin-certify.ts`
// and not inside it, because that module imports the worker's entity extractor
// and the ephemeral note generator to run the certification proof. Confirming a
// mapping needs NONE of that — and a module whose test has to mock the world in
// order to load is a module doing too much. Keeping the import graph small here
// also means the confirm path cannot acquire a dependency on note GENERATION,
// which is a boundary worth having on a physician-facing write.
// ============================================================================

import { requireSession, type Session } from '@/lib/auth';
import { templateNativeDocxEnabled } from '@/config/template-native-docx';
import {
  updateTemplateTwinMappings,
  TemplateTwinLifecycleError,
} from '@/lib/template-twin/certification-lifecycle';
import { readTemplateTwinWorkspace } from '@/lib/template-twin/workspace-read';
import type { TemplateTwinWorkspace } from '@/lib/template-twin/client-types';
import type { SemanticMapping } from '@/lib/template-twin/ir';

/**
 * Mirrors the certify action's result shape deliberately rather than importing
 * it: that import would tie this module's graph back to the certify action,
 * which pulls the worker's extractor and note generator. A short structural
 * type is a smaller cost than that edge, and `tsc` still checks both sides
 * against the same `TemplateTwinWorkspace`.
 */
export type MappingsActionResult<T> =
  | { ok: true; data: T }
  | {
      ok: false;
      error: string;
      reason: 'disabled' | 'conflict' | 'lifecycle' | 'unexpected';
    };

const DISABLED = 'Native template fill is not enabled for your account.';

/** Same shape the certify action builds — the SESSION is the only identity. */
function actorFrom(session: Session) {
  return {
    userId: session.user.id,
    userEmail: session.user.email,
    practiceId: session.user.practiceId,
  };
}

// ============================================================================
// OPEN AN EXISTING TEMPLATE'S WORKSPACE — the READ half of the door.
//
// ⚠️ SHIPPED WITH ITS CALLER, AND THAT IS THE WHOLE REASON THIS IS SAFE TO ADD.
// `getNativeTemplateWorkspaceAction` was DELETED on 2026-07-28 for having zero
// callers — see the note where it used to live in `template-twin-certify.ts`.
// Its reasoning was right and is not being overturned: a server action is an
// HTTP endpoint, so an exported one with no caller is attack surface that no
// test covers and no reviewer reads. What changed is the caller, not the
// judgement — `NativeTemplateManager`'s existing-template rows invoke this in
// the same commit, and a gate arm fails if that stops being true.
//
// WHY IT HAD TO COME BACK. `NativeTemplateManager` obtained its workspace from
// `uploadNativeTemplateAction` and NOTHING else, so the only route back into a
// template that had already compiled was to upload the same file again — the
// ritual `settings/page.tsx:241-244` correctly retired. Every doctor whose
// template compiled on upload (RC-2 does this on every `.docx`) therefore had
// a draft mapping set nothing in the application could open. `MAPPINGS_NOT_READY`
// was refusing certification on fields that no surface could confirm.
//
// TENANCY: `readTemplateTwinWorkspace` filters on `doctorId`, which T7's
// `note_templates_practice_iff_doctor` biconditional makes strictly narrower
// than practice scope. The session is the only identity; the id is never
// trusted. A template belonging to anyone else reads as absent, which is the
// correct answer to give a caller who should not know it exists.
//
// READ-ONLY. It writes nothing, and it must not: the confirm action below is
// the write half and carries the optimistic-concurrency hash this read returns.
// ============================================================================
export async function openNativeTemplateWorkspaceAction(
  noteTemplateId: string,
): Promise<MappingsActionResult<TemplateTwinWorkspace>> {
  if (!templateNativeDocxEnabled()) return { ok: false, reason: 'disabled', error: DISABLED };
  const session = await requireSession();
  const workspace = await readTemplateTwinWorkspace({
    noteTemplateId,
    doctorId: session.user.id,
    practiceId: session.user.practiceId,
  });
  if (!workspace) {
    // ⚠️ ONE MESSAGE FOR "does not exist", "not yours" and "has no twin".
    // Distinguishing them would let a caller enumerate other doctors'
    // template ids by reading which refusal came back.
    return {
      ok: false,
      reason: 'lifecycle',
      error: 'That template could not be opened for review.',
    };
  }
  return { ok: true, data: workspace };
}

// ============================================================================
// CONFIRM THE FIELD MAPPINGS — the door `MAPPINGS_NOT_READY` was waiting for.
//
// ⚠️ `updateTemplateTwinMappings` HAD NO CALLER. It has existed, correct and
// tested, with nothing in the application able to invoke it — the only
// reference anywhere was a test grepping its source text. So certification
// refused 79 of 80 fields not because the gate was strict but because NOTHING
// COULD EVER CONFIRM THEM: the gate was right and unsatisfiable.
//
// That is RC-2's shape one layer up — correct, working code with no door — and
// the fix is the same: give it a caller, never soften the thing it guards.
// `MAPPINGS_NOT_READY` is untouched by this action.
//
// TENANCY. `updateTemplateTwinMappings` loads through `loadOwnedCompilation`,
// which scopes by `doctorId` — STRICTLY NARROWER than a practice, and T7's
// `note_templates_practice_iff_doctor` biconditional makes doctor-scope imply
// practice-scope. A second hand-written predicate here would be a second copy
// of a tenancy rule, which is how the two drift.
//
// OPTIMISTIC CONCURRENCY IS THE CALLER'S JOB TO CARRY, NOT TO INVENT.
// `expectedMappingsSha256` is the hash the reviewer's page was rendered from.
// The writer refuses if the stored mappings have moved since — two physicians
// confirming the same template must not silently overwrite each other, and a
// stale tab is the ordinary way that happens.
// ============================================================================
export async function updateTemplateTwinMappingsAction(
  noteTemplateId: string,
  expectedMappingsSha256: string,
  mappings: readonly SemanticMapping[],
): Promise<MappingsActionResult<TemplateTwinWorkspace>> {
  if (!templateNativeDocxEnabled()) return { ok: false, reason: 'disabled', error: DISABLED };
  const session = await requireSession();
  const actor = actorFrom(session);
  try {
    await updateTemplateTwinMappings({
      noteTemplateId,
      actor,
      expectedMappingsSha256,
      mappings,
    });
    const workspace = await readTemplateTwinWorkspace({
      noteTemplateId,
      doctorId: session.user.id,
      practiceId: session.user.practiceId,
    });
    if (!workspace) {
      // The write succeeded and the read did not. Do NOT report success with no
      // data — the UI would render an empty workspace over confirmed mappings.
      return {
        ok: false,
        reason: 'unexpected',
        error: 'Your changes were saved but the page could not be reloaded. Refresh to continue.',
      };
    }
    return { ok: true, data: workspace };
  } catch (err) {
    if (err instanceof TemplateTwinLifecycleError) {
      if (err.code === 'CONFLICT') {
        return {
          ok: false,
          reason: 'conflict',
          error:
            'This template changed since you opened it — someone else may have edited it, or this tab is stale. Reload and review again.',
        };
      }
      if (err.code === 'IMMUTABLE') {
        return {
          ok: false,
          reason: 'lifecycle',
          error: 'This template is already certified. Certified versions cannot be edited.',
        };
      }
      return { ok: false, reason: 'lifecycle', error: err.message };
    }
    // ⚠️ NEVER SURFACE THE RAW THROW. A mapping payload can carry the doctor's
    // own field labels, which are customer-confidential (SPEC §4.3a(e)); a Zod
    // issue path can quote them. Log for the operator, return a typed class.
    console.error(
      `[template-twin:mappings] update failed for ${noteTemplateId}: ${
        err instanceof Error ? err.message : String(err)
      }`,
    );
    return {
      ok: false,
      reason: 'unexpected',
      error: 'Those changes could not be saved. Reload the page and try again.',
    };
  }
}
