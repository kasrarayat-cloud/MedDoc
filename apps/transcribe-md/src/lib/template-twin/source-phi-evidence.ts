import { z } from 'zod';

import { canonicalSha256 } from './canonical';

const SHA256 = /^[a-f0-9]{64}$/;

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

export function templateTwinSourcePhiScanEvidenceSha256(
  value: unknown,
): string | null {
  const parsed = TemplateTwinSourcePhiScanEvidenceSchema.safeParse(value);
  return parsed.success ? canonicalSha256(parsed.data) : null;
}
