import { createHash } from "node:crypto";

import { canonicalSha256 } from "./canonical";

export const TEMPLATE_TWIN_STAGING_QA_REQUEST_CONTRACT_VERSION =
  "template-twin-staging-qa-request/1.0.0" as const;

/** One request identity is persisted on both the child admission and run. */
export function templateTwinStagingQaRunRequestSha256(input: {
  practiceId: string;
  doctorId: string;
  idempotencyKey: string;
}): string {
  return canonicalSha256({
    contractVersion: TEMPLATE_TWIN_STAGING_QA_REQUEST_CONTRACT_VERSION,
    practiceId: input.practiceId,
    doctorId: input.doctorId,
    idempotencyKey: input.idempotencyKey,
  });
}

export function templateTwinStagingQaPayloadSha256(input: {
  templateId: string;
  expectedTemplateVersion: number;
  mode: "typed" | "mock_voice";
  fixtureVersion: string;
  evidenceText: string;
}): string {
  const evidenceSha256 = createHash("sha256")
    .update(input.evidenceText, "utf8")
    .digest("hex");
  return canonicalSha256({
    contractVersion: TEMPLATE_TWIN_STAGING_QA_REQUEST_CONTRACT_VERSION,
    templateId: input.templateId,
    expectedTemplateVersion: input.expectedTemplateVersion,
    mode: input.mode,
    fixtureVersion: input.fixtureVersion,
    evidenceSha256,
  });
}
