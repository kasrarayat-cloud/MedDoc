import { createHash } from 'node:crypto';

import { z } from 'zod';

import { canonicalJson } from '../canonical';

export const MEDIA_REVIEW_EVIDENCE_VERSION =
  'template-twin-media-review-worksheet/1.0.0' as const;

const Sha256Schema = z.string().regex(/^[a-f0-9]{64}$/);
const CommitShaSchema = z.string().regex(/^[a-f0-9]{40}$/);

export const MediaReviewEvidencePayloadSchema = z
  .object({
    contractVersion: z.literal(MEDIA_REVIEW_EVIDENCE_VERSION),
    sourceCommit: CommitShaSchema,
    authorizationEffect: z.literal('none_authenticated_quillmd_workflow_required'),
    reviewer: z
      .object({
        name: z.string().min(2).max(160),
        professionalRole: z.literal('authorized_practice_administrator'),
        practiceId: z.string().min(2).max(160),
        jurisdiction: z.string().min(2).max(160),
      })
      .strict(),
    reviewedAtIso: z.string().datetime({ offset: true }),
    assetMetadata: z
      .object({
        practiceScopedSha256: Sha256Schema,
        mimeType: z.literal('image/png'),
        width: z.number().int().positive().max(4_096),
        height: z.number().int().positive().max(4_096),
        byteCount: z.number().int().positive().max(5 * 1024 * 1024),
        scannerVersion: z.string().min(1).max(160),
        ocrEngineVersion: z.string().min(1).max(160),
        ocrEvidenceSha256: Sha256Schema,
        metadataEvidenceSha256: Sha256Schema,
        privacyEvidenceSha256: Sha256Schema,
        privacyScanResult: z.enum(['clear', 'rejected', 'unavailable']),
      })
      .strict(),
    retentionAndVersion: z
      .object({
        currentAuthenticatedState: z.enum([
          'pending_review',
          'approved',
          'rejected',
          'revoked',
          'not_available',
        ]),
        decisionVersion: z.number().int().positive().nullable(),
        retentionPolicyStatus: z.enum([
          'confirmed',
          'policy_review_required',
          'not_available',
        ]),
        retentionPolicyReference: z.string().min(2).max(240).nullable(),
      })
      .strict()
      .superRefine((value, context) => {
        if (
          (value.currentAuthenticatedState === 'not_available') !==
          (value.decisionVersion === null)
        ) {
          context.addIssue({
            code: 'custom',
            path: ['decisionVersion'],
            message:
              'Decision version is required for an authenticated state and must be null when state is unavailable.',
          });
        }
        if (
          (value.retentionPolicyStatus === 'confirmed') !==
          (value.retentionPolicyReference !== null)
        ) {
          context.addIssue({
            code: 'custom',
            path: ['retentionPolicyReference'],
            message:
              'A retention policy reference is required only when policy status is confirmed.',
          });
        }
      }),
    checklist: z
      .object({
        reusablePracticeLogoOrStaticAsset: z.boolean(),
        containsPatientInformation: z.boolean(),
        containsPatientOrPersonNamesOrIdentifiers: z.boolean(),
        containsAuthorizedOrganizationOrPracticeName: z.boolean(),
        containsPersonPhotographs: z.boolean(),
        containsBarcodesOrMachineReadableIdentifiers: z.boolean(),
        containsHiddenOrUnreviewedMetadata: z.boolean(),
        organizationOwnsOrMayUseAsset: z.boolean(),
      })
      .strict(),
    recommendation: z.enum([
      'recommend_authenticated_approval',
      'recommend_authenticated_rejection',
      'defer_for_privacy_review',
    ]),
    reason: z.string().min(10).max(1_000),
    attestation: z
      .object({
        IAmAuthorizedForThisPractice: z.literal(true),
        IReviewedOnlyThroughTheApprovedLocalOrAuthenticatedWorkflow: z.literal(true),
        IDidNotUploadTheAssetToGitHubOrCI: z.literal(true),
        IUnderstandFounderApprovalIsNotClinicalOrPrivacyApproval: z.literal(true),
        IUnderstandApprovalIsPracticeScoped: z.literal(true),
        IUnderstandAnyByteChangeRequiresNewApproval: z.literal(true),
        IConfirmedRetentionAndVersionStatusFromAuthenticatedWorkflow: z.literal(true),
        IUnderstandRevocationBlocksNewCertificationButDoesNotAlterSignedDocuments: z.literal(true),
        IUnderstandThisWorksheetCannotApproveTheAsset: z.literal(true),
      })
      .strict(),
  })
  .strict()
  .superRefine((payload, context) => {
    if (payload.recommendation !== 'recommend_authenticated_approval') return;
    const checklist = payload.checklist;
    if (
      !checklist.reusablePracticeLogoOrStaticAsset ||
      checklist.containsPatientInformation ||
      checklist.containsPatientOrPersonNamesOrIdentifiers ||
      checklist.containsPersonPhotographs ||
      checklist.containsBarcodesOrMachineReadableIdentifiers ||
      checklist.containsHiddenOrUnreviewedMetadata ||
      !checklist.organizationOwnsOrMayUseAsset ||
      payload.assetMetadata.privacyScanResult !== 'clear'
    ) {
      context.addIssue({
        code: 'custom',
        path: ['recommendation'],
        message:
          'Approval may be recommended only for an authorized reusable practice asset with clear privacy evidence and no patient/identifier content.',
      });
    }
  });

export const MediaReviewEvidenceFileSchema = z
  .object({
    payload: MediaReviewEvidencePayloadSchema,
    payloadSha256: Sha256Schema,
  })
  .strict();
export type MediaReviewEvidenceFile = z.infer<typeof MediaReviewEvidenceFileSchema>;

export function createMediaReviewEvidenceFile(
  payload: z.input<typeof MediaReviewEvidencePayloadSchema>,
): MediaReviewEvidenceFile {
  const parsed = MediaReviewEvidencePayloadSchema.parse(payload);
  return {
    payload: parsed,
    payloadSha256: createHash('sha256').update(canonicalJson(parsed), 'utf8').digest('hex'),
  };
}

export function validateMediaReviewEvidenceFile(input: {
  expectedSourceCommit: string;
  evidenceFile: unknown;
}): MediaReviewEvidenceFile {
  const evidenceFile = MediaReviewEvidenceFileSchema.parse(input.evidenceFile);
  if (evidenceFile.payload.sourceCommit !== input.expectedSourceCommit) {
    throw new Error('TT_HUMAN_GATE_MEDIA_SOURCE_MISMATCH: media worksheet belongs to another commit.');
  }
  const actualSha256 = createHash('sha256')
    .update(canonicalJson(evidenceFile.payload), 'utf8')
    .digest('hex');
  if (actualSha256 !== evidenceFile.payloadSha256) {
    throw new Error('TT_HUMAN_GATE_MEDIA_HASH_MISMATCH: media worksheet was altered.');
  }
  return evidenceFile;
}
