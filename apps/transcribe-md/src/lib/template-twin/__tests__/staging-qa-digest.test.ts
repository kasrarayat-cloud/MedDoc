import { describe, expect, it } from "vitest";

import { canonicalSha256 } from "../canonical";
import {
  TEMPLATE_TWIN_STAGING_QA_REQUEST_CONTRACT_VERSION,
  templateTwinStagingQaRunRequestSha256,
} from "../staging-qa-digest";

describe("durable synthetic QA request identity", () => {
  it("uses the run-lineage contract for the tenant, physician, and idempotency key", () => {
    const input = {
      practiceId: "practice-durable-request-synthetic",
      doctorId: "doctor-durable-request-synthetic",
      idempotencyKey: "durable-request-synthetic-0001",
    };

    expect(templateTwinStagingQaRunRequestSha256(input)).toBe(
      canonicalSha256({
        contractVersion: TEMPLATE_TWIN_STAGING_QA_REQUEST_CONTRACT_VERSION,
        practiceId: input.practiceId,
        doctorId: input.doctorId,
        idempotencyKey: input.idempotencyKey,
      }),
    );
  });
});
