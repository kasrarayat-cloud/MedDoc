import { type SyntheticQaProviderEnvironment } from "@meddoc/ai";

import {
  pinTemplateTwinRollout,
  type TemplateTwinRolloutToken,
} from "./rollout";
import { isTemplateTwinStagingQaFixtureSource } from "./staging-qa-fixtures";
import {
  confirmTemplateTwinStagingQaMappings,
  type TemplateTwinStagingQaExpectedMappingConfirmation,
} from "./staging-qa-mapping-confirmation";
import {
  TemplateTwinStagingQaLifecycleGuardError,
  runWithTemplateTwinStagingQaLifecycleGuard,
} from "./staging-qa-lifecycle-guard";

export class TemplateTwinStagingQaCertificationProviderError extends Error {
  readonly code = "TEMPLATE_TWIN_STAGING_QA_PROVIDER_UNAVAILABLE" as const;

  constructor() {
    super("Template Twin synthetic QA is unavailable.");
    this.name = "TemplateTwinStagingQaCertificationProviderError";
  }
}

interface CertificationProviderDependencies {
  readonly env: SyntheticQaProviderEnvironment;
  readonly pinRollout: (input: {
    practiceId: string;
    env?: Readonly<Record<string, string | undefined>>;
  }) => Promise<TemplateTwinRolloutToken>;
  readonly confirmMappings: typeof confirmTemplateTwinStagingQaMappings;
}

/**
 * Provider boundary for the legacy certification-test routes.
 *
 * Ordinary templates retain their existing provider path. The exact staging
 * fixture is different: its immutable source digest and size force every
 * typed-extraction and voice-transcription call into the visit-bound mock
 * context. Process/resource admission and the persisted rollout generations
 * are checked before `operation` is invoked. Once admitted, the context wins
 * at each provider call even if process flags are revoked concurrently, so a
 * staging operation can fail later but can never fall through to a live
 * provider. Its final proof remains protected by the existing transactional
 * rollout-generation check.
 */
export async function runWithTemplateTwinStagingQaCertificationProvider<
  T,
>(input: {
  source: { sha256: string; sizeBytes: number };
  noteTemplateId: string;
  doctorId: string;
  practiceId: string;
  rolloutToken: TemplateTwinRolloutToken;
  encounterMode: "text" | "dictation";
  evidenceText: string;
  expectedMappingConfirmation?: TemplateTwinStagingQaExpectedMappingConfirmation;
  operation: (providerVisitId: string | null) => Promise<T> | T;
  dependencies?: Partial<CertificationProviderDependencies>;
}): Promise<T> {
  if (!isTemplateTwinStagingQaFixtureSource(input.source)) {
    return input.operation(null);
  }
  try {
    return await runWithTemplateTwinStagingQaLifecycleGuard({
      noteTemplateId: input.noteTemplateId,
      actor: {
        userId: input.doctorId,
        practiceId: input.practiceId,
        rolloutToken: input.rolloutToken,
      },
      purpose: `certification-${input.encounterMode}`,
      evidenceText: input.evidenceText,
      requireConfirmedMappings: true,
      expectedMappingConfirmation: input.expectedMappingConfirmation,
      operation: input.operation,
      dependencies: {
        env: input.dependencies?.env ?? process.env,
        pinRollout: input.dependencies?.pinRollout ?? pinTemplateTwinRollout,
        confirmMappings:
          input.dependencies?.confirmMappings ??
          confirmTemplateTwinStagingQaMappings,
        // The caller already loaded this immutable source through the owned
        // template relation; mapping confirmation repeats doctor/practice and
        // exact-source ownership before any provider admission.
        inspect: async () => ({ stagingQa: true, source: input.source }),
      },
    });
  } catch (error) {
    if (error instanceof TemplateTwinStagingQaLifecycleGuardError) {
      throw new TemplateTwinStagingQaCertificationProviderError();
    }
    throw error;
  }
}
