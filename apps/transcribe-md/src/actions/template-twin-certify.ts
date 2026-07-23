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
import { readTemplateTwinWorkspace } from '@/lib/template-twin/workspace-read';
import {
  certifyAndActivateTemplateTwin,
  TemplateTwinLifecycleError,
} from '@/lib/template-twin/certification-lifecycle';
import { runTemplateTwinSyntheticTest } from '@/lib/template-twin/synthetic-test';
import { extractTemplateTwinEntities } from '@/worker/layers/03-extract-entities';
import { TemplateDocxError } from '@/lib/note-template-docx';
import { TemplateTwinPhiRejectedError } from '@/lib/template-twin/source-phi';
import type { TemplateTwinWorkspace } from '@/lib/template-twin/client-types';
import { sendTemplateCertifiedEmail } from '@/lib/email';
import { isEmailDeliveryEnabled } from '@/lib/email-enabled';

// A synthetic, PHI-free clinical encounter used to prove the template renders +
// roundtrips before certification (the certify step binds this verified proof).
// Generic enough to exercise common fields; the roundtrip proof is about render
// mechanics, not fill completeness.
const VERIFICATION_ENCOUNTER = [
  'Bilateral lower extremity venous reflux study, standing, with distal augmentation.',
  'Indication: bilateral leg heaviness, aching, and visible varicosities.',
  'Right great saphenous vein 6.2 millimeters at the saphenofemoral junction with reflux time 3.4 seconds; incompetent.',
  'Right small saphenous vein competent, no reflux. Left great saphenous vein 4.8 millimeters, reflux 0.4 seconds, within normal limits.',
  'Deep venous system patent bilaterally, compressible, phasic, no deep vein thrombosis.',
].join(' ');

const MAX_DOCX_BYTES = 5 * 1024 * 1024; // 5 MB — a single clinical template
const DISABLED = 'Native template fill is not enabled for your account.';

export type CertifyActionResult<T> =
  | { ok: true; data: T }
  | { ok: false; error: string };

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

/** Re-read the review workspace (fields, mappings, certification status). */
export async function getNativeTemplateWorkspaceAction(
  noteTemplateId: string,
): Promise<CertifyActionResult<TemplateTwinWorkspace>> {
  if (!templateNativeDocxEnabled()) return { ok: false, error: DISABLED };
  const session = await requireSession();
  const workspace = await readTemplateTwinWorkspace({
    noteTemplateId,
    doctorId: session.user.id,
    practiceId: session.user.practiceId,
  });
  if (!workspace) return { ok: false, error: 'Template not found.' };
  return { ok: true, data: workspace };
}

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
        return { ok: false, error: 'This template changed since you reviewed it. Reload and review again before certifying.' };
      }
      if (err.code === 'CERTIFICATION_BLOCKED') {
        return { ok: false, error: 'This template can’t be certified — it has elements that can’t be safely reproduced. Simplify it in Word and re-upload.' };
      }
      return { ok: false, error: err.message };
    }
    return { ok: false, error: 'Certification failed. Please try again.' };
  }
}
