'use server';

// ============================================================================
// Template Twin — certify-once server actions (Stage 4).
// ----------------------------------------------------------------------------
// The doctor uploads their .docx ONCE in Settings → it is securely compiled to
// the IR → the mapping proposal is reviewed → certify hash-locks the binding.
// Every future visit on that template then fills + native-exports automatically
// (the worker fill step); the doctor never reviews per-note.
//
// Flag-gated at the action boundary (defense-in-depth beyond the UI gate) and
// doctor-scoped via requireSession. PHI-safe: never surfaces raw model output or
// document content — only typed lifecycle/security error messages.
//
// DESIGN NOTE (BOUND-002): certifyNativeTemplateAction runs the synthetic-test
// proof (a bounded Anthropic L3 extract) INLINE on the request thread rather than
// enqueuing it. This is a deliberate call: certification is a ONE-TIME, explicit,
// interactive step the doctor is actively waiting on ("Verifying & certifying…"),
// not a per-visit hot path — inline keeps the UX a single confirmed action with
// immediate success/failure, and a transient model outage surfaces as a retriable
// error rather than a stuck background job. If certify latency/availability ever
// becomes a problem, move the proof to the worker + poll (mirror actions/visits
// retryVisit).
// ============================================================================

import { requireSession, type Session } from '@/lib/auth';
import { templateNativeDocxEnabled } from '@/config/template-native-docx';
import {
  createTemplateTwinDraft,
  TemplateTwinDraftError,
} from '@/lib/template-twin/create-draft';
import { VERIFICATION_ENCOUNTER } from '@/lib/template-twin/verification-encounter';
import { readTemplateTwinWorkspace } from '@/lib/template-twin/workspace-read';
import {
  certifyAndActivateTemplateTwin,
  TemplateTwinLifecycleError,
} from '@/lib/template-twin/certification-lifecycle';
import {
  runTemplateTwinSyntheticTest,
  TemplateTwinSyntheticTestError,
} from '@/lib/template-twin/synthetic-test';
import { mappingsNotReadyMessage } from '@/lib/template-twin/mappings-not-ready-message';
import { extractTemplateTwinEntities } from '@/worker/layers/03-extract-entities';
import { createEphemeralVisitNoteGenerator } from '@/worker/template-twin-note-generator';
import { TemplateDocxError } from '@/lib/note-template-docx';
import { TemplateTwinPhiRejectedError } from '@/lib/template-twin/source-phi';
import type { TemplateTwinWorkspace } from '@/lib/template-twin/client-types';
import { sendTemplateCertifiedEmail } from '@/lib/email';
import { isEmailDeliveryEnabled } from '@/lib/email-enabled';
import { logTwinAudit } from '@/lib/template-twin/twin-audit';

// A synthetic, PHI-free clinical encounter used to prove the template renders +
// roundtrips before certification (the certify step binds this verified proof).
// Generic enough to exercise common fields; the roundtrip proof is about render
// mechanics, not fill completeness.
/** ⚠️ EXPORTED so the auto-certify worker job uses THE SAME synthetic encounter
 *  the manual path attests against. Two verification encounters would mean the
 *  automatic path proves something the manual path never proved, and neither
 *  reader would know which one their template passed. Ruling #127. */

const MAX_DOCX_BYTES = 5 * 1024 * 1024; // 5 MB — a single clinical template
const DISABLED = 'Native template fill is not enabled for your account.';

export type CertifyActionResult<T> =
  | { ok: true; data: T }
  | {
      ok: false;
      error: string;
      /** WHY it failed, as a machine-readable class the UI can render honestly.
       *
       *  `unexpected` is the honest name for the case that used to be dressed up
       *  as "Please try again." — an exception the action did not anticipate.
       *  Telling a doctor to retry an operation that will fail identically every
       *  time is worse than telling them it broke. */
      reason?:
        | 'disabled'
        | 'conflict'
        | 'certification_blocked'
        | 'lifecycle'
        | 'mappings_not_ready'
        | 'unexpected';
      /** Present only for `unexpected`, and only the error's CLASS — never its
       *  message, which can quote document content. The message goes to the
       *  server log and the audit row, which are not the doctor's screen. */
      errorClass?: string;
      /** Present only for `mappings_not_ready`: how many fields still need a
       *  physician's confirmation, and how many the form has in total.
       *
       *  ⚠️ COUNTS ONLY. The field LABELS are the customer's own form and never
       *  cross this boundary — the same rule `errorClass` exists to keep. The
       *  opaque fieldIds stay in the audit row. */
      remaining?: number;
      totalFields?: number | null;
    };

function actorFrom(session: Session) {
  return {
    userId: session.user.id,
    userEmail: session.user.email,
    practiceId: session.user.practiceId,
  };
}

/** PHI-safe message for a compile/security/persist failure — never the raw
 *  document, model output, or stack. Known typed errors carry safe copy. */
function safeUploadError(err: unknown): string {
  if (err instanceof TemplateTwinPhiRejectedError) {
    return 'The upload was blocked because it appears to contain patient information. Upload a blank template, not a filled note.';
  }
  if (err instanceof TemplateDocxError) {
    return 'This document could not be read as a safe Word template. Remove macros / embedded objects and try a plain .docx.';
  }
  if (err instanceof TemplateTwinDraftError) {
    if (err.code === 'NO_FILLABLE_FIELDS') {
      return 'This template has no fillable fields (dropdowns, checkboxes, or table cells) to map. Add form fields in Word and re-upload.';
    }
    return 'This template could not be prepared for native fill. Try a simpler .docx.';
  }
  return 'Something went wrong preparing this template. Please try again.';
}

/**
 * Upload a .docx, securely compile it to a draft twin, and return the review
 * workspace (fields + proposed mappings) for the doctor to certify.
 */
export async function uploadNativeTemplateAction(
  formData: FormData,
): Promise<CertifyActionResult<TemplateTwinWorkspace>> {
  if (!templateNativeDocxEnabled()) return { ok: false, error: DISABLED };
  const session = await requireSession();

  const file = formData.get('file');
  if (!(file instanceof File)) return { ok: false, error: 'No file was uploaded.' };
  if (!file.name.toLowerCase().endsWith('.docx')) {
    return { ok: false, error: 'Upload a Word .docx file.' };
  }
  if (file.size === 0) return { ok: false, error: 'The file is empty.' };
  if (file.size > MAX_DOCX_BYTES) {
    return { ok: false, error: 'The file is too large (max 5 MB).' };
  }

  const bytes = new Uint8Array(await file.arrayBuffer());
  let noteTemplateId: string;
  try {
    const created = await createTemplateTwinDraft({ source: bytes, actor: actorFrom(session) });
    noteTemplateId = created.noteTemplateId;
  } catch (err) {
    return { ok: false, error: safeUploadError(err) };
  }

  const workspace = await readTemplateTwinWorkspace({
    noteTemplateId,
    doctorId: session.user.id,
    practiceId: session.user.practiceId,
  });
  if (!workspace) return { ok: false, error: 'The template was uploaded but could not be loaded for review.' };
  return { ok: true, data: workspace };
}

// `getNativeTemplateWorkspaceAction` removed 2026-07-28 — ZERO callers. A
// server action is an HTTP endpoint: every exported one is reachable by a POST
// from anyone with a session, so an unused one is attack surface that no test
// covers and no reviewer reads. The upload and certify actions each return the
// workspace they produce, which is how the UI has always obtained it.

/**
 * Certify + activate: hash-locks the reviewed mapping set. Optimistic-locked on
 * the mappings hash the doctor reviewed — a stale review (mappings changed under
 * them) is rejected rather than silently certifying the wrong binding.
 */
export async function certifyNativeTemplateAction(
  noteTemplateId: string,
  expectedMappingsSha256: string,
): Promise<CertifyActionResult<TemplateTwinWorkspace>> {
  if (!templateNativeDocxEnabled()) return { ok: false, error: DISABLED };
  const session = await requireSession();
  const actor = actorFrom(session);
  try {
    // Certification binds a synthetic roundtrip proof. If one for THIS exact
    // mapping set doesn't exist yet, produce it first (one-time, per template).
    const current = await readTemplateTwinWorkspace({
      noteTemplateId,
      doctorId: session.user.id,
      practiceId: session.user.practiceId,
    });
    const proofFresh =
      current?.latestSyntheticTest?.roundTripVerified === true &&
      current.latestSyntheticTest.mappingsSha256 === expectedMappingsSha256;
    if (!proofFresh) {
      await runTemplateTwinSyntheticTest({
        noteTemplateId,
        actor,
        expectedMappingsSha256,
        encounterText: VERIFICATION_ENCOUNTER,
        encounterMode: 'dictation',
        extractEntities: extractTemplateTwinEntities,
        // Run the proof through the LIVE fill path: a real (ephemeral) visit,
        // the real L4, then bridgeTemplateFill over the resulting picks —
        // exactly what a patient visit does. Costs one generation per
        // certification, which is the price of attesting the real path.
        generateNote: createEphemeralVisitNoteGenerator({
          specialty: current?.template.encounterType ?? 'General',
        }),
      });
    }
    const workspace = await certifyAndActivateTemplateTwin({
      noteTemplateId,
      actor,
      expectedMappingsSha256,
    });
    // Notify the doctor their note format is ready — ONLY on the genuine
    // recognized→certified transition (never on an idempotent re-certify), and
    // only when email delivery is configured. Fire-and-forget + fully fail-safe:
    // an email hiccup must never fail or roll back certification.
    const becameCertified =
      current?.template.certificationStatus !== 'certified' &&
      workspace.template.certificationStatus === 'certified';
    if (becameCertified && isEmailDeliveryEnabled()) {
      void sendTemplateCertifiedEmail({
        toEmail: session.user.email,
        userName: session.user.fullName ?? null,
        templateName: workspace.template.name,
      }).catch((err) => {
        console.warn(
          `[template-twin] certified-email non-blocking failure template=${noteTemplateId}: ${
            err instanceof Error ? err.message : String(err)
          }`,
        );
      });
    }
    return { ok: true, data: workspace };
  } catch (err) {
    if (err instanceof TemplateTwinLifecycleError) {
      if (err.code === 'CONFLICT') {
        return {
          ok: false,
          reason: 'conflict',
          error: 'This template changed since you reviewed it. Reload and review again before certifying.',
        };
      }
      if (err.code === 'CERTIFICATION_BLOCKED') {
        return {
          ok: false,
          reason: 'certification_blocked',
          error: 'This template can’t be certified — it has elements that can’t be safely reproduced. Simplify it in Word and re-upload.',
        };
      }
      return { ok: false, reason: 'lifecycle', error: err.message };
    }

    // ⚠️ MAPPINGS_NOT_READY IS A DESIGNED REFUSAL AND BELONGS ON THIS LADDER,
    // NOT IN THE UNANTICIPATED-THROW BRANCH BELOW. (F16.)
    //
    // Measured on production 2026-08-17: a physician uploaded their form at
    // 17:39Z, confirmed 74 of its 80 fields at 18:11:33Z, pressed Certify at
    // 18:11:38Z and AGAIN at 18:11:52Z. Both attempts fell through to `:298`
    // and told them:
    //
    //   "Certification could not be completed (MAPPINGS_NOT_READY). This has
    //    been recorded — it will not succeed on a retry until it is fixed."
    //
    // That sentence frames a state THEY could clear in a minute as a fault
    // someone else must repair, and names neither how many fields remain nor
    // which. They pressed twice and stopped. The useful sentence — "Every
    // field needs a physician-confirmed mapping" — went only to the audit row.
    //
    // ⚠️ THE GATE IS NOT WEAKENED BY ONE FIELD. This branch changes what is
    // SAID about a refusal that already happened; `runTemplateTwinSyntheticTest`
    // decides the refusal and is untouched. A certified twin nobody confirmed
    // is worse than no twin.
    //
    // ⚠️ AND IT CARRIES NO FIELD LABELS — the constraint the branch below
    // states in its own comment, and the reason it withholds `err.message`.
    // Only a COUNT and a route cross to the doctor. The opaque fieldIds stay
    // in the audit row, where they already were.
    if (err instanceof TemplateTwinSyntheticTestError && err.code === 'MAPPINGS_NOT_READY') {
      const remaining = err.blocking.length;
      const total = err.totalFields;
      void logTwinAudit({
        action: 'TEMPLATE_TWIN_CERTIFY_FAILED',
        targetType: 'note_template',
        targetId: noteTemplateId,
        success: false,
        errorCode: 'MAPPINGS_NOT_READY',
        metadata: {
          errorClass: 'TemplateTwinSyntheticTestError',
          code: 'MAPPINGS_NOT_READY',
          message: err.message,
          stage: 'certifyNativeTemplateAction',
          // ⚠️ IDS AND CLOSED REASON CODES ONLY — AND THIS IS THE FIRST TIME
          // `blocking` HAS EVER BEEN WRITTEN TO AN AUDIT ROW.
          //
          // An earlier version of this comment claimed it used "the same
          // PHI-safe channel VALIDATION_FAILED already uses". That precedent
          // does not exist. Measured on production during the independent
          // adversarial pass:
          //
          //     select count(*) from audit_logs where metadata ? 'blocking';
          //       -> 0     (positive control: `errorClass` -> 2)
          //
          // VALIDATION_FAILED's `blocking` goes to a `console.warn` server log
          // and into the thrown error; it never reaches `audit_logs`, because
          // that path falls through to the unanticipated-throw branch below
          // whose metadata is {errorClass, code, message, stage} only.
          //
          // ⚠️ SO READ THIS AS A NEW CHANNEL, NOT A SANCTIONED ONE. `logAudit`
          // JSON-stringifies the whole entry onto the admin activity stream, so
          // every entry here fans out to any subscribed SUPER_ADMIN — across
          // tenants. That is acceptable for `ttf_<sha256-prefix>:<reason>`,
          // which carries no customer content: the ids are opaque BY
          // CONSTRUCTION (`compiler.ts:1303` hashes sourceSha256 + partName +
          // nodePath + kind — the LABEL is not an input), and `UnreadyReason`
          // is a closed union.
          //
          // ⚠️ IT IS NOT ACCEPTABLE FOR FREE TEXT. Anyone widening `blocking`
          // to carry an issue message, a field label or a parser complaint is
          // putting that text on a cross-tenant stream, and must re-decide this
          // rather than inherit it.
          blocking: err.blocking,
          totalFields: total,
        },
      });
      return {
        ok: false,
        reason: 'mappings_not_ready',
        remaining,
        totalFields: total,
        error: mappingsNotReadyMessage(remaining, total),
      };
    }

    // AN UNANTICIPATED THROW. This branch used to return "Certification failed.
    // Please try again." and do nothing else: no log line, no audit row, and a
    // message that invites a retry which will fail identically every time.
    //
    // A hand-driven QA run reached this exact branch and there was no way to
    // learn why — not from the database, not from the container log. That is the
    // failure mode this codebase keeps paying for: a guard that reports without
    // naming what it found teaches its reader to ignore it.
    //
    // So: name it three ways. The STACK to the server log (operators), the class
    // and message to an audit row (durable, queryable, survives the container),
    // and to the doctor an honest sentence plus the error class — never the
    // message, which can quote the field labels of their own form.
    // NAMING AN ERROR IN A MINIFIED BUNDLE. `err.constructor.name` is the
    // obvious choice and it is wrong here: production minification renamed
    // TemplateTwinSyntheticTestError to `w`, so the first audit row this branch
    // ever wrote recorded `errorClass: "w"` — technically accurate, useless.
    //
    // Prefer, in order: a structured `code` the error carries (the twin's error
    // classes expose one, and it is the most actionable thing available), then
    // `name`, then the class name the STACK preserves, then the minified
    // constructor. The stack is the only place the real class survives.
    const asErr = err instanceof Error ? err : null;
    const maybeCode = (asErr as unknown as { code?: unknown } | null)?.code;
    const structuredCode = typeof maybeCode === 'string' ? maybeCode : null;
    const stackClass = asErr?.stack?.match(/^\s*([A-Za-z_$][\w$]*Error)\b/)?.[1] ?? null;
    const errorClass =
      stackClass ??
      (asErr && asErr.name && asErr.name !== 'Error' ? asErr.name : null) ??
      (asErr ? asErr.constructor.name : typeof err);
    const message = asErr ? asErr.message : String(err);
    console.error(
      `[template-twin:certify] UNEXPECTED failure noteTemplateId=${noteTemplateId} ` +
        `class=${errorClass} message=${message}`,
      err instanceof Error ? err.stack : undefined,
    );
    void logTwinAudit({
      action: 'TEMPLATE_TWIN_CERTIFY_FAILED',
      targetType: 'note_template',
      targetId: noteTemplateId,
      success: false,
      errorCode: errorClass,
      // Class + message only. NEVER document content: the template is the
      // customer's form and its field labels are theirs.
      metadata: {
        errorClass,
        // The typed refusal code when the error carries one — e.g.
        // MAPPINGS_NOT_READY. This is the field that turns "it failed" into
        // "it refused, and here is the rule".
        code: structuredCode,
        message,
        stage: 'certifyNativeTemplateAction',
      },
    });
    return {
      ok: false,
      reason: 'unexpected',
      errorClass,
      error: `Certification could not be completed (${structuredCode ?? errorClass}). This has been recorded — it will not succeed on a retry until it is fixed.`,
    };
  }
}
