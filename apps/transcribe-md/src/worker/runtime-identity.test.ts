import { readFileSync } from "node:fs";
import { resolve } from "node:path";

import { describe, expect, it } from "vitest";

import {
  assertTranscribeMdWorkerRuntimeIdentity,
  TranscribeMdWorkerRuntimeIdentityError,
} from "./runtime-identity";

const exactProductionEnvironment = (): Record<string, string | undefined> => ({
  NODE_ENV: "production",
  QUILLMD_SERVICE_ROLE: "transcribe-md-worker",
  QUILLMD_DATABASE_PRINCIPAL_PROFILE: "exact-production-v1",
});

describe("TranscribeMD worker runtime identity", () => {
  it("accepts the exact production worker role", () => {
    expect(() =>
      assertTranscribeMdWorkerRuntimeIdentity(exactProductionEnvironment()),
    ).not.toThrow();
  });

  it.each([
    "meddoc-pro-app",
    "physician-app",
    "template-twin-admin-app",
    "template-twin-admin-control",
    "template-twin-audit-dispatcher",
    "auth-email-dispatcher",
  ])("rejects the known but wrong %s role", (role) => {
    expect(() =>
      assertTranscribeMdWorkerRuntimeIdentity({
        ...exactProductionEnvironment(),
        QUILLMD_SERVICE_ROLE: role,
      }),
    ).toThrow(TranscribeMdWorkerRuntimeIdentityError);
  });

  it.each([undefined, "", " transcribe-md-worker ", "unknown-worker"])(
    "rejects a non-exact production role (%s)",
    (role) => {
      expect(() =>
        assertTranscribeMdWorkerRuntimeIdentity({
          ...exactProductionEnvironment(),
          QUILLMD_SERVICE_ROLE: role,
        }),
      ).toThrow(TranscribeMdWorkerRuntimeIdentityError);
    },
  );

  it("rejects a configured wrong role outside production", () => {
    expect(() =>
      assertTranscribeMdWorkerRuntimeIdentity({
        NODE_ENV: "development",
        QUILLMD_SERVICE_ROLE: "physician-app",
      }),
    ).toThrow(TranscribeMdWorkerRuntimeIdentityError);
  });

  it("permits truly identity-free local development", () => {
    expect(() =>
      assertTranscribeMdWorkerRuntimeIdentity({ NODE_ENV: "development" }),
    ).not.toThrow();
  });

  it("keeps the exact-role assertion ahead of database and queue startup", () => {
    const source = readFileSync(resolve(process.cwd(), "src/worker.ts"), "utf8");
    const roleAssertion = source.indexOf(
      "assertTranscribeMdWorkerRuntimeIdentity(process.env)",
    );
    const runtimeProtocol = source.indexOf(
      "assertQuillmdRuntimeProtocol(process.env)",
      roleAssertion,
    );
    const databaseProof = source.indexOf(
      "assertProductionRuntimeDatabasePrincipal({",
      roleAssertion,
    );
    const queueConstruction = source.indexOf("new Worker<", roleAssertion);

    expect(roleAssertion).toBeGreaterThan(-1);
    expect(runtimeProtocol).toBeGreaterThan(roleAssertion);
    expect(databaseProof).toBeGreaterThan(runtimeProtocol);
    expect(queueConstruction).toBeGreaterThan(databaseProof);
  });
});
