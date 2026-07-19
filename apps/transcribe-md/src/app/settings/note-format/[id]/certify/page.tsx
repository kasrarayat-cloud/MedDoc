import type { Metadata } from "next";
import { notFound, redirect } from "next/navigation";

import { AppFrame } from "@/components/ui/app-frame";
import { requireDoctorSession } from "@/lib/auth";
import { logAudit } from "@/lib/audit";
import { readTemplateTwinWorkspace } from "@/lib/template-twin/workspace-read";
import { findTemplateTwinWorkspaceRecoveryCandidate } from "@/lib/template-twin/workspace-recovery";
import { evaluateTemplateTwinStagingQaGate } from "@/lib/template-twin/staging-qa-gate";
import {
  TemplateTwinStagingQaLifecycleGuardError,
  runWithTemplateTwinStagingQaLifecycleGuard,
} from "@/lib/template-twin/staging-qa-lifecycle-guard";

import { TemplateTwinCertificationWorkspace } from "./template-twin-certification-workspace";

export const metadata: Metadata = { title: "Certify Word template" };

export default async function TemplateTwinCertificationPage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const session = await requireDoctorSession();
  const { id } = await params;
  const actor = {
    userId: session.user.id,
    practiceId: session.user.practiceId,
    rolloutToken: session.templateTwinRolloutToken,
  };
  const readGuardedWorkspace = (noteTemplateId: string) =>
    runWithTemplateTwinStagingQaLifecycleGuard({
      noteTemplateId,
      actor,
      purpose: "workspace-read",
      operation: () =>
        readTemplateTwinWorkspace({
          noteTemplateId,
          doctorId: session.user.id,
          practiceId: session.user.practiceId,
        }),
    });
  const recover = async () => {
    const candidate = await findTemplateTwinWorkspaceRecoveryCandidate({
      noteTemplateId: id,
      doctorId: session.user.id,
      practiceId: session.user.practiceId,
    });
    if (!candidate) return null;
    try {
      const recovered = await readGuardedWorkspace(candidate.id);
      return recovered ? candidate : null;
    } catch (error) {
      if (error instanceof TemplateTwinStagingQaLifecycleGuardError) return null;
      throw error;
    }
  };
  let workspace;
  try {
    workspace = await readGuardedWorkspace(id);
  } catch (error) {
    if (error instanceof TemplateTwinStagingQaLifecycleGuardError) {
      const candidate = await recover();
      if (candidate) {
        redirect(
          `/settings/note-format/${encodeURIComponent(candidate.id)}/certify?recoveredFrom=${encodeURIComponent(id)}`,
        );
      }
      notFound();
    }
    throw error;
  }
  if (!workspace) {
    const candidate = await recover();
    if (candidate) {
      redirect(
        `/settings/note-format/${encodeURIComponent(candidate.id)}/certify?recoveredFrom=${encodeURIComponent(id)}`,
      );
    }
    notFound();
  }

  void logAudit({
    action: "VIEWED_SETTINGS",
    targetType: "TemplateTwinCompiledVersion",
    targetId: workspace.template.id,
    userId: session.user.id,
    userEmail: session.user.email,
    practiceId: session.user.practiceId,
    metadata: {
      source: "rsc:/settings/note-format/[id]/certify",
      templateVersion: workspace.template.version,
      certificationStatus: workspace.template.certificationStatus,
    },
  });

  return (
    <AppFrame>
      <TemplateTwinCertificationWorkspace
        initial={workspace}
        stagingQaGateAllowed={
          evaluateTemplateTwinStagingQaGate(process.env).allowed
        }
      />
    </AppFrame>
  );
}
