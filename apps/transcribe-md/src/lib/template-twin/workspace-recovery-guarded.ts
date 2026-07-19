import type { TemplateTwinWorkspace } from "./client-types";
import type { TemplateTwinRolloutToken } from "./rollout";
import {
  runWithTemplateTwinStagingQaLifecycleGuard,
  TemplateTwinStagingQaLifecycleGuardError,
} from "./staging-qa-lifecycle-guard";
import { readTemplateTwinWorkspace } from "./workspace-read";
import {
  findTemplateTwinWorkspaceRecoveryCandidate,
  type TemplateTwinWorkspaceRecoveryCandidate,
} from "./workspace-recovery";

export interface GuardedTemplateTwinWorkspaceRecovery {
  candidate: TemplateTwinWorkspaceRecoveryCandidate;
  workspace: TemplateTwinWorkspace;
}

/**
 * Resolve and read an editable successor through its own current staging
 * capability. Returning the candidate ID alone would let a stale/unauthorized
 * lineage leak into navigation; returning the old immutable workspace would
 * make a client rebase dead-end. Expected read failures are carried outside
 * the provider context so they cannot terminally fail the admission.
 */
export async function readGuardedTemplateTwinWorkspaceRecovery(input: {
  noteTemplateId: string;
  actor: {
    userId: string;
    practiceId: string;
    rolloutToken: TemplateTwinRolloutToken;
  };
}): Promise<GuardedTemplateTwinWorkspaceRecovery | null> {
  const candidate = await findTemplateTwinWorkspaceRecoveryCandidate({
    noteTemplateId: input.noteTemplateId,
    doctorId: input.actor.userId,
    practiceId: input.actor.practiceId,
  });
  if (!candidate) return null;

  try {
    const guarded = await runWithTemplateTwinStagingQaLifecycleGuard({
      noteTemplateId: candidate.id,
      actor: input.actor,
      purpose: "workspace-recovery-read",
      operation: async () => {
        try {
          return {
            ok: true as const,
            workspace: await readTemplateTwinWorkspace({
              noteTemplateId: candidate.id,
              doctorId: input.actor.userId,
              practiceId: input.actor.practiceId,
            }),
          };
        } catch (error) {
          return { ok: false as const, error };
        }
      },
    });
    if (!guarded.ok) throw guarded.error;
    if (
      !guarded.workspace ||
      guarded.workspace.template.id !== candidate.id ||
      !guarded.workspace.canEdit
    ) {
      return null;
    }
    return { candidate, workspace: guarded.workspace };
  } catch (error) {
    if (error instanceof TemplateTwinStagingQaLifecycleGuardError) return null;
    throw error;
  }
}
