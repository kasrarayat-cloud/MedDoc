import prisma from "@meddoc/db";

export interface CurrentVisitExportActor {
  id: string;
  practiceId: string;
}

/**
 * Current account/practice lifecycle gate shared by account and patient ZIP
 * exports. Template Twin rollout is intentionally not consulted: ordinary
 * data export remains available while its rollout is disabled, while each
 * Twin artifact retains its stronger delivery claim.
 */
export async function loadCurrentVisitExportActor(
  userId: string,
): Promise<CurrentVisitExportActor | null> {
  const actor = await prisma.user.findUnique({
    where: { id: userId },
    select: {
      id: true,
      practiceId: true,
      role: true,
      isActive: true,
      deactivatedAt: true,
      suspendedAt: true,
      softDeletedAt: true,
      products: true,
      practice: { select: { isActive: true } },
    },
  });
  if (
    !actor ||
    actor.role !== "DOCTOR" ||
    actor.isActive !== true ||
    actor.deactivatedAt !== null ||
    actor.suspendedAt !== null ||
    actor.softDeletedAt !== null ||
    !actor.products.includes("TRANSCRIBE_MD") ||
    actor.practice.isActive !== true
  ) {
    return null;
  }
  return { id: actor.id, practiceId: actor.practiceId };
}
