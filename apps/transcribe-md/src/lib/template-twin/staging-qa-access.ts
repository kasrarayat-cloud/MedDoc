import prisma from "@meddoc/db";

/**
 * Generic exports are intentionally unavailable for a synthetic QA visit.
 * The only delivery boundary is the signed, stored-byte-verified Original
 * Template DOCX route. This lookup is owner-scoped and returns only a boolean,
 * so callers can answer with the same 404 used for a missing visit.
 */
export async function isOwnedTemplateTwinStagingQaVisit(input: {
  visitId: string;
  userId: string;
}): Promise<boolean> {
  const marker = await prisma.templateTwinSyntheticQaRun.findFirst({
    where: {
      visitId: input.visitId,
      doctorId: input.userId,
      visit: { userId: input.userId },
    },
    select: { id: true },
  });
  return marker !== null;
}
