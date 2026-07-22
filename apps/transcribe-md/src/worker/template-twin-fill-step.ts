// ============================================================================
// Template Twin — note-generation FILL STEP (Phase 2c). Flag-gated + FAIL-SAFE.
// ----------------------------------------------------------------------------
// When NEXT_PUBLIC_TEMPLATE_NATIVE_DOCX is ON and the visit's active template is
// a CERTIFIED twin, produce the fill manifest (processTemplateTwinVisit) AFTER
// note generation and BEFORE sign — so native export reads a cached, provenance-
// pinned artifact (the manifest computes once per visit). A fill failure NEVER
// blocks the visit or signing: it is logged + surfaced, the visit proceeds to
// READY, and native export falls back to the QuillMD-styled generator.
//
// Flag OFF: returns immediately with no DB read/write and no side effect — the
// worker's observable behavior is identical to the flag-OFF live pipeline.
// ============================================================================

import prisma from '@meddoc/db';

import { templateNativeDocxEnabled } from '@/config/template-native-docx';
import type { EncounterInputMode } from '@/lib/template-twin/encounter-facts';
import { processTemplateTwinVisit } from '@/lib/template-twin/fill-engine';

export type TwinFillStepResult =
  | { status: 'skipped'; reason: 'flag_off' | 'not_certified_twin' }
  | { status: 'filled'; roundTripVerified: boolean }
  | { status: 'failed'; reason: string };

/** visit.inputMode ("audio_upload"|"voice_dictation"|"text_notes") ->
 *  the twin resolver's EncounterInputMode. */
function mapInputMode(inputMode: string): EncounterInputMode {
  if (inputMode === 'voice_dictation') return 'dictation';
  if (inputMode === 'text_notes') return 'text';
  return 'conversation'; // audio_upload
}

/** Hard ceiling so a stalled fill/storage call can never delay the visit reaching
 *  READY. On timeout the step is treated as a (non-blocking) failure. */
const FILL_TIMEOUT_MS = 45_000;

async function withTimeout<T>(work: Promise<T>, ms: number): Promise<T> {
  let timer: ReturnType<typeof setTimeout> | undefined;
  const timeout = new Promise<never>((_, reject) => {
    timer = setTimeout(() => reject(new Error('TWIN_FILL_TIMEOUT')), ms);
  });
  try {
    return await Promise.race([work, timeout]);
  } finally {
    if (timer) clearTimeout(timer);
  }
}

/** Cheap gate: only a CERTIFIED twin compiled version triggers the fill. Avoids
 *  running the provenance claim for the common non-twin (SOAP) visit. */
async function isCertifiedTwinTemplate(noteTemplateId: string): Promise<boolean> {
  const compiled = await prisma.templateTwinCompiledVersion.findUnique({
    where: { noteTemplateId },
    select: { certificationStatus: true },
  });
  return compiled?.certificationStatus === 'CERTIFIED';
}

export async function runTemplateTwinFillStep(input: {
  visitId: string;
  practiceId: string;
  doctorId: string;
  noteTemplateId: string;
  noteTemplateVersion: number;
  inputMode: string;
  contextText: string;
  entities: unknown;
  /** The generated note (soapFinal) — its CHOICE_SLOT picks + table measurements
   *  are bridged into the native fill. */
  generatedNote: string;
}): Promise<TwinFillStepResult> {
  // Flag OFF: no-op, no DB, behavior-identical to the live pipeline.
  if (!templateNativeDocxEnabled()) return { status: 'skipped', reason: 'flag_off' };

  try {
    if (!(await isCertifiedTwinTemplate(input.noteTemplateId))) {
      return { status: 'skipped', reason: 'not_certified_twin' };
    }
    const prepared = await withTimeout(
      processTemplateTwinVisit({
        visitId: input.visitId,
        practiceId: input.practiceId,
        doctorId: input.doctorId,
        noteTemplateId: input.noteTemplateId,
        noteTemplateVersion: input.noteTemplateVersion,
        inputMode: mapInputMode(input.inputMode),
        contextText: input.contextText,
        entities: input.entities,
        generatedNote: input.generatedNote,
        validationNow: new Date(),
        resolverModelVersion: null,
      }),
      FILL_TIMEOUT_MS,
    );
    return {
      status: 'filled',
      roundTripVerified: prepared.render?.verification.verified === true,
    };
  } catch (err) {
    // FAIL-SAFE: never rethrow. Logged + surfaced; the visit + sign proceed and
    // native export falls back to styled. Non-PHI: ids/reason only.
    const reason = err instanceof Error ? err.message : String(err);
    console.warn(
      `[template-twin-fill] non-blocking fill failure for visit=${input.visitId}: ${reason}`
    );
    return { status: 'failed', reason };
  }
}
