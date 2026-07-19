import { z } from "zod";

export const CompletedCandidateComparisonSchema = z
  .object({
    exampleCount: z.number().int().min(2).max(3),
    identicalStructure: z.literal(true),
    sourceBlockCount: z.number().int().positive(),
    candidateFieldCount: z.number().int().positive(),
    preservedStaticBlockCount: z.number().int().nonnegative(),
    sourceSummary: z.string().min(1).max(500),
    candidateSummary: z.string().min(1).max(500),
  })
  .strict();

export const CompletedCandidatePrivacyEvidenceSchema = z
  .object({
    profileVersion: z.literal(
      "completed-candidate-local-synthetic-privacy/1.0.0",
    ),
    providerEgress: z.literal(false),
    exampleCount: z.number().int().min(2).max(3),
    sentinelVerified: z.literal(true),
    structuredIdentifierClasses: z.tuple([]),
    evidenceSha256: z.string().regex(/^[a-f0-9]{64}$/u),
  })
  .strict();

export const CompletedCandidateIdentitySchema = z
  .object({
    name: z.string().trim().min(3).max(120),
    encounterScope: z.string().trim().min(3).max(120),
    versionDescription: z.string().trim().min(3).max(500),
  })
  .strict();

export const CompletedCandidateReviewDecisionSchema = z
  .object({
    regionId: z.string().regex(/^tccr_[a-f0-9]{24}$/u),
    decision: z.enum(["APPROVED", "REJECTED"]),
  })
  .strict();

export const CompletedCandidateReviewPayloadSchema = z
  .object({
    decisions: z.array(CompletedCandidateReviewDecisionSchema).min(1).max(2000),
    physicianAttestation: z.literal(true),
  })
  .strict();

export interface CompletedCandidateReviewRegionDto {
  readonly regionId: string;
  readonly displayOrder: number;
  readonly label: string;
  readonly evidenceType: "stable_label_changed_scalar_cell";
  readonly location: string;
  readonly candidateTag: string;
  readonly sourceEvidenceSha256: string;
  readonly sourceDescription: string;
  readonly candidateDescription: string;
  readonly decision: "PENDING" | "APPROVED" | "REJECTED";
}

export interface CompletedCandidateReviewDto {
  readonly id: string;
  readonly name: string;
  readonly encounterScope: string;
  readonly versionDescription: string;
  readonly status: "PENDING_REVIEW" | "APPROVED" | "REJECTED";
  readonly candidateSha256: string;
  readonly inventorySha256: string;
  readonly comparison: z.infer<typeof CompletedCandidateComparisonSchema>;
  readonly privacy: z.infer<typeof CompletedCandidatePrivacyEvidenceSchema>;
  readonly regions: readonly CompletedCandidateReviewRegionDto[];
}
