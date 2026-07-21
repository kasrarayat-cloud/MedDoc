import { describe, expect, it } from "vitest";

import {
  evaluateSyntheticQaResourceBoundary,
  isExactSyntheticQaRuntimeProfile,
} from "./synthetic-qa-runtime-profile";

const SYNTHETIC_QA_DATABASE_CREDENTIAL = "s".repeat(43);
const EXACT_SYNTHETIC_QA_ENVIRONMENT = Object.freeze({
  NODE_ENV: "production",
  QUILLMD_SERVICE_ROLE: "physician-app",
  QUILLMD_DATABASE_PRINCIPAL_PROFILE: "synthetic-disposable-qa-v1",
  TEMPLATE_TWIN_STAGING_QA_ENVIRONMENT: "qa",
  TEMPLATE_TWIN_STAGING_QA_RESOURCE_ATTESTATION: "isolated-disposable-qa-v1",
  TEMPLATE_TWIN_STORAGE_PROFILE: "qa",
  DATABASE_URL: `postgresql://meddoc_runtime:${SYNTHETIC_QA_DATABASE_CREDENTIAL}@postgres:5432/meddoc_qa_test?schema=public&options=-c%20search_path%3Dpg_catalog%2Cpublic`,
  REDIS_URL: "redis://redis:6379/15",
  MINIO_ENDPOINT: "minio:9000",
  MINIO_USE_SSL: "false",
  TRANSCRIBE_MD_MINIO_BUCKET: "transcribe-md-audio-qa",
  TRANSCRIBE_MD_TEMPLATE_BUCKET: "transcribe-md-template-artifacts-qa",
  ADMIN_SYNTHETIC_QA_SHARED_HOST_ATTESTATION:
    "accepted-isolated-synthetic-qa-shared-host",
  ADMIN_PUBLIC_HOST: "localhost",
  PHYSICIAN_PUBLIC_HOST: "localhost",
  AUTH_URL: "http://localhost:9020",
  NEXTAUTH_URL: "http://localhost:9020",
});

describe("synthetic QA runtime profile", () => {
  it("admits the exact disposable resource and runtime identity", () => {
    expect(
      evaluateSyntheticQaResourceBoundary(EXACT_SYNTHETIC_QA_ENVIRONMENT),
    ).toEqual({ allowed: true, environment: "qa" });
    expect(
      isExactSyntheticQaRuntimeProfile(EXACT_SYNTHETIC_QA_ENVIRONMENT),
    ).toBe(true);
  });

  it.each([
    ["environment", { TEMPLATE_TWIN_STAGING_QA_ENVIRONMENT: "production" }],
    ["production marker", { DEPLOYMENT_ENV: "prod" }],
    [
      "resource attestation",
      { TEMPLATE_TWIN_STAGING_QA_RESOURCE_ATTESTATION: "" },
    ],
    [
      "database host",
      {
        DATABASE_URL: `postgresql://meddoc_runtime:${SYNTHETIC_QA_DATABASE_CREDENTIAL}@db.internal:5432/meddoc_qa_test`,
      },
    ],
    [
      "database name",
      {
        DATABASE_URL: `postgresql://meddoc_runtime:${SYNTHETIC_QA_DATABASE_CREDENTIAL}@postgres:5432/meddoc`,
      },
    ],
    [
      "database port",
      {
        DATABASE_URL: `postgresql://meddoc_runtime:${SYNTHETIC_QA_DATABASE_CREDENTIAL}@postgres:5433/meddoc_qa_test`,
      },
    ],
    [
      "database option",
      {
        DATABASE_URL: `postgresql://meddoc_runtime:${SYNTHETIC_QA_DATABASE_CREDENTIAL}@postgres:5432/meddoc_qa_test?sslmode=disable`,
      },
    ],
    [
      "duplicate database option",
      {
        DATABASE_URL: `postgresql://meddoc_runtime:${SYNTHETIC_QA_DATABASE_CREDENTIAL}@postgres:5432/meddoc_qa_test?schema=public&schema=public`,
      },
    ],
    ["Redis namespace", { REDIS_URL: "redis://redis:6379/0" }],
    ["Redis host", { REDIS_URL: "redis://cache.internal:6379/15" }],
    ["object-store host", { MINIO_ENDPOINT: "storage.internal:9000" }],
    [
      "object-store TLS",
      {
        MINIO_ENDPOINT: "minio-qa.synthetic.test:9000",
        MINIO_USE_SSL: "false",
      },
    ],
    ["audio bucket", { TRANSCRIBE_MD_MINIO_BUCKET: "transcribe-md-audio" }],
    [
      "distinct buckets",
      { TRANSCRIBE_MD_TEMPLATE_BUCKET: "transcribe-md-audio-qa" },
    ],
    ["storage profile", { TEMPLATE_TWIN_STORAGE_PROFILE: "production" }],
  ] as const)("rejects a non-isolated %s", (_label, override) => {
    expect(
      evaluateSyntheticQaResourceBoundary({
        ...EXACT_SYNTHETIC_QA_ENVIRONMENT,
        ...override,
      }).allowed,
    ).toBe(false);
  });

  it.each([
    ["Node environment", { NODE_ENV: "development" }],
    ["service role", { QUILLMD_SERVICE_ROLE: "template-twin-admin-app" }],
    [
      "principal profile",
      { QUILLMD_DATABASE_PRINCIPAL_PROFILE: "exact-production-v1" },
    ],
    [
      "database login",
      {
        DATABASE_URL: `postgresql://meddoc:${SYNTHETIC_QA_DATABASE_CREDENTIAL}@postgres:5432/meddoc_qa_test?schema=public&options=-c%20search_path%3Dpg_catalog%2Cpublic`,
      },
    ],
    [
      "database credential shape",
      {
        DATABASE_URL:
          "postgresql://meddoc_runtime:short@postgres:5432/meddoc_qa_test?schema=public&options=-c%20search_path%3Dpg_catalog%2Cpublic",
      },
    ],
    [
      "canonical database options",
      {
        DATABASE_URL: `postgresql://meddoc_runtime:${SYNTHETIC_QA_DATABASE_CREDENTIAL}@postgres:5432/meddoc_qa_test`,
      },
    ],
    [
      "shared-host attestation",
      { ADMIN_SYNTHETIC_QA_SHARED_HOST_ATTESTATION: "unreviewed" },
    ],
    ["admin host", { ADMIN_PUBLIC_HOST: "admin.quillmd.com" }],
    ["physician host", { PHYSICIAN_PUBLIC_HOST: "app.quillmd.com" }],
    ["Auth.js origin", { AUTH_URL: "https://app.quillmd.com" }],
    ["NextAuth origin", { NEXTAUTH_URL: "https://app.quillmd.com" }],
  ] as const)("rejects a mismatched %s", (_label, override) => {
    expect(
      isExactSyntheticQaRuntimeProfile({
        ...EXACT_SYNTHETIC_QA_ENVIRONMENT,
        ...override,
      }),
    ).toBe(false);
  });
});
