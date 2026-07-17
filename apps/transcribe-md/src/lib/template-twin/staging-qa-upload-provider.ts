import { createHash } from "node:crypto";

import {
  TEMPLATE_TWIN_SYNTHETIC_QA_FIXTURE_VERSION,
  TEMPLATE_TWIN_SYNTHETIC_QA_MODE,
  TEMPLATE_TWIN_SYNTHETIC_QA_TRANSCRIPT,
  SyntheticQaProviderContextError,
  assertTemplateTwinSyntheticQaProviderEnvironment,
  runWithTemplateTwinSyntheticQaProviderContext,
  type SyntheticQaProviderEnvironment,
} from "@meddoc/ai";

import {
  pinTemplateTwinRollout,
  type TemplateTwinRolloutToken,
} from "./rollout";
import { isTemplateTwinStagingQaFixtureSource } from "./staging-qa-fixtures";
import { assertTemplateTwinStagingQaGate } from "./staging-qa-gate";

export const TEMPLATE_TWIN_STAGING_QA_UPLOAD_PROVIDER_CODE =
  "TEMPLATE_TWIN_STAGING_QA_UPLOAD_PROVIDER_UNAVAILABLE" as const;

export class TemplateTwinStagingQaUploadProviderError extends Error {
  readonly code = TEMPLATE_TWIN_STAGING_QA_UPLOAD_PROVIDER_CODE;

  constructor() {
    super("Template Twin synthetic QA is unavailable.");
    this.name = "TemplateTwinStagingQaUploadProviderError";
  }
}

interface UploadProviderDependencies {
  readonly env: SyntheticQaProviderEnvironment;
  readonly pinRollout: (input: {
    practiceId: string;
    env?: Readonly<Record<string, string | undefined>>;
  }) => Promise<TemplateTwinRolloutToken>;
}

function digest(value: string): string {
  return createHash("sha256").update(value, "utf8").digest("hex");
}

function deterministicClaimId(value: string): string {
  const hash = digest(`template-twin-staging-upload-claim:${value}`);
  return `${hash.slice(0, 8)}-${hash.slice(8, 12)}-4${hash.slice(13, 16)}-8${hash.slice(17, 20)}-${hash.slice(20, 32)}`;
}

function sameRolloutGeneration(
  expected: TemplateTwinRolloutToken,
  current: TemplateTwinRolloutToken,
): boolean {
  return (
    expected.practiceId === current.practiceId &&
    expected.globalGeneration === current.globalGeneration &&
    expected.practiceGeneration === current.practiceGeneration
  );
}

/**
 * Admit the exact byte-reviewed staging source before draft compilation.
 *
 * The callback starts inside a deterministic provider context, so compilation,
 * source privacy inspection, and semantic proposal cannot fall through to a
 * live provider. `createTemplateTwinDraft` still owns the transactional final
 * rollout claim; revocation after this admission leaves any written object
 * unclaimed for the durable reconciler instead of creating a draft.
 */
export async function runWithTemplateTwinStagingQaUploadProvider<T>(input: {
  source: { readonly sha256: string; readonly sizeBytes: number };
  actor: {
    readonly userId: string;
    readonly practiceId: string;
    readonly rolloutToken: TemplateTwinRolloutToken;
  };
  operation: (providerVisitId: string) => Promise<T> | T;
  dependencies?: Partial<UploadProviderDependencies>;
}): Promise<T> {
  if (!isTemplateTwinStagingQaFixtureSource(input.source)) {
    throw new TemplateTwinStagingQaUploadProviderError();
  }

  const env = input.dependencies?.env ?? process.env;
  const pinRollout = input.dependencies?.pinRollout ?? pinTemplateTwinRollout;
  let currentToken: TemplateTwinRolloutToken;
  try {
    assertTemplateTwinStagingQaGate(env);
    assertTemplateTwinSyntheticQaProviderEnvironment(env);
    currentToken = await pinRollout({
      practiceId: input.actor.practiceId,
      env,
    });
  } catch {
    throw new TemplateTwinStagingQaUploadProviderError();
  }
  if (!sameRolloutGeneration(input.actor.rolloutToken, currentToken)) {
    throw new TemplateTwinStagingQaUploadProviderError();
  }

  const identity = digest(
    [
      "template-twin-staging-upload-v1",
      input.source.sha256,
      String(input.source.sizeBytes),
      input.actor.practiceId,
      input.actor.userId,
      currentToken.globalGeneration.toString(),
      currentToken.practiceGeneration.toString(),
    ].join(":"),
  );
  const providerVisitId = `template-twin-staging-upload-visit:${identity}`;
  const requestSha256 = digest(
    JSON.stringify({
      contract: "template-twin-staging-upload-provider-v1",
      sourceSha256: input.source.sha256,
      sourceSizeBytes: input.source.sizeBytes,
      practiceId: input.actor.practiceId,
      globalGeneration: currentToken.globalGeneration.toString(),
      practiceGeneration: currentToken.practiceGeneration.toString(),
    }),
  );

  try {
    return await runWithTemplateTwinSyntheticQaProviderContext(
      {
        mode: TEMPLATE_TWIN_SYNTHETIC_QA_MODE,
        fixtureVersion: TEMPLATE_TWIN_SYNTHETIC_QA_FIXTURE_VERSION,
        runId: `template-twin-staging-upload-run:${identity}`,
        visitId: providerVisitId,
        practiceId: input.actor.practiceId,
        requestSha256,
        attempt: 1,
        workerClaimId: deterministicClaimId(identity),
        pinnedGlobalGeneration: currentToken.globalGeneration,
        pinnedPracticeGeneration: currentToken.practiceGeneration,
        evidenceText: TEMPLATE_TWIN_SYNTHETIC_QA_TRANSCRIPT,
      },
      () => input.operation(providerVisitId),
      env,
    );
  } catch (error) {
    if (error instanceof SyntheticQaProviderContextError) {
      throw new TemplateTwinStagingQaUploadProviderError();
    }
    throw error;
  }
}
