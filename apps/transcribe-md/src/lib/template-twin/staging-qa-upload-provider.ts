import type { SyntheticQaProviderEnvironment } from "@meddoc/ai";

import type { TemplateTwinRolloutToken } from "./rollout";
import { TemplateTwinRolloutError } from "./rollout";
import {
  runWithVerifiedTemplateTwinStagingQaAdmissionProvider,
  TemplateTwinStagingQaAdmissionError,
} from "./staging-qa-admission";
import { isTemplateTwinStagingQaFixtureSource } from "./staging-qa-fixtures";
import { TemplateTwinStagingQaDisabledError } from "./staging-qa-gate";

export const TEMPLATE_TWIN_STAGING_QA_UPLOAD_PROVIDER_CODE =
  "TEMPLATE_TWIN_STAGING_QA_UPLOAD_PROVIDER_UNAVAILABLE" as const;

export class TemplateTwinStagingQaUploadProviderError extends Error {
  readonly code = TEMPLATE_TWIN_STAGING_QA_UPLOAD_PROVIDER_CODE;

  constructor() {
    super("Template Twin synthetic QA is unavailable.");
    this.name = "TemplateTwinStagingQaUploadProviderError";
  }
}

/**
 * Enter the upload provider boundary only through a separately committed,
 * database-reverified capability. The admission service deliberately uses the
 * root Prisma client, so a row visible only to an uncommitted caller
 * transaction cannot authorize this callback.
 */
export async function runWithTemplateTwinStagingQaUploadProvider<T>(input: {
  admissionId: string;
  source: { readonly sha256: string; readonly sizeBytes: number };
  actor: {
    readonly userId: string;
    readonly practiceId: string;
    readonly rolloutToken: TemplateTwinRolloutToken;
  };
  operation: (providerVisitId: string) => Promise<T> | T;
  env?: SyntheticQaProviderEnvironment;
}): Promise<T> {
  if (!isTemplateTwinStagingQaFixtureSource(input.source)) {
    throw new TemplateTwinStagingQaUploadProviderError();
  }
  try {
    return await runWithVerifiedTemplateTwinStagingQaAdmissionProvider({
      admissionId: input.admissionId,
      actor: input.actor,
      allowedPhases: ["ADMITTED"],
      expectedProviderMode: "SYNTHETIC_LIFECYCLE",
      expectedSource: input.source,
      operation: input.operation,
      env: input.env,
    });
  } catch (error) {
    if (
      error instanceof TemplateTwinStagingQaAdmissionError ||
      error instanceof TemplateTwinStagingQaDisabledError ||
      error instanceof TemplateTwinRolloutError
    ) {
      throw new TemplateTwinStagingQaUploadProviderError();
    }
    throw error;
  }
}
