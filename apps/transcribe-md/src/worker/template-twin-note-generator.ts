// ============================================================================
// The certification proof's note generator — a REAL visit on synthetic data.
// ----------------------------------------------------------------------------
// The certificate must attest the path production actually takes. Production
// runs runLayer4GenerateSoap over a real visit, then bridgeTemplateFill overlays
// the resulting CHOICE_SLOT picks onto the resolver baseline. The synthetic test
// previously ran the resolver alone, so it certified a path no visit uses.
//
// Layer4Input is built around a visit: it takes a visitId and the layer writes
// telemetry against it. Rather than fabricate that context — which would
// recreate the very defect this exists to remove — the proof creates an ACTUAL
// visit from synthetic data, runs the real L4 against it, and then removes it.
// Nothing is faked; the contract is satisfied honestly.
//
// WHAT IS SYNTHETIC, AND VISIBLY SO:
//   * a fixture patient named so it cannot be mistaken for a person, created
//     and destroyed inside this call
//   * the transcript IS the physician-supplied synthetic encounter, which has
//     already passed the synthetic-evidence gate (explicit marker required, no
//     identifiers)
//
// CLEANUP: the visit and fixture patient are deleted in a finally block, so a
// failed generation cannot leave either in the doctor's dashboard. audit_logs
// are NOT deleted — they reference the visit by targetId (a plain string, no
// FK), so the append-only trail survives the visit row by construction. Rows
// from this path carry the fixture patient's name in their target metadata,
// which is how you tell them apart in an audit export.
//
// COST: one L4 generation per certification. Accepted deliberately — the
// alternative is certifying a path production does not take.
// ============================================================================

import prisma from '@meddoc/db';

import type { TwinNoteGenerator } from '@/lib/template-twin/synthetic-test';
import { runLayer4GenerateSoap } from '@/worker/layers/04-generate-soap';
import { normalizeTemplate } from '@/worker/note-templates/build-soap-prompt';
import type { ExtractedEntities } from '@/worker/layers/03-extract-entities';

/** Unmistakable in a patient list, a chart export, or an audit row. */
const FIXTURE_PATIENT_NAME = 'ZZ SYNTHETIC — template certification (not a patient)';

export interface EphemeralVisitGeneratorDeps {
  /** Specialty the twin template is for. Drives L4's report-vs-SOAP routing,
   *  exactly as the worker orchestrator supplies it on a real visit. */
  specialty: string;
}

/**
 * Build a {@link TwinNoteGenerator} that runs the real L4 against a real,
 * short-lived visit.
 */
export function createEphemeralVisitNoteGenerator(
  deps: EphemeralVisitGeneratorDeps,
): TwinNoteGenerator {
  return async (input) => {
    const template = await prisma.noteTemplate.findUnique({
      where: { id: input.noteTemplateId },
      select: {
        id: true,
        version: true,
        isSystemDefault: true,
        sections: true,
        styleProfile: true,
      },
    });
    if (!template) {
      throw new Error('template-twin proof: note template not found for generation');
    }

    let patientId: string | null = null;
    let visitId: string | null = null;
    try {
      const patient = await prisma.transcribeMdPatient.create({
        data: { practiceId: input.practiceId, name: FIXTURE_PATIENT_NAME },
        select: { id: true },
      });
      patientId = patient.id;

      const visit = await prisma.transcribeVisit.create({
        data: {
          userId: input.userId,
          patientId: patient.id,
          // T4 — the author.
          createdBy: input.userId,
          // T3 — from the patient, which this function just created with
          // `input.practiceId`. Threaded from the same value rather than read
          // back, but it must MATCH: the composite FK refuses anything else.
          practiceId: input.practiceId,
          specialty: deps.specialty,
          inputMode: 'text_notes',
          // The synthetic encounter itself — already cleared by the
          // synthetic-evidence gate before this point.
          transcriptText: input.encounterText,
          noteTemplateId: template.id,
          noteTemplateVersion: template.version,
        },
        select: { id: true },
      });
      visitId = visit.id;

      // The REAL layer, unmodified, over a real row.
      return await runLayer4GenerateSoap({
        visitId: visit.id,
        practiceId: input.practiceId,
        userId: input.userId,
        specialty: deps.specialty,
        roleLabeledTranscript: input.roleLabeledTranscript,
        entities: input.entities as ExtractedEntities,
        // text_notes has no utterance segmentation, exactly as a real
        // text-mode visit reports it.
        audioConfidenceStats: null,
        noteTemplate: normalizeTemplate(template),
      });
    } finally {
      // Ordered child-first. Failures here are logged, never thrown: the
      // caller's certification result must not hinge on fixture teardown, and
      // the names make any stragglers obvious.
      if (visitId) {
        await prisma.transcribeVisit
          .delete({ where: { id: visitId } })
          .catch((err: unknown) =>
            console.warn('[template-twin:proof] fixture visit cleanup failed:', err),
          );
      }
      if (patientId) {
        await prisma.transcribeMdPatient
          .delete({ where: { id: patientId } })
          .catch((err: unknown) =>
            console.warn('[template-twin:proof] fixture patient cleanup failed:', err),
          );
      }
    }
  };
}
