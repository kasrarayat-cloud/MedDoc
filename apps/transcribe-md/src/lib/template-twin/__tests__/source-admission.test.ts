import { createHash } from "node:crypto";

import { describe, expect, it } from "vitest";

import {
  isTemplateTwinSourceAdmissionCurrent,
  type TemplateTwinSourceAdmissionRecord,
} from "../source-admission";

function admittedSource(): TemplateTwinSourceAdmissionRecord {
  const malware = {
    profileVersion: "template-twin-clamd-instream-v1",
    scanner: "clamav-clamd",
    transport: "unix-domain-socket",
    engineVersion: "1.4.3",
    signatureVersion: "27888",
    sourceSha256: "a".repeat(64),
    sourceSizeBytes: 140,
    verdict: "clean",
    threatNameSha256: null,
    scannedAt: "2026-07-19T00:00:00.000Z",
  } as const;
  return {
    practiceId: "practice-synthetic-admission",
    lineageId: "lineage-synthetic-admission",
    objectVersionId: "source-version",
    objectEtag: "source-etag",
    sha256: "c".repeat(64),
    sizeBytes: 120,
    validationStatus: "accepted",
    quarantineArtifact: {
      practiceId: "practice-synthetic-admission",
      lineageId: "lineage-synthetic-admission",
      intakeMode: "NATIVE_TEMPLATE",
      sha256: malware.sourceSha256,
      sizeBytes: malware.sourceSizeBytes,
      status: "ADMITTED",
      malwareScanEvidence: {
        ...malware,
        attestationSha256: createHash("sha256")
          .update(JSON.stringify(malware))
          .digest("hex"),
      },
      metadataMinimizationEvidence: {
        profileVersion: "template-twin-docx-metadata-minimization-v1",
        originalSha256: malware.sourceSha256,
        minimizedSha256: "c".repeat(64),
        replacedParts: [],
        zipEntryTimestampsNormalized: true,
      },
      rejectionCodes: [],
      scannedAt: new Date(malware.scannedAt),
      admittedAt: new Date("2026-07-19T00:01:00.000Z"),
    },
  };
}

describe("Template Twin source admission runtime contract", () => {
  it("accepts an exact native, clean, minimized, admitted source binding", () => {
    expect(isTemplateTwinSourceAdmissionCurrent(admittedSource())).toBe(true);
  });

  it.each([
    ["missing quarantine", (source: TemplateTwinSourceAdmissionRecord) => ({ ...source, quarantineArtifact: null })],
    ["legacy certification without provider identity", (source: TemplateTwinSourceAdmissionRecord) => ({ ...source, objectVersionId: null })],
    ["completed-example mode", (source: TemplateTwinSourceAdmissionRecord) => ({ ...source, quarantineArtifact: { ...source.quarantineArtifact!, intakeMode: "COMPLETED_EXAMPLE" } })],
    ["tampered malware receipt", (source: TemplateTwinSourceAdmissionRecord) => ({ ...source, quarantineArtifact: { ...source.quarantineArtifact!, malwareScanEvidence: { ...(source.quarantineArtifact!.malwareScanEvidence as Record<string, unknown>), attestationSha256: "f".repeat(64) } } })],
    ["stale minimized hash", (source: TemplateTwinSourceAdmissionRecord) => ({ ...source, sha256: "d".repeat(64) })],
    ["rejection code", (source: TemplateTwinSourceAdmissionRecord) => ({ ...source, quarantineArtifact: { ...source.quarantineArtifact!, rejectionCodes: ["SYNTHETIC_REJECTION"] } })],
    ["admission before scan", (source: TemplateTwinSourceAdmissionRecord) => ({ ...source, quarantineArtifact: { ...source.quarantineArtifact!, admittedAt: new Date("2026-07-18T23:59:59.000Z") } })],
  ])("rejects %s", (_label, mutate) => {
    expect(isTemplateTwinSourceAdmissionCurrent(mutate(admittedSource()))).toBe(false);
  });
});
