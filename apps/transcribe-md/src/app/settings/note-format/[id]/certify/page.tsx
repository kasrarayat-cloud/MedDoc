import type { Metadata } from "next";
import { notFound } from "next/navigation";

import { AppFrame } from "@/components/ui/app-frame";
import { requireDoctorSession } from "@/lib/auth";
import { logAudit } from "@/lib/audit";
import { readTemplateTwinWorkspace } from "@/lib/template-twin/workspace-read";
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
  let workspace;
  try {
    workspace = await runWithTemplateTwinStagingQaLifecycleGuard({
      noteTemplateId: id,
      actor: {
        userId: session.user.id,
        practiceId: session.user.practiceId,
        rolloutToken: session.templateTwinRolloutToken,
      },
      purpose: "workspace-read",
      operation: () =>
        readTemplateTwinWorkspace({
          noteTemplateId: id,
          doctorId: session.user.id,
          practiceId: session.user.practiceId,
        }),
    });
  } catch (error) {
    if (error instanceof TemplateTwinStagingQaLifecycleGuardError) notFound();
    throw error;
  }
  if (!workspace) notFound();

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
