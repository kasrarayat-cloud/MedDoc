import { z } from "zod";

export const HUMAN_GATE_PACKAGE_VERSION =
  "template-twin-human-release-gate-package/3.0.0" as const;
export const WORD_HUMAN_EVIDENCE_VERSION =
  "template-twin-desktop-word-human-evidence/3.0.0" as const;
export const WORD_DOCUMENT_MANIFEST_VERSION =
  "template-twin-desktop-word-document-manifest/3.0.0" as const;
export const WORD_PDF_EXPORT_BINDING_VERSION =
  "template-twin-word-pdf-export-binding/1.0.0" as const;
export const WORD_OPENXML_VALIDATOR_NAME =
  "DocumentFormat.OpenXml.OpenXmlValidator" as const;
export const WORD_OPENXML_VALIDATOR_SDK_VERSION = "3.5.1.0" as const;
export const WORD_VERIFICATION_CONTRACT_VERSION =
  "template-docx-readback/2.0.0" as const;

const Sha256Schema = z.string().regex(/^[a-f0-9]{64}$/u);
const CommitShaSchema = z.string().regex(/^[a-f0-9]{40}$/u);
const IsoDateTimeSchema = z.string().datetime({ offset: true });
const PortableRelativePathSchema = z
  .string()
  .min(1)
  .max(500)
  .refine(
    (value) =>
      !value.startsWith("/") &&
      !value.includes("\\") &&
      !value.split("/").some((segment) => segment === ".." || segment === ""),
    "A portable relative path without traversal is required.",
  );

export const ReleaseGateFileEvidenceSchema = z
  .object({
    relativePath: PortableRelativePathSchema,
    sizeBytes: z.number().int().nonnegative(),
    sha256: Sha256Schema,
  })
  .strict();

export const WordQaDocumentSchema = ReleaseGateFileEvidenceSchema.extend({
  caseId: z.string().regex(/^[a-z0-9][a-z0-9-]{0,79}$/u),
  documentRole: z.enum(["source", "renderer_output"]),
  expectedPageCount: z.number().int().positive().max(500),
  minimumExpectedPages: z.number().int().positive().max(500),
  verification: z
    .object({
      contractVersion: z.literal(WORD_VERIFICATION_CONTRACT_VERSION),
      expectedValueManifest: ReleaseGateFileEvidenceSchema,
    })
    .strict(),
}).strict();

export const WordQaDocumentManifestSchema = z
  .object({
    contractVersion: z.literal(WORD_DOCUMENT_MANIFEST_VERSION),
    sourceCommit: CommitShaSchema,
    artifactName: z.string().regex(/^template-twin-human-gate-[a-f0-9]{12}$/u),
    syntheticOnly: z.literal(true),
    generatedAtIso: IsoDateTimeSchema,
    originalsMayBeOpenedByWord: z.literal(false),
    openXmlValidator: z
      .object({
        name: z.literal(WORD_OPENXML_VALIDATOR_NAME),
        sdkVersion: z.literal(WORD_OPENXML_VALIDATOR_SDK_VERSION),
        executableSha256: Sha256Schema,
        targets: z.tuple([z.literal("Office2013"), z.literal("Microsoft365")]),
      })
      .strict(),
    documentCount: z.number().int().positive(),
    documents: z.array(WordQaDocumentSchema).min(2),
  })
  .strict()
  .superRefine((manifest, context) => {
    if (manifest.documentCount !== manifest.documents.length) {
      context.addIssue({
        code: "custom",
        path: ["documentCount"],
        message: "Document count does not match the explicit allowlist.",
      });
    }
    const paths = manifest.documents.map((document) => document.relativePath);
    if (new Set(paths).size !== paths.length) {
      context.addIssue({
        code: "custom",
        path: ["documents"],
        message: "Each allowlisted document path must be unique.",
      });
    }
  });
export type WordQaDocumentManifest = z.infer<
  typeof WordQaDocumentManifestSchema
>;

const WordAutomationFileSchema = ReleaseGateFileEvidenceSchema.extend({
  kind: z.enum([
    "work_copy",
    "word_reopened_docx",
    "word_exported_pdf",
    "pdf_export_binding_json",
    "openxml_office2013_json",
    "openxml_microsoft365_json",
  ]),
}).strict();

export const WordPdfExportBindingSchema = z
  .object({
    contractVersion: z.literal(WORD_PDF_EXPORT_BINDING_VERSION),
    sourceCommit: CommitShaSchema,
    syntheticOnly: z.literal(true),
    authorizesClinicalOrProductionAction: z.literal(false),
    caseId: z.string().regex(/^[a-z0-9][a-z0-9-]{0,79}$/u),
    documentRole: z.enum(["source", "renderer_output"]),
    reopenedDocxSha256: Sha256Schema,
    reopenedDocxSizeBytes: z.number().int().positive(),
    exportedPdfSha256: Sha256Schema,
    exportedPdfSizeBytes: z.number().int().positive(),
    wordPageCount: z.number().int().positive().max(500),
    recordedAtIso: IsoDateTimeSchema,
  })
  .strict();
export type WordPdfExportBinding = z.infer<typeof WordPdfExportBindingSchema>;

const HumanPassFailBlockedSchema = z.enum(["PASS", "FAIL", "BLOCKED"]);

export const WordHumanObservationSchema = z
  .object({
    repairDialog: z.enum([
      "NO_REPAIR_DIALOG",
      "REPAIR_DIALOG_SHOWN",
      "NOT_OBSERVED",
    ]),
    visibleClinicalValues: HumanPassFailBlockedSchema,
    controlBehavior: HumanPassFailBlockedSchema,
    duplicateOrMissingFields: HumanPassFailBlockedSchema,
    clinicallyMeaningfulStaticText: HumanPassFailBlockedSchema,
    tablesHeadersAndFooters: HumanPassFailBlockedSchema,
    marginsFontsAndPagination: HumanPassFailBlockedSchema,
    overall: HumanPassFailBlockedSchema,
  })
  .strict();

export const WordQaDocumentEvidenceSchema = z
  .object({
    caseId: z.string().regex(/^[a-z0-9][a-z0-9-]{0,79}$/u),
    documentRole: z.enum(["source", "renderer_output"]),
    allowlistedRelativePath: PortableRelativePathSchema,
    originalExpectedSha256: Sha256Schema,
    originalExpectedSizeBytes: z.number().int().nonnegative(),
    originalBeforeSha256: Sha256Schema,
    originalAfterSha256: Sha256Schema,
    originalUnchanged: z.boolean(),
    automationStatus: z.enum(["COMPLETED", "FAILED", "BLOCKED"]),
    automationErrorCode: z.enum([
      "NONE",
      "WORD_NOT_INSTALLED",
      "WORD_COM_AUTOMATION_FAILED",
      "ORIGINAL_HASH_CHANGED",
      "PAGE_COUNT_BELOW_MINIMUM",
      "PAGE_COUNT_MISMATCH",
      "OPENXML_SCHEMA_INVALID",
    ]),
    saveAsCompleted: z.boolean(),
    reopenReadOnlyCompleted: z.boolean(),
    pdfExportCompleted: z.boolean(),
    pageCountBeforeSave: z.number().int().positive().max(500).nullable(),
    pageCountAfterReopen: z.number().int().positive().max(500).nullable(),
    expectedPageCount: z.number().int().positive().max(500),
    pageCountMatchesExpected: z.boolean(),
    minimumExpectedPages: z.number().int().positive().max(500),
    compatibilityModeBeforeSave: z.number().int().nullable(),
    compatibilityModeAfterReopen: z.number().int().nullable(),
    generatedFiles: z.array(WordAutomationFileSchema).max(6),
    humanObservation: WordHumanObservationSchema,
  })
  .strict();

export const WordHumanEvidenceSchema = z
  .object({
    contractVersion: z.literal(WORD_HUMAN_EVIDENCE_VERSION),
    sourceCommit: CommitShaSchema,
    packageManifestSha256: Sha256Schema,
    syntheticOnly: z.literal(true),
    reviewedAtIso: IsoDateTimeSchema,
    reviewer: z
      .object({
        reviewerId: z.string().regex(/^[A-Za-z0-9][A-Za-z0-9._-]{1,63}$/u),
        role: z.literal("desktop_word_qa_reviewer"),
      })
      .strict(),
    environment: z
      .object({
        windowsVersion: z.string().min(1).max(240),
        wordVersion: z.string().min(1).max(80),
        wordBuild: z.string().min(1).max(80),
        wordProductCode: z.string().min(1).max(160),
      })
      .strict(),
    networkRequestsMadeByScript: z.literal(0),
    administratorPrivilegesRequired: z.literal(false),
    originalsOpenedByWord: z.literal(0),
    documentsExpected: z.number().int().positive(),
    documentsCompleted: z.number().int().nonnegative(),
    documentsFailedOrBlocked: z.number().int().nonnegative(),
    documents: z.array(WordQaDocumentEvidenceSchema).min(2),
    attestation: z
      .object({
        reviewedOnlySyntheticDocuments: z.boolean(),
        observedRepairDialogsInDesktopWord: z.boolean(),
        completedVisualChecklistForEveryDocument: z.boolean(),
        understandsAutomationCannotJudgeVisualCorrectness: z.boolean(),
      })
      .strict(),
  })
  .strict()
  .superRefine((evidence, context) => {
    if (evidence.documentsExpected !== evidence.documents.length) {
      context.addIssue({
        code: "custom",
        path: ["documentsExpected"],
        message: "Evidence must contain every allowlisted document.",
      });
    }
    const completed = evidence.documents.filter(
      (document) => document.automationStatus === "COMPLETED",
    ).length;
    if (completed !== evidence.documentsCompleted) {
      context.addIssue({
        code: "custom",
        path: ["documentsCompleted"],
        message: "Completed count does not match document evidence.",
      });
    }
    if (
      evidence.documents.length - completed !==
      evidence.documentsFailedOrBlocked
    ) {
      context.addIssue({
        code: "custom",
        path: ["documentsFailedOrBlocked"],
        message: "Failed/blocked count does not match document evidence.",
      });
    }
  });
export type WordHumanEvidence = z.infer<typeof WordHumanEvidenceSchema>;

export const EvidenceFileHashManifestSchema = z
  .object({
    contractVersion: z.literal(
      "template-twin-return-evidence-file-hashes/1.0.0",
    ),
    files: z.array(ReleaseGateFileEvidenceSchema).min(1),
  })
  .strict()
  .superRefine((manifest, context) => {
    const paths = manifest.files.map((file) => file.relativePath);
    if (new Set(paths).size !== paths.length) {
      context.addIssue({
        code: "custom",
        path: ["files"],
        message: "Duplicate evidence path.",
      });
    }
  });

export const WORD_HUMAN_EVIDENCE_JSON_SCHEMA = Object.freeze(
  z.toJSONSchema(WordHumanEvidenceSchema, {
    target: "draft-2020-12",
    io: "input",
  }),
);
export const WORD_DOCUMENT_MANIFEST_JSON_SCHEMA = Object.freeze(
  z.toJSONSchema(WordQaDocumentManifestSchema, {
    target: "draft-2020-12",
    io: "input",
  }),
);
export const WORD_PDF_EXPORT_BINDING_JSON_SCHEMA = Object.freeze(
  z.toJSONSchema(WordPdfExportBindingSchema, {
    target: "draft-2020-12",
    io: "input",
  }),
);
export const EVIDENCE_FILE_HASH_MANIFEST_JSON_SCHEMA = Object.freeze(
  z.toJSONSchema(EvidenceFileHashManifestSchema, {
    target: "draft-2020-12",
    io: "input",
  }),
);

export type HumanGateValidationStatus = "PASS" | "FAIL" | "BLOCKED";

export interface HumanGateValidationIssue {
  readonly code: string;
  readonly status: Exclude<HumanGateValidationStatus, "PASS">;
  readonly message: string;
}

export interface HumanGateValidationReport {
  readonly contractVersion: "template-twin-human-release-gate-validation/1.0.0";
  readonly sourceCommit: string;
  readonly status: HumanGateValidationStatus;
  readonly authorizesClinicalOrProductionAction: false;
  readonly inputs: {
    readonly originalCiPackageZipSha256: string;
    readonly wordEvidenceZipSha256: string;
    readonly physicianDecisionSha256: string;
    readonly mediaReviewSha256: string;
  };
  readonly issues: readonly HumanGateValidationIssue[];
  readonly checkedAtIso: string;
}
