import { beforeAll, beforeEach, describe, expect, it, vi } from "vitest";

const mocks = vi.hoisted(() => ({
  findTemplate: vi.fn(),
  executionCreate: vi.fn(),
  executionFindMany: vi.fn(),
  executionFindFirst: vi.fn(),
  executionUpdateMany: vi.fn(),
  outboxCreate: vi.fn(),
  transaction: vi.fn(),
  rollout: vi.fn(),
  currentPhysician: vi.fn(),
  queryRaw: vi.fn(),
  execute: vi.fn(),
  evaluate: vi.fn(),
}));

const storedRows: Array<Record<string, unknown>> = [];

vi.mock("@meddoc/db", () => {
  const tx = {
    $queryRaw: mocks.queryRaw,
    noteTemplate: { findFirst: mocks.findTemplate },
    templateTwinCustomExampleExecution: {
      create: mocks.executionCreate,
      findMany: mocks.executionFindMany,
      findFirst: mocks.executionFindFirst,
      updateMany: mocks.executionUpdateMany,
    },
    templateTwinAuditOutbox: { create: mocks.outboxCreate },
  };
  return {
    default: {
      ...tx,
      $transaction: mocks.transaction,
    },
    __tx: tx,
  };
});

vi.mock("../rollout", async (importOriginal) => ({
  ...(await importOriginal<typeof import("../rollout")>()),
  lockTemplateTwinRolloutForFinalClaim: mocks.rollout,
}));

vi.mock("../final-claim-authority", async (importOriginal) => ({
  ...(await importOriginal<typeof import("../final-claim-authority")>()),
  lockAndAssertCurrentTemplateTwinPhysician: mocks.currentPhysician,
}));

vi.mock("../custom-concepts/example-coverage", async (importOriginal) => ({
  ...(await importOriginal<
    typeof import("../custom-concepts/example-coverage")
  >()),
  executeTemplateTwinCustomExamples: mocks.execute,
  evaluateTemplateTwinCustomExampleCoverage: mocks.evaluate,
}));

import { buildSyntheticDocx } from "../../note-template-docx/__tests__/synthetic-docx";
import { compileTemplateDocx } from "../../note-template-docx/compiler";
import {
  acknowledgeTemplateTwinCustomExamples,
  readTemplateTwinCustomExampleCoverage,
  runTemplateTwinCustomExamples,
} from "../custom-example-service";
import { certifyCustomFieldSpecification } from "../field-intent";
import { synchronizeCustomSyntheticExamples } from "../custom-concepts/example-authoring";
import { deriveCustomConceptId } from "../custom-concepts";
import type { TemplateTwinRolloutToken } from "../rollout";

const W = "http://schemas.openxmlformats.org/wordprocessingml/2006/main";
const ACTOR = {
  userId: "doctor-custom-service@synthetic.test",
  userEmail: "doctor-custom-service@synthetic.test",
  practiceId: "practice-custom-service",
  rolloutToken: {
    practiceId: "practice-custom-service",
    globalGeneration: BigInt(2),
    practiceGeneration: BigInt(3),
  } satisfies TemplateTwinRolloutToken,
};
const REENABLED_ACTOR = {
  ...ACTOR,
  rolloutToken: {
    practiceId: ACTOR.practiceId,
    globalGeneration: BigInt(2),
    practiceGeneration: BigInt(4),
  } satisfies TemplateTwinRolloutToken,
};

let ownedRow: Record<string, unknown>;
let fieldId: string;
let conceptId: string;

function execution(batchId = "batch-custom-service") {
  return {
    id: "execution-custom-service",
    batchId,
    definition: {
      fieldId,
      conceptId,
      physicianName: "Synthetic score",
      approvedEvidenceCues: ["synthetic score"],
      allowedUnits: [],
      kind: "positive" as const,
      exampleId: "positive-1",
      syntheticEvidence: "Synthetic example: synthetic score is 8.",
      expectedValue: 8,
      expectedUnit: null,
      expectedStatus: "supported" as const,
      prohibitedValue: null,
      possibleValues: [],
      definitionSha256: "a".repeat(64),
      evidenceSha256: "b".repeat(64),
      specificationSha256: "c".repeat(64),
    },
    contractVersion: "template-twin-custom-example-proof/1.0.0" as const,
    specificationSetSha256: "d".repeat(64),
    extractionSchemaSha256: "e".repeat(64),
    extractorVersion: "template-twin-custom-scalar-extractor/1.0.0" as const,
    extractionSchemaVersion:
      "template-twin-custom-scalar-schema/1.0.0" as const,
    provider: "anthropic",
    providerSha256: "f".repeat(64),
    model: "synthetic-model-v1",
    modelSha256: "1".repeat(64),
    resultStatus: "supported",
    resultValue: 8,
    resultUnit: null,
    resultFactCount: 1,
    resultSummary: {
      sourceFactCount: 1,
      evidenceAnchorCount: 1,
      evidenceAnchorIds: ["anchor-synthetic"],
      candidateValues: [],
      unexpectedUnsafeOutcome: false,
    },
    resultSha256: "2".repeat(64),
    passed: true,
    failureCode: null,
  };
}

beforeAll(async () => {
  const source = await buildSyntheticDocx({
    documentXml: `<?xml version="1.0" encoding="UTF-8"?><w:document xmlns:w="${W}" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships"><w:body><w:p><w:r><w:t>[[synthetic score]]</w:t></w:r></w:p><w:sectPr><w:headerReference w:type="default" r:id="rIdHeader"/></w:sectPr></w:body></w:document>`,
    extraEntries: {
      "word/header1.xml": `<?xml version="1.0" encoding="UTF-8"?><w:hdr xmlns:w="${W}"><w:p><w:r><w:t>Synthetic header</w:t></w:r></w:p></w:hdr>`,
    },
  });
  const ir = compileTemplateDocx(source);
  const field = ir.fields[0]!;
  fieldId = field.fieldId;
  conceptId = deriveCustomConceptId({
    templateLineageId: "lineage-custom-service",
    compiledVersionId: "compiled-custom-service",
    fieldId,
  });
  const draft = synchronizeCustomSyntheticExamples({
    specificationVersion: "template-twin-field-specification/1.1.0",
    templateLineageId: "lineage-custom-service",
    compiledVersionId: "compiled-custom-service",
    fieldId,
    conceptId,
    physicianName: "Synthetic score",
    physicianDescription: "Synthetic scalar score for service tests only.",
    approvedEvidenceCues: ["synthetic score"],
    dataType: "number",
    allowedOptions: [],
    allowedUnits: [],
    permittedUnitConversions: [],
    allowedTemporalities: ["current"],
    allowedLateralities: ["not_applicable"],
    polarityPolicy: { allowExplicitDenial: false, exactDeniedOutput: null },
    required: true,
    unknownPolicy: "requires_input",
    maximumLength: null,
    numericRange: { minimum: 0, maximum: 20 },
    evidenceRequirements: {
      minimumAnchors: 1,
      acceptedEvidenceQualities: ["direct"],
    },
    positiveSyntheticExamples: [],
    negativeSyntheticExamples: [],
    ambiguitySyntheticExamples: [],
  });
  const specification = certifyCustomFieldSpecification({
    content: draft,
    templateLineageId: "lineage-custom-service",
    compiledVersionId: "compiled-custom-service",
    fieldId,
    physicianUserId: ACTOR.userId,
    certifiedAt: new Date("2026-07-16T12:00:00.000Z"),
  });
  ownedRow = {
    status: "draft",
    templateTwinCompiledVersion: {
      id: "compiled-custom-service",
      certificationStatus: "NEEDS_CONFIRMATION",
      certification: null,
      compiledDocumentIr: ir,
      sourceArtifact: { practiceId: ACTOR.practiceId },
      fields: [
        {
          id: "definition-custom-service",
          fieldId,
          mapping: {
            clinicalConcept: conceptId,
            expectedDataType: "number",
            polarityBehavior: "value_only",
            temporality: "current",
            laterality: "not_applicable",
            unitPolicy: "not_applicable",
            approvedSynonyms: [],
            required: true,
            blankPolicy: "requires_input",
            unknownPolicy: "requires_input",
            practiceDefault: null,
            mappingStatus: "CERTIFIED",
          },
          intentDecisions: [
            {
              id: "decision-custom-service",
              version: 1,
              intentKind: "CUSTOM_CONCEPT",
              supportedConcept: null,
              customConceptId: conceptId,
              customSpec: specification,
              customSpecSha256: specification.certification.contentSha256,
              reason: null,
              decidedById: ACTOR.userId,
              decidedAt: new Date("2026-07-16T12:00:00.000Z"),
            },
          ],
        },
      ],
    },
  };
});

beforeEach(() => {
  vi.clearAllMocks();
  storedRows.splice(0);
  mocks.findTemplate.mockResolvedValue(ownedRow);
  mocks.rollout.mockResolvedValue({ allowed: true, token: ACTOR.rolloutToken });
  mocks.currentPhysician.mockResolvedValue({ email: ACTOR.userEmail });
  mocks.queryRaw.mockResolvedValue([{ id: ACTOR.practiceId }]);
  mocks.execute.mockResolvedValue([execution()]);
  mocks.executionCreate.mockImplementation(async ({ data }) => {
    storedRows.push({ ...data, executedAt: new Date() });
    return data;
  });
  mocks.executionFindMany.mockImplementation(async () => [...storedRows]);
  mocks.executionFindFirst.mockImplementation(async () =>
    storedRows.length ? { batchId: storedRows.at(-1)?.batchId } : null,
  );
  mocks.executionUpdateMany.mockImplementation(async ({ where, data }) => {
    const row = storedRows.find(
      (candidate) =>
        candidate.id === where.id && candidate.acknowledgedAt == null,
    );
    if (!row) return { count: 0 };
    Object.assign(row, data);
    return { count: 1 };
  });
  mocks.outboxCreate.mockResolvedValue({ id: "outbox-custom-service" });
  mocks.transaction.mockImplementation(async (callback) => {
    const snapshot = structuredClone(storedRows);
    try {
      const database = await import("@meddoc/db");
      return await callback((database as unknown as { __tx: unknown }).__tx);
    } catch (error) {
      storedRows.splice(0, storedRows.length, ...snapshot);
      throw error;
    }
  });
  mocks.evaluate.mockImplementation(({ rows }) => ({
    requiredCount: 1,
    passedCount: rows.length === 1 ? 1 : 0,
    acknowledgedCount: rows[0]?.acknowledgedAt ? 1 : 0,
    ready: rows.length === 1 && Boolean(rows[0]?.acknowledgedAt),
    stale: false,
    latestBatchId: rows[0]?.batchId ?? null,
    proofSha256: rows[0]?.acknowledgedAt ? "3".repeat(64) : null,
    examples: [],
  }));
});

describe("Template Twin custom-example service finality", () => {
  it("projects no custom specification content for a stale physician identity", async () => {
    mocks.currentPhysician.mockRejectedValueOnce(
      new Error("synthetic current-authority revocation"),
    );

    await expect(
      readTemplateTwinCustomExampleCoverage({
        noteTemplateId: "template",
        doctorId: ACTOR.userId,
        practiceId: ACTOR.practiceId,
      }),
    ).rejects.toThrow("synthetic current-authority revocation");

    expect(mocks.findTemplate).not.toHaveBeenCalled();
    expect(mocks.executionFindFirst).not.toHaveBeenCalled();
    expect(mocks.queryRaw).toHaveBeenCalledTimes(1);
  });

  it("holds the active-practice lock before the actor and every coverage projection", async () => {
    await readTemplateTwinCustomExampleCoverage({
      noteTemplateId: "template",
      doctorId: ACTOR.userId,
      practiceId: ACTOR.practiceId,
    });

    expect(mocks.queryRaw).toHaveBeenCalledTimes(1);
    const sql = mocks.queryRaw.mock.calls[0]?.[0];
    expect(sql?.strings?.join(" ") ?? "").toContain('FROM "practices"');
    expect(mocks.queryRaw.mock.invocationCallOrder[0]).toBeLessThan(
      mocks.currentPhysician.mock.invocationCallOrder[0]!,
    );
    expect(mocks.currentPhysician.mock.invocationCallOrder[0]).toBeLessThan(
      mocks.findTemplate.mock.invocationCallOrder[0]!,
    );
    expect(mocks.findTemplate.mock.invocationCallOrder[0]).toBeLessThan(
      mocks.executionFindFirst.mock.invocationCallOrder[0]!,
    );
  });

  it("binds content-bearing custom specification reads to the current lifecycle in the same query", async () => {
    await expect(
      readTemplateTwinCustomExampleCoverage({
        noteTemplateId: "template",
        doctorId: ACTOR.userId,
        practiceId: ACTOR.practiceId,
      }),
    ).resolves.toMatchObject({ ready: false });

    expect(mocks.findTemplate.mock.calls[0]![0].where).toMatchObject({
      doctorId: ACTOR.userId,
      doctor: {
        is: {
          id: ACTOR.userId,
          practiceId: ACTOR.practiceId,
          role: "DOCTOR",
          isActive: true,
          deactivatedAt: null,
          suspendedAt: null,
          softDeletedAt: null,
          products: { has: "TRANSCRIBE_MD" },
          practice: { is: { id: ACTOR.practiceId, isActive: true } },
        },
      },
    });
  });

  it("checks owner and practice before invoking the example provider", async () => {
    mocks.findTemplate.mockResolvedValueOnce(null);
    await expect(
      runTemplateTwinCustomExamples({
        noteTemplateId: "template",
        actor: ACTOR,
      }),
    ).rejects.toMatchObject({ code: "NOT_FOUND" });
    expect(mocks.execute).not.toHaveBeenCalled();
    expect(storedRows).toHaveLength(0);
  });

  it("rejects a rollout change after provider work and persists no rows or audit", async () => {
    let release!: (value: unknown) => void;
    const barrier = new Promise((resolve) => {
      release = resolve;
    });
    mocks.execute.mockReturnValueOnce(barrier);
    const pending = runTemplateTwinCustomExamples({
      noteTemplateId: "template",
      actor: ACTOR,
    });
    await vi.waitFor(() => expect(mocks.execute).toHaveBeenCalledTimes(1));
    mocks.rollout.mockResolvedValueOnce({
      allowed: false,
      code: "TEMPLATE_TWIN_PRACTICE_GENERATION_STALE",
    });
    release([execution()]);
    await expect(pending).rejects.toMatchObject({ code: "ROLLOUT_CHANGED" });
    expect(storedRows).toHaveLength(0);
    expect(mocks.outboxCreate).not.toHaveBeenCalled();
  });

  it("persists no provider result when current physician authority is revoked before the final claim", async () => {
    let release!: (value: unknown) => void;
    const barrier = new Promise((resolve) => {
      release = resolve;
    });
    mocks.execute.mockReturnValueOnce(barrier);
    const pending = runTemplateTwinCustomExamples({
      noteTemplateId: "template",
      actor: ACTOR,
    });
    await vi.waitFor(() => expect(mocks.execute).toHaveBeenCalledTimes(1));
    mocks.currentPhysician.mockRejectedValueOnce(
      new Error("synthetic current-authority revocation"),
    );
    release([execution()]);

    await expect(pending).rejects.toThrow(
      "synthetic current-authority revocation",
    );
    expect(mocks.rollout.mock.invocationCallOrder[0]).toBeLessThan(
      mocks.currentPhysician.mock.invocationCallOrder[0]!,
    );
    expect(storedRows).toHaveLength(0);
    expect(mocks.outboxCreate).not.toHaveBeenCalled();
  });

  it("does not revive an old admission token after disable and re-enable", async () => {
    mocks.rollout.mockImplementation(async ({ pinnedToken }) =>
      pinnedToken.practiceGeneration === BigInt(4)
        ? { allowed: true, token: pinnedToken }
        : {
            allowed: false,
            code: "TEMPLATE_TWIN_PRACTICE_GENERATION_STALE",
          },
    );

    await expect(
      runTemplateTwinCustomExamples({
        noteTemplateId: "template",
        actor: ACTOR,
      }),
    ).rejects.toMatchObject({ code: "ROLLOUT_CHANGED" });
    expect(storedRows).toHaveLength(0);

    await expect(
      runTemplateTwinCustomExamples({
        noteTemplateId: "template",
        actor: REENABLED_ACTOR,
      }),
    ).resolves.toMatchObject({ ready: false });
    expect(storedRows).toHaveLength(1);
    expect(mocks.rollout).toHaveBeenNthCalledWith(
      1,
      expect.objectContaining({ pinnedToken: ACTOR.rolloutToken }),
    );
    expect(mocks.rollout).toHaveBeenNthCalledWith(
      2,
      expect.objectContaining({ pinnedToken: REENABLED_ACTOR.rolloutToken }),
    );
  });

  it("rejects a mapping/specification change between provider and final claim", async () => {
    const changed = structuredClone(ownedRow);
    const compiled = changed.templateTwinCompiledVersion as {
      fields: Array<{ mapping: { required: boolean } }>;
    };
    compiled.fields[0]!.mapping.required = false;
    mocks.findTemplate
      .mockResolvedValueOnce(ownedRow)
      .mockResolvedValueOnce(changed);
    await expect(
      runTemplateTwinCustomExamples({
        noteTemplateId: "template",
        actor: ACTOR,
      }),
    ).rejects.toMatchObject({ code: "STALE_CONFIGURATION" });
    expect(storedRows).toHaveLength(0);
    expect(mocks.outboxCreate).not.toHaveBeenCalled();
  });

  it("rolls back execution rows when the critical audit outbox fails", async () => {
    mocks.outboxCreate.mockRejectedValueOnce(
      new Error("synthetic outbox down"),
    );
    await expect(
      runTemplateTwinCustomExamples({
        noteTemplateId: "template",
        actor: ACTOR,
      }),
    ).rejects.toThrow("synthetic outbox down");
    expect(storedRows).toHaveLength(0);
  });

  it("persists execution+audit atomically, then acknowledges the exact batch", async () => {
    const run = await runTemplateTwinCustomExamples({
      noteTemplateId: "template",
      actor: ACTOR,
    });
    expect(run.ready).toBe(false);
    expect(storedRows).toHaveLength(1);
    expect(mocks.outboxCreate).toHaveBeenCalledTimes(1);

    const acknowledged = await acknowledgeTemplateTwinCustomExamples({
      noteTemplateId: "template",
      batchId: "batch-custom-service",
      actor: ACTOR,
    });
    expect(acknowledged.ready).toBe(true);
    expect(mocks.outboxCreate).toHaveBeenCalledTimes(2);
  });

  it("rolls back acknowledgement when its audit outbox fails", async () => {
    await runTemplateTwinCustomExamples({
      noteTemplateId: "template",
      actor: ACTOR,
    });
    mocks.outboxCreate.mockRejectedValueOnce(
      new Error("synthetic ack audit down"),
    );
    await expect(
      acknowledgeTemplateTwinCustomExamples({
        noteTemplateId: "template",
        batchId: "batch-custom-service",
        actor: ACTOR,
      }),
    ).rejects.toThrow("synthetic ack audit down");
    expect(storedRows[0]?.acknowledgedAt).toBeUndefined();
  });

  it("cannot acknowledge a batch after the physician is suspended, demoted, transferred, or loses product access", async () => {
    await runTemplateTwinCustomExamples({
      noteTemplateId: "template",
      actor: ACTOR,
    });
    mocks.currentPhysician.mockRejectedValueOnce(
      new Error("synthetic current-authority revocation"),
    );
    const priorAuditCount = mocks.outboxCreate.mock.calls.length;

    await expect(
      acknowledgeTemplateTwinCustomExamples({
        noteTemplateId: "template",
        batchId: "batch-custom-service",
        actor: ACTOR,
      }),
    ).rejects.toThrow("synthetic current-authority revocation");

    expect(storedRows[0]?.acknowledgedAt).toBeUndefined();
    expect(mocks.outboxCreate).toHaveBeenCalledTimes(priorAuditCount);
    expect(mocks.rollout.mock.invocationCallOrder.at(-1)!).toBeLessThan(
      mocks.currentPhysician.mock.invocationCallOrder.at(-1)!,
    );
  });

  it("allows exactly one winner in a concurrent acknowledgement CAS race", async () => {
    await runTemplateTwinCustomExamples({
      noteTemplateId: "template",
      actor: ACTOR,
    });

    const database = await import("@meddoc/db");
    const tx = (database as unknown as { __tx: unknown }).__tx;
    mocks.transaction.mockImplementation(async (callback) => callback(tx));

    let bothArrived!: () => void;
    const arrivals = new Promise<void>((resolve) => {
      bothArrived = resolve;
    });
    let release!: () => void;
    const barrier = new Promise<void>((resolve) => {
      release = resolve;
    });
    let updateCalls = 0;
    mocks.executionUpdateMany.mockImplementation(async ({ where, data }) => {
      updateCalls += 1;
      if (updateCalls === 2) bothArrived();
      await barrier;
      const row = storedRows.find(
        (candidate) =>
          candidate.id === where.id && candidate.acknowledgedAt == null,
      );
      if (!row) return { count: 0 };
      Object.assign(row, data);
      return { count: 1 };
    });

    const first = acknowledgeTemplateTwinCustomExamples({
      noteTemplateId: "template",
      batchId: "batch-custom-service",
      actor: ACTOR,
    });
    const second = acknowledgeTemplateTwinCustomExamples({
      noteTemplateId: "template",
      batchId: "batch-custom-service",
      actor: ACTOR,
    });
    await arrivals;
    release();
    const results = await Promise.allSettled([first, second]);

    expect(
      results.filter((result) => result.status === "fulfilled"),
    ).toHaveLength(1);
    const rejected = results.find((result) => result.status === "rejected");
    expect(rejected).toMatchObject({
      status: "rejected",
      reason: expect.objectContaining({ code: "ALREADY_ACKNOWLEDGED" }),
    });
    expect(storedRows[0]?.acknowledgedAt).toBeInstanceOf(Date);
    expect(mocks.outboxCreate).toHaveBeenCalledTimes(2);
  });
});
