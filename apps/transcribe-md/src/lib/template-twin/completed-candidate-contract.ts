import { z } from "zod";

const SHA256 = /^[a-f0-9]{64}$/u;
const REGION_ID = /^tccr_[a-f0-9]{24}$/u;

const CompletedCandidateProjectionRoleSchema = z.discriminatedUnion("kind", [
  z.object({ kind: z.literal("static_redacted") }).strict(),
  z
    .object({
      kind: z.literal("stable_label"),
      label: z.string().min(1).max(120),
      forRegionId: z.string().regex(REGION_ID),
    })
    .strict(),
  z
    .object({
      kind: z.literal("candidate_region"),
      regionId: z.string().regex(REGION_ID),
      candidateTag: z.string().min(1).max(200),
      controlKind: z.literal("plain_text"),
      sourceState: z.literal("VALUE_WITHHELD"),
      candidateState: z.literal("BLANK_CONTROL"),
    })
    .strict(),
]);

const CompletedCandidateProjectionCellSchema = z
  .object({
    cellKey: z.string().min(1).max(500),
    cellIndex: z.number().int().nonnegative(),
    columnStart: z.number().int().nonnegative(),
    columnSpan: z.number().int().min(1).max(64),
    rowSpan: z.literal(1),
    role: CompletedCandidateProjectionRoleSchema,
  })
  .strict();

const CompletedCandidateProjectionBlockSchema = z.discriminatedUnion("kind", [
  z
    .object({
      kind: z.literal("redacted_paragraph"),
      blockKey: z.string().min(1).max(500),
      displayOrder: z.number().int().nonnegative(),
    })
    .strict(),
  z
    .object({
      kind: z.literal("table"),
      blockKey: z.string().min(1).max(500),
      displayOrder: z.number().int().nonnegative(),
      tableIndex: z.number().int().nonnegative(),
      gridColumnBasisPoints: z
        .array(z.number().int().min(1).max(10_000))
        .min(1)
        .max(64),
      rows: z
        .array(
          z
            .object({
              rowIndex: z.number().int().nonnegative(),
              cells: z
                .array(CompletedCandidateProjectionCellSchema)
                .min(1)
                .max(64),
            })
            .strict(),
        )
        .min(1)
        .max(500),
    })
    .strict(),
]);

export const CompletedCandidateReviewProjectionSchema = z
  .object({
    profileVersion: z.literal(
      "completed-candidate-redacted-structural-review/1.0.0",
    ),
    valuesRedacted: z.literal(true),
    sourceBytesReturned: z.literal(false),
    providerEgress: z.literal(false),
    paginationRepresented: z.literal(false),
    sourceExampleSha256s: z.array(z.string().regex(SHA256)).min(2).max(3),
    sourceStructureSha256: z.string().regex(SHA256),
    candidateStructureSha256: z.string().regex(SHA256),
    inventorySha256: z.string().regex(SHA256),
    candidateSha256: z.string().regex(SHA256),
    blocks: z.array(CompletedCandidateProjectionBlockSchema).min(1).max(600),
    regionCount: z.number().int().min(1).max(2000),
  })
  .strict()
  .superRefine((projection, context) => {
    const blockKeys = new Set<string>();
    const regionIds = new Set<string>();
    const labelRegionIds = new Set<string>();
    let totalRows = 0;
    let totalCells = 0;
    for (const block of projection.blocks) {
      if (blockKeys.has(block.blockKey)) {
        context.addIssue({ code: "custom", message: "Duplicate block key." });
      }
      blockKeys.add(block.blockKey);
      if (block.kind !== "table") continue;
      totalRows += block.rows.length;
      const gridSize = block.gridColumnBasisPoints.length;
      if (
        block.gridColumnBasisPoints.reduce((sum, value) => sum + value, 0) !==
        10_000
      ) {
        context.addIssue({ code: "custom", message: "Invalid table grid." });
      }
      for (const row of block.rows) {
        totalCells += row.cells.length;
        let expectedColumn = 0;
        for (const cell of row.cells) {
          if (
            cell.columnStart !== expectedColumn ||
            cell.columnStart + cell.columnSpan > gridSize
          ) {
            context.addIssue({
              code: "custom",
              message: "Invalid table cell topology.",
            });
          }
          expectedColumn = cell.columnStart + cell.columnSpan;
          if (cell.role.kind === "candidate_region") {
            if (regionIds.has(cell.role.regionId)) {
              context.addIssue({
                code: "custom",
                message: "Duplicate candidate region.",
              });
            }
            regionIds.add(cell.role.regionId);
          } else if (cell.role.kind === "stable_label") {
            labelRegionIds.add(cell.role.forRegionId);
          }
        }
        if (expectedColumn !== gridSize) {
          context.addIssue({
            code: "custom",
            message: "Table row does not cover the exact grid.",
          });
        }
      }
    }
    if (
      totalRows > 500 ||
      totalCells > 2000 ||
      regionIds.size !== projection.regionCount ||
      labelRegionIds.size !== projection.regionCount ||
      [...regionIds].some((regionId) => !labelRegionIds.has(regionId))
    ) {
      context.addIssue({
        code: "custom",
        message: "Projection inventory is incomplete.",
      });
    }
  });

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
      "completed-candidate-local-synthetic-privacy/1.1.0",
    ),
    providerEgress: z.literal(false),
    exampleCount: z.number().int().min(2).max(3),
    sentinelVerified: z.literal(true),
    structuredIdentifierClasses: z.tuple([]),
    sourceBinding: z.literal(
      "minimized-package-structure-visible-text-digests",
    ),
    exampleEvidenceSha256s: z.array(z.string().regex(SHA256)).min(2).max(3),
    evidenceSha256: z.string().regex(SHA256),
  })
  .strict()
  .superRefine((value, context) => {
    if (value.exampleEvidenceSha256s.length !== value.exampleCount) {
      context.addIssue({
        code: "custom",
        path: ["exampleEvidenceSha256s"],
        message: "Every isolated example requires one privacy evidence hash.",
      });
    }
    if (
      new Set(value.exampleEvidenceSha256s).size !==
      value.exampleEvidenceSha256s.length
    ) {
      context.addIssue({
        code: "custom",
        path: ["exampleEvidenceSha256s"],
        message: "Example privacy evidence hashes must be distinct.",
      });
    }
  });

export const CompletedCandidateIdentitySchema = z
  .object({
    name: z.string().trim().min(3).max(120),
    encounterScope: z.string().trim().min(3).max(120),
    versionDescription: z.string().trim().min(3).max(500),
  })
  .strict();

export const CompletedCandidateReviewDecisionSchema = z
  .object({
    regionId: z.string().regex(REGION_ID),
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

export type CompletedCandidateReviewProjection = z.infer<
  typeof CompletedCandidateReviewProjectionSchema
>;
