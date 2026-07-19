import prisma from "@meddoc/db";

export interface TemplateTwinWorkspaceRecoveryCandidate {
  id: string;
  version: number;
}

/**
 * Resolve only a same-owner, same-lineage, same-source successor. This helper
 * deliberately returns an identity rather than workspace data: callers must
 * run the normal lifecycle/admission guard for the candidate before exposing
 * it or navigating to it.
 */
export async function findTemplateTwinWorkspaceRecoveryCandidate(input: {
  noteTemplateId: string;
  doctorId: string;
  practiceId: string;
}): Promise<TemplateTwinWorkspaceRecoveryCandidate | null> {
  const requested = await prisma.noteTemplate.findFirst({
    where: {
      id: input.noteTemplateId,
      doctorId: input.doctorId,
      templateKind: "template_twin_docx",
    },
    select: {
      id: true,
      lineageId: true,
      version: true,
      templateTwinCompiledVersion: {
        select: {
          sourceArtifactId: true,
          sourceArtifact: { select: { practiceId: true } },
        },
      },
    },
  });
  const compiled = requested?.templateTwinCompiledVersion;
  if (
    !requested ||
    !compiled ||
    compiled.sourceArtifact.practiceId !== input.practiceId
  ) {
    return null;
  }

  const successor = await prisma.noteTemplate.findFirst({
    where: {
      id: { not: requested.id },
      doctorId: input.doctorId,
      lineageId: requested.lineageId,
      templateKind: "template_twin_docx",
      status: "draft",
      version: { gt: requested.version },
      templateTwinCompiledVersion: {
        is: {
          sourceArtifactId: compiled.sourceArtifactId,
          sourceArtifact: { is: { practiceId: input.practiceId } },
        },
      },
    },
    orderBy: [{ version: "desc" }, { createdAt: "desc" }],
    select: { id: true, version: true },
  });

  return successor ?? null;
}
