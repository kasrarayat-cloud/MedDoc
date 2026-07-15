import { z } from 'zod';

import { canonicalSha256 } from './canonical';

const SHA256 = /^[a-f0-9]{64}$/;

/** Stable physician-visible safety gate for source artifacts created before,
 * outside, or after tampering with the current safe-alpha inspection
 * profile. Keep the code stable so UI, audit, and support material can refer
 * to one remediation path without exposing scan contents. */
export const TEMPLATE_TWIN_SOURCE_PROVENANCE_GATE_CODE =
  'TT_SOURCE_PROVENANCE_CURRENT_PROFILE_REQUIRED';
export const TEMPLATE_TWIN_SOURCE_PROVENANCE_GATE_MESSAGE =
  `${TEMPLATE_TWIN_SOURCE_PROVENANCE_GATE_CODE}: This Template Twin source is not bound to the current privacy and static-asset safety inspection. Upload a newly inspected version before testing, and certify that version before clinical review or rendering.`;

export const TemplateTwinSourcePhiScanEvidenceSchema = z
  .object({
    profileVersion: z.literal('template-twin-source-phi-safe-alpha-v1'),
    provider: z.literal('anthropic'),
    model: z.string().trim().min(1).max(120),
    scannedAt: z.string().datetime({ offset: true }),
    scannedPartCount: z.number().int().positive(),
    approvedStaticAssetPolicySha256: z.string().regex(SHA256),
    approvedStaticAssetCount: z.number().int().min(0).max(100),
    approvedStaticAssetUsedCount: z.number().int().min(0).max(100),
    approvedStaticAssetUsageSha256: z.string().regex(SHA256),
  })
  .strict()
  .superRefine((value, context) => {
    if (value.approvedStaticAssetUsedCount > value.approvedStaticAssetCount) {
      context.addIssue({
        code: 'custom',
        path: ['approvedStaticAssetUsedCount'],
        message: 'Used static assets cannot exceed the approved set.',
      });
    }
  });

export type TemplateTwinSourcePhiScanEvidence = z.infer<
  typeof TemplateTwinSourcePhiScanEvidenceSchema
>;

export interface TemplateTwinSourceProvenance {
  evidence: TemplateTwinSourcePhiScanEvidence;
  evidenceSha256: string;
}

export class TemplateTwinSourceProvenanceError extends Error {
  readonly code = TEMPLATE_TWIN_SOURCE_PROVENANCE_GATE_CODE;

  constructor(
    readonly reason:
      | 'evidence_not_current'
      | 'binding_missing'
      | 'binding_mismatch',
  ) {
    super(TEMPLATE_TWIN_SOURCE_PROVENANCE_GATE_MESSAGE);
    this.name = 'TemplateTwinSourceProvenanceError';
  }
}

export function templateTwinSourcePhiScanEvidenceSha256(
  value: unknown,
): string | null {
  const parsed = TemplateTwinSourcePhiScanEvidenceSchema.safeParse(value);
  return parsed.success ? canonicalSha256(parsed.data) : null;
}

/**
 * Parse the current safe-alpha profile and, for any post-certification or
 * persisted-proof use, require an exact canonical hash binding. Callers must
 * set `requireBinding` explicitly: omitted bindings are permitted only while
 * creating the pre-certification synthetic proof that will carry the returned
 * hash forward.
 */
export function assertTemplateTwinSourceProvenance(input: {
  privacyScanEvidence: unknown;
  requireBinding: boolean;
  boundEvidenceSha256?: string | null;
}): TemplateTwinSourceProvenance {
  const parsed = TemplateTwinSourcePhiScanEvidenceSchema.safeParse(
    input.privacyScanEvidence,
  );
  if (!parsed.success) {
    throw new TemplateTwinSourceProvenanceError('evidence_not_current');
  }

  const evidenceSha256 = canonicalSha256(parsed.data);
  if (input.requireBinding) {
    if (!input.boundEvidenceSha256 || !SHA256.test(input.boundEvidenceSha256)) {
      throw new TemplateTwinSourceProvenanceError('binding_missing');
    }
    if (input.boundEvidenceSha256 !== evidenceSha256) {
      throw new TemplateTwinSourceProvenanceError('binding_mismatch');
    }
  }

  return { evidence: parsed.data, evidenceSha256 };
}

/** Attach the exact pre-storage scan evidence hash to the independently
 * derived synthetic round-trip proof. Certification later requires this
 * binding to still equal the source artifact's current canonical evidence. */
export function bindTemplateTwinSyntheticProofToSourceProvenance(
  roundTripVerification: object,
  evidenceSha256: string,
): object {
  if (!SHA256.test(evidenceSha256)) {
    throw new TemplateTwinSourceProvenanceError('binding_missing');
  }
  return {
    ...roundTripVerification,
    sourcePrivacyScanEvidenceSha256: evidenceSha256,
  };
}

export function templateTwinSyntheticProofSourceEvidenceSha256(
  roundTripVerification: unknown,
): string | null {
  if (
    typeof roundTripVerification !== 'object' ||
    roundTripVerification === null ||
    Array.isArray(roundTripVerification)
  ) {
    return null;
  }
  const value = (
    roundTripVerification as Record<string, unknown>
  ).sourcePrivacyScanEvidenceSha256;
  return typeof value === 'string' && SHA256.test(value) ? value : null;
}
