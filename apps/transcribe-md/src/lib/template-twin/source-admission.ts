import { isTemplateTwinMalwareScanEvidenceValid } from "./malware-scan";
import { isTemplateTwinMetadataEvidenceValid } from "./source-metadata";

export const TEMPLATE_TWIN_SOURCE_ADMISSION_GATE_MESSAGE =
  "This Template Twin source is not bound to an admitted native-template quarantine record with exact clean-malware and metadata-minimization evidence. Upload and certify a new version.";

export interface TemplateTwinSourceAdmissionRecord {
  readonly practiceId: string;
  readonly lineageId: string;
  readonly objectVersionId?: string | null;
  readonly objectEtag?: string | null;
  readonly sha256: string;
  readonly sizeBytes: number;
  readonly validationStatus: string;
  readonly quarantineArtifact?: {
    readonly practiceId: string;
    readonly lineageId: string;
    readonly intakeMode: string;
    readonly sha256: string;
    readonly sizeBytes: number;
    readonly status: string;
    readonly malwareScanEvidence: unknown;
    readonly metadataMinimizationEvidence: unknown;
    readonly rejectionCodes: readonly string[];
    readonly scannedAt: Date | string | null;
    readonly admittedAt: Date | string | null;
  } | null;
}

function timestamp(value: Date | string | null | undefined): number | null {
  if (!value) return null;
  const parsed = value instanceof Date ? value : new Date(value);
  const milliseconds = parsed.valueOf();
  return Number.isNaN(milliseconds) ? null : milliseconds;
}

/**
 * One pure runtime contract shared by certification, activation, worker
 * selection, filling, signing, and download. Historical/synthetic rows that
 * predate raw first-write quarantine deliberately fail this check even when a
 * legacy certification remains present.
 */
export function isTemplateTwinSourceAdmissionCurrent(
  source: TemplateTwinSourceAdmissionRecord,
): boolean {
  const quarantine = source.quarantineArtifact;
  const scannedAt = timestamp(quarantine?.scannedAt);
  const admittedAt = timestamp(quarantine?.admittedAt);
  if (
    source.validationStatus !== "accepted" ||
    !source.objectVersionId?.trim() ||
    !source.objectEtag?.trim() ||
    !quarantine ||
    quarantine.status !== "ADMITTED" ||
    quarantine.intakeMode !== "NATIVE_TEMPLATE" ||
    quarantine.practiceId !== source.practiceId ||
    quarantine.lineageId !== source.lineageId ||
    quarantine.rejectionCodes.length !== 0 ||
    scannedAt === null ||
    admittedAt === null ||
    admittedAt < scannedAt
  ) {
    return false;
  }

  const malwareBinding = {
    evidence: quarantine.malwareScanEvidence,
    sourceSha256: quarantine.sha256,
    sourceSizeBytes: quarantine.sizeBytes,
    requireClean: true,
  } as const;
  return Boolean(
    isTemplateTwinMalwareScanEvidenceValid(malwareBinding) &&
      timestamp(malwareBinding.evidence.scannedAt) === scannedAt &&
      isTemplateTwinMetadataEvidenceValid({
        evidence: quarantine.metadataMinimizationEvidence,
        originalSha256: quarantine.sha256,
        minimizedSha256: source.sha256,
      }),
  );
}
