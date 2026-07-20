import type { Prisma } from "@prisma/client";

import { TEMPLATE_TWIN_SYNTHETIC_QA_PATIENT_EXTERNAL_ID } from "./synthetic-qa-patient";

/**
 * Fail-closed predicate for generic background writers that have no current
 * physician/final-claim context. Every durable marker is excluded; a separate
 * reviewed Template Twin retention workflow must own these rows.
 */
export const TEMPLATE_TWIN_DURABLE_VISIT_EXCLUSION_WHERE = {
  AND: [
    {
      OR: [
        { noteTemplateId: null },
        {
          noteTemplate: {
            is: {
              templateKind: { not: "template_twin_docx" },
              templateTwinCompiledVersion: { is: null },
            },
          },
        },
      ],
    },
    { templateTwinFill: { is: null } },
    { templateTwinSyntheticQaRun: { is: null } },
    { templateTwinSyntheticQaAdmission: { is: null } },
    { templateTwinProviderExecutions: { none: {} } },
    {
      patient: {
        is: {
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
} satisfies Prisma.TranscribeVisitWhereInput;
