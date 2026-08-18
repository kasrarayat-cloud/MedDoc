/**
 * AUTO-CERTIFY, THE WORKER JOB — ruling #125.
 *
 * Enqueued by compile-on-upload when the twin compiles with zero blocking
 * elements. Confirms the model's own proposals, runs the round-trip proof, and
 * certifies. The doctor uploads and runs visits; this is the part they never see.
 *
 * ⚠️ IT NEVER HALF-CERTIFIES — clause 2(a). Certification only happens after
 * `runTemplateTwinSyntheticTest` returns; if the proof throws, the throw
 * propagates and the template stays NEEDS_CONFIRMATION with the reason logged
 * and audited. A template is certified or it is not.
 *
 * ⚠️ AND IT REUSES THE MANUAL PATH'S OWN PIECES — the same VERIFICATION_ENCOUNTER,
 * the same synthetic test, the same lifecycle transition. An automatic path that
 * proved something different from the manual one would leave neither reader able
 * to say what their template actually passed.
 */
import { readTemplateTwinWorkspace } from '@/lib/template-twin/workspace-read';
import { updateTemplateTwinMappings, certifyAndActivateTemplateTwin } from '@/lib/template-twin/certification-lifecycle';
import { runTemplateTwinSyntheticTest } from '@/lib/template-twin/synthetic-test';
import { extractTemplateTwinEntities } from '@/worker/layers/03-extract-entities';
import { createEphemeralVisitNoteGenerator } from '@/worker/template-twin-note-generator';
import { VERIFICATION_ENCOUNTER } from '@/actions/template-twin-certify';
import { planAutoConfirm } from '@/lib/template-twin/auto-certify-eligibility';
import { auditAutoConfirm } from '@/lib/template-twin/auto-certify';
import { logTwinAudit } from '@/lib/template-twin/twin-audit';
import type { AutoCertifyTwinPayload } from '@/lib/queue';
import prisma from '@meddoc/db';

export interface AutoCertifyResult {
  status: 'certified' | 'declined' | 'proof_failed';
  confirmed: number;
  declined: string[];
  reason?: string;
}

export async function runAutoCertifyTwin(
  payload: AutoCertifyTwinPayload,
): Promise<AutoCertifyResult> {
  const { noteTemplateId, userId, userEmail, practiceId } = payload;
  const actor = { userId, userEmail, practiceId };

  const workspace = await readTemplateTwinWorkspace({
    noteTemplateId,
    doctorId: userId,
    practiceId,
  });
  if (!workspace) {
    return { status: 'declined', confirmed: 0, declined: [], reason: 'workspace_not_found' };
  }

  const plan = planAutoConfirm(workspace);

  // ⚠️ A DECLINED FIELD STOPS CERTIFICATION, AND THAT IS THE DESIGN. The doctor
  // is told which field and why (#713's banner), and the manual screen resolves
  // it in seconds. Certifying around an unresolvable field would be the
  // half-certify clause 2(a) forbids.
  if (plan.declined.length > 0) {
    await logTwinAudit({
      action: 'TEMPLATE_TWIN_CERTIFY_FAILED',
      userId,
      practiceId,
      targetType: 'note_template',
      targetId: noteTemplateId,
      metadata: {
        auto: true,
        stage: 'plan',
        declinedCount: plan.declined.length,
        declined: plan.declined,
      },
    });
    return {
      status: 'declined',
      confirmed: 0,
      declined: plan.declined.map((d) => d.label),
      reason: 'fields_need_confirmation',
    };
  }

  await updateTemplateTwinMappings({
    noteTemplateId,
    actor,
    expectedMappingsSha256: workspace.mappingsSha256,
    mappings: plan.mappings,
  });

  await auditAutoConfirm({
    noteTemplateId,
    actorUserId: userId,
    practiceId,
    // ⚠️ READ FROM THE ROW, NOT THE WORKSPACE. `proposedByModel` is a DB column
    // and is deliberately NOT on the client-facing mapping type — the browser has
    // no business knowing which model proposed a mapping. The audit row does.
    proposedByModel: await proposingModel(noteTemplateId),
    outcome: plan,
  });

  // Re-read: persisting changes the mappings sha, and the proof + certification
  // both bind to it. Using the pre-write sha here would fail as a CONFLICT.
  const persisted = await readTemplateTwinWorkspace({
    noteTemplateId,
    doctorId: userId,
    practiceId,
  });
  if (!persisted) {
    return { status: 'declined', confirmed: plan.mappings.length, declined: [], reason: 'reread_failed' };
  }

  try {
    await runTemplateTwinSyntheticTest({
      noteTemplateId,
      actor,
      expectedMappingsSha256: persisted.mappingsSha256,
      encounterText: VERIFICATION_ENCOUNTER,
      encounterMode: 'dictation',
      extractEntities: extractTemplateTwinEntities,
      generateNote: createEphemeralVisitNoteGenerator({
        specialty: persisted.template.encounterType ?? 'General',
      }),
    });
  } catch (err) {
    // ⚠️ THE PROOF FAILED, SO NOTHING CERTIFIES. The mappings stay confirmed —
    // that work is real and the doctor should not have to redo it — but the
    // template remains NEEDS_CONFIRMATION and #713's banner names the reason.
    const reason = err instanceof Error ? err.message : String(err);
    await logTwinAudit({
      action: 'TEMPLATE_TWIN_CERTIFY_FAILED',
      userId,
      practiceId,
      targetType: 'note_template',
      targetId: noteTemplateId,
      metadata: { auto: true, stage: 'synthetic_test', reason },
    });
    return { status: 'proof_failed', confirmed: plan.mappings.length, declined: [], reason };
  }

  await certifyAndActivateTemplateTwin({
    noteTemplateId,
    actor,
    expectedMappingsSha256: persisted.mappingsSha256,
  });

  return { status: 'certified', confirmed: plan.mappings.length, declined: [] };
}

/** Which model proposed this template's mappings. One read, for the audit row.
 *  Null-safe: a missing value must never fail a certification. */
async function proposingModel(noteTemplateId: string): Promise<string | null> {
  try {
    const row = await prisma.templateTwinSemanticMapping.findFirst({
      where: { fieldDefinition: { compiledVersion: { noteTemplateId } } },
      select: { proposedByModel: true },
    });
    return row?.proposedByModel ?? null;
  } catch {
    return null;
  }
}
