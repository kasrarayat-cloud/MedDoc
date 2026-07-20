import { createHash } from "node:crypto";

import { beforeAll, beforeEach, describe, expect, it, vi } from "vitest";

const mocks = vi.hoisted(() => ({
  claimVisit: vi.fn(),
  createFill: vi.fn(),
  findFill: vi.fn(),
  findTemplate: vi.fn(),
  updateFill: vi.fn(),
  transaction: vi.fn(),
  ledgerUpdate: vi.fn(),
  ledgerFind: vi.fn(),
  findPractice: vi.fn(),
  outboxCreate: vi.fn(),
  lockVisit: vi.fn(),
  getProviderContext: vi.fn(),
  getPlanDisposition: vi.fn(),
  recordNotApplicable: vi.fn(),
  buildProviderReceipt: vi.fn(),
}));

vi.mock("@meddoc/db", () => ({
  default: {
    transcribeVisit: { updateMany: mocks.claimVisit },
    noteTemplate: { findFirst: mocks.findTemplate },
    templateTwinFillManifest: {
      create: mocks.createFill,
      findUnique: mocks.findFill,
      updateMany: mocks.updateFill,
    },
    templateTwinAuditOutbox: { create: mocks.outboxCreate },
    $transaction: mocks.transaction,
    practice: { findFirst: mocks.findPractice },
  },
}));
vi.mock("../runtime-attestation", () => ({
  registerTemplateTwinRuntimeAttestation: vi.fn().mockResolvedValue({
    instanceId: "app-1",
  }),
  TemplateTwinRuntimeAttestationError: class extends Error {},
}));
vi.mock("../provider-ownership", () => ({
  getTemplateTwinProviderOwnershipContext: mocks.getProviderContext,
  getTemplateTwinProviderPlanDisposition: mocks.getPlanDisposition,
  recordTemplateTwinProviderNotApplicable: mocks.recordNotApplicable,
  buildTemplateTwinProviderOwnershipReceipt: mocks.buildProviderReceipt,
  TemplateTwinProviderOwnershipError: class extends Error {
    constructor(readonly code: string) {
      super(
        "The Template Twin provider result is unavailable or cannot be safely reused.",
      );
    }
  },
}));

import { templateTwinMappingsSha256 } from "../mapping-hash";
import { templateTwinFieldIntentsSha256 } from "../field-intent";
import { processTemplateTwinVisit } from "../fill-engine";
import { canonicalSha256 } from "../canonical";
import { canonicalSoapSha256 } from "../soap-binding";
import { templateTwinVisitProviderSubjectSha256 } from "../live-provider-ownership";
import type { TemplateTwinArtifactStore } from "../storage";
import {
  buildTemplateTwinIntegrationFixture,
  SYNTHETIC_CONTEXT,
  SYNTHETIC_ENTITIES,
} from "./integration-fixture";
import { syntheticSourceAdmission } from "./source-admission-fixture";
import { sourceProviderOwnershipFixture } from "./provider-ownership-fixture";

const PRACTICE_ID = "practice-fill-concurrency";
const DOCTOR_ID = "doctor-fill-concurrency";
const VISIT_ID = "visit-fill-concurrency";
const PATIENT_ID = "patient-fill-concurrency";
const TEMPLATE_ID = "template-fill-concurrency";
const COMPILED_ID = "compiled-fill-concurrency";
const SOURCE_ID = "source-fill-concurrency";
const RELEASE_ID = "0eb13c1b-0893-4cb0-bbd6-68b3e544baac";
const RELEASE_IDENTITY_SHA256 = "1".repeat(64);
const RUNTIME_MANIFEST_SHA256 = "2".repeat(64);
const RUNTIME_INSTANCE_ID = "app-1";
const OLD_MANIFEST_SHA = "b".repeat(64);
const PROVIDER_RECEIPT_SHA = "c".repeat(64);
const CURRENT_SOAP = "Synthetic current SOAP for concurrency verification.";
const SOURCE_PRIVACY_SCAN_EVIDENCE = {
  profileVersion: "template-twin-source-phi-safe-alpha-v1" as const,
  provider: "anthropic" as const,
  model: "synthetic-privacy-model-v1",
  scannedAt: "2026-07-15T12:00:00.000Z",
  scannedPartCount: 8,
  approvedStaticAssetPolicySha256: "a".repeat(64),
  approvedStaticAssetCount: 0,
  approvedStaticAssetUsedCount: 0,
  approvedStaticAssetUsageSha256: "b".repeat(64),
};
const EMPTY_FIELD_INTENTS_SHA256 = templateTwinFieldIntentsSha256([]);

type Fixture = Awaited<ReturnType<typeof buildTemplateTwinIntegrationFixture>>;
let fixture: Fixture;
let outputWrites: number;
let globalRolloutEnabled: boolean;
let globalRolloutGeneration: bigint;
let practiceRolloutEnabled: boolean;
let practiceRolloutGeneration: bigint;

function templateRow() {
  const ownership = sourceProviderOwnershipFixture({
    practiceId: PRACTICE_ID,
    actorUserId: DOCTOR_ID,
    sourceArtifactId: SOURCE_ID,
    sourceSha256: fixture.ir.source.sha256,
    compiledVersionId: COMPILED_ID,
    noteTemplateId: TEMPLATE_ID,
    noteTemplateVersion: 1,
    sourceLineageId: "lineage-fill-concurrency",
    sourceLineageVersion: 1,
  });
  return {
    id: TEMPLATE_ID,
    version: 1,
    templateTwinCompiledVersion: {
      id: COMPILED_ID,
      compilerVersion: fixture.ir.compilerVersion,
      compiledDocumentIr: fixture.ir,
      certificationStatus: "CERTIFIED",
      providerOwnershipEvidence: ownership.evidence,
      providerOwnershipSha256: ownership.sha256,
      certification: {
        id: "certification-fill-concurrency",
        approvedMappingsSha256: templateTwinMappingsSha256(fixture.mappings),
        approvedFieldIntentsSha256: EMPTY_FIELD_INTENTS_SHA256,
        approvedCustomExampleProofSha256: null,
        sourcePrivacyScanEvidenceSha256: canonicalSha256(
          SOURCE_PRIVACY_SCAN_EVIDENCE,
        ),
      },
      sourceArtifact: {
        id: SOURCE_ID,
        lineageVersion: 1,
        ...syntheticSourceAdmission({
          practiceId: PRACTICE_ID,
          lineageId: "lineage-fill-concurrency",
          minimizedSha256: fixture.ir.source.sha256,
          minimizedSizeBytes: fixture.source.byteLength,
        }),
        objectKey: `practices/${PRACTICE_ID}/template-twin/sources/lineage/v1/source/${fixture.ir.source.sha256}.docx`,
        privacyScanEvidence: SOURCE_PRIVACY_SCAN_EVIDENCE,
        providerOwnershipEvidence: ownership.evidence,
        providerOwnershipSha256: ownership.sha256,
      },
      fields: fixture.mappings.map((mapping) => ({
        fieldId: mapping.fieldId,
        detectionStatus: "CERTIFIED",
        intentDecisions: [],
        mapping: {
          clinicalConcept: mapping.clinicalConcept,
          expectedDataType: mapping.expectedDataType,
          polarityBehavior: mapping.polarityBehavior,
          temporality: mapping.temporality,
          laterality: mapping.laterality,
          unitPolicy: mapping.unitPolicy,
          approvedSynonyms: mapping.approvedSynonyms,
          required: mapping.required,
          blankPolicy: mapping.blankPolicy,
          unknownPolicy: mapping.unknownPolicy,
          practiceDefault: mapping.practiceDefault,
          mappingStatus: "CERTIFIED",
        },
      })),
    },
  };
}

function lockedVisitRow(
  overrides: Partial<{
    soapVersion: number;
    soapFinal: string | null;
    status: string;
  }> = {},
) {
  return {
    id: VISIT_ID,
    patientId: PATIENT_ID,
    userId: DOCTOR_ID,
    status: overrides.status ?? "READY",
    deletedAt: null,
    archivedAt: null,
    soapVersion: overrides.soapVersion ?? 1,
    soapFinal:
      overrides.soapFinal === undefined ? CURRENT_SOAP : overrides.soapFinal,
    reviewReason: null,
    inputMode: "text_notes",
    noteTemplateId: TEMPLATE_ID,
    noteTemplateVersion: 1,
    manualRetryCount: 0,
  };
}

function mockRolloutAndVisitLocks(visit = lockedVisitRow()) {
  mocks.lockVisit.mockImplementation(async (query: unknown) => {
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
    if (text.includes('FROM "practices"')) {
      return [{ id: PRACTICE_ID }];
    }
    if (text.includes('FROM "users"')) {
      return [
        {
          id: DOCTOR_ID,
          practiceId: PRACTICE_ID,
          role: "DOCTOR",
          isActive: true,
          deactivatedAt: null,
          suspendedAt: null,
          softDeletedAt: null,
          products: ["TRANSCRIBE_MD"],
        },
      ];
    }
    if (text.includes('FROM "note_templates"')) {
      return [
        {
          id: TEMPLATE_ID,
          version: 1,
          doctorId: DOCTOR_ID,
          templateKind: "template_twin_docx",
          status: "active",
        },
      ];
    }
    if (text.includes('FROM "template_twin_compiled_versions"')) {
      return [
        {
          id: COMPILED_ID,
          noteTemplateId: TEMPLATE_ID,
          sourceArtifactId: SOURCE_ID,
          certificationStatus: "CERTIFIED",
          providerOwnershipSha256: "a".repeat(64),
        },
      ];
    }
    if (text.includes('FROM "template_twin_source_artifacts"')) {
      return [
        {
          id: SOURCE_ID,
          practiceId: PRACTICE_ID,
          createdById: DOCTOR_ID,
          lineageId: "lineage-fill-concurrency",
          lineageVersion: 1,
          sha256: fixture.ir.source.sha256,
          validationStatus: "accepted",
          providerOwnershipSha256: "b".repeat(64),
        },
      ];
    }
    if (text.includes('FROM "template_twin_certifications"')) {
      return [
        {
          id: "certification-fill-concurrency",
          compiledVersionId: COMPILED_ID,
          certifiedById: DOCTOR_ID,
          providerAuthorizationMode: "LIVE",
          providerAuthorizationAdmissionId: null,
        },
      ];
    }
    if (text.includes("template_twin_live_provider_compilation_is_valid")) {
      return [{ valid: true }];
    }
    if (text.includes('FROM "transcribe_md_patients"')) {
      return [
        {
          id: PATIENT_ID,
          practiceId: PRACTICE_ID,
          externalId: "synthetic-unit-patient",
          deletedAt: null,
        },
      ];
    }
    return [visit];
  });
}

function providerContext(
  globalGeneration = BigInt(1),
  practiceGeneration = BigInt(1),
) {
  const identity = {
    practiceId: PRACTICE_ID,
    actorUserId: DOCTOR_ID,
    visitId: VISIT_ID,
    visitInputMode: "text_notes" as const,
    sourceArtifactId: SOURCE_ID,
    compiledVersionId: COMPILED_ID,
    noteTemplateId: TEMPLATE_ID,
    noteTemplateVersion: 1,
    sourceLineageId: "lineage-fill-concurrency",
    sourceLineageVersion: 1,
    sourceSha256: fixture.ir.source.sha256,
    logicalAttempt: 1,
  };
  return {
    ...identity,
    scope: "VISIT_PIPELINE" as const,
    subjectId: VISIT_ID,
    subjectSha256: templateTwinVisitProviderSubjectSha256(identity),
    syntheticAdmissionId: null,
    rolloutToken: {
      practiceId: PRACTICE_ID,
      globalGeneration,
      practiceGeneration,
      releaseId: RELEASE_ID,
      releaseIdentitySha256: RELEASE_IDENTITY_SHA256,
      runtimeManifestSha256: RUNTIME_MANIFEST_SHA256,
      runtimeInstanceId: RUNTIME_INSTANCE_ID,
    },
  };
}

function storage(
  onOutputStored?: () => void | Promise<void>,
): TemplateTwinArtifactStore {
  return {
    bucket: "synthetic-memory-only",
    storeQuarantineArtifact: vi.fn(),
    readQuarantineArtifact: vi.fn(),
    storeCandidateArtifact: vi.fn(),
    readCandidateArtifact: vi.fn(),
    storeSourceArtifact: vi.fn(),
    readSourceArtifact: vi.fn(async () => Buffer.from(fixture.source)),
    readOutputArtifact: vi.fn(),
    storeOutputArtifact: vi.fn(async (input) => {
      outputWrites += 1;
      const outputSha256 = createHash("sha256")
        .update(input.bytes)
        .digest("hex");
      const stored = {
        bucket: "synthetic-memory-only",
        objectKey: `practices/${PRACTICE_ID}/template-twin/outputs/${VISIT_ID}/${input.manifestSha256}/artifact/${outputSha256}.docx`,
        objectVersionId: "provider-output-version-synthetic",
        objectEtag: "provider-output-etag-synthetic",
        sha256: outputSha256,
        mimeType:
          "application/vnd.openxmlformats-officedocument.wordprocessingml.document" as const,
        sizeBytes: input.bytes.byteLength,
        created: true,
      };
      await onOutputStored?.();
      return stored;
    }),
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

function processInput(artifactStorage = storage()) {
  return {
    visitId: VISIT_ID,
    soapVersion: 1,
    soapFinal: CURRENT_SOAP,
    practiceId: PRACTICE_ID,
    doctorId: DOCTOR_ID,
    noteTemplateId: TEMPLATE_ID,
    noteTemplateVersion: 1,
    inputMode: "text" as const,
    contextText: SYNTHETIC_CONTEXT,
    entities: SYNTHETIC_ENTITIES,
    validationNow: "2026-07-15T12:00:00.000Z",
    resolverModelVersion: "synthetic-resolver-model",
    rolloutToken: {
      practiceId: PRACTICE_ID,
      globalGeneration: BigInt(1),
      practiceGeneration: BigInt(1),
      releaseId: RELEASE_ID,
      releaseIdentitySha256: RELEASE_IDENTITY_SHA256,
      runtimeManifestSha256: RUNTIME_MANIFEST_SHA256,
      runtimeInstanceId: RUNTIME_INSTANCE_ID,
    },
    storage: artifactStorage,
  };
}

beforeAll(async () => {
  fixture = await buildTemplateTwinIntegrationFixture();
});

beforeEach(() => {
  vi.clearAllMocks();
  delete process.env.TEMPLATE_TWIN_RUNTIME_MODE;
  process.env.TEMPLATE_TWIN_KILL_SWITCH = "false";
  outputWrites = 0;
  globalRolloutEnabled = true;
  globalRolloutGeneration = BigInt(1);
  practiceRolloutEnabled = true;
  practiceRolloutGeneration = BigInt(1);
  mocks.claimVisit.mockResolvedValue({ count: 1 });
  mocks.findTemplate.mockImplementation(async () => templateRow());
  mocks.createFill.mockResolvedValue({ id: "fill-created" });
  mocks.updateFill.mockResolvedValue({ count: 1 });
  mocks.findPractice.mockResolvedValue({ id: PRACTICE_ID });
  mocks.ledgerUpdate.mockResolvedValue({ count: 1 });
  mocks.ledgerFind.mockResolvedValue(null);
  mocks.outboxCreate.mockResolvedValue({ id: "render-audit-outbox" });
  mocks.getProviderContext.mockReturnValue(providerContext());
  mocks.getPlanDisposition.mockImplementation(
    ({ operation, operationInstance = "primary" }) => {
      if (operation === "L4_ANCHOR_VERIFY") {
        return {
          operation,
          operationInstance,
          disposition: "NOT_APPLICABLE",
          reasonCode: "EVIDENCE_ANCHORS_DISABLED",
        };
      }
      if (operation === "L6_POLISH") {
        return {
          operation,
          operationInstance,
          disposition: "NOT_APPLICABLE",
          reasonCode: "NO_FIXABLE_CRITIQUE_WORK",
        };
      }
      return {
        operation,
        operationInstance,
        disposition: "NOT_APPLICABLE",
        reasonCode: "POLISH_NOT_EXECUTED",
      };
    },
  );
  mocks.buildProviderReceipt.mockImplementation(
    ({ projection }: { projection: Record<string, unknown> }) => ({
      evidence: {
        contractVersion: "template-twin-provider-ownership-receipt-v2",
        practiceId: PRACTICE_ID,
        ...projection,
        executions: [
          {
            executionId: "provider-execution-fill-concurrency",
            operation: "L3_EXTRACT_ENTITIES",
            resultSha256: "e".repeat(64),
          },
          {
            executionId: "provider-execution-fill-concurrency-l4",
            operation: "L4_GENERATE_SOAP",
            resultSha256: "f".repeat(64),
          },
          {
            executionId: "provider-execution-fill-concurrency-l5",
            operation: "L5_SELF_CRITIQUE",
            resultSha256: "a".repeat(64),
          },
        ],
      },
      sha256: PROVIDER_RECEIPT_SHA,
    }),
  );
  mockRolloutAndVisitLocks();
  mocks.transaction.mockImplementation(
    async (callback: (tx: unknown) => Promise<unknown>) =>
      callback({
        transcribeVisit: { updateMany: mocks.claimVisit },
        templateTwinFillManifest: {
          create: mocks.createFill,
          findUnique: mocks.findFill,
          updateMany: mocks.updateFill,
        },
        templateTwinObjectLedger: {
          updateMany: mocks.ledgerUpdate,
          findUnique: mocks.ledgerFind,
        },
        templateTwinAuditOutbox: { create: mocks.outboxCreate },
        $queryRaw: mocks.lockVisit,
      }),
  );
});

describe("Template Twin worker provenance and manifest concurrency", () => {
  it("blocks direct provider/fill work before database or object access in bridge mode", async () => {
    process.env.TEMPLATE_TWIN_RUNTIME_MODE = "rollback-compat-v2";
    const artifacts = storage();

    await expect(
      processTemplateTwinVisit(processInput(artifacts)),
    ).rejects.toMatchObject({
      code: "TEMPLATE_TWIN_ROLLBACK_COMPAT_ACTIVE",
      message:
        "Template Twin provider work is unavailable in this runtime mode.",
    });
    expect(mocks.findPractice).not.toHaveBeenCalled();
    expect(mocks.claimVisit).not.toHaveBeenCalled();
    expect(artifacts.readSourceArtifact).not.toHaveBeenCalled();
    expect(outputWrites).toBe(0);
  });

  it("durably records a failed clinical render gate in the manifest transaction", async () => {
    mocks.findFill.mockResolvedValue(null);

    const result = await processTemplateTwinVisit({
      ...processInput(),
      entities: [],
    });

    expect(result.render).toBeNull();
    expect(mocks.createFill).toHaveBeenCalledWith(
      expect.objectContaining({
        data: expect.objectContaining({ status: "NEEDS_REVIEW" }),
      }),
    );
    expect(mocks.outboxCreate).toHaveBeenCalledWith(
      expect.objectContaining({
        data: expect.objectContaining({
          action: "TEMPLATE_TWIN_SAFETY_GATE_BLOCKED",
          metadata: expect.objectContaining({
            reasonCode: "FIELD_VALIDATION_BLOCKED_RENDER",
            blockerCount: expect.any(Number),
          }),
        }),
      }),
    );
    expect(mocks.transaction).toHaveBeenLastCalledWith(expect.any(Function), {
      isolationLevel: "ReadCommitted",
    });
    expect(outputWrites).toBe(0);
  });

  it("fails before pinning or rendering when the practice rollout flag is disabled", async () => {
    mocks.findPractice.mockResolvedValue(null);
    const artifacts = storage();

    await expect(
      processTemplateTwinVisit(processInput(artifacts)),
    ).rejects.toMatchObject({
      code: "ROLLOUT_DISABLED",
      message: "Template Twin is not enabled for this practice.",
    });

    expect(mocks.claimVisit).not.toHaveBeenCalled();
    expect(artifacts.readSourceArtifact).not.toHaveBeenCalled();
    expect(outputWrites).toBe(0);
  });

  it.each([
    {
      name: "practice",
      revoke: () => {
        practiceRolloutEnabled = false;
        practiceRolloutGeneration = BigInt(2);
      },
      code: "TEMPLATE_TWIN_PRACTICE_DISABLED",
    },
    {
      name: "global",
      revoke: () => {
        globalRolloutEnabled = false;
        globalRolloutGeneration = BigInt(2);
      },
      code: "TEMPLATE_TWIN_GLOBAL_DISABLED",
    },
  ])(
    "rejects a final output claim when $name rollout is revoked after worker admission",
    async ({ revoke, code }) => {
      mocks.findFill.mockResolvedValue(null);
      const barrier = deterministicBarrier();
      const operation = processTemplateTwinVisit(
        processInput(storage(() => barrier.stop())),
      );

      await barrier.entered;
      revoke();
      barrier.release();

      await expect(operation).rejects.toMatchObject({ code });
      expect(outputWrites).toBe(1);
      expect(mocks.createFill).not.toHaveBeenCalled();
      expect(mocks.updateFill).not.toHaveBeenCalled();
      expect(mocks.ledgerUpdate).not.toHaveBeenCalled();
      expect(mocks.outboxCreate).toHaveBeenCalledWith({
        data: expect.objectContaining({
          action: "TEMPLATE_TWIN_SAFETY_GATE_BLOCKED",
          metadata: expect.objectContaining({
            reasonCode: code,
            operation: "final_output_claim",
            outputWrittenUnclaimed: true,
          }),
        }),
      });
    },
  );

  it("rejects an old worker token after disable and re-enable advances the generation", async () => {
    mocks.findFill.mockResolvedValue(null);
    const barrier = deterministicBarrier();
    const operation = processTemplateTwinVisit(
      processInput(storage(() => barrier.stop())),
    );

    await barrier.entered;
    globalRolloutEnabled = false;
    globalRolloutGeneration = BigInt(2);
    globalRolloutEnabled = true;
    globalRolloutGeneration = BigInt(3);
    barrier.release();

    await expect(operation).rejects.toMatchObject({
      code: "TEMPLATE_TWIN_GLOBAL_GENERATION_STALE",
    });
    expect(mocks.createFill).not.toHaveBeenCalled();
    expect(mocks.ledgerUpdate).not.toHaveBeenCalled();
  });

  it("rejects the selection token when disable and re-enable happen before fill processing starts", async () => {
    mocks.findFill.mockResolvedValue(null);
    const admittedAtTemplateSelection = processInput().rolloutToken;

    // Selection admitted generation 1. A complete disable/re-enable cycle
    // happens before L4-L6 hand the selected Twin to the fill engine.
    globalRolloutEnabled = false;
    globalRolloutGeneration = BigInt(2);
    globalRolloutEnabled = true;
    globalRolloutGeneration = BigInt(3);

    await expect(
      processTemplateTwinVisit({
        ...processInput(),
        rolloutToken: admittedAtTemplateSelection,
      }),
    ).rejects.toMatchObject({
      code: "VISIT_AUTOMATION_LOCK_REJECTED",
    });
    // The live provider authority fence now rejects the stale selection at
    // the first owned database mutation, before source/output object I/O.
    expect(outputWrites).toBe(0);
    expect(mocks.createFill).not.toHaveBeenCalled();
    expect(mocks.updateFill).not.toHaveBeenCalled();
    expect(mocks.ledgerUpdate).not.toHaveBeenCalled();
  });

  it("admits and claims a new worker operation at the re-enabled generation", async () => {
    globalRolloutGeneration = BigInt(3);
    practiceRolloutGeneration = BigInt(3);
    mocks.getProviderContext.mockReturnValue(
      providerContext(BigInt(3), BigInt(3)),
    );
    mocks.findFill.mockResolvedValue(null);

    await expect(
      processTemplateTwinVisit({
        ...processInput(),
        rolloutToken: {
          practiceId: PRACTICE_ID,
          globalGeneration: BigInt(3),
          practiceGeneration: BigInt(3),
          releaseId: RELEASE_ID,
          releaseIdentitySha256: RELEASE_IDENTITY_SHA256,
          runtimeManifestSha256: RUNTIME_MANIFEST_SHA256,
          runtimeInstanceId: RUNTIME_INSTANCE_ID,
        },
      }),
    ).resolves.toBeDefined();

    expect(mocks.createFill).toHaveBeenCalledWith(
      expect.objectContaining({
        data: expect.objectContaining({
          status: "VERIFIED",
          pinnedGlobalRolloutGeneration: BigInt(3),
          pinnedPracticeRolloutGeneration: BigInt(3),
        }),
      }),
    );
    expect(mocks.ledgerUpdate).toHaveBeenCalledWith(
      expect.objectContaining({
        data: expect.objectContaining({ state: "CLAIMED" }),
      }),
    );
  });

  it("pins the selected template before source access and stops on a conflicting pin", async () => {
    const artifacts = storage();
    mocks.claimVisit.mockResolvedValue({ count: 0 });

    await expect(
      processTemplateTwinVisit(processInput(artifacts)),
    ).rejects.toMatchObject({ code: "TEMPLATE_PROVENANCE_MISMATCH" });

    expect(mocks.claimVisit).toHaveBeenCalledWith(
      expect.objectContaining({
        where: expect.objectContaining({
          id: VISIT_ID,
          userId: DOCTOR_ID,
        }),
        data: {
          noteTemplateId: TEMPLATE_ID,
          noteTemplateVersion: 1,
        },
      }),
    );
    expect(mocks.findTemplate).not.toHaveBeenCalled();
    expect(artifacts.readSourceArtifact).not.toHaveBeenCalled();
  });

  it("rejects a legacy certified source before object access or rendering", async () => {
    const admitted = templateRow();
    const legacy = {
      ...admitted,
      templateTwinCompiledVersion: {
        ...admitted.templateTwinCompiledVersion,
        sourceArtifact: {
          ...admitted.templateTwinCompiledVersion.sourceArtifact,
          quarantineArtifact: null,
        },
      },
    };
    mocks.findTemplate.mockResolvedValueOnce(legacy);
    const artifacts = storage();

    await expect(
      processTemplateTwinVisit(processInput(artifacts)),
    ).rejects.toMatchObject({ code: "TEMPLATE_PROVENANCE_MISMATCH" });

    expect(artifacts.readSourceArtifact).not.toHaveBeenCalled();
    expect(outputWrites).toBe(0);
    expect(mocks.createFill).not.toHaveBeenCalled();
    expect(mocks.updateFill).not.toHaveBeenCalled();
  });

  it("cannot overwrite a manifest that is signed while rendering is in flight", async () => {
    mocks.findFill
      .mockResolvedValueOnce({
        id: "fill-existing",
        status: "VERIFIED",
        signedDecisionAt: null,
        reviewedAt: null,
        soapVersion: 1,
        soapSha256: canonicalSoapSha256(CURRENT_SOAP),
        manifestVersion: 4,
        manifestSha256: OLD_MANIFEST_SHA,
        roundTripVerified: true,
        providerOwnershipSha256: PROVIDER_RECEIPT_SHA,
      })
      .mockResolvedValueOnce({
        status: "SIGNED",
        signedDecisionAt: new Date("2026-07-15T12:05:00.000Z"),
      });
    mocks.updateFill.mockResolvedValue({ count: 0 });

    await expect(
      processTemplateTwinVisit(processInput()),
    ).rejects.toMatchObject({
      code: "SIGNED_MANIFEST_IMMUTABLE",
    });

    expect(outputWrites).toBe(1);
    expect(mocks.updateFill).toHaveBeenCalledWith(
      expect.objectContaining({
        where: expect.objectContaining({
          id: "fill-existing",
          status: { not: "SIGNED" },
          signedDecisionAt: null,
          reviewedAt: null,
          soapVersion: 1,
          soapSha256: canonicalSoapSha256(CURRENT_SOAP),
          manifestVersion: 4,
          manifestSha256: OLD_MANIFEST_SHA,
        }),
      }),
    );
    expect(mocks.createFill).not.toHaveBeenCalled();
    expect(mocks.outboxCreate).not.toHaveBeenCalled();
  });

  it("never replaces a clinician-reviewed manifest with stale worker evidence", async () => {
    mocks.findFill.mockResolvedValue({
      id: "fill-existing",
      status: "VERIFIED",
      signedDecisionAt: null,
      reviewedAt: new Date("2026-07-15T12:03:00.000Z"),
      soapVersion: 1,
      soapSha256: canonicalSoapSha256(CURRENT_SOAP),
      manifestVersion: 5,
      manifestSha256: OLD_MANIFEST_SHA,
      roundTripVerified: true,
      providerOwnershipSha256: PROVIDER_RECEIPT_SHA,
    });

    await expect(
      processTemplateTwinVisit(processInput()),
    ).rejects.toMatchObject({
      code: "MANIFEST_CONFLICT",
    });

    expect(outputWrites).toBe(0);
    expect(mocks.updateFill).not.toHaveBeenCalled();
    expect(mocks.createFill).not.toHaveBeenCalled();
    expect(mocks.outboxCreate).not.toHaveBeenCalled();
  });

  it("regenerates an explicitly invalidated reviewed manifest after a SOAP edit", async () => {
    const reviewedAt = new Date("2026-07-15T12:03:00.000Z");
    mocks.findFill.mockResolvedValue({
      id: "fill-existing",
      status: "NEEDS_REVIEW",
      signedDecisionAt: null,
      reviewedAt,
      soapVersion: 1,
      soapSha256: canonicalSoapSha256(CURRENT_SOAP),
      manifestVersion: 6,
      manifestSha256: OLD_MANIFEST_SHA,
      roundTripVerified: false,
      providerOwnershipSha256: PROVIDER_RECEIPT_SHA,
    });

    const editedSoap = `${CURRENT_SOAP} Synthetic plan edit.`;
    mockRolloutAndVisitLocks(
      lockedVisitRow({ soapVersion: 2, soapFinal: editedSoap }),
    );
    await expect(
      processTemplateTwinVisit({
        ...processInput(),
        soapVersion: 2,
        soapFinal: editedSoap,
      }),
    ).resolves.toBeDefined();

    expect(mocks.updateFill).toHaveBeenCalledWith(
      expect.objectContaining({
        where: expect.objectContaining({
          id: "fill-existing",
          reviewedAt,
          soapVersion: 1,
          soapSha256: canonicalSoapSha256(CURRENT_SOAP),
        }),
        data: expect.objectContaining({
          soapVersion: 2,
          soapSha256: canonicalSoapSha256(editedSoap),
          reviewedAt: null,
          manifestVersion: { increment: 1 },
        }),
      }),
    );
  });

  it("updates only the exact unsigned manifest version observed before storage", async () => {
    mocks.findFill.mockResolvedValue({
      id: "fill-existing",
      status: "NEEDS_REVIEW",
      signedDecisionAt: null,
      reviewedAt: null,
      soapVersion: 1,
      soapSha256: canonicalSoapSha256(CURRENT_SOAP),
      manifestVersion: 7,
      manifestSha256: OLD_MANIFEST_SHA,
      roundTripVerified: false,
      providerOwnershipSha256: PROVIDER_RECEIPT_SHA,
    });

    const result = await processTemplateTwinVisit(processInput());

    expect(result.manifest.validation.issues).toEqual([]);
    expect(result.render?.verification.verified).toBe(true);
    const outputObjectKey =
      `practices/${PRACTICE_ID}/template-twin/outputs/${VISIT_ID}/` +
      `${result.manifestSha256}/artifact/${result.render!.outputSha256}.docx`;
    const expectedRenderEventKey = `template-twin:render-verified:${canonicalSha256(
      {
        visitId: VISIT_ID,
        manifestSha256: result.manifestSha256,
        outputObjectKey,
      },
    )}`;
    expect(mocks.updateFill).toHaveBeenCalledWith(
      expect.objectContaining({
        where: expect.objectContaining({
          id: "fill-existing",
          manifestVersion: 7,
          manifestSha256: OLD_MANIFEST_SHA,
          signedDecisionAt: null,
          reviewedAt: null,
          soapVersion: 1,
          soapSha256: canonicalSoapSha256(CURRENT_SOAP),
        }),
        data: expect.objectContaining({
          status: "VERIFIED",
          manifestVersion: { increment: 1 },
          criticalUnresolvedCount: 0,
          roundTripVerified: true,
        }),
      }),
    );
    expect(mocks.ledgerUpdate).toHaveBeenCalledWith(
      expect.objectContaining({
        where: expect.objectContaining({
          practiceId: PRACTICE_ID,
          state: { in: ["WRITTEN_UNCLAIMED", "CLAIMED"] },
        }),
        data: expect.objectContaining({
          state: "CLAIMED",
          claimType: "fill_manifest",
          claimId: "fill-existing",
        }),
      }),
    );
    expect(mocks.outboxCreate).toHaveBeenCalledWith({
      data: expect.objectContaining({
        eventKey: expectedRenderEventKey,
        practiceId: PRACTICE_ID,
        actorId: DOCTOR_ID,
        action: "TEMPLATE_TWIN_RENDER_VERIFIED",
        targetType: "TranscribeVisit",
        targetId: VISIT_ID,
        metadata: expect.objectContaining({
          compiledVersionId: COMPILED_ID,
          manifestSha256: result.manifestSha256,
          outputSha256: result.render!.outputSha256,
          rendererVersion: result.render!.rendererVersion,
        }),
      }),
    });
    expect(mocks.ledgerUpdate.mock.invocationCallOrder[0]).toBeLessThan(
      mocks.outboxCreate.mock.invocationCallOrder[0]!,
    );
  });

  it("claims a newly created output for the manifest in the same transaction", async () => {
    mocks.findFill.mockResolvedValue(null);
    mocks.createFill.mockResolvedValue({ id: "fill-created" });

    await expect(
      processTemplateTwinVisit(processInput()),
    ).resolves.toBeDefined();

    // Template provenance is pinned in one canonical-lock transaction before
    // source I/O, then the output is claimed in a second transaction. Both
    // retain the caller's admission; neither obtains a replacement rollout
    // generation after revocation.
    expect(mocks.transaction).toHaveBeenCalledTimes(2);
    expect(mocks.createFill).toHaveBeenCalledWith(
      expect.objectContaining({
        data: expect.objectContaining({
          practiceId: PRACTICE_ID,
          visitId: VISIT_ID,
          soapVersion: 1,
          soapSha256: expect.stringMatching(/^[a-f0-9]{64}$/),
        }),
        select: { id: true },
      }),
    );
    expect(mocks.ledgerUpdate).toHaveBeenCalledWith(
      expect.objectContaining({
        data: expect.objectContaining({
          state: "CLAIMED",
          claimType: "fill_manifest",
          claimId: "fill-created",
        }),
      }),
    );
    expect(mocks.outboxCreate).toHaveBeenCalledTimes(1);
  });

  it("quarantines create-path bytes when the exact SOAP source changes without a version bump", async () => {
    mocks.findFill.mockResolvedValue(null);
    const editedSoap = `${CURRENT_SOAP} Synthetic allergy edit.`;
    const artifacts = storage(() => {
      mockRolloutAndVisitLocks(
        lockedVisitRow({ soapVersion: 1, soapFinal: editedSoap }),
      );
    });

    await expect(
      processTemplateTwinVisit(processInput(artifacts)),
    ).rejects.toMatchObject({
      code: "SOAP_BINDING_STALE",
      message:
        "The SOAP note changed while the Original Template DOCX was being generated. Regenerate and review it before signing.",
    });

    expect(outputWrites).toBe(1);
    // Both the provenance pin and the final output claim traverse the full
    // live-authority lock set. Keep this additive so a future authority row
    // cannot make an otherwise-correct concurrency test brittle.
    const authorityLockSql = mocks.lockVisit.mock.calls
      .map(([query]) =>
        String(
          (query as { strings?: readonly string[] }).strings?.join(" ") ?? "",
        ),
      )
      .join("\n");
    expect(mocks.lockVisit.mock.calls.length).toBeGreaterThanOrEqual(16);
    for (const table of [
      '"users"',
      '"note_templates"',
      '"template_twin_compiled_versions"',
      '"template_twin_source_artifacts"',
      '"template_twin_certifications"',
      '"transcribe_visits"',
    ]) {
      expect(authorityLockSql).toContain(table);
    }
    expect(mocks.createFill).not.toHaveBeenCalled();
    expect(mocks.updateFill).not.toHaveBeenCalled();
    expect(mocks.ledgerUpdate).toHaveBeenCalledWith({
      where: expect.objectContaining({
        practiceId: PRACTICE_ID,
        state: "WRITTEN_UNCLAIMED",
        claimType: null,
        claimId: null,
      }),
      data: expect.objectContaining({
        state: "RETAINED",
        lastErrorCode: "SOAP_BINDING_STALE",
      }),
    });
    expect(mocks.outboxCreate).toHaveBeenCalledWith({
      data: expect.objectContaining({
        action: "TEMPLATE_TWIN_SAFETY_GATE_BLOCKED",
        metadata: expect.objectContaining({
          reasonCode: "SOAP_BINDING_STALE",
          expectedSoapVersion: 1,
          currentSoapVersion: 1,
          outputQuarantined: true,
        }),
      }),
    });
  });

  it("transitions the observed update-path fill to NEEDS_REVIEW when SOAP changes during storage", async () => {
    mocks.findFill.mockResolvedValue({
      id: "fill-existing",
      status: "VERIFIED",
      signedDecisionAt: null,
      reviewedAt: null,
      soapVersion: 1,
      soapSha256: canonicalSoapSha256(CURRENT_SOAP),
      manifestVersion: 8,
      manifestSha256: OLD_MANIFEST_SHA,
      roundTripVerified: true,
      providerOwnershipSha256: PROVIDER_RECEIPT_SHA,
    });
    const editedSoap = `${CURRENT_SOAP} Synthetic medication edit.`;
    const artifacts = storage(() => {
      mockRolloutAndVisitLocks(
        lockedVisitRow({ soapVersion: 2, soapFinal: editedSoap }),
      );
    });

    await expect(
      processTemplateTwinVisit(processInput(artifacts)),
    ).rejects.toMatchObject({ code: "SOAP_BINDING_STALE" });

    expect(outputWrites).toBe(1);
    expect(mocks.createFill).not.toHaveBeenCalled();
    expect(mocks.updateFill).toHaveBeenCalledTimes(1);
    expect(mocks.updateFill).toHaveBeenCalledWith({
      where: expect.objectContaining({
        id: "fill-existing",
        status: { not: "SIGNED" },
        signedDecisionAt: null,
        soapVersion: 1,
        soapSha256: canonicalSoapSha256(CURRENT_SOAP),
        manifestVersion: 8,
        manifestSha256: OLD_MANIFEST_SHA,
      }),
      data: {
        status: "NEEDS_REVIEW",
        reviewedAt: null,
        reviewedById: null,
        reviewedManifestVersion: null,
        reviewedManifestSha256: null,
      },
    });
    expect(mocks.ledgerUpdate).toHaveBeenCalledTimes(1);
    expect(mocks.ledgerUpdate).toHaveBeenCalledWith(
      expect.objectContaining({
        data: expect.objectContaining({
          state: "RETAINED",
          lastErrorCode: "SOAP_BINDING_STALE",
        }),
      }),
    );
    expect(mocks.outboxCreate).toHaveBeenCalledWith({
      data: expect.objectContaining({
        metadata: expect.objectContaining({
          reasonCode: "SOAP_BINDING_STALE",
          currentSoapVersion: 2,
        }),
      }),
    });
  });

  it("does not enqueue render verification when the object claim fails", async () => {
    mocks.findFill.mockResolvedValue(null);
    mocks.ledgerUpdate.mockResolvedValue({ count: 0 });
    mocks.ledgerFind.mockResolvedValue(null);

    await expect(
      processTemplateTwinVisit(processInput()),
    ).rejects.toMatchObject({
      code: "TEMPLATE_TWIN_OBJECT_LEDGER_CONFLICT",
    });

    expect(mocks.createFill).toHaveBeenCalledTimes(1);
    expect(mocks.outboxCreate).not.toHaveBeenCalled();
  });

  it("fails closed when durable render audit enqueue fails", async () => {
    mocks.findFill.mockResolvedValue(null);
    mocks.outboxCreate.mockRejectedValue(
      new Error("synthetic audit outbox unavailable"),
    );

    await expect(processTemplateTwinVisit(processInput())).rejects.toThrow(
      "synthetic audit outbox unavailable",
    );

    expect(mocks.ledgerUpdate).toHaveBeenCalledTimes(1);
    expect(mocks.outboxCreate).toHaveBeenCalledTimes(1);
  });
});
