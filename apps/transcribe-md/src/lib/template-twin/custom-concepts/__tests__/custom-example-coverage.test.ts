import { describe, expect, it, vi } from "vitest";

vi.mock("../../provider-ownership", () => ({
  getTemplateTwinProviderOwnershipContext: vi.fn(() => null),
  requireTemplateTwinProviderOwnershipContext: vi.fn(() => ({
    scope: "CUSTOM_EXAMPLE",
  })),
  runTemplateTwinOwnedModelComplete: vi.fn(
    async (input: {
      args: unknown;
      client: { complete(args: unknown): Promise<unknown> };
    }) => input.client.complete(input.args),
  ),
  runWithTemplateTwinProviderOwnershipContext: vi.fn(
    async (_context: unknown, callback: () => Promise<unknown>) => callback(),
  ),
  buildTemplateTwinProviderOwnershipReceipt: vi.fn(() => ({
    evidence: {
      contractVersion: "template-twin-provider-ownership-receipt-v2",
      providerMode: "LIVE",
      executions: [],
    },
    sha256: "c".repeat(64),
  })),
}));

import {
  buildCanonicalCustomConceptEvidence,
  computeCustomExtractionSchemaHash,
  computeTemplateFieldSpecificationContentSha256,
  computeTemplateFieldSyntheticCoverageSha256,
  deriveCustomConceptId,
  type CertifiedTemplateFieldSpecification,
  type ExtractCertifiedCustomConceptsInput,
  type TemplateFieldSpecificationContent,
} from "../index";
import {
  evaluateTemplateTwinCustomExampleCoverage,
  executeTemplateTwinCustomExamples,
  type PersistedTemplateTwinCustomExampleExecution,
  type TemplateTwinCustomExampleExecution,
} from "../example-coverage";
import { assertTemplateTwinCustomExamplesReadyForCertification } from "../../custom-example-service";
import { canonicalSha256 } from "../../canonical";
import { runWithTemplateTwinProviderOwnershipContext } from "../../provider-ownership";

const FIELD_ID = `ttf_${"1".repeat(24)}`;
const LINEAGE_ID = "synthetic-custom-example-lineage";
const COMPILED_ID = "synthetic-custom-example-compiled";
const PHYSICIAN_ID = "doctor-custom-example@synthetic.test";
const ROLLOUT_TOKEN = {
  practiceId: "practice-synthetic-example",
  globalGeneration: BigInt(1),
  practiceGeneration: BigInt(1),
};
const EXECUTION_IDENTITY = {
  noteTemplateVersion: 1,
  sourceArtifactId: "synthetic-custom-example-source",
  compiledVersionId: COMPILED_ID,
  sourceLineageId: LINEAGE_ID,
  sourceLineageVersion: 1,
  sourceSha256: "d".repeat(64),
};

function specification(
  overrides: Partial<TemplateFieldSpecificationContent> = {},
): CertifiedTemplateFieldSpecification {
  const conceptId = deriveCustomConceptId({
    templateLineageId: LINEAGE_ID,
    compiledVersionId: COMPILED_ID,
    fieldId: FIELD_ID,
  });
  const content: TemplateFieldSpecificationContent = {
    specificationVersion: "template-twin-field-specification/1.1.0",
    templateLineageId: LINEAGE_ID,
    compiledVersionId: COMPILED_ID,
    fieldId: FIELD_ID,
    conceptId,
    physicianName: "Synthetic finding",
    physicianDescription:
      "A fictional scalar finding used only to test the template extractor.",
    approvedEvidenceCues: ["synthetic finding"],
    dataType: "narrative_text",
    allowedOptions: [],
    allowedUnits: [],
    permittedUnitConversions: [],
    allowedTemporalities: ["current"],
    allowedLateralities: ["not_applicable"],
    polarityPolicy: {
      allowExplicitDenial: false,
      exactDeniedOutput: null,
    },
    required: true,
    unknownPolicy: "requires_input",
    maximumLength: 120,
    numericRange: null,
    evidenceRequirements: {
      minimumAnchors: 1,
      acceptedEvidenceQualities: ["direct"],
    },
    positiveSyntheticExamples: [
      {
        exampleId: "positive-alpha",
        syntheticEvidence: "Synthetic example: synthetic finding is alpha.",
        expectedValue: "alpha",
        expectedUnit: null,
      },
    ],
    negativeSyntheticExamples: [
      {
        exampleId: "negative-absent",
        syntheticEvidence:
          "Synthetic example: this encounter discusses an unrelated detail.",
        prohibitedValue: "alpha",
        reason: "The field-specific value is not present.",
      },
    ],
    ambiguitySyntheticExamples: [
      {
        exampleId: "ambiguous-alpha-beta",
        syntheticEvidence:
          "Synthetic example: synthetic finding might be alpha or beta.",
        possibleValues: ["alpha", "beta"],
        reason: "Two incompatible values remain possible.",
      },
    ],
    ...overrides,
  };
  return {
    ...content,
    certification: {
      status: "certified",
      certifiedByUserId: PHYSICIAN_ID,
      certifiedAt: "2026-07-16T12:00:00.000Z",
      contentSha256: computeTemplateFieldSpecificationContentSha256(content),
      syntheticCoverageSha256:
        computeTemplateFieldSyntheticCoverageSha256(content),
    },
  };
}

function anchorId(evidence: string): string {
  return buildCanonicalCustomConceptEvidence({
    mode: "text",
    contextText: evidence,
  }).anchors[0]!.evidenceAnchorId;
}

function response(input: {
  spec: CertifiedTemplateFieldSpecification;
  state:
    | "supported"
    | "not_mentioned"
    | "ambiguous"
    | "conflict";
  evidence: string;
  value?: string;
  values?: readonly string[];
}) {
  const noObservation = input.state === "not_mentioned";
  return {
    extractionSchemaHash: computeCustomExtractionSchemaHash([input.spec]),
    fields: [
      {
        conceptId: input.spec.conceptId,
        state: input.state,
        reasonCode:
          input.state === "supported"
            ? "EVIDENCE_PRESENT"
            : input.state === "not_mentioned"
              ? "NO_EVIDENCE"
              : input.state === "conflict"
                ? "CONFLICTING_EVIDENCE"
                : "AMBIGUOUS_EVIDENCE",
        observations: noObservation
          ? []
          : (input.values ?? [input.value ?? "alpha"]).map((value) => ({
                value,
                unit: null,
                polarity: "affirmed",
                temporality: "current",
                laterality: "not_applicable",
                evidenceAnchorIds: [anchorId(input.evidence)],
              })),
      },
    ],
  };
}

function clientWith(...responses: unknown[]) {
  const complete = vi.fn();
  for (const item of responses) complete.mockResolvedValueOnce(item);
  return {
    complete,
    client: { complete } as unknown as NonNullable<
      ExtractCertifiedCustomConceptsInput["client"]
    >,
  };
}

function privacyClient() {
  return {
    complete: vi.fn().mockResolvedValue({
      directIdentifierClasses: [],
      appearsExplicitlySynthetic: true,
      anyUncertain: false,
    }),
  } as unknown as NonNullable<
    Parameters<typeof executeTemplateTwinCustomExamples>[0]["privacyClient"]
  >;
}

function persisted(
  execution: TemplateTwinCustomExampleExecution,
  overrides: Partial<PersistedTemplateTwinCustomExampleExecution> = {},
): PersistedTemplateTwinCustomExampleExecution {
  return {
    id: execution.id,
    batchId: execution.batchId,
    fieldId: execution.definition.fieldId,
    conceptId: execution.definition.conceptId,
    exampleKind: execution.definition.kind,
    exampleId: execution.definition.exampleId,
    exampleDefinitionSha256: execution.definition.definitionSha256,
    specificationSha256: execution.definition.specificationSha256,
    specificationSetSha256: execution.specificationSetSha256,
    mappingsSha256: "a".repeat(64),
    fieldIntentsSha256: "b".repeat(64),
    contractVersion: execution.contractVersion,
    extractionSchemaSha256: execution.extractionSchemaSha256,
    extractorVersion: execution.extractorVersion,
    extractionSchemaVersion: execution.extractionSchemaVersion,
    provider: execution.provider,
    providerSha256: execution.providerSha256,
    model: execution.model,
    modelSha256: execution.modelSha256,
    resultStatus: execution.resultStatus,
    resultValue: execution.resultValue,
    resultUnit: execution.resultUnit,
    resultFactCount: execution.resultFactCount,
    resultSummary: execution.resultSummary,
    resultSha256: execution.resultSha256,
    passed: execution.passed,
    failureCode: execution.failureCode,
    acknowledgedById: PHYSICIAN_ID,
    acknowledgedAt: new Date("2026-07-16T13:00:00.000Z"),
    ...overrides,
  };
}

function rehashPersistedResult(
  execution: TemplateTwinCustomExampleExecution,
  row: PersistedTemplateTwinCustomExampleExecution,
): PersistedTemplateTwinCustomExampleExecution {
  const core = {
    id: row.id,
    batchId: row.batchId,
    definition: execution.definition,
    contractVersion: row.contractVersion,
    specificationSetSha256: row.specificationSetSha256,
    extractionSchemaSha256: row.extractionSchemaSha256,
    extractorVersion: row.extractorVersion,
    extractionSchemaVersion: row.extractionSchemaVersion,
    provider: row.provider,
    providerSha256: row.providerSha256,
    model: row.model,
    modelSha256: row.modelSha256,
    resultStatus: row.resultStatus,
    resultValue: row.resultValue,
    resultUnit: row.resultUnit,
    resultFactCount: row.resultFactCount,
    resultSummary: row.resultSummary,
    passed: row.passed,
    failureCode: row.failureCode,
  };
  return { ...row, resultSha256: canonicalSha256(core) };
}

describe("physician-reviewed custom-concept example coverage", () => {
  it("executes every exact positive, negative, and ambiguity example through the shared extractor", async () => {
    const spec = specification();
    const positive = spec.positiveSyntheticExamples[0]!;
    const negative = spec.negativeSyntheticExamples[0]!;
    const ambiguity = spec.ambiguitySyntheticExamples[0]!;
    const mock = clientWith(
      response({
        spec,
        state: "supported",
        evidence: positive.syntheticEvidence,
        value: "alpha",
      }),
      response({
        spec,
        state: "not_mentioned",
        evidence: negative.syntheticEvidence,
      }),
      response({
        spec,
        state: "ambiguous",
        evidence: ambiguity.syntheticEvidence,
        values: ["alpha", "beta"],
      }),
    );
    const privacy = privacyClient();
    const executions = await executeTemplateTwinCustomExamples({
      specifications: [spec],
      practiceId: "practice-synthetic-example",
      userId: PHYSICIAN_ID,
      noteTemplateId: "template-synthetic-example",
      ...EXECUTION_IDENTITY,
      rolloutToken: ROLLOUT_TOKEN,
      model: "mock-certified-example-model-v1",
      client: mock.client,
      privacyClient: privacy,
      batchId: "00000000-0000-4000-8000-000000000001",
    });

    expect(mock.complete).toHaveBeenCalledTimes(3);
    expect(privacy.complete).toHaveBeenCalledTimes(1);
    expect(executions.map((item) => [item.definition.kind, item.passed])).toEqual(
      [
        ["positive", true],
        ["negative", true],
        ["ambiguity", true],
      ],
    );
    expect(executions[2]?.resultFactCount).toBe(0);
    expect(executions.every((item) => item.modelSha256.length === 64)).toBe(
      true,
    );
    expect(new Set(executions.map((item) => item.id)).size).toBe(3);
    expect(
      executions.every(
        (item) => item.providerOwnershipReceipt?.sha256 === "c".repeat(64),
      ),
    ).toBe(true);
    expect(
      vi
        .mocked(runWithTemplateTwinProviderOwnershipContext)
        .mock.calls.slice(-3)
        .map(([context]) => context),
    ).toEqual(
      executions.map((execution) =>
        expect.objectContaining({
          visitId: null,
          scope: "CUSTOM_EXAMPLE",
          subjectId: execution.id,
          subjectSha256: execution.definition.evidenceSha256,
          sourceArtifactId: EXECUTION_IDENTITY.sourceArtifactId,
          compiledVersionId: EXECUTION_IDENTITY.compiledVersionId,
          noteTemplateId: "template-synthetic-example",
        }),
      ),
    );
  });

  it("fails a negative example that produces its prohibited value", async () => {
    const spec = specification({
      positiveSyntheticExamples: [
        {
          exampleId: "positive-alpha",
          syntheticEvidence: "Synthetic example: synthetic finding is alpha.",
          expectedValue: "alpha",
          expectedUnit: null,
        },
      ],
      negativeSyntheticExamples: [
        {
          exampleId: "negative-alpha",
          syntheticEvidence: "Synthetic example: synthetic finding is alpha.",
          prohibitedValue: "alpha",
          reason: "This adversarial example must reject alpha.",
        },
      ],
    });
    const positive = spec.positiveSyntheticExamples[0]!;
    const negative = spec.negativeSyntheticExamples[0]!;
    const ambiguity = spec.ambiguitySyntheticExamples[0]!;
    const mock = clientWith(
      response({ spec, state: "supported", evidence: positive.syntheticEvidence }),
      response({ spec, state: "supported", evidence: negative.syntheticEvidence }),
      response({
        spec,
        state: "ambiguous",
        evidence: ambiguity.syntheticEvidence,
        values: ["alpha", "beta"],
      }),
    );
    const executions = await executeTemplateTwinCustomExamples({
      specifications: [spec],
      practiceId: "practice-synthetic-example",
      userId: PHYSICIAN_ID,
      noteTemplateId: "template-synthetic-example",
      ...EXECUTION_IDENTITY,
      rolloutToken: ROLLOUT_TOKEN,
      model: "mock-certified-example-model-v1",
      client: mock.client,
      privacyClient: privacyClient(),
    });
    expect(executions.find((item) => item.definition.kind === "negative")).toMatchObject({
      passed: false,
      failureCode: "TT_CUSTOM_EXAMPLE_NEGATIVE_FALSE_POSITIVE",
    });
  });

  it("keeps caught extraction failures receipt-free and nonpassing", async () => {
    const spec = specification();
    const complete = vi.fn().mockRejectedValue(new Error("synthetic failure"));
    const executions = await executeTemplateTwinCustomExamples({
      specifications: [spec],
      practiceId: "practice-synthetic-example",
      userId: PHYSICIAN_ID,
      noteTemplateId: "template-synthetic-example",
      ...EXECUTION_IDENTITY,
      rolloutToken: ROLLOUT_TOKEN,
      model: "mock-certified-example-model-v1",
      client: { complete } as never,
      privacyClient: privacyClient(),
    });

    expect(executions).toHaveLength(3);
    expect(new Set(executions.map((execution) => execution.id)).size).toBe(3);
    expect(
      executions.every(
        (execution) =>
          !execution.passed &&
          execution.resultStatus === "extraction_rejected" &&
          execution.providerOwnershipReceipt === null,
      ),
    ).toBe(true);
  });

  it("fails a negative example that produces any different usable value", async () => {
    const spec = specification({
      negativeSyntheticExamples: [
        {
          exampleId: "negative-different-value",
          syntheticEvidence:
            "Synthetic example: synthetic finding is beta.",
          prohibitedValue: "alpha",
          reason:
            "Negative examples must reject every usable false positive, not only one named value.",
        },
      ],
    });
    const positive = spec.positiveSyntheticExamples[0]!;
    const negative = spec.negativeSyntheticExamples[0]!;
    const ambiguity = spec.ambiguitySyntheticExamples[0]!;
    const mock = clientWith(
      response({ spec, state: "supported", evidence: positive.syntheticEvidence }),
      response({
        spec,
        state: "supported",
        evidence: negative.syntheticEvidence,
        value: "beta",
      }),
      response({
        spec,
        state: "ambiguous",
        evidence: ambiguity.syntheticEvidence,
        values: ["alpha", "beta"],
      }),
    );
    const executions = await executeTemplateTwinCustomExamples({
      specifications: [spec],
      practiceId: "practice-synthetic-example",
      userId: PHYSICIAN_ID,
      noteTemplateId: "template-synthetic-example",
      ...EXECUTION_IDENTITY,
      rolloutToken: ROLLOUT_TOKEN,
      model: "mock-certified-example-model-v1",
      client: mock.client,
      privacyClient: privacyClient(),
    });
    expect(
      executions.find((item) => item.definition.kind === "negative"),
    ).toMatchObject({
      passed: false,
      failureCode: "TT_CUSTOM_EXAMPLE_NEGATIVE_FALSE_POSITIVE",
    });
  });

  it("requires an ambiguity or conflict outcome with no renderable target", async () => {
    const spec = specification({
      ambiguitySyntheticExamples: [
        {
          exampleId: "ambiguous-model-overreach",
          syntheticEvidence:
            "Synthetic example: synthetic finding is alpha.",
          possibleValues: ["alpha", "beta"],
          reason:
            "The certified example requires an ambiguity outcome even if a model tries to render one candidate.",
        },
      ],
    });
    const examples = [
      spec.positiveSyntheticExamples[0]!,
      spec.negativeSyntheticExamples[0]!,
      spec.ambiguitySyntheticExamples[0]!,
    ];
    const mock = clientWith(
      response({ spec, state: "supported", evidence: examples[0].syntheticEvidence }),
      response({ spec, state: "not_mentioned", evidence: examples[1].syntheticEvidence }),
      response({ spec, state: "supported", evidence: examples[2].syntheticEvidence }),
    );
    const executions = await executeTemplateTwinCustomExamples({
      specifications: [spec],
      practiceId: "practice-synthetic-example",
      userId: PHYSICIAN_ID,
      noteTemplateId: "template-synthetic-example",
      ...EXECUTION_IDENTITY,
      rolloutToken: ROLLOUT_TOKEN,
      model: "mock-certified-example-model-v1",
      client: mock.client,
      privacyClient: privacyClient(),
    });
    expect(executions.find((item) => item.definition.kind === "ambiguity")).toMatchObject({
      passed: false,
      failureCode: "TT_CUSTOM_EXAMPLE_AMBIGUITY_MISMATCH",
    });
  });

  it("does not accept a model-omitted certified cue as a clean negative", async () => {
    const spec = specification({
      negativeSyntheticExamples: [
        {
          exampleId: "negative-visible-cue",
          syntheticEvidence:
            "Synthetic example: synthetic finding is not reported clearly.",
          prohibitedValue: "alpha",
          reason: "A visible certified cue cannot be erased by the model.",
        },
      ],
    });
    const mock = clientWith(
      response({ spec, state: "supported", evidence: spec.positiveSyntheticExamples[0]!.syntheticEvidence }),
      response({ spec, state: "not_mentioned", evidence: spec.negativeSyntheticExamples[0]!.syntheticEvidence }),
      response({
        spec,
        state: "ambiguous",
        evidence: spec.ambiguitySyntheticExamples[0]!.syntheticEvidence,
        values: ["alpha", "beta"],
      }),
    );
    const executions = await executeTemplateTwinCustomExamples({
      specifications: [spec],
      practiceId: "practice-synthetic-example",
      userId: PHYSICIAN_ID,
      noteTemplateId: "template-synthetic-example",
      ...EXECUTION_IDENTITY,
      rolloutToken: ROLLOUT_TOKEN,
      model: "mock-certified-example-model-v1",
      client: mock.client,
      privacyClient: privacyClient(),
    });
    expect(executions.find((item) => item.definition.kind === "negative")).toMatchObject({
      passed: false,
      failureCode: "TT_CUSTOM_EXAMPLE_NEGATIVE_FALSE_POSITIVE",
    });
  });

  it("does not borrow ambiguity candidates from an unrelated later clause", async () => {
    const spec = specification({
      ambiguitySyntheticExamples: [
        {
          exampleId: "ambiguous-unrelated-candidates",
          syntheticEvidence:
            "Synthetic example: synthetic finding may be unclear; unrelated pulse values are alpha or beta.",
          possibleValues: ["alpha", "beta"],
          reason: "Candidates must be bound to the exact certified cue clause.",
        },
      ],
    });
    const mock = clientWith(
      response({ spec, state: "supported", evidence: spec.positiveSyntheticExamples[0]!.syntheticEvidence }),
      response({ spec, state: "not_mentioned", evidence: spec.negativeSyntheticExamples[0]!.syntheticEvidence }),
      response({
        spec,
        state: "ambiguous",
        evidence: spec.ambiguitySyntheticExamples[0]!.syntheticEvidence,
        values: ["alpha", "beta"],
      }),
    );
    const executions = await executeTemplateTwinCustomExamples({
      specifications: [spec],
      practiceId: "practice-synthetic-example",
      userId: PHYSICIAN_ID,
      noteTemplateId: "template-synthetic-example",
      ...EXECUTION_IDENTITY,
      rolloutToken: ROLLOUT_TOKEN,
      model: "mock-certified-example-model-v1",
      client: mock.client,
      privacyClient: privacyClient(),
    });
    expect(executions.find((item) => item.definition.kind === "ambiguity")).toMatchObject({
      passed: false,
      failureCode: "TT_CUSTOM_EXAMPLE_AMBIGUITY_MISMATCH",
    });
  });

  it("privacy-gates all prompt metadata once before any extraction call", async () => {
    const spec = specification({
      physicianDescription:
        "Synthetic field for patient@example.test must never reach extraction.",
    });
    const extraction = clientWith();
    const privacy = privacyClient();
    await expect(
      executeTemplateTwinCustomExamples({
        specifications: [spec],
        practiceId: "practice-synthetic-example",
        userId: PHYSICIAN_ID,
        noteTemplateId: "template-synthetic-example",
        ...EXECUTION_IDENTITY,
        rolloutToken: ROLLOUT_TOKEN,
        model: "mock-certified-example-model-v1",
        client: extraction.client,
        privacyClient: privacy,
      }),
    ).rejects.toMatchObject({
      code: "TEMPLATE_TWIN_SYNTHETIC_EVIDENCE_REJECTED",
    });
    expect(privacy.complete).not.toHaveBeenCalled();
    expect(extraction.complete).not.toHaveBeenCalled();
  });

  it.each([
    [
      "positive expected scalar",
      {
        positiveSyntheticExamples: [
          {
            exampleId: "positive-identifier",
            syntheticEvidence: "Synthetic example: synthetic finding is alpha.",
            expectedValue: "patient@example.test",
            expectedUnit: null,
          },
        ],
      },
    ],
    [
      "negative prohibited scalar",
      {
        negativeSyntheticExamples: [
          {
            exampleId: "negative-identifier",
            syntheticEvidence:
              "Synthetic example: this encounter discusses an unrelated detail.",
            prohibitedValue: "patient@example.test",
            reason: "The custom field is not present.",
          },
        ],
      },
    ],
    [
      "ambiguity candidate scalar",
      {
        ambiguitySyntheticExamples: [
          {
            exampleId: "ambiguity-identifier",
            syntheticEvidence:
              "Synthetic example: synthetic finding might be alpha or beta.",
            possibleValues: ["patient@example.test", "beta"],
            reason: "Two incompatible values remain possible.",
          },
        ],
      },
    ],
    [
      "exact denial scalar",
      {
        polarityPolicy: {
          allowExplicitDenial: true,
          exactDeniedOutput: "patient@example.test",
        },
        positiveSyntheticExamples: [
          {
            exampleId: "positive-alpha",
            syntheticEvidence: "Synthetic example: synthetic finding is alpha.",
            expectedValue: "alpha",
            expectedUnit: null,
          },
          {
            exampleId: "denied-identifier",
            syntheticEvidence:
              "Synthetic example: synthetic finding is explicitly denied.",
            expectedValue: "patient@example.test",
            expectedUnit: null,
            expectedStatus: "explicitly_denied" as const,
          },
        ],
      },
    ],
  ] satisfies Array<
    [string, Partial<TemplateFieldSpecificationContent>]
  >)("privacy-gates PHI in %s before any provider call", async (_label, overrides) => {
    const spec = specification(overrides);
    const extraction = clientWith();
    const privacy = privacyClient();

    await expect(
      executeTemplateTwinCustomExamples({
        specifications: [spec],
        practiceId: "practice-synthetic-example",
        userId: PHYSICIAN_ID,
        noteTemplateId: "template-synthetic-example",
        ...EXECUTION_IDENTITY,
        rolloutToken: ROLLOUT_TOKEN,
        model: "mock-certified-example-model-v1",
        client: extraction.client,
        privacyClient: privacy,
      }),
    ).rejects.toMatchObject({
      code: "TEMPLATE_TWIN_SYNTHETIC_EVIDENCE_REJECTED",
    });
    expect(privacy.complete).not.toHaveBeenCalled();
    expect(extraction.complete).not.toHaveBeenCalled();
  });

  it("fails closed when mapping, model hash, acknowledgement, or example identity is stale", async () => {
    const spec = specification();
    const mock = clientWith(
      response({
        spec,
        state: "supported",
        evidence: spec.positiveSyntheticExamples[0]!.syntheticEvidence,
      }),
      response({
        spec,
        state: "not_mentioned",
        evidence: spec.negativeSyntheticExamples[0]!.syntheticEvidence,
      }),
      response({
        spec,
        state: "ambiguous",
        evidence: spec.ambiguitySyntheticExamples[0]!.syntheticEvidence,
        values: ["alpha", "beta"],
      }),
    );
    const executions = await executeTemplateTwinCustomExamples({
      specifications: [spec],
      practiceId: "practice-synthetic-example",
      userId: PHYSICIAN_ID,
      noteTemplateId: "template-synthetic-example",
      ...EXECUTION_IDENTITY,
      rolloutToken: ROLLOUT_TOKEN,
      model: "mock-certified-example-model-v1",
      client: mock.client,
      privacyClient: privacyClient(),
    });
    const rows = executions.map((execution) => persisted(execution));
    const current = evaluateTemplateTwinCustomExampleCoverage({
      specifications: [spec],
      mappingsSha256: "a".repeat(64),
      fieldIntentsSha256: "b".repeat(64),
      physicianUserId: PHYSICIAN_ID,
      rows,
    });
    expect(current).toMatchObject({
      requiredCount: 3,
      passedCount: 3,
      acknowledgedCount: 3,
      ready: true,
      stale: false,
    });

    for (const tampered of [
      rows.map((row, index) =>
        index === 0 ? { ...row, mappingsSha256: "c".repeat(64) } : row,
      ),
      rows.map((row, index) =>
        index === 0 ? { ...row, modelSha256: "d".repeat(64) } : row,
      ),
      rows.map((row, index) =>
        index === 0 ? { ...row, acknowledgedAt: null } : row,
      ),
      rows.map((row, index) =>
        index === 0
          ? { ...row, exampleDefinitionSha256: "e".repeat(64) }
          : row,
      ),
    ]) {
      const result = evaluateTemplateTwinCustomExampleCoverage({
        specifications: [spec],
        mappingsSha256: "a".repeat(64),
        fieldIntentsSha256: "b".repeat(64),
        physicianUserId: PHYSICIAN_ID,
        rows: tampered,
      });
      expect(result.ready).toBe(false);
    }
  });

  it("independently reclassifies a failed negative even when passed and its hash are recomputed", async () => {
    const spec = specification();
    const positive = spec.positiveSyntheticExamples[0]!;
    const negative = spec.negativeSyntheticExamples[0]!;
    const ambiguity = spec.ambiguitySyntheticExamples[0]!;
    const mock = clientWith(
      response({
        spec,
        state: "supported",
        evidence: positive.syntheticEvidence,
      }),
      response({
        spec,
        state: "supported",
        evidence: negative.syntheticEvidence,
        value: "alpha",
      }),
      response({
        spec,
        state: "ambiguous",
        evidence: ambiguity.syntheticEvidence,
        values: ["alpha", "beta"],
      }),
    );
    const executions = await executeTemplateTwinCustomExamples({
      specifications: [spec],
      practiceId: "practice-synthetic-example",
      userId: PHYSICIAN_ID,
      noteTemplateId: "template-synthetic-example",
      ...EXECUTION_IDENTITY,
      rolloutToken: ROLLOUT_TOKEN,
      model: "mock-certified-example-model-v1",
      client: mock.client,
      privacyClient: privacyClient(),
    });
    const rows = executions.map((execution) => persisted(execution));
    const negativeIndex = executions.findIndex(
      (execution) => execution.definition.kind === "negative",
    );
    const negativeExecution = executions[negativeIndex]!;
    expect(negativeExecution.passed).toBe(false);
    const forged = {
      ...rows[negativeIndex]!,
      passed: true,
      failureCode: null,
    };
    rows[negativeIndex] = rehashPersistedResult(
      negativeExecution,
      forged,
    );

    const coverage = evaluateTemplateTwinCustomExampleCoverage({
      specifications: [spec],
      mappingsSha256: "a".repeat(64),
      fieldIntentsSha256: "b".repeat(64),
      physicianUserId: PHYSICIAN_ID,
      rows,
    });
    expect(coverage).toMatchObject({
      ready: false,
      stale: true,
      passedCount: 2,
    });
    expect(
      coverage.examples.find((example) => example.exampleKind === "negative"),
    ).toMatchObject({
      passed: false,
      failureCode: "TT_CUSTOM_EXAMPLE_NEGATIVE_FALSE_POSITIVE",
    });
  });

  it("blocks template activation when no current acknowledged execution batch exists", async () => {
    const spec = specification();
    const tx = {
      templateTwinCustomExampleExecution: {
        findFirst: vi.fn().mockResolvedValue(null),
        findMany: vi.fn(),
      },
    };
    await expect(
      assertTemplateTwinCustomExamplesReadyForCertification({
        tx: tx as never,
        compiledVersionId: COMPILED_ID,
        specifications: [spec],
        mappingsSha256: "a".repeat(64),
        fieldIntentsSha256: "b".repeat(64),
        physicianUserId: PHYSICIAN_ID,
      }),
    ).rejects.toMatchObject({
      code: "EXAMPLES_FAILED",
      message: expect.stringContaining("TT_CUSTOM_EXAMPLE_PROOF_REQUIRED"),
    });
  });
});
