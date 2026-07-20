import { createHash } from "node:crypto";

export const MFA_SECRET_BACKFILL_MANIFEST_DOMAIN =
  "quillmd:mfa-secret-backfill:candidate-manifest:v1" as const;

export interface MfaSecretBackfillManifestEntry {
  id: string;
  practiceId: string;
  mfaEnabled: boolean;
  verifiedTimestamp: string;
  secretState: "encrypted" | "legacy" | "none" | "invalid";
  totalRecoveryVerifierCount: number;
  currentRecoveryVerifierCount: number;
  legacyRecoveryVerifierCount: number;
}

/**
 * Review binding for a candidate set. Inputs deliberately contain no secret,
 * ciphertext, key ID, or verifier value, so the published aggregate digest
 * cannot become an offline oracle for old low-entropy recovery codes.
 */
export function buildMfaSecretBackfillCandidateManifest(
  entries: readonly MfaSecretBackfillManifestEntry[],
): string {
  const digest = createHash("sha256");
  digest.update(`${MFA_SECRET_BACKFILL_MANIFEST_DOMAIN}\n`, "utf8");
  for (const entry of [...entries].sort((left, right) =>
    left.id < right.id ? -1 : left.id > right.id ? 1 : 0,
  )) {
    digest.update(
      `${JSON.stringify([
        entry.id,
        entry.practiceId,
        entry.mfaEnabled,
        entry.verifiedTimestamp,
        entry.secretState,
        entry.totalRecoveryVerifierCount,
        entry.currentRecoveryVerifierCount,
        entry.legacyRecoveryVerifierCount,
      ])}\n`,
      "utf8",
    );
  }
  return digest.digest("hex");
}
