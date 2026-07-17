import { createHash } from "node:crypto";

import { canonicalSha256 } from "./canonical";

export const TEMPLATE_TWIN_STAGING_QA_REQUEST_CONTRACT_VERSION =
  "template-twin-staging-qa-request/1.0.0" as const;

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
