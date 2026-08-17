/**
 * AUTO-CERTIFICATION — the engine. Ruling #124.
 *
 * The doctor uploads a .docx and runs visits. The model's own proposals are
 * confirmed, the round-trip proof runs, and the template certifies — with no
 * sitting and no eighty clicks.
 *
 * ⚠️ THIS RUNS IN THE WORKER, NEVER ON THE UPLOAD REQUEST. The round-trip proof
 * is a LIVE model generation (`createEphemeralVisitNoteGenerator` → real L4 →
 * real bridge fill). Putting that on the upload thread would make an upload hang
 * on a generation, and a slow or failing model would read to the doctor as a
 * broken upload. Upload returns fast; the row says "Preparing your format…";
 * this finishes the job out of band.
 *
 * ⚠️ AND IT NEVER HALF-CERTIFIES. Clause 2(a): the proof must pass before
 * certification completes. `runTemplateTwinSyntheticTest` throws on failure and
 * the throw propagates — the template stays NEEDS_CONFIRMATION and the
 * doctor-facing banner (PR #713) names the reason. A template is certified or it
 * is not; there is no third state.
 */
import { logTwinAudit } from './twin-audit';
import { type AutoConfirmOutcome, type AutoConfirmProvenance } from './auto-certify-eligibility';

export { planAutoConfirm, type AutoConfirmOutcome } from './auto-certify-eligibility';

/**
 * The audit trail for an auto-confirmation pass.
 *
 * ⚠️ ONE ROW FOR THE PASS, NOT EIGHTY. Eighty rows for one upload is noise that
 * buries the signal, and the per-field detail is carried in the metadata where
 * it can be queried. The row answers "who confirmed these, how, and which ones
 * did the engine decline" — which is the question the trail exists for.
 *
 * ⚠️ AND IT REUSES `TEMPLATE_TWIN_MAPPING_UPDATED` DELIBERATELY. A new
 * AuditAction value is THREE edits — the TS union, the Prisma enum, and a
 * Postgres `ALTER TYPE` migration — and this codebase has shipped that gap
 * twice, where the first two landed and the write then failed at runtime and was
 * swallowed. Nothing here needs a new verb; `auto: true` in the metadata is the
 * discriminator.
 */
export async function auditAutoConfirm(input: {
  noteTemplateId: string;
  actorUserId: string;
  practiceId: string;
  proposedByModel: string | null;
  outcome: AutoConfirmOutcome;
}): Promise<void> {
  await logTwinAudit({
    action: 'TEMPLATE_TWIN_MAPPING_UPDATED',
    userId: input.actorUserId,
    practiceId: input.practiceId,
    targetType: 'note_template',
    targetId: input.noteTemplateId,
    metadata: {
      auto: true,
      // ⚠️ MODEL IDENTITY, NOT CONFIDENCE — ruling #124(c) as AMENDED. There is
      // no numeric confidence anywhere on the mapping-proposal path; inventing a
      // column to carry a number nothing produces is the fabricated-signal class.
      proposedByModel: input.proposedByModel,
      confirmedCount: input.outcome.mappings.filter((m) => m.status === 'certified').length,
      provenance: input.outcome.provenanceCounts,
      declinedCount: input.outcome.declined.length,
      declinedLabels: input.outcome.declined.map((d) => d.label),
    },
  });
}
