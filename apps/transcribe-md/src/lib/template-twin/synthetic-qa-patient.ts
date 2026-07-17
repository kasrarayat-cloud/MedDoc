import type { Prisma } from "@prisma/client";

/**
 * Reserved identity for the staging-only Template Twin patient row.
 *
 * The row exists solely to let the authenticated synthetic QA workflow use
 * the real tenant-scoped visit pipeline. Ordinary patient and visit surfaces
 * must treat it as non-existent so it cannot be edited, exported, selected,
 * or confused with a clinical patient chart.
 */
export const TEMPLATE_TWIN_SYNTHETIC_QA_PATIENT_EXTERNAL_ID =
  "SYNTHETIC-QA-ONLY" as const;

export const TEMPLATE_TWIN_SYNTHETIC_QA_PATIENT_NAME =
  "Template Twin Synthetic QA" as const;

export function isTemplateTwinSyntheticQaPatient(
  patient: { externalId: string | null } | null | undefined,
): boolean {
  return patient?.externalId === TEMPLATE_TWIN_SYNTHETIC_QA_PATIENT_EXTERNAL_ID;
}

/**
 * Adds the fail-closed isolation boundary used by ordinary clinical visit
 * surfaces. Both markers are checked deliberately:
 *
 * - the durable staging-run relation is authoritative for synthetic QA; and
 * - the reserved patient identity prevents a damaged/incomplete run row from
 *   making its isolated patient appear in ordinary counts or pagination.
 *
 * Guarded staging routes intentionally do not use this helper. They load the
 * exact visit and then apply the staging rollout/tenant/attempt guard instead.
 */
export function ordinaryClinicalVisitWhere(
  where: Prisma.TranscribeVisitWhereInput,
): Prisma.TranscribeVisitWhereInput {
  return {
    AND: [
      where,
      { templateTwinSyntheticQaRun: { is: null } },
      {
        patient: {
          is: {
            // `externalId` is nullable. A negated equality predicate excludes
            // NULL through SQL three-valued logic, which previously hid every
            // ordinary patient without an external ID. Spell out both valid
            // ordinary states so only the exact reserved identity is hidden.
            OR: [
              { externalId: null },
              {
                externalId: {
                  not: TEMPLATE_TWIN_SYNTHETIC_QA_PATIENT_EXTERNAL_ID,
                },
              },
            ],
          },
        },
      },
    ],
  };
}
