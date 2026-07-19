import { z } from "zod";

const SHA256 = /^[a-f0-9]{64}$/u;
const REGION_ID = /^tccr_[a-f0-9]{24}$/u;
const CANDIDATE_TAG = /^qmd:candidate:[a-f0-9]{24}$/u;
export const COMPLETED_CANDIDATE_REVIEW_RECEIPT =
  /^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}\.[A-Za-z0-9_-]{43}$/u;

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
      candidateTag: z.string().regex(CANDIDATE_TAG),
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
    const cellKeys = new Set<string>();
    const candidateTags = new Set<string>();
    const candidateRegionCounts = new Map<string, number>();
    const labelRegionCounts = new Map<string, number>();
    let totalRows = 0;
    let totalCells = 0;
    let expectedTableIndex = 0;
    if (
      new Set(projection.sourceExampleSha256s).size !==
      projection.sourceExampleSha256s.length
    ) {
      context.addIssue({
        code: "custom",
        path: ["sourceExampleSha256s"],
        message: "Source example identities must be distinct.",
      });
    }
    for (const [blockIndex, block] of projection.blocks.entries()) {
      if (blockKeys.has(block.blockKey)) {
        context.addIssue({ code: "custom", message: "Duplicate block key." });
      }
      blockKeys.add(block.blockKey);
      if (block.displayOrder !== blockIndex) {
        context.addIssue({
          code: "custom",
          message: "Block display order must be unique and contiguous.",
        });
      }
      if (block.kind !== "table") continue;
      if (block.tableIndex !== expectedTableIndex) {
        context.addIssue({
          code: "custom",
          message: "Table indexes must be unique and contiguous.",
        });
      }
      expectedTableIndex += 1;
      totalRows += block.rows.length;
      const gridSize = block.gridColumnBasisPoints.length;
      if (
        block.gridColumnBasisPoints.reduce((sum, value) => sum + value, 0) !==
        10_000
      ) {
        context.addIssue({ code: "custom", message: "Invalid table grid." });
      }
      for (const [rowIndex, row] of block.rows.entries()) {
        if (row.rowIndex !== rowIndex) {
          context.addIssue({
            code: "custom",
            message: "Table row indexes must be unique and contiguous.",
          });
        }
        totalCells += row.cells.length;
        let expectedColumn = 0;
        for (const [cellIndex, cell] of row.cells.entries()) {
          const expectedCellKey = `table:${block.tableIndex}:row:${row.rowIndex}:cell:${cell.cellIndex}`;
          if (
            cell.cellIndex !== cellIndex ||
            cell.cellKey !== expectedCellKey ||
            cellKeys.has(cell.cellKey)
          ) {
            context.addIssue({
              code: "custom",
              message: "Table cell identities must be unique and contiguous.",
            });
          }
          cellKeys.add(cell.cellKey);
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
            candidateRegionCounts.set(
              cell.role.regionId,
              (candidateRegionCounts.get(cell.role.regionId) ?? 0) + 1,
            );
            if (candidateTags.has(cell.role.candidateTag)) {
              context.addIssue({
                code: "custom",
                message: "Duplicate candidate binding tag.",
              });
            }
            candidateTags.add(cell.role.candidateTag);
          } else if (cell.role.kind === "stable_label") {
            labelRegionCounts.set(
              cell.role.forRegionId,
              (labelRegionCounts.get(cell.role.forRegionId) ?? 0) + 1,
            );
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
      expectedTableIndex < 1 ||
      candidateRegionCounts.size !== projection.regionCount ||
      labelRegionCounts.size !== projection.regionCount ||
      [...candidateRegionCounts].some(
        ([regionId, count]) =>
          count !== 1 || labelRegionCounts.get(regionId) !== 1,
      ) ||
      [...labelRegionCounts].some(
        ([regionId, count]) =>
          count !== 1 || candidateRegionCounts.get(regionId) !== 1,
      )
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
    reviewReceipt: z.string().regex(COMPLETED_CANDIDATE_REVIEW_RECEIPT),
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

export interface CompletedCandidateReviewPreviewDto {
  readonly projection: CompletedCandidateReviewProjection;
  /** Opaque bearer proof. Keep in memory only; never render or persist it. */
  readonly reviewReceipt: string;
  readonly expiresAtIso: string;
}

export type CompletedCandidateReviewProjection = z.infer<
  typeof CompletedCandidateReviewProjectionSchema
>;
