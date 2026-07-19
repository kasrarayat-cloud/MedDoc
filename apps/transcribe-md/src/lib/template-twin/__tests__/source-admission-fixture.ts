import { createHash } from "node:crypto";

export function syntheticSourceAdmission(input: {
  practiceId: string;
  lineageId: string;
  minimizedSha256: string;
  minimizedSizeBytes: number;
  rawSha256?: string;
  rawSizeBytes?: number;
}) {
  const rawSha256 = input.rawSha256 ?? "a".repeat(64);
  const rawSizeBytes = input.rawSizeBytes ?? input.minimizedSizeBytes + 20;
  const malware = {
    profileVersion: "template-twin-clamd-instream-v1",
    scanner: "clamav-clamd",
    transport: "unix-domain-socket",
    engineVersion: "1.4.3",
    signatureVersion: "27888",
    sourceSha256: rawSha256,
    sourceSizeBytes: rawSizeBytes,
    verdict: "clean",
    threatNameSha256: null,
    scannedAt: "2026-07-15T11:30:00.000Z",
  } as const;

  return {
    practiceId: input.practiceId,
    lineageId: input.lineageId,
    objectVersionId: "provider-source-version-synthetic",
    objectEtag: "provider-source-etag-synthetic",
    sha256: input.minimizedSha256,
    sizeBytes: input.minimizedSizeBytes,
    validationStatus: "accepted",
    quarantineArtifact: {
      practiceId: input.practiceId,
      lineageId: input.lineageId,
      intakeMode: "NATIVE_TEMPLATE",
      sha256: rawSha256,
      sizeBytes: rawSizeBytes,
      status: "ADMITTED",
      malwareScanEvidence: {
        ...malware,
        attestationSha256: createHash("sha256")
          .update(JSON.stringify(malware))
          .digest("hex"),
      },
      metadataMinimizationEvidence: {
        profileVersion: "template-twin-docx-metadata-minimization-v1",
        originalSha256: rawSha256,
        minimizedSha256: input.minimizedSha256,
        replacedParts: [] as string[],
        zipEntryTimestampsNormalized: true,
      },
      rejectionCodes: [] as string[],
      scannedAt: new Date(malware.scannedAt),
      admittedAt: new Date("2026-07-15T11:31:00.000Z"),
    },
  };
}
