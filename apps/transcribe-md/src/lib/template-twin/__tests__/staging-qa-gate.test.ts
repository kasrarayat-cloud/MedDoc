import { describe, expect, it } from "vitest";

import { evaluateTemplateTwinStagingQaGate } from "../staging-qa-gate";

const SAFE_ENV = Object.freeze({
  TEMPLATE_TWIN_STAGING_QA_ENABLED: "true",
  TEMPLATE_TWIN_STAGING_QA_ENVIRONMENT: "qa",
  TEMPLATE_TWIN_STAGING_QA_RESOURCE_ATTESTATION: "isolated-disposable-qa-v1",
  TEMPLATE_TWIN_STORAGE_PROFILE: "qa",
  MOCK_AI_CALLS: "true",
  MOCK_TEMPLATE_TWIN_E2E: "true",
  DATABASE_URL:
    "postgresql://synthetic:synthetic@127.0.0.1:5432/meddoc_qa_test",
  REDIS_URL: "redis://redis:6379/15",
  MINIO_ENDPOINT: "minio:9000",
  MINIO_USE_SSL: "false",
  TRANSCRIBE_MD_MINIO_BUCKET: "transcribe-md-audio-qa",
  TRANSCRIBE_MD_TEMPLATE_BUCKET: "transcribe-md-template-artifacts-qa",
});

describe("Template Twin synthetic staging process gate", () => {
  it("admits only the exact isolated synthetic configuration", () => {
    expect(evaluateTemplateTwinStagingQaGate(SAFE_ENV)).toEqual({
      allowed: true,
      environment: "qa",
    });
  });

  it.each([
    ["TEMPLATE_TWIN_STAGING_QA_ENABLED", "TRUE", "STAGING_QA_DISABLED"],
    [
      "TEMPLATE_TWIN_STAGING_QA_ENVIRONMENT",
      " qa ",
      "STAGING_QA_ENVIRONMENT_INVALID",
    ],
    [
      "TEMPLATE_TWIN_STORAGE_PROFILE",
      "QA",
      "STAGING_QA_STORAGE_PROFILE_INVALID",
    ],
    [
      "TEMPLATE_TWIN_STAGING_QA_RESOURCE_ATTESTATION",
      "",
      "STAGING_QA_RESOURCE_ATTESTATION_INVALID",
    ],
    ["MOCK_AI_CALLS", "false", "STAGING_QA_MOCK_PROVIDER_DISABLED"],
    ["MOCK_TEMPLATE_TWIN_E2E", "", "STAGING_QA_MOCK_PROVIDER_DISABLED"],
  ] as const)("fails closed for non-exact %s=%j", (key, value, code) => {
    expect(
      evaluateTemplateTwinStagingQaGate({ ...SAFE_ENV, [key]: value }),
    ).toEqual({ allowed: false, code });
  });

  it.each([
    "postgresql://synthetic:synthetic@127.0.0.1:5432/meddoc",
    "https://example.test/meddoc_qa_test",
    "not-a-url",
    "postgresql://synthetic:synthetic@127.0.0.1:5432/meddoc_qa_test/extra",
  ])("rejects a database URL that is not positively isolated: %s", (url) => {
    expect(
      evaluateTemplateTwinStagingQaGate({ ...SAFE_ENV, DATABASE_URL: url }),
    ).toEqual({
      allowed: false,
      code: "STAGING_QA_DATABASE_NOT_ISOLATED",
    });
  });

  it.each([
    [undefined, "missing Redis URL"],
    ["redis://redis:6379/0", "shared Redis database zero"],
    ["redis://redis:6379", "implicit Redis database zero"],
    ["redis://redis:6379/15?db=0", "ambiguous Redis query override"],
    ["redis://cache.internal:6379/15", "unattested remote Redis host"],
    ["https://redis-qa.synthetic.test/15", "non-Redis protocol"],
  ] as const)("rejects %s (%s)", (redisUrl, reason) => {
    expect(
      evaluateTemplateTwinStagingQaGate({
        ...SAFE_ENV,
        REDIS_URL: redisUrl,
      }),
      reason,
    ).toEqual({ allowed: false, code: "STAGING_QA_REDIS_NOT_ISOLATED" });
  });

  it.each([
    ["MINIO_ENDPOINT", "storage.internal:9000"],
    ["MINIO_ENDPOINT", "https://minio:9000"],
    ["MINIO_USE_SSL", "true"],
    ["TRANSCRIBE_MD_MINIO_BUCKET", "transcribe-md-audio"],
    ["TRANSCRIBE_MD_TEMPLATE_BUCKET", "transcribe-md-template-artifacts"],
    ["TRANSCRIBE_MD_TEMPLATE_BUCKET", "transcribe-md-audio-qa"],
  ] as const)("rejects non-isolated object storage %s=%j", (key, value) => {
    expect(
      evaluateTemplateTwinStagingQaGate({ ...SAFE_ENV, [key]: value }),
    ).toEqual({
      allowed: false,
      code: "STAGING_QA_OBJECT_STORAGE_NOT_ISOLATED",
    });
  });

  it("allows a QA-named remote object store only with explicit TLS", () => {
    expect(
      evaluateTemplateTwinStagingQaGate({
        ...SAFE_ENV,
        MINIO_ENDPOINT: "minio-qa.synthetic.test:9000",
        MINIO_USE_SSL: "true",
      }),
    ).toEqual({ allowed: true, environment: "qa" });
  });
});
