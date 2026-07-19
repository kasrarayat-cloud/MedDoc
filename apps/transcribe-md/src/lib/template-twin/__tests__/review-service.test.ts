import { TemplateTwinDetectionStatus } from "@prisma/client";
import { beforeEach, describe, expect, it, vi } from "vitest";

const audit = vi.hoisted(() => vi.fn());
vi.mock("@/lib/audit", () => ({ logAudit: audit }));

const database = vi.hoisted(() => ({
  transaction: vi.fn(),
  manifestFindFirst: vi.fn(),
  manifestUpdateMany: vi.fn(),
  decisionCreate: vi.fn(),
  ledgerUpdateMany: vi.fn(),
  ledgerFindUnique: vi.fn(),
  outboxCreate: vi.fn(),
  lockVisit: vi.fn(),
  assessAutomation: vi.fn(),
  lockAutomation: vi.fn(),
  lockActor: vi.fn(),
}));
vi.mock("@meddoc/db", () => {
  const tx = {
    templateTwinFillManifest: { updateMany: database.manifestUpdateMany },
    templateTwinReviewDecision: { create: database.decisionCreate },
    templateTwinObjectLedger: {
      updateMany: database.ledgerUpdateMany,
      findUnique: database.ledgerFindUnique,
    },
    templateTwinAuditOutbox: { create: database.outboxCreate },
    $queryRaw: database.lockVisit,
  };
  return {
    default: {
      $transaction: database.transaction,
      templateTwinFillManifest: { findFirst: database.manifestFindFirst },
    },
    prisma: { $transaction: database.transaction },
    __tx: tx,
  };
});
vi.mock("../runtime-attestation", () => ({
  registerTemplateTwinRuntimeAttestation: vi.fn().mockResolvedValue({
    instanceId: "app-1",
  }),
  TemplateTwinRuntimeAttestationError: class extends Error {},
}));
vi.mock("../staging-qa-visit-guard", async (importOriginal) => ({
  ...(await importOriginal<typeof import("../staging-qa-visit-guard")>()),
  lockAndAssertTemplateTwinStagingQaActor: database.lockActor,
}));
vi.mock("@/worker/automation-finalization", async (importOriginal) => ({
  ...(await importOriginal<
    typeof import("@/worker/automation-finalization")
  >()),
  assessVisitAutomationProof: database.assessAutomation,
  lockAndAssertVisitAutomationProof: database.lockAutomation,
}));

import { canonicalSha256 } from "../canonical";
import { canonicalSoapSha256 } from "../soap-binding";
import { TEMPLATE_TWIN_SOURCE_PROVENANCE_GATE_CODE } from "../source-phi-evidence";
import { type TemplateTwinFieldCorrectionRequest } from "../contracts";
import {
  TEMPLATE_TWIN_REVIEW_REASON,
  type FinalizeTemplateTwinFillInput,
  type PreparedTemplateTwinFill,
} from "../fill-engine";
import {
  TEMPLATE_TWIN_COMPILER_VERSION,
  TEMPLATE_TWIN_IR_SCHEMA_VERSION,
  TEMPLATE_TWIN_RENDERER_VERSION,
  TEMPLATE_TWIN_RESOLVER_VERSION,
  TemplateTwinFillManifestSchema,
  templateTwinCounts,
  type FieldResolution,
  type SemanticMapping,
  type TemplateDocIR,
  type TemplateField,
} from "../ir";
import { createTemplateTwinEncounterSourceReceipt } from "../canonical-encounter-source";
import {
  buildClinicianCorrection,
  createTemplateTwinReviewRepository,
  reviewTemplateTwinField,
  TemplateTwinReviewError,
  type TemplateTwinReviewRepository,
} from "../review-service";
import { validateTemplateTwin } from "../validation";
import { VisitAutomationIncompleteError } from "@/worker/automation-finalization";
import {
  DOCX_MIME_TYPE,
  type StoredTemplateTwinArtifact,
  type TemplateTwinArtifactStore,
} from "../storage";

const SHA = "a".repeat(64);
const OUTPUT_SHA = "b".repeat(64);
const RELEASE_ID = "0eb13c1b-0893-4cb0-bbd6-68b3e544baac";
const RELEASE_IDENTITY_SHA256 = "1".repeat(64);
const RUNTIME_MANIFEST_SHA256 = "2".repeat(64);
const RUNTIME_INSTANCE_ID = "app-1";
const FIELD_ID = `ttf_${"c".repeat(24)}`;
const NOW = "2026-07-15T17:00:00.000Z";
const REVIEWED_SOAP =
  "## Assessment\nSynthetic severity under physician review.";
const SOURCE_PRIVACY_SCAN_EVIDENCE = {
  profileVersion: "template-twin-source-phi-safe-alpha-v1" as const,
  provider: "anthropic" as const,
  model: "synthetic-privacy-model-v1",
  scannedAt: "2026-07-15T12:00:00.000Z",
  scannedPartCount: 3,
  approvedStaticAssetPolicySha256: "e".repeat(64),
  approvedStaticAssetCount: 0,
  approvedStaticAssetUsedCount: 0,
  approvedStaticAssetUsageSha256: "f".repeat(64),
};
let globalRolloutEnabled: boolean;
let globalRolloutGeneration: bigint;
let practiceRolloutEnabled: boolean;
let practiceRolloutGeneration: bigint;

type ReviewContext = NonNullable<
  Awaited<ReturnType<TemplateTwinReviewRepository["loadOwned"]>>
>;
type CommitPlan = Parameters<TemplateTwinReviewRepository["commit"]>[0];

function field(
  kind: TemplateField["kind"] = "single_select",
  overrides: Partial<TemplateField> = {},
): TemplateField {
  return {
    fieldId: FIELD_ID,
    kind,
    originalLabel: "Synthetic severity",
    labelSource: "tag",
    displayOrder: 0,
    detectionStatus: "certified",
    allowedOptions:
      kind === "single_select" || kind === "multi_select"
        ? [
            { ordinal: 0, displayText: "Mild", value: "Mild" },
            { ordinal: 1, displayText: "Severe", value: "Severe" },
          ]
        : [],
    rendererBinding: {
      partName: "word/document.xml",
      bindingType: "content_control",
      path: "/document/body/sdt[0]",
      canonicalPath: "/document/body/sdt[0]",
      ordinal: 0,
      sdtId: "1",
      tag: "synthetic_severity",
      alias: null,
      legacyName: null,
      tableIndex: null,
      rowIndex: null,
      cellIndex: null,
      repeatAncestorPath: null,
      canonicalRepeatAncestorPath: null,
      sourceControlSha256: SHA,
      sourceBindingIdentitySha256: SHA,
      certifiedBindingSha256: SHA,
      originalContentSha256: SHA,
    },
    required: false,
    unknownPolicy: "blank",
    clinicallyMaterial: false,
    criticality: "routine",
    tableId: null,
    rowPrototype: false,
    ...overrides,
  };
}

function mapping(
  definition: TemplateField,
  overrides: Partial<SemanticMapping> = {},
): SemanticMapping {
  const dataTypes: Record<
    TemplateField["kind"],
    SemanticMapping["expectedDataType"]
  > = {
    narrative_text: "text",
    single_select: "single_select",
    multi_select: "multi_select",
    checkbox: "boolean",
    date: "date",
    number: "number",
    measurement: "measurement",
  };
  return {
    fieldId: definition.fieldId,
    clinicalConcept: "hpi.severity",
    expectedDataType: dataTypes[definition.kind],
    polarityBehavior:
      definition.kind === "checkbox" ? "explicit_denial_allowed" : "value_only",
    temporality: "current",
    laterality: "not_applicable",
    unitPolicy:
      definition.kind === "measurement" ? "required" : "not_applicable",
    approvedSynonyms: [],
    required: false,
    blankPolicy: "blank",
    unknownPolicy: "blank",
    practiceDefault: null,
    status: "certified",
    ...overrides,
  };
}

function ir(definition = field()): TemplateDocIR {
  return {
    irSchemaVersion: TEMPLATE_TWIN_IR_SCHEMA_VERSION,
    compilerVersion: TEMPLATE_TWIN_COMPILER_VERSION,
    source: {
      sha256: SHA,
      sizeBytes: 20,
      mimeType: DOCX_MIME_TYPE,
    },
    parts: [
      {
        partName: "[Content_Types].xml",
        contentType: "application/xml",
        kind: "other",
        sha256: SHA,
        staticSha256: SHA,
        relationshipCount: 0,
      },
      {
        partName: "_rels/.rels",
        contentType: "application/vnd.openxmlformats-package.relationships+xml",
        kind: "relationships",
        sha256: SHA,
        staticSha256: SHA,
        relationshipCount: 1,
      },
      {
        partName: "word/document.xml",
        contentType:
          "application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml",
        kind: "document",
        sha256: SHA,
        staticSha256: SHA,
        relationshipCount: 0,
      },
    ],
    nodes: [
      {
        nodeId: `ttn_${"d".repeat(20)}`,
        partName: "word/document.xml",
        path: "/document/body/sdt[0]",
        displayOrder: 0,
        kind: definition.kind,
        fieldId: definition.fieldId,
        tableId: null,
        staticTextSha256: null,
        bookmarkNames: [],
      },
    ],
    fields: [definition],
    tables: [],
    unsupported: [],
    structureSha256: SHA,
    staticContentSha256: SHA,
    stats: {
      totalFields: 1,
      dropdowns: definition.kind === "single_select" ? 1 : 0,
      comboBoxes: 0,
      checkboxes: definition.kind === "checkbox" ? 1 : 0,
      dateControls: definition.kind === "date" ? 1 : 0,
      tables: 0,
      repeatingTables: 0,
      headers: 0,
      footers: 0,
      unsupported: 0,
      blockingUnsupported: 0,
    },
  };
}

function unresolved(fieldId = FIELD_ID): FieldResolution {
  return {
    fieldId,
    status: "needs_clinician_input",
    value: null,
    sourceFactIds: [],
    evidenceAnchorIds: [],
    selectedOptionOrdinal: null,
    reasonCode: "required_fact_not_mentioned",
    clinicianReviewed: false,
  };
}

function persistedMapping(semantic: SemanticMapping) {
  return {
    clinicalConcept: semantic.clinicalConcept,
    expectedDataType: semantic.expectedDataType,
    polarityBehavior: semantic.polarityBehavior,
    temporality: semantic.temporality,
    laterality: semantic.laterality,
    unitPolicy: semantic.unitPolicy,
    approvedSynonyms: semantic.approvedSynonyms,
    required: semantic.required,
    blankPolicy: semantic.blankPolicy,
    unknownPolicy: semantic.unknownPolicy,
    practiceDefault: semantic.practiceDefault,
    mappingStatus: TemplateTwinDetectionStatus.CERTIFIED,
    proposedByModel: null,
    approvedById: "doctor-1",
    approvedAt: new Date(NOW),
  };
}

function context(definition = field()): ReviewContext {
  const documentIr = ir(definition);
  const semantic = mapping(definition);
  const validation = validateTemplateTwin({
    fields: documentIr.fields,
    mappings: [semantic],
    facts: [],
    resolutions: [unresolved(definition.fieldId)],
    now: NOW,
  });
  const manifest = TemplateTwinFillManifestSchema.parse({
    manifestVersion: 1,
    soapVersion: 7,
    soapSha256: canonicalSoapSha256(REVIEWED_SOAP),
    compiledVersionId: "compiled-1",
    noteTemplateId: "template-1",
    noteTemplateVersion: 1,
    compilerVersion: TEMPLATE_TWIN_COMPILER_VERSION,
    resolverVersion: TEMPLATE_TWIN_RESOLVER_VERSION,
    resolverModelVersion: null,
    rendererVersion: TEMPLATE_TWIN_RENDERER_VERSION,
    encounterSourceReceipt: createTemplateTwinEncounterSourceReceipt({
      mode: "text",
      contextText: REVIEWED_SOAP,
    }),
    facts: [],
    fields: [unresolved(definition.fieldId)],
    validation,
    counts: templateTwinCounts([unresolved(definition.fieldId)], [definition]),
  });
  const manifestSha256 = canonicalSha256(manifest);
  return {
    id: "fill-1",
    practiceId: "practice-1",
    visitId: "visit-1",
    status: "NEEDS_REVIEW",
    signedDecisionAt: null,
    manifestVersion: 4,
    manifestSha256,
    fillManifest: manifest,
    resolverModelVersion: null,
    visit: {
      userId: "doctor-1",
      status: "READY",
      reviewReason: TEMPLATE_TWIN_REVIEW_REASON,
      soapFinal: REVIEWED_SOAP,
      soapVersion: 7,
      inputMode: "text_notes",
      rawTextInput: REVIEWED_SOAP,
      transcriptText: null,
      transcriptRaw: null,
      speakerMap: null,
    },
    compiledVersion: {
      id: "compiled-1",
      sourceArtifactId: "source-1",
      compilerVersion: TEMPLATE_TWIN_COMPILER_VERSION,
      irSchemaVersion: TEMPLATE_TWIN_IR_SCHEMA_VERSION,
      compiledDocumentIr: documentIr,
      unsupportedElements: [],
      structureSha256: SHA,
      staticContentSha256: SHA,
      certificationStatus: "CERTIFIED",
      blockingUnsupportedCount: 0,
      certification: {
        sourcePrivacyScanEvidenceSha256: canonicalSha256(
          SOURCE_PRIVACY_SCAN_EVIDENCE,
        ),
      },
      sourceArtifact: {
        practiceId: "practice-1",
        objectKey: `practices/practice-1/template-twin/sources/lineage-1/v1/${SHA}/artifact/${SHA}.docx`,
        objectVersionId: "provider-source-version-synthetic",
        objectEtag: "provider-source-etag-synthetic",
        sha256: SHA,
        sizeBytes: 20,
        validationStatus: "accepted",
        privacyScanEvidence: SOURCE_PRIVACY_SCAN_EVIDENCE,
      },
      noteTemplate: {
        id: "template-1",
        doctorId: "doctor-1",
        name: "Synthetic template",
        encounterType: null,
        specialtyBaseline: null,
        sections: [],
        styleProfile: null,
        version: 1,
        status: "active",
        lineageId: "lineage-1",
        templateKind: "template_twin_docx",
      },
      fields: [
        {
          id: "definition-1",
          fieldId: definition.fieldId,
          displayOrder: 0,
          originalLabel: definition.originalLabel,
          fieldKind: definition.kind,
          allowedOptions: definition.allowedOptions,
          rendererBinding: definition.rendererBinding,
          detectionStatus: TemplateTwinDetectionStatus.CERTIFIED,
          clinicallyMaterial: definition.clinicallyMaterial,
          criticality: definition.criticality,
          required: definition.required,
          mapping: persistedMapping(semantic),
        },
      ],
    },
  };
}

function correction(
  overrides: Partial<TemplateTwinFieldCorrectionRequest> = {},
): TemplateTwinFieldCorrectionRequest {
  return {
    expectedManifestVersion: 4,
    fieldId: FIELD_ID,
    value: "Severe",
    sourceFactIds: [],
    reasonCode: "physician_review_correction",
    createMappingRule: false,
    ...overrides,
  };
}

function lockedVisitRow(
  overrides: Partial<{
    soapVersion: number;
    soapFinal: string | null;
    status: string;
    rawTextInput: string | null;
  }> = {},
) {
  return {
    id: "visit-1",
    userId: "doctor-1",
    status: overrides.status ?? "READY",
    deletedAt: null,
    archivedAt: null,
    soapVersion: overrides.soapVersion ?? 7,
    soapFinal:
      overrides.soapFinal === undefined ? REVIEWED_SOAP : overrides.soapFinal,
    noteTemplateId: "template-1",
    noteTemplateVersion: 1,
    inputMode: "text_notes",
    rawTextInput:
      overrides.rawTextInput === undefined
        ? REVIEWED_SOAP
        : overrides.rawTextInput,
    transcriptText: null,
    transcriptRaw: null,
    speakerMap: null,
  };
}

function mockRolloutAndVisitLocks(visit = lockedVisitRow()) {
  database.lockVisit.mockImplementation(async (query: unknown) => {
    const text = String(
      (query as { strings?: readonly string[] }).strings?.join(" ") ?? "",
    );
    if (text.includes("template_twin_rollout_controls")) {
      return [
        {
          enabled: globalRolloutEnabled,
          generation: globalRolloutGeneration,
          rollbackFenceState: "OPEN",
          rollbackOperationId: null,
        },
      ];
    }
    if (text.includes("templateTwinRolloutGeneration")) {
      return [
        {
          templateTwinEnabled: practiceRolloutEnabled,
          templateTwinRolloutGeneration: practiceRolloutGeneration,
          isActive: true,
        },
      ];
    }
    if (text.includes("template_twin_current_runtime_release")) {
      return [
        {
          id: RELEASE_ID,
          releaseIdentitySha256: RELEASE_IDENTITY_SHA256,
          runtimeManifestSha256: RUNTIME_MANIFEST_SHA256,
          runtimeReady: true,
        },
      ];
    }
    if (text.includes("template_twin_lineage_migration_progress")) {
      return [{ phase: "CONTRACTED" }];
    }
    return [visit];
  });
}

function repository(
  loaded: ReviewContext | null,
  result: Partial<
    Awaited<ReturnType<TemplateTwinReviewRepository["commit"]>>
  > = {},
) {
  let committed: CommitPlan | null = null;
  const repo: TemplateTwinReviewRepository = {
    pinRollout: vi.fn(async (practiceId: string) => ({
      practiceId,
      globalGeneration: BigInt(1),
      practiceGeneration: BigInt(1),
      releaseId: RELEASE_ID,
      releaseIdentitySha256: RELEASE_IDENTITY_SHA256,
      runtimeManifestSha256: RUNTIME_MANIFEST_SHA256,
      runtimeInstanceId: RUNTIME_INSTANCE_ID,
    })),
    loadOwned: vi.fn(async () => loaded),
    commit: vi.fn(async (plan) => {
      committed = plan;
      return {
        applied: true,
        manifestVersion: 5,
        draftTemplateId: null,
        draftTemplateVersion: null,
        ...result,
      };
    }),
  };
  return { repo, committed: () => committed };
}

function storage(
  onOutputStored?: () => void | Promise<void>,
): TemplateTwinArtifactStore {
  const storeOutputArtifact: TemplateTwinArtifactStore["storeOutputArtifact"] =
    vi.fn(async (): Promise<StoredTemplateTwinArtifact> => {
      const stored = {
        bucket: "synthetic-private-bucket",
        objectKey: `practices/practice-1/template-twin/outputs/visit-1/${SHA}/artifact/${OUTPUT_SHA}.docx`,
        objectVersionId: "provider-output-version-synthetic",
        objectEtag: "provider-output-etag-synthetic",
        sha256: OUTPUT_SHA,
        mimeType: DOCX_MIME_TYPE,
        sizeBytes: 24,
        created: true,
      } as const;
      await onOutputStored?.();
      return stored;
    });

  return {
    bucket: "synthetic-private-bucket",
    storeQuarantineArtifact: vi.fn(),
    readQuarantineArtifact: vi.fn(),
    storeCandidateArtifact: vi.fn(),
    readCandidateArtifact: vi.fn(),
    storeSourceArtifact: vi.fn(),
    readOutputArtifact: vi.fn(),
    readSourceArtifact: vi.fn(async () => Buffer.alloc(20, 1)),
    storeOutputArtifact,
  };
}

function deterministicBarrier() {
  let signalEntered!: () => void;
  let release!: () => void;
  const entered = new Promise<void>((resolve) => {
    signalEntered = resolve;
  });
  const released = new Promise<void>((resolve) => {
    release = resolve;
  });
  return {
    entered,
    release,
    async stop() {
      signalEntered();
      await released;
    },
  };
}

async function fakeFinalize(
  input: FinalizeTemplateTwinFillInput,
): Promise<PreparedTemplateTwinFill> {
  const validation = validateTemplateTwin({
    fields: input.ir.fields,
    mappings: input.mappings,
    facts: input.facts,
    resolutions: input.resolutions,
    tables: input.ir.tables,
    unsupported: input.ir.unsupported,
    now: input.validationNow,
  });
  const counts = templateTwinCounts(input.resolutions, input.ir.fields);
  const manifest = TemplateTwinFillManifestSchema.parse({
    manifestVersion: 1,
    soapVersion: input.soapVersion,
    soapSha256: canonicalSoapSha256(input.soapFinal),
    compiledVersionId: input.compiledVersionId,
    noteTemplateId: input.noteTemplateId,
    noteTemplateVersion: input.noteTemplateVersion,
    compilerVersion: input.ir.compilerVersion,
    resolverVersion: TEMPLATE_TWIN_RESOLVER_VERSION,
    resolverModelVersion: input.resolverModelVersion,
    rendererVersion: TEMPLATE_TWIN_RENDERER_VERSION,
    encounterSourceReceipt: input.encounterSourceReceipt,
    facts: input.facts,
    fields: input.resolutions,
    validation,
    counts,
  });
  return {
    manifest,
    manifestSha256: canonicalSha256(manifest),
    factSetSha256: canonicalSha256(input.facts),
    render: validation.valid
      ? {
          document: Buffer.from("synthetic-corrected-docx"),
          outputSha256: OUTPUT_SHA,
          rendererVersion: TEMPLATE_TWIN_RENDERER_VERSION,
          verification: {
            verificationContractVersion:
              "template-docx-readback/2.0.0" as const,
            verified: true as const,
            packageCheck: "verified" as const,
            fieldCheck: "verified" as const,
            staticRegionCheck: "verified" as const,
            sourceSha256: SHA,
            outputSha256: OUTPUT_SHA,
            untouchedEntriesVerified: 3,
            modifiedPartsVerified: 1,
            fields: [],
            warningCodes: [],
          },
        }
      : null,
  };
}

const actor = {
  userId: "doctor-1",
  userEmail: "synthetic-doctor@example.test",
  practiceId: "practice-1",
};

beforeEach(async () => {
  vi.clearAllMocks();
  process.env.TEMPLATE_TWIN_KILL_SWITCH = "false";
  globalRolloutEnabled = true;
  globalRolloutGeneration = BigInt(1);
  practiceRolloutEnabled = true;
  practiceRolloutGeneration = BigInt(1);
  const databaseModule = await import("@meddoc/db");
  const tx = (databaseModule as unknown as { __tx: unknown }).__tx;
  database.transaction.mockImplementation(
    async (callback: (client: unknown) => Promise<unknown>) => callback(tx),
  );
  database.manifestUpdateMany.mockResolvedValue({ count: 1 });
  database.manifestFindFirst.mockResolvedValue(context());
  database.decisionCreate.mockResolvedValue({ id: "decision-synthetic-1" });
  database.ledgerUpdateMany.mockResolvedValue({ count: 1 });
  database.outboxCreate.mockResolvedValue({ id: "outbox-synthetic-1" });
  database.assessAutomation.mockReturnValue({ ready: true, blockerCodes: [] });
  database.lockAutomation.mockResolvedValue({
    id: "automation-proof-synthetic",
  });
  database.lockActor.mockResolvedValue(undefined);
  mockRolloutAndVisitLocks();
});

describe("buildClinicianCorrection exact rules", () => {
  it("accepts only an exact native dropdown option and records physician evidence", () => {
    const definition = field();
    expect(() =>
      buildClinicianCorrection({
        field: definition,
        mapping: mapping(definition),
        value: "Closest severe option",
        existingFactIds: new Set(),
        factIdFactory: () => "1".repeat(24),
      }),
    ).toThrow(TemplateTwinReviewError);

    const result = buildClinicianCorrection({
      field: definition,
      mapping: mapping(definition),
      value: "Severe",
      existingFactIds: new Set(),
      factIdFactory: () => "1".repeat(24),
    });
    expect(result.resolution).toMatchObject({
      value: "Severe",
      selectedOptionOrdinal: 1,
      clinicianReviewed: true,
    });
    expect(result.facts[0]).toMatchObject({
      speaker: "Physician correction",
      evidenceQuote:
        "Physician correction entered during Template Twin review.",
      quality: { asr: "unknown", evidence: "direct" },
    });
  });

  it("requires checkbox polarity and explicit measurement units", () => {
    const checkbox = field("checkbox");
    const checked = buildClinicianCorrection({
      field: checkbox,
      mapping: mapping(checkbox),
      value: false,
      existingFactIds: new Set(),
      factIdFactory: () => "2".repeat(24),
    });
    expect(checked.resolution.status).toBe("explicitly_denied");
    expect(checked.facts[0]?.polarity).toBe("denied");
    expect(() =>
      buildClinicianCorrection({
        field: checkbox,
        mapping: mapping(checkbox, {
          polarityBehavior: "affirmative_only",
        }),
        value: false,
        existingFactIds: new Set(),
        factIdFactory: () => "2".repeat(24),
      }),
    ).toThrow(/does not define unchecked as false/i);

    const measurement = field("measurement");
    expect(() =>
      buildClinicianCorrection({
        field: measurement,
        mapping: mapping(measurement),
        value: 12,
        existingFactIds: new Set(),
        factIdFactory: () => "3".repeat(24),
      }),
    ).toThrow(/explicit unit/i);
    const measured = buildClinicianCorrection({
      field: measurement,
      mapping: mapping(measurement),
      value: "12 mg",
      existingFactIds: new Set(),
      factIdFactory: () => "3".repeat(24),
    });
    expect(measured.resolution.value).toBe("12 mg");
    expect(measured.facts[0]).toMatchObject({ number: 12, unit: "mg" });
  });

  it("validates exact multi-selects and typed values in repeating rows", () => {
    const multi = field("multi_select");
    const selected = buildClinicianCorrection({
      field: multi,
      mapping: mapping(multi),
      value: ["Mild", "Severe"],
      existingFactIds: new Set(),
      factIdFactory: vi
        .fn()
        .mockReturnValueOnce("4".repeat(24))
        .mockReturnValueOnce("5".repeat(24)),
    });
    expect(selected.resolution.value).toEqual(["Mild", "Severe"]);
    expect(selected.resolution.sourceFactIds).toHaveLength(2);
    expect(() =>
      buildClinicianCorrection({
        field: multi,
        mapping: mapping(multi),
        value: ["Mild", "Closest option"],
        existingFactIds: new Set(),
      }),
    ).toThrow(/exact certified options/i);

    const repeatingNumber = field("number", { rowPrototype: true });
    const rows = buildClinicianCorrection({
      field: repeatingNumber,
      mapping: mapping(repeatingNumber),
      value: [{ value: "12" }, { value: "13.5" }],
      existingFactIds: new Set(),
      factIdFactory: vi
        .fn()
        .mockReturnValueOnce("6".repeat(24))
        .mockReturnValueOnce("7".repeat(24)),
    });
    expect(rows.resolution.value).toEqual([
      expect.objectContaining({ value: "12" }),
      expect.objectContaining({ value: "13.5" }),
    ]);
    expect(rows.facts.map((fact) => fact.number)).toEqual([12, 13.5]);
  });
});

describe("reviewTemplateTwinField lifecycle", () => {
  it("blocks correction before source I/O when automation proof is incomplete", async () => {
    const capture = repository(context());
    const artifacts = storage();
    database.assessAutomation.mockReturnValue({
      ready: false,
      blockerCodes: ["VISIT_AUTOMATION_REQUIRED_LAYER_INCOMPLETE"],
    });

    await expect(
      reviewTemplateTwinField(
        { visitId: "visit-1", actor, correction: correction() },
        { repository: capture.repo, storage: artifacts },
      ),
    ).rejects.toMatchObject({ code: "VISIT_AUTOMATION_INCOMPLETE" });
    expect(artifacts.readSourceArtifact).not.toHaveBeenCalled();
    expect(capture.repo.commit).not.toHaveBeenCalled();
  });

  it("rolls a production correction back when automation changes after precheck", async () => {
    const artifacts = storage();
    database.lockAutomation.mockRejectedValue(
      new VisitAutomationIncompleteError([
        "VISIT_AUTOMATION_REQUIRED_LAYER_INCOMPLETE",
      ]),
    );

    await expect(
      reviewTemplateTwinField(
        { visitId: "visit-1", actor, correction: correction() },
        { storage: artifacts, finalizeFill: fakeFinalize },
      ),
    ).rejects.toMatchObject({ code: "VISIT_AUTOMATION_INCOMPLETE" });
    expect(database.manifestUpdateMany).not.toHaveBeenCalled();
    expect(database.outboxCreate).not.toHaveBeenCalled();
  });

  it("fails closed when the authenticated doctor/practice does not own the visit", async () => {
    const { repo } = repository(null);

    await expect(
      reviewTemplateTwinField(
        { visitId: "visit-1", actor, correction: correction() },
        { repository: repo },
      ),
    ).rejects.toMatchObject({ code: "NOT_FOUND" });
    expect(repo.commit).not.toHaveBeenCalled();
  });

  it("rejects stale and signed manifests before reading or writing artifacts", async () => {
    const stale = context();
    stale.manifestVersion = 5;
    const staleRepo = repository(stale).repo;
    const signed = context();
    signed.status = "SIGNED";
    signed.signedDecisionAt = new Date(NOW);
    const signedRepo = repository(signed).repo;
    const artifacts = storage();

    await expect(
      reviewTemplateTwinField(
        { visitId: "visit-1", actor, correction: correction() },
        { repository: staleRepo, storage: artifacts },
      ),
    ).rejects.toMatchObject({ code: "OPTIMISTIC_CONFLICT" });
    await expect(
      reviewTemplateTwinField(
        { visitId: "visit-1", actor, correction: correction() },
        { repository: signedRepo, storage: artifacts },
      ),
    ).rejects.toMatchObject({ code: "SIGNED_IMMUTABLE" });
    expect(artifacts.readSourceArtifact).not.toHaveBeenCalled();
    expect(artifacts.storeOutputArtifact).not.toHaveBeenCalled();
  });

  it("refuses field review when the physician-visible SOAP changed after generation", async () => {
    const staleSoap = context();
    staleSoap.visit.soapVersion = 8;
    staleSoap.visit.soapFinal = `${REVIEWED_SOAP}\nEdited synthetic plan.`;
    const { repo } = repository(staleSoap);
    const artifacts = storage();

    await expect(
      reviewTemplateTwinField(
        { visitId: "visit-1", actor, correction: correction() },
        { repository: repo, storage: artifacts },
      ),
    ).rejects.toMatchObject({ code: "SOAP_BINDING_STALE" });
    expect(artifacts.readSourceArtifact).not.toHaveBeenCalled();
    expect(repo.commit).not.toHaveBeenCalled();
  });

  it.each([
    {
      name: "null evidence",
      mutate: (loaded: ReviewContext) => {
        loaded.compiledVersion.sourceArtifact.privacyScanEvidence = null;
      },
    },
    {
      name: "a legacy profile",
      mutate: (loaded: ReviewContext) => {
        loaded.compiledVersion.sourceArtifact.privacyScanEvidence = {
          ...SOURCE_PRIVACY_SCAN_EVIDENCE,
          profileVersion: "template-twin-source-phi-legacy-v0",
        };
      },
    },
    {
      name: "a certification hash mismatch",
      mutate: (loaded: ReviewContext) => {
        loaded.compiledVersion.certification = {
          sourcePrivacyScanEvidenceSha256: "0".repeat(64),
        };
      },
    },
  ])(
    "blocks correction before source I/O when provenance contains $name",
    async ({ mutate }) => {
      const loaded = context();
      mutate(loaded);
      const { repo } = repository(loaded);
      const artifacts = storage();
      const finalizeFill = vi.fn(fakeFinalize);

      await expect(
        reviewTemplateTwinField(
          {
            visitId: "visit-1",
            actor,
            correction: correction(),
            validationNow: NOW,
          },
          { repository: repo, storage: artifacts, finalizeFill },
        ),
      ).rejects.toMatchObject({
        code: "TEMPLATE_PROVENANCE_INVALID",
        message: expect.stringContaining(
          TEMPLATE_TWIN_SOURCE_PROVENANCE_GATE_CODE,
        ),
      });
      expect(artifacts.readSourceArtifact).not.toHaveBeenCalled();
      expect(artifacts.storeOutputArtifact).not.toHaveBeenCalled();
      expect(finalizeFill).not.toHaveBeenCalled();
      expect(repo.commit).not.toHaveBeenCalled();
    },
  );

  it("quarantines correction output when canonical encounter evidence changes during storage", async () => {
    const artifacts = storage(() => {
      mockRolloutAndVisitLocks(
        lockedVisitRow({
          rawTextInput: `${REVIEWED_SOAP}\nSynthetic encounter source drift.`,
        }),
      );
    });

    await expect(
      reviewTemplateTwinField(
        {
          visitId: "visit-1",
          actor,
          correction: correction(),
          validationNow: NOW,
        },
        {
          storage: artifacts,
          finalizeFill: fakeFinalize,
          factIdFactory: () => "a".repeat(24),
          now: () => new Date(NOW),
        },
      ),
    ).rejects.toMatchObject({ code: "ENCOUNTER_EVIDENCE_INVALID" });

    expect(artifacts.storeOutputArtifact).toHaveBeenCalledTimes(1);
    expect(database.manifestUpdateMany).not.toHaveBeenCalled();
  });

  it("appends a value delta, independently validates, renders, stores, and commits once", async () => {
    const loaded = context();
    const { repo, committed } = repository(loaded);
    const artifacts = storage();

    const result = await reviewTemplateTwinField(
      {
        visitId: "visit-1",
        actor,
        correction: correction(),
        validationNow: NOW,
      },
      {
        repository: repo,
        storage: artifacts,
        finalizeFill: fakeFinalize,
        factIdFactory: () => "4".repeat(24),
        now: () => new Date(NOW),
      },
    );

    expect(result).toMatchObject({
      manifestVersion: 5,
      status: "verified",
      roundTripVerified: true,
      certificationUrl: null,
    });
    expect(artifacts.readSourceArtifact).toHaveBeenCalledTimes(1);
    expect(artifacts.storeOutputArtifact).toHaveBeenCalledTimes(1);
    expect(committed()?.decision).toMatchObject({
      previousValue: null,
      correctedValue: "Severe",
      decisionKind: "clinician_correction",
      expectedManifestVersion: 4,
      createMappingRule: false,
    });
    expect(committed()?.soapVersion).toBe(7);
    expect(committed()?.prepared.manifest.facts.at(-1)).toMatchObject({
      speaker: "Physician correction",
    });
    expect(committed()?.reviewerEmail).toBe(actor.userEmail);
    expect(committed()).not.toHaveProperty("clearTemplateTwinVisitReview");
    expect(audit).not.toHaveBeenCalled();
  });

  it("claims the rendered object and durably enqueues correction audit in the owning transaction", async () => {
    const loaded = context();
    const capture = repository(loaded);
    await reviewTemplateTwinField(
      {
        visitId: "visit-1",
        actor,
        correction: correction(),
        validationNow: NOW,
      },
      {
        repository: capture.repo,
        storage: storage(),
        finalizeFill: fakeFinalize,
        factIdFactory: () => "8".repeat(24),
        now: () => new Date(NOW),
      },
    );
    const plan = capture.committed();
    expect(plan).not.toBeNull();

    await createTemplateTwinReviewRepository().commit(plan!);

    expect(database.transaction).toHaveBeenCalledWith(expect.any(Function), {
      isolationLevel: "ReadCommitted",
    });

    expect(database.ledgerUpdateMany).toHaveBeenCalledWith({
      where: {
        objectKey: plan!.storedOutput!.objectKey,
        practiceId: actor.practiceId,
        state: { in: ["WRITTEN_UNCLAIMED", "CLAIMED"] },
      },
      data: expect.objectContaining({
        state: "CLAIMED",
        claimType: "fill_manifest",
        claimId: loaded.id,
      }),
    });
    expect(database.outboxCreate).toHaveBeenCalledWith({
      data: expect.objectContaining({
        eventKey: `template-twin:field-reviewed:${loaded.id}:v5`,
        action: "TEMPLATE_TWIN_FIELD_REVIEWED",
        status: "PENDING",
        metadata: expect.not.objectContaining({
          previousValue: expect.anything(),
          correctedValue: expect.anything(),
          evidenceQuote: expect.anything(),
        }),
      }),
    });
    expect(
      database.manifestUpdateMany.mock.invocationCallOrder[0],
    ).toBeLessThan(database.outboxCreate.mock.invocationCallOrder[0]!);
    expect(database.decisionCreate.mock.invocationCallOrder[0]).toBeLessThan(
      database.outboxCreate.mock.invocationCallOrder[0]!,
    );
    expect(database.ledgerUpdateMany.mock.invocationCallOrder[0]).toBeLessThan(
      database.outboxCreate.mock.invocationCallOrder[0]!,
    );
  });

  it.each([
    {
      name: "same-version exact SOAP source drift",
      soapVersion: 7,
      soapFinal: `${REVIEWED_SOAP}\nSynthetic allergy correction outside the review.`,
    },
    {
      name: "SOAP version bump",
      soapVersion: 8,
      soapFinal: `${REVIEWED_SOAP}\nSynthetic medication correction outside the review.`,
    },
  ])(
    "quarantines correction output and leaves the fill NEEDS_REVIEW after $name during storage",
    async ({ soapVersion, soapFinal }) => {
      const artifacts = storage(() => {
        mockRolloutAndVisitLocks(lockedVisitRow({ soapVersion, soapFinal }));
      });

      await expect(
        reviewTemplateTwinField(
          {
            visitId: "visit-1",
            actor,
            correction: correction(),
            validationNow: NOW,
          },
          {
            storage: artifacts,
            finalizeFill: fakeFinalize,
            factIdFactory: () => "a".repeat(24),
            now: () => new Date(NOW),
          },
        ),
      ).rejects.toMatchObject({
        code: "SOAP_BINDING_STALE",
        message:
          "The SOAP note changed after the Original Template DOCX was generated. Regenerate and review the document before signing.",
      });

      expect(artifacts.storeOutputArtifact).toHaveBeenCalledTimes(1);
      expect(database.lockVisit).toHaveBeenCalledTimes(9);
      expect(database.manifestUpdateMany).toHaveBeenCalledTimes(1);
      expect(database.manifestUpdateMany).toHaveBeenCalledWith({
        where: {
          id: "fill-1",
          practiceId: "practice-1",
          status: { not: "SIGNED" },
          signedDecisionAt: null,
          manifestVersion: 4,
          manifestSha256: expect.stringMatching(/^[a-f0-9]{64}$/),
          soapVersion: 7,
          soapSha256: canonicalSoapSha256(REVIEWED_SOAP),
        },
        data: {
          status: "NEEDS_REVIEW",
          reviewedAt: null,
          reviewedById: null,
          reviewedManifestVersion: null,
          reviewedManifestSha256: null,
        },
      });
      expect(database.decisionCreate).not.toHaveBeenCalled();
      expect(database.ledgerUpdateMany).toHaveBeenCalledTimes(1);
      expect(database.ledgerUpdateMany).toHaveBeenCalledWith({
        where: expect.objectContaining({
          objectKey: expect.stringContaining("/template-twin/outputs/"),
          practiceId: "practice-1",
          state: "WRITTEN_UNCLAIMED",
          claimType: null,
          claimId: null,
        }),
        data: expect.objectContaining({
          state: "RETAINED",
          lastErrorCode: "SOAP_BINDING_STALE",
        }),
      });
      expect(database.outboxCreate).toHaveBeenCalledTimes(1);
      expect(database.outboxCreate).toHaveBeenCalledWith({
        data: expect.objectContaining({
          action: "TEMPLATE_TWIN_SAFETY_GATE_BLOCKED",
          metadata: expect.objectContaining({
            reasonCode: "SOAP_BINDING_STALE",
            expectedSoapVersion: 7,
            currentSoapVersion: soapVersion,
            outputQuarantined: true,
          }),
        }),
      });
    },
  );

  it("fails the correction transaction when durable audit enqueue fails", async () => {
    const loaded = context();
    const capture = repository(loaded);
    await reviewTemplateTwinField(
      {
        visitId: "visit-1",
        actor,
        correction: correction(),
        validationNow: NOW,
      },
      {
        repository: capture.repo,
        storage: storage(),
        finalizeFill: fakeFinalize,
        factIdFactory: () => "9".repeat(24),
        now: () => new Date(NOW),
      },
    );
    database.outboxCreate.mockRejectedValueOnce(
      new Error("synthetic durable audit unavailable"),
    );

    await expect(
      createTemplateTwinReviewRepository().commit(capture.committed()!),
    ).rejects.toThrow("synthetic durable audit unavailable");
  });

  it("rejects a corrected output claim when rollout generation changes during rendering", async () => {
    const barrier = deterministicBarrier();
    const artifacts = storage(() => barrier.stop());
    const operation = reviewTemplateTwinField(
      {
        visitId: "visit-1",
        actor,
        correction: correction(),
        validationNow: NOW,
      },
      {
        storage: artifacts,
        finalizeFill: fakeFinalize,
        factIdFactory: () => "d".repeat(24),
        now: () => new Date(NOW),
      },
    );

    await barrier.entered;
    practiceRolloutEnabled = false;
    practiceRolloutGeneration = BigInt(2);
    barrier.release();

    await expect(operation).rejects.toMatchObject({
      code: "TEMPLATE_TWIN_PRACTICE_DISABLED",
    });
    expect(database.manifestUpdateMany).not.toHaveBeenCalled();
    expect(database.decisionCreate).not.toHaveBeenCalled();
    expect(database.ledgerUpdateMany).not.toHaveBeenCalled();
    expect(database.outboxCreate).toHaveBeenCalledWith({
      data: expect.objectContaining({
        action: "TEMPLATE_TWIN_SAFETY_GATE_BLOCKED",
        metadata: expect.objectContaining({
          reasonCode: "TEMPLATE_TWIN_PRACTICE_DISABLED",
          operation: "field_correction_final_claim",
          outputWrittenUnclaimed: true,
        }),
      }),
    });
  });

  it("never asks the repository to clear generic visit review state", async () => {
    const loaded = context();
    loaded.visit.reviewReason =
      "Synthetic unrelated pipeline warning that still requires review.";
    const { repo, committed } = repository(loaded);

    await reviewTemplateTwinField(
      {
        visitId: "visit-1",
        actor,
        correction: correction(),
        validationNow: NOW,
      },
      {
        repository: repo,
        storage: storage(),
        finalizeFill: fakeFinalize,
        factIdFactory: () => "7".repeat(24),
        now: () => new Date(NOW),
      },
    );

    expect(committed()).not.toHaveProperty("clearTemplateTwinVisitReview");
  });

  it("records an explicit required-field clear while keeping review and signing blocked", async () => {
    const requiredField = field("narrative_text", { required: true });
    const loaded = context(requiredField);
    const { repo, committed } = repository(loaded);
    const artifacts = storage();

    const result = await reviewTemplateTwinField(
      {
        visitId: "visit-1",
        actor,
        correction: correction({ value: null }),
        validationNow: NOW,
      },
      {
        repository: repo,
        storage: artifacts,
        finalizeFill: fakeFinalize,
        now: () => new Date(NOW),
      },
    );

    expect(result).toMatchObject({
      status: "needs_review",
      roundTripVerified: false,
    });
    expect(committed()?.decision).toMatchObject({
      decisionKind: "clinician_clear",
      correctedValue: null,
    });
    expect(committed()).not.toHaveProperty("clearTemplateTwinVisitReview");
    expect(artifacts.readSourceArtifact).not.toHaveBeenCalled();
    expect(artifacts.storeOutputArtifact).not.toHaveBeenCalled();
  });

  it("plans an immutable-source mapping fork and returns its certification URL", async () => {
    const loaded = context();
    const { repo, committed } = repository(loaded, {
      draftTemplateId: "template-draft-2",
      draftTemplateVersion: 2,
    });

    const result = await reviewTemplateTwinField(
      {
        visitId: "visit-1",
        actor,
        correction: correction({ createMappingRule: true }),
        validationNow: NOW,
      },
      {
        repository: repo,
        storage: storage(),
        finalizeFill: fakeFinalize,
        factIdFactory: () => "5".repeat(24),
        now: () => new Date(NOW),
      },
    );

    expect(committed()?.fork).toMatchObject({
      targetFieldId: FIELD_ID,
      context: {
        compiledVersion: {
          sourceArtifactId: "source-1",
          noteTemplate: { id: "template-1", lineageId: "lineage-1" },
        },
      },
    });
    expect(result).toMatchObject({
      certificationUrl: "/settings/note-format/template-draft-2/certify",
      draftTemplateVersion: 2,
    });
  });

  it("rejects a transaction-time optimistic conflict after rendering", async () => {
    const { repo } = repository(context(), {
      applied: false,
      manifestVersion: null,
    });
    await expect(
      reviewTemplateTwinField(
        {
          visitId: "visit-1",
          actor,
          correction: correction(),
          validationNow: NOW,
        },
        {
          repository: repo,
          storage: storage(),
          finalizeFill: fakeFinalize,
          factIdFactory: () => "6".repeat(24),
        },
      ),
    ).rejects.toMatchObject({ code: "OPTIMISTIC_CONFLICT" });
  });
});
