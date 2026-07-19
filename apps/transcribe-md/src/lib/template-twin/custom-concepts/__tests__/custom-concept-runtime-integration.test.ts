import { describe, expect, it } from "vitest";

import { buildSyntheticDocx } from "../../../note-template-docx/__tests__/synthetic-docx";
import { compileTemplateDocx } from "../../../note-template-docx/compiler";
import {
  EncounterFactSchema,
  SemanticMappingSchema,
  TemplateTwinFillManifestSchema,
  type TemplateDocIR,
  type EncounterFact,
  type SemanticMapping,
  type TemplateField,
} from "../../ir";
import {
  fieldsWithCertifiedCustomIntent,
  templateTwinFieldIntentsSha256,
  type TemplateTwinFieldIntentView,
} from "../../field-intent";
import { canonicalSha256 } from "../../canonical";
import { createTemplateTwinEncounterSourceReceipt } from "../../canonical-encounter-source";
import { prepareTemplateTwinFill } from "../../fill-engine";
import { templateTwinMappingsSha256 } from "../../mapping-hash";
import { resolveTemplateFields } from "../../resolver";
import {
  assessTemplateTwinSigning,
  type TemplateTwinSigningContext,
} from "../../signing-gate";
import { DOCX_MIME_TYPE, createOutputArtifactKey } from "../../storage/keys";
import { syntheticSourceAdmission } from "../../__tests__/source-admission-fixture";
import { validateTemplateTwin } from "../../validation";
import {
  buildClinicianCorrection,
} from "../../review-service";
import {
  CertifiedTemplateFieldSpecificationSchema,
  buildCanonicalCustomConceptEvidence,
  TEMPLATE_CUSTOM_EXTRACTION_SCHEMA_VERSION,
  TEMPLATE_CUSTOM_EXTRACTION_VERSION,
  TEMPLATE_FIELD_SPECIFICATION_VERSION,
  TemplateFieldSpecificationContentSchema,
  computeCustomExtractionSchemaHash,
  computeTemplateFieldSpecificationContentSha256,
  computeTemplateFieldSyntheticCoverageSha256,
  createCertifiedCustomConceptProvider,
  deriveCustomConceptId,
  isCertifiedCustomExtractionProvenanceCurrent,
  type CertifiedTemplateFieldSpecification,
  type CustomScalarDataType,
  type CustomScalarValue,
  type TemplateFieldSpecificationContent,
} from "..";

const W = "http://schemas.openxmlformats.org/wordprocessingml/2006/main";
const LINEAGE_ID = "synthetic-custom-lineage-v1";
const COMPILED_VERSION_ID = "synthetic-custom-compiled-v1";
const NOW = "2026-07-16T12:00:00.000Z";
const CUSTOM_EXAMPLE_PROOF_SHA256 = "e".repeat(64);
const SOURCE_PRIVACY_SCAN_EVIDENCE = {
  profileVersion: "template-twin-source-phi-safe-alpha-v1" as const,
  provider: "anthropic" as const,
  model: "synthetic-privacy-model-v1",
  scannedAt: NOW,
  scannedPartCount: 8,
  approvedStaticAssetPolicySha256: "a".repeat(64),
  approvedStaticAssetCount: 0,
  approvedStaticAssetUsedCount: 0,
  approvedStaticAssetUsageSha256: "b".repeat(64),
};

function expectedValue(dataType: CustomScalarDataType): CustomScalarValue {
  switch (dataType) {
    case "narrative_text":
      return "Synthetic supported finding";
    case "number":
      return 7;
    case "measurement":
      return 12.5;
    case "date":
      return "2099-02-03";
    case "boolean":
      return true;
    case "single_select":
      return "Present";
  }
}

async function compilePlaceholderFixture(): Promise<{
  source: Buffer;
  ir: TemplateDocIR;
  field: TemplateField;
}> {
  const documentXml = `<?xml version="1.0" encoding="UTF-8" standalone="yes"?><w:document xmlns:w="${W}"><w:body><w:p><w:r><w:t>Custom detail: [[synthetic custom value]]</w:t></w:r></w:p><w:sectPr/></w:body></w:document>`;
  const source = await buildSyntheticDocx({
    documentXml,
    extraEntries: {
      "word/header1.xml": `<w:hdr xmlns:w="${W}"><w:p><w:r><w:t>Synthetic header</w:t></w:r></w:p></w:hdr>`,
      "word/footer1.xml": `<w:ftr xmlns:w="${W}"><w:p><w:r><w:t>Synthetic footer</w:t></w:r></w:p></w:ftr>`,
    },
  });
  const ir = compileTemplateDocx(source);
  const fields = ir.fields.filter(
    (field) => field.rendererBinding.bindingType === "ordinary_placeholder",
  );
  expect(fields).toHaveLength(1);
  return { source, ir, field: fields[0]! };
}

async function compileOnePlaceholder(): Promise<TemplateField> {
  return (await compilePlaceholderFixture()).field;
}

function makeSpecification(
  field: TemplateField,
  dataType: CustomScalarDataType,
  overrides: Partial<TemplateFieldSpecificationContent> = {},
): CertifiedTemplateFieldSpecification {
  const identity = {
    templateLineageId: LINEAGE_ID,
    compiledVersionId: COMPILED_VERSION_ID,
    fieldId: field.fieldId,
  };
  const candidate: TemplateFieldSpecificationContent = {
    specificationVersion: TEMPLATE_FIELD_SPECIFICATION_VERSION,
    ...identity,
    conceptId: deriveCustomConceptId(identity),
    physicianName: `Synthetic ${dataType} detail`,
    physicianDescription:
      "Extract only the exact synthetic value directly supported by encounter evidence.",
    approvedEvidenceCues: [`synthetic ${dataType} detail`],
    dataType,
    allowedOptions:
      dataType === "single_select"
        ? [
            { ordinal: 0, value: "Absent", displayText: "Absent" },
            { ordinal: 1, value: "Present", displayText: "Present" },
            { ordinal: 2, value: "Reduced", displayText: "Reduced" },
          ]
        : [],
    allowedUnits: dataType === "measurement" ? ["mm"] : [],
    permittedUnitConversions: [],
    allowedTemporalities: ["current"],
    allowedLateralities: ["not_applicable"],
    polarityPolicy: {
      allowExplicitDenial: false,
      exactDeniedOutput: null,
    },
    required: true,
    unknownPolicy: "requires_input",
    maximumLength: dataType === "narrative_text" ? 240 : null,
    numericRange:
      dataType === "number" || dataType === "measurement"
        ? { minimum: 0, maximum: 100 }
        : null,
    evidenceRequirements: {
      minimumAnchors: 1,
      acceptedEvidenceQualities: ["direct"],
    },
    positiveSyntheticExamples: [
      {
        exampleId: "positive-1",
        syntheticEvidence:
          "Synthetic evidence states the exact expected value.",
        expectedValue: expectedValue(dataType),
        expectedUnit: dataType === "measurement" ? "mm" : null,
      },
    ],
    negativeSyntheticExamples: [
      {
        exampleId: "negative-1",
        syntheticEvidence: "Synthetic evidence does not mention this detail.",
        prohibitedValue: null,
        reason: "No direct supporting evidence is present.",
      },
    ],
    ambiguitySyntheticExamples: [
      {
        exampleId: "ambiguous-1",
        syntheticEvidence: "Synthetic evidence says this detail is unclear.",
        possibleValues: [expectedValue(dataType)],
        reason: "The source explicitly marks the value as unclear.",
      },
    ],
    ...overrides,
  };
  const positives = [...candidate.positiveSyntheticExamples];
  if (candidate.dataType === "single_select") {
    for (const option of candidate.allowedOptions) {
      if (
        positives.some(
          (example) =>
            example.expectedValue === option.value &&
            ((example.expectedStatus ?? "supported") === "supported" ||
              (example.expectedStatus === "explicitly_denied" &&
                candidate.polarityPolicy.exactDeniedOutput === option.value)),
        )
      ) {
        continue;
      }
      positives.push({
        exampleId: `positive-option-${option.ordinal}`,
        syntheticEvidence: `Synthetic evidence: ${candidate.approvedEvidenceCues[0]} is ${option.value}.`,
        expectedValue: option.value,
        expectedUnit: null,
        expectedStatus: "supported",
      });
    }
  }
  if (candidate.dataType === "measurement") {
    for (const [index, unit] of candidate.allowedUnits.entries()) {
      if (
        positives.some(
          (example) =>
            example.expectedUnit === unit &&
            (example.expectedStatus ?? "supported") === "supported",
        )
      ) {
        continue;
      }
      positives.push({
        exampleId: `positive-unit-${index}`,
        syntheticEvidence: `Synthetic evidence: ${candidate.approvedEvidenceCues[0]} is 1 ${unit}.`,
        expectedValue: 1,
        expectedUnit: unit,
        expectedStatus: "supported",
      });
    }
  }
  if (
    candidate.polarityPolicy.allowExplicitDenial &&
    !positives.some(
      (example) => example.expectedStatus === "explicitly_denied",
    )
  ) {
    positives.push({
      exampleId: "positive-explicit-denial",
      syntheticEvidence: `Synthetic evidence: no ${candidate.approvedEvidenceCues[0]}.`,
      expectedValue: candidate.polarityPolicy.exactDeniedOutput!,
      expectedUnit: null,
      expectedStatus: "explicitly_denied",
    });
  }
  candidate.positiveSyntheticExamples = positives;
  const content = TemplateFieldSpecificationContentSchema.parse(candidate);
  return CertifiedTemplateFieldSpecificationSchema.parse({
    ...content,
    certification: {
      status: "certified",
      certifiedByUserId: "synthetic-physician@example.test",
      certifiedAt: NOW,
      contentSha256: computeTemplateFieldSpecificationContentSha256(content),
      syntheticCoverageSha256:
        computeTemplateFieldSyntheticCoverageSha256(content),
    },
  });
}

function intentFor(
  specification: CertifiedTemplateFieldSpecification,
): TemplateTwinFieldIntentView {
  return {
    intentKind: "custom_concept",
    decisionId: "synthetic-intent-decision-v1",
    version: 1,
    supportedConcept: null,
    customConceptId: specification.conceptId,
    customSpec: specification,
    reason: "Synthetic physician-confirmed custom intent.",
    decidedAtIso: NOW,
    lockedInVersion: true,
  };
}

const DATA_TYPE_TO_MAPPING = {
  narrative_text: "text",
  number: "number",
  measurement: "measurement",
  date: "date",
  boolean: "boolean",
  single_select: "single_select",
} as const;

function mappingFor(
  field: TemplateField,
  specification: CertifiedTemplateFieldSpecification,
): SemanticMapping {
  return SemanticMappingSchema.parse({
    fieldId: field.fieldId,
    clinicalConcept: specification.conceptId,
    expectedDataType: DATA_TYPE_TO_MAPPING[specification.dataType],
    polarityBehavior: specification.polarityPolicy.allowExplicitDenial
      ? "explicit_denial_allowed"
      : specification.dataType === "boolean"
        ? "affirmative_only"
        : "value_only",
    temporality: "any",
    laterality: "optional",
    unitPolicy:
      specification.dataType === "measurement"
        ? "required"
        : specification.dataType === "number"
          ? "forbidden"
          : "not_applicable",
    approvedSynonyms: [],
    required: specification.required,
    blankPolicy: specification.unknownPolicy,
    unknownPolicy: specification.unknownPolicy,
    practiceDefault: null,
    status: "certified",
  });
}

function makeFact(input: {
  specification: CertifiedTemplateFieldSpecification;
  value: string | number | boolean;
  ordinal?: number;
  polarity?: EncounterFact["polarity"];
  evidence?: EncounterFact["quality"]["evidence"];
  unit?: string | null;
}): EncounterFact {
  const ordinal = input.ordinal ?? 0;
  return EncounterFactSchema.parse({
    factId: `ttfact_${ordinal.toString(16).padStart(24, "0")}`,
    sourceType: "encounter_evidence",
    concept: input.specification.conceptId,
    value: input.value,
    polarity: input.polarity ?? "affirmed",
    temporality: "current",
    experiencer: "patient",
    laterality: "not_applicable",
    number: typeof input.value === "number" ? input.value : null,
    unit: input.unit ?? null,
    speaker: "Synthetic clinician",
    sourceTranscriptOffsets: null,
    audioTimestampSeconds: null,
    evidenceAnchorIds: [`synthetic-custom-anchor-${ordinal}`],
    evidenceQuote: `Synthetic evidence for ${String(input.value)}.`,
    quality: {
      asr: "unknown",
      evidence: input.evidence ?? "direct",
    },
  });
}

function runtimeFixture(input: {
  sourceField: TemplateField;
  specification: CertifiedTemplateFieldSpecification;
  facts: readonly EncounterFact[];
}) {
  const intents = [
    {
      fieldId: input.sourceField.fieldId,
      intent: intentFor(input.specification),
    },
  ];
  const fields = fieldsWithCertifiedCustomIntent({
    fields: [input.sourceField],
    intents,
  });
  const mapping = mappingFor(fields[0]!, input.specification);
  const conceptProviders = [
    createCertifiedCustomConceptProvider([input.specification]),
  ];
  const resolutions = resolveTemplateFields({
    fields,
    mappings: [mapping],
    facts: input.facts,
    certifiedFieldIds: [input.sourceField.fieldId],
    conceptProviders,
    customSpecifications: [input.specification],
  });
  const validation = validateTemplateTwin({
    fields,
    mappings: [mapping],
    facts: input.facts,
    resolutions,
    certifiedFieldIds: [input.sourceField.fieldId],
    conceptProviders,
    customSpecifications: [input.specification],
    now: NOW,
  });
  return { fields, mapping, resolutions, validation };
}

async function buildCustomSigningContext(): Promise<TemplateTwinSigningContext> {
  const { source, ir, field } = await compilePlaceholderFixture();
  const specification = makeSpecification(field, "narrative_text");
  const intent = intentFor(specification);
  const intentRows = [{ fieldId: field.fieldId, intent }];
  const fieldIntentsSha256 = templateTwinFieldIntentsSha256(intentRows);
  const effectiveFields = fieldsWithCertifiedCustomIntent({
    fields: ir.fields,
    intents: intentRows,
  });
  const mapping = mappingFor(effectiveFields[0]!, specification);
  const encounterSource = "Synthetic evidence for Synthetic supported finding.";
  const canonicalEvidence = buildCanonicalCustomConceptEvidence({
    mode: "text",
    contextText: encounterSource,
  });
  const supportedFact = makeFact({
    specification,
    value: "Synthetic supported finding",
  });
  supportedFact.sourceTranscriptOffsets =
    canonicalEvidence.anchors[0]!.sourceTranscriptOffsets;
  supportedFact.evidenceAnchorIds = [
    canonicalEvidence.anchors[0]!.evidenceAnchorId,
  ];
  supportedFact.evidenceQuote = canonicalEvidence.anchors[0]!.quote;
  const customExtraction = {
    extractorVersion: TEMPLATE_CUSTOM_EXTRACTION_VERSION,
    extractionSchemaVersion: TEMPLATE_CUSTOM_EXTRACTION_SCHEMA_VERSION,
    extractionSchemaHash: computeCustomExtractionSchemaHash([specification]),
    provider: "anthropic",
    model: "mock-custom-extractor-v1",
    fields: [
      {
        fieldId: field.fieldId,
        conceptId: specification.conceptId,
        status: "supported",
        sourceFactIds: [supportedFact.factId],
        evidenceAnchorIds: [...supportedFact.evidenceAnchorIds],
        reasonCode: "TT_CUSTOM_SUPPORTED_V1",
        needsClinicianReview: false,
        blocksSigning: false,
      },
    ],
    blocksSigning: false,
  } as const;
  const prepared = await prepareTemplateTwinFill({
    soapVersion: 4,
    soapFinal: "Synthetic reviewed SOAP note.",
    compiledVersionId: COMPILED_VERSION_ID,
    noteTemplateId: "synthetic-template-v1",
    noteTemplateVersion: 1,
    ir,
    effectiveFields,
    mappings: [mapping],
    facts: [supportedFact],
    encounterSourceReceipt: createTemplateTwinEncounterSourceReceipt({
      mode: "text",
      contextText: encounterSource,
    }),
    certifiedFieldIds: [field.fieldId],
    source,
    resolverModelVersion: customExtraction.model,
    validationNow: NOW,
    fieldIntentsSha256,
    conceptProviders: [createCertifiedCustomConceptProvider([specification])],
    customExtraction,
    customSpecifications: [specification],
    customExampleProofSha256: CUSTOM_EXAMPLE_PROOF_SHA256,
  });
  if (!prepared.render) {
    throw new Error("Synthetic custom signing fixture did not render.");
  }

  const outputObjectKey = createOutputArtifactKey({
    practiceId: "synthetic-practice",
    visitId: "synthetic-visit",
    manifestSha256: prepared.manifestSha256,
    outputSha256: prepared.render.outputSha256,
    idFactory: () => "synthetic-output-artifact",
  });
  const certificationOutputObjectKey = createOutputArtifactKey({
    practiceId: "synthetic-practice",
    visitId: "synthetic-certification",
    manifestSha256: prepared.manifestSha256,
    outputSha256: prepared.render.outputSha256,
    idFactory: () => "synthetic-certification-artifact",
  });

  return {
    visitId: "synthetic-visit",
    practiceId: "synthetic-practice",
    visitStatus: "READY",
    soapVersion: 4,
    soapFinal: "Synthetic reviewed SOAP note.",
    inputMode: "text_notes",
    rawTextInput: encounterSource,
    transcriptText: null,
    transcriptRaw: null,
    speakerMap: null,
    noteTemplateId: "synthetic-template-v1",
    noteTemplateVersion: 1,
    noteTemplate: {
      id: "synthetic-template-v1",
      version: 1,
      templateKind: "template_twin_docx",
      templateTwinCompiledVersion: {
        id: COMPILED_VERSION_ID,
        noteTemplateId: "synthetic-template-v1",
        compilerVersion: ir.compilerVersion,
        irSchemaVersion: ir.irSchemaVersion,
        compiledDocumentIr: ir,
        structureSha256: ir.structureSha256,
        staticContentSha256: ir.staticContentSha256,
        latestTestOutputObjectKey: certificationOutputObjectKey,
        latestTestOutputVersionId: "synthetic-certification-version",
        latestTestOutputEtag: "synthetic-certification-etag",
        latestTestOutputSha256: prepared.render.outputSha256,
        certificationStatus: "CERTIFIED",
        sourceArtifact: {
          ...syntheticSourceAdmission({
            practiceId: "synthetic-practice",
            lineageId: LINEAGE_ID,
            minimizedSha256: ir.source.sha256,
            minimizedSizeBytes: ir.source.sizeBytes,
          }),
          mimeType: ir.source.mimeType,
          privacyScanEvidence: SOURCE_PRIVACY_SCAN_EVIDENCE,
        },
        fields: [
          {
            id: "synthetic-field-definition",
            fieldId: field.fieldId,
            detectionStatus: "CERTIFIED",
            intentDecisions: [
              {
                id: intent.decisionId!,
                version: intent.version!,
                intentKind: "CUSTOM_CONCEPT",
                supportedConcept: null,
                customConceptId: specification.conceptId,
                customSpec: specification,
                customSpecSha256:
                  computeTemplateFieldSpecificationContentSha256(specification),
                reason: intent.reason,
                decidedById: "synthetic-physician@example.test",
                decidedAt: new Date(intent.decidedAtIso!),
              },
            ],
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
              approvedById: "synthetic-physician@example.test",
              approvedAt: new Date(NOW),
            },
          },
        ],
        certification: {
          id: "synthetic-certification",
          compiledStructureSha256: ir.structureSha256,
          approvedMappingsSha256: templateTwinMappingsSha256([mapping]),
          approvedFieldIntentsSha256: fieldIntentsSha256,
          approvedCustomExampleProofSha256: CUSTOM_EXAMPLE_PROOF_SHA256,
          sourcePrivacyScanEvidenceSha256: canonicalSha256(
            SOURCE_PRIVACY_SCAN_EVIDENCE,
          ),
          testOutputObjectKey: certificationOutputObjectKey,
          testOutputVersionId: "synthetic-certification-version",
          testOutputEtag: "synthetic-certification-etag",
          testOutputSha256: prepared.render.outputSha256,
        },
      },
    },
    templateTwinFill: {
      id: "synthetic-fill",
      practiceId: "synthetic-practice",
      compiledVersionId: COMPILED_VERSION_ID,
      noteTemplateId: "synthetic-template-v1",
      noteTemplateVersion: 1,
      compilerVersion: prepared.manifest.compilerVersion,
      resolverVersion: prepared.manifest.resolverVersion,
      resolverModelVersion: prepared.manifest.resolverModelVersion,
      rendererVersion: prepared.manifest.rendererVersion,
      status: "VERIFIED",
      fillManifest: prepared.manifest,
      manifestVersion: prepared.manifest.manifestVersion,
      manifestSha256: prepared.manifestSha256,
      factSetSha256: prepared.factSetSha256,
      fieldIntentsSha256,
      validationResult: prepared.manifest.validation,
      filledCount: prepared.manifest.counts.filled,
      needsReviewCount: prepared.manifest.counts.needsReview,
      notMentionedCount: prepared.manifest.counts.notMentioned,
      conflictCount: prepared.manifest.counts.conflicts,
      criticalUnresolvedCount: prepared.manifest.counts.criticalUnresolved,
      outputObjectKey,
      outputVersionId: "synthetic-output-version",
      outputEtag: "synthetic-output-etag",
      outputSha256: prepared.render.outputSha256,
      outputMimeType: DOCX_MIME_TYPE,
      outputSizeBytes: prepared.render.document.byteLength,
      staticContentSha256: ir.staticContentSha256,
      roundTripVerified: prepared.render.verification.verified,
      roundTripVerification: prepared.render.verification,
      pinnedGlobalRolloutGeneration: BigInt(1),
      pinnedPracticeRolloutGeneration: BigInt(1),
      signedGlobalRolloutGeneration: null,
      signedPracticeRolloutGeneration: null,
      reviewedAt: new Date(NOW),
      reviewedById: "synthetic-physician@example.test",
      reviewedManifestVersion: prepared.manifest.manifestVersion,
      reviewedManifestSha256: prepared.manifestSha256,
      signedDecisionAt: null,
      updatedAt: new Date(NOW),
    },
  };
}

describe("custom concept runtime integration", () => {
  it.each([
    ["narrative_text", "narrative_text", "Synthetic supported finding", null],
    ["number", "number", 7, null],
    ["measurement", "measurement", 12.5, "mm"],
    ["date", "date", "2099-02-03", null],
    ["boolean", "checkbox", true, null],
    ["single_select", "single_select", "Present", null],
  ] as const)(
    "applies a physician-certified %s type to the immutable placeholder binding",
    async (dataType, expectedKind, value, unit) => {
      const {
        source,
        ir,
        field: sourceField,
      } = await compilePlaceholderFixture();
      const specification = makeSpecification(sourceField, dataType);
      const fact = makeFact({ specification, value, unit });
      const fixture = runtimeFixture({
        sourceField,
        specification,
        facts: [fact],
      });

      expect(fixture.fields[0]).toMatchObject({
        fieldId: sourceField.fieldId,
        kind: expectedKind,
        rendererBinding: sourceField.rendererBinding,
      });
      expect(fixture.resolutions).toHaveLength(1);
      expect(fixture.resolutions[0]).toMatchObject({
        status: "supported",
        value: dataType === "measurement" ? "12.5 mm" : value,
        sourceFactIds: [expect.stringMatching(/^ttfact_/)],
      });
      expect(fixture.validation.issues).toEqual([]);
      expect(fixture.validation.valid).toBe(true);

      const intentRows = [
        { fieldId: sourceField.fieldId, intent: intentFor(specification) },
      ];
      const prepared = await prepareTemplateTwinFill({
        soapVersion: 1,
        soapFinal: `Synthetic reviewed ${dataType} SOAP.`,
        compiledVersionId: COMPILED_VERSION_ID,
        noteTemplateId: "synthetic-custom-runtime-template",
        noteTemplateVersion: 1,
        ir,
        effectiveFields: fixture.fields,
        mappings: [fixture.mapping],
        facts: [fact],
        certifiedFieldIds: [sourceField.fieldId],
        source,
        resolverModelVersion: "mock-custom-extractor-v1",
        validationNow: NOW,
        fieldIntentsSha256: templateTwinFieldIntentsSha256(intentRows),
        conceptProviders: [
          createCertifiedCustomConceptProvider([specification]),
        ],
        customExtraction: {
          extractorVersion: TEMPLATE_CUSTOM_EXTRACTION_VERSION,
          extractionSchemaVersion: TEMPLATE_CUSTOM_EXTRACTION_SCHEMA_VERSION,
          extractionSchemaHash: computeCustomExtractionSchemaHash([
            specification,
          ]),
          provider: "anthropic",
          model: "mock-custom-extractor-v1",
          fields: [
            {
              fieldId: sourceField.fieldId,
              conceptId: specification.conceptId,
              status: "supported",
              sourceFactIds: [fact.factId],
              evidenceAnchorIds: [...fact.evidenceAnchorIds],
              reasonCode: "TT_CUSTOM_SUPPORTED_V1",
              needsClinicianReview: false,
              blocksSigning: false,
            },
          ],
          blocksSigning: false,
        },
        customSpecifications: [specification],
      });
      expect(prepared.render?.verification).toMatchObject({
        verified: true,
        fields: [
          expect.objectContaining({
            fieldId: sourceField.fieldId,
            status: "verified",
            disposition: "rendered",
          }),
        ],
      });
    },
  );

  it("renders false only from an exact physician-certified denial and never from unresolved evidence", async () => {
    const sourceField = await compileOnePlaceholder();
    const specification = makeSpecification(sourceField, "boolean", {
      polarityPolicy: {
        allowExplicitDenial: true,
        exactDeniedOutput: false,
      },
    });
    const denied = runtimeFixture({
      sourceField,
      specification,
      facts: [
        makeFact({
          specification,
          value: false,
          polarity: "denied",
        }),
      ],
    });
    expect(denied.resolutions[0]).toMatchObject({
      status: "explicitly_denied",
      value: false,
    });
    expect(denied.validation.valid).toBe(true);

    const notMentioned = runtimeFixture({
      sourceField,
      specification,
      facts: [],
    });
    expect(notMentioned.resolutions[0]).toMatchObject({
      status: "needs_clinician_input",
      value: null,
    });

    const uncertain = runtimeFixture({
      sourceField,
      specification,
      facts: [
        makeFact({
          specification,
          value: false,
          polarity: "uncertain",
        }),
      ],
    });
    expect(uncertain.resolutions[0]).toMatchObject({
      status: "ambiguous",
      value: null,
    });

    const conflict = runtimeFixture({
      sourceField,
      specification,
      facts: [
        makeFact({ specification, value: true, ordinal: 1 }),
        makeFact({
          specification,
          value: false,
          ordinal: 2,
          polarity: "denied",
        }),
      ],
    });
    expect(conflict.resolutions[0]).toMatchObject({
      status: "conflict",
      value: null,
    });
    expect(
      [notMentioned, uncertain, conflict].every(
        (fixture) => fixture.validation.valid === false,
      ),
    ).toBe(true);
  });

  it("round-trips an explicitly denied custom boolean as exact false text", async () => {
    const { source, ir, field } = await compilePlaceholderFixture();
    const specification = makeSpecification(field, "boolean", {
      polarityPolicy: {
        allowExplicitDenial: true,
        exactDeniedOutput: false,
      },
    });
    const deniedFact = makeFact({
      specification,
      value: false,
      polarity: "denied",
    });
    const fixture = runtimeFixture({
      sourceField: field,
      specification,
      facts: [deniedFact],
    });
    const intentRows = [
      { fieldId: field.fieldId, intent: intentFor(specification) },
    ];
    const prepared = await prepareTemplateTwinFill({
      soapVersion: 1,
      soapFinal: "Synthetic denied boolean SOAP.",
      compiledVersionId: COMPILED_VERSION_ID,
      noteTemplateId: "synthetic-custom-boolean-denial-template",
      noteTemplateVersion: 1,
      ir,
      effectiveFields: fixture.fields,
      mappings: [fixture.mapping],
      facts: [deniedFact],
      certifiedFieldIds: [field.fieldId],
      source,
      resolverModelVersion: "mock-custom-extractor-v1",
      validationNow: NOW,
      fieldIntentsSha256: templateTwinFieldIntentsSha256(intentRows),
      conceptProviders: [createCertifiedCustomConceptProvider([specification])],
      customExtraction: {
        extractorVersion: TEMPLATE_CUSTOM_EXTRACTION_VERSION,
        extractionSchemaVersion: TEMPLATE_CUSTOM_EXTRACTION_SCHEMA_VERSION,
        extractionSchemaHash: computeCustomExtractionSchemaHash([
          specification,
        ]),
        provider: "anthropic",
        model: "mock-custom-extractor-v1",
        fields: [
          {
            fieldId: field.fieldId,
            conceptId: specification.conceptId,
            status: "explicitly_denied",
            sourceFactIds: [deniedFact.factId],
            evidenceAnchorIds: [...deniedFact.evidenceAnchorIds],
            reasonCode: "TT_CUSTOM_EXPLICIT_DENIAL_V1",
            needsClinicianReview: false,
            blocksSigning: false,
          },
        ],
        blocksSigning: false,
      },
      customSpecifications: [specification],
    });
    expect(prepared.render?.verification.fields[0]).toMatchObject({
      disposition: "rendered",
      status: "verified",
    });
  });

  it("keeps non-checkbox denial aligned across resolver and independent validation", async () => {
    const {
      source,
      ir,
      field: sourceField,
    } = await compilePlaceholderFixture();
    const specification = makeSpecification(sourceField, "narrative_text", {
      polarityPolicy: {
        allowExplicitDenial: true,
        exactDeniedOutput: "Not present",
      },
    });
    const deniedFact = makeFact({
      specification,
      value: "Not present",
      polarity: "denied",
    });
    const fixture = runtimeFixture({
      sourceField,
      specification,
      facts: [deniedFact],
    });

    expect(fixture.resolutions[0]).toMatchObject({
      status: "explicitly_denied",
      value: "Not present",
    });
    expect(fixture.validation.issues).toEqual([]);
    expect(fixture.validation.valid).toBe(true);
    const intentRows = [
      { fieldId: sourceField.fieldId, intent: intentFor(specification) },
    ];
    const prepared = await prepareTemplateTwinFill({
      soapVersion: 1,
      soapFinal: "Synthetic explicitly denied custom field SOAP.",
      compiledVersionId: COMPILED_VERSION_ID,
      noteTemplateId: "synthetic-custom-denial-template",
      noteTemplateVersion: 1,
      ir,
      effectiveFields: fixture.fields,
      mappings: [fixture.mapping],
      facts: [deniedFact],
      certifiedFieldIds: [sourceField.fieldId],
      source,
      resolverModelVersion: "mock-custom-extractor-v1",
      validationNow: NOW,
      fieldIntentsSha256: templateTwinFieldIntentsSha256(intentRows),
      conceptProviders: [createCertifiedCustomConceptProvider([specification])],
      customExtraction: {
        extractorVersion: TEMPLATE_CUSTOM_EXTRACTION_VERSION,
        extractionSchemaVersion: TEMPLATE_CUSTOM_EXTRACTION_SCHEMA_VERSION,
        extractionSchemaHash: computeCustomExtractionSchemaHash([
          specification,
        ]),
        provider: "anthropic",
        model: "mock-custom-extractor-v1",
        fields: [
          {
            fieldId: sourceField.fieldId,
            conceptId: specification.conceptId,
            status: "explicitly_denied",
            sourceFactIds: [deniedFact.factId],
            evidenceAnchorIds: [...deniedFact.evidenceAnchorIds],
            reasonCode: "TT_CUSTOM_EXPLICIT_DENIAL_V1",
            needsClinicianReview: false,
            blocksSigning: false,
          },
        ],
        blocksSigning: false,
      },
      customSpecifications: [specification],
    });
    expect(prepared.render?.verification.fields[0]).toMatchObject({
      fieldId: sourceField.fieldId,
      disposition: "rendered",
      status: "verified",
    });
  });

  it("accepts a physician correction only through the exact certified custom policy", async () => {
    const sourceField = await compileOnePlaceholder();
    const specification = makeSpecification(sourceField, "number", {
      evidenceRequirements: {
        minimumAnchors: 2,
        acceptedEvidenceQualities: ["direct"],
      },
    });
    const effectiveField = fieldsWithCertifiedCustomIntent({
      fields: [sourceField],
      intents: [
        { fieldId: sourceField.fieldId, intent: intentFor(specification) },
      ],
    })[0]!;
    const mapping = mappingFor(effectiveField, specification);
    const provider = createCertifiedCustomConceptProvider([specification]);
    const correction = buildClinicianCorrection({
      field: effectiveField,
      mapping,
      value: 8,
      existingFactIds: new Set(),
      factIdFactory: () => "c".repeat(24),
      conceptProviders: [provider],
      customSpecification: specification,
    });
    expect(correction.resolution).toMatchObject({
      status: "supported",
      value: 8,
      clinicianReviewed: true,
    });
    expect(correction.facts[0]).toMatchObject({
      sourceType: "clinician_correction",
      temporality: "current",
      laterality: "not_applicable",
    });
    expect(
      validateTemplateTwin({
        fields: [effectiveField],
        mappings: [mapping],
        facts: correction.facts,
        resolutions: [correction.resolution],
        certifiedFieldIds: [effectiveField.fieldId],
        conceptProviders: [provider],
        customSpecifications: [specification],
        now: NOW,
      }).valid,
    ).toBe(true);

    expect(() =>
      makeSpecification(sourceField, "number", {
        allowedTemporalities: ["current", "historical"],
      }),
    ).toThrow(/one fixed temporality/iu);
  });

  it("records an exact custom non-checkbox denial as explicitly denied", async () => {
    const sourceField = await compileOnePlaceholder();
    const specification = makeSpecification(sourceField, "narrative_text", {
      polarityPolicy: {
        allowExplicitDenial: true,
        exactDeniedOutput: "Not present",
      },
    });
    const effectiveField = fieldsWithCertifiedCustomIntent({
      fields: [sourceField],
      intents: [
        { fieldId: sourceField.fieldId, intent: intentFor(specification) },
      ],
    })[0]!;
    const correction = buildClinicianCorrection({
      field: effectiveField,
      mapping: mappingFor(effectiveField, specification),
      value: "Not present",
      existingFactIds: new Set(),
      factIdFactory: () => "d".repeat(24),
      conceptProviders: [createCertifiedCustomConceptProvider([specification])],
      customSpecification: specification,
    });
    expect(correction.resolution.status).toBe("explicitly_denied");
    expect(correction.facts[0]?.polarity).toBe("denied");
  });

  it("preserves conflict evidence but refuses to render a conflicting custom scalar", async () => {
    const sourceField = await compileOnePlaceholder();
    const specification = makeSpecification(sourceField, "number");
    const fixture = runtimeFixture({
      sourceField,
      specification,
      facts: [
        makeFact({
          specification,
          value: 3,
          ordinal: 3,
          evidence: "conflicting",
        }),
        makeFact({
          specification,
          value: 8,
          ordinal: 4,
          evidence: "conflicting",
        }),
      ],
    });

    expect(fixture.resolutions[0]).toMatchObject({
      status: "conflict",
      value: null,
      sourceFactIds: [
        expect.stringMatching(/^ttfact_/),
        expect.stringMatching(/^ttfact_/),
      ],
    });
    expect(fixture.validation.valid).toBe(false);
    expect(fixture.validation.issues).toContainEqual(
      expect.objectContaining({
        fieldId: sourceField.fieldId,
        severity: "blocking",
      }),
    );
  });

  it("persists ambiguous custom outcomes as signing blockers without a renderable fact", async () => {
    const { source, ir, field } = await compilePlaceholderFixture();
    const specification = makeSpecification(field, "number");
    const intentRows = [
      { fieldId: field.fieldId, intent: intentFor(specification) },
    ];
    const effectiveFields = fieldsWithCertifiedCustomIntent({
      fields: ir.fields,
      intents: intentRows,
    });
    const mapping = mappingFor(effectiveFields[0]!, specification);
    const prepared = await prepareTemplateTwinFill({
      soapVersion: 1,
      soapFinal: "Synthetic ambiguous custom field SOAP.",
      compiledVersionId: COMPILED_VERSION_ID,
      noteTemplateId: "synthetic-ambiguous-custom-template",
      noteTemplateVersion: 1,
      ir,
      effectiveFields,
      mappings: [mapping],
      facts: [],
      certifiedFieldIds: [field.fieldId],
      source,
      resolverModelVersion: "mock-custom-extractor-v1",
      validationNow: NOW,
      fieldIntentsSha256: templateTwinFieldIntentsSha256(intentRows),
      conceptProviders: [createCertifiedCustomConceptProvider([specification])],
      customExtraction: {
        extractorVersion: TEMPLATE_CUSTOM_EXTRACTION_VERSION,
        extractionSchemaVersion: TEMPLATE_CUSTOM_EXTRACTION_SCHEMA_VERSION,
        extractionSchemaHash: computeCustomExtractionSchemaHash([
          specification,
        ]),
        provider: "anthropic",
        model: "mock-custom-extractor-v1",
        fields: [
          {
            fieldId: field.fieldId,
            conceptId: specification.conceptId,
            status: "ambiguous",
            sourceFactIds: [],
            evidenceAnchorIds: ["synthetic-ambiguous-anchor"],
            reasonCode: "TT_CUSTOM_AMBIGUOUS_V1",
            needsClinicianReview: true,
            blocksSigning: true,
          },
        ],
        blocksSigning: true,
      },
      customSpecifications: [specification],
    });

    expect(prepared.render).toBeNull();
    expect(prepared.manifest.fields[0]).toMatchObject({
      status: "ambiguous",
      value: null,
    });
    expect(prepared.manifest.validation.issues).toContainEqual(
      expect.objectContaining({
        code: "CUSTOM_EXTRACTION_REVIEW_REQUIRED",
        severity: "blocking",
      }),
    );
  });

  it("fails closed when signing or correction sees stale custom extraction provenance", async () => {
    const sourceField = await compileOnePlaceholder();
    const specification = makeSpecification(sourceField, "number");
    const specifications = [specification];
    const current = {
      extractorVersion: TEMPLATE_CUSTOM_EXTRACTION_VERSION,
      extractionSchemaVersion: TEMPLATE_CUSTOM_EXTRACTION_SCHEMA_VERSION,
      extractionSchemaHash: computeCustomExtractionSchemaHash(specifications),
      provider: "anthropic",
      model: "mock-custom-extractor-v1",
    };

    expect(
      isCertifiedCustomExtractionProvenanceCurrent({
        specifications,
        provenance: current,
      }),
    ).toBe(true);
    for (const provenance of [
      null,
      { ...current, extractionSchemaHash: "f".repeat(64) },
      { ...current, extractorVersion: "obsolete-extractor/0" },
      { ...current, extractionSchemaVersion: "obsolete-schema/0" },
      { ...current, provider: "unapproved-provider" },
      { ...current, model: "" },
    ]) {
      expect(
        isCertifiedCustomExtractionProvenanceCurrent({
          specifications,
          provenance,
        }),
      ).toBe(false);
    }
    expect(
      isCertifiedCustomExtractionProvenanceCurrent({
        specifications: [],
        provenance: null,
      }),
    ).toBe(true);
    expect(
      isCertifiedCustomExtractionProvenanceCurrent({
        specifications: [],
        provenance: current,
      }),
    ).toBe(false);
  });

  it("blocks signing when a coherently rehashed manifest carries a stale custom extraction schema hash", async () => {
    const valid = await buildCustomSigningContext();
    const baseline = assessTemplateTwinSigning(valid);
    expect(baseline).toMatchObject({
      applies: true,
      ready: true,
      blockerCodes: [],
    });

    const stale = structuredClone(valid);
    const manifest = TemplateTwinFillManifestSchema.parse(
      stale.templateTwinFill!.fillManifest,
    );
    if (!manifest.customExtraction) {
      throw new Error("Synthetic custom signing manifest lacks provenance.");
    }
    manifest.customExtraction = {
      ...manifest.customExtraction,
      extractionSchemaHash: "f".repeat(64),
    };
    const staleManifestSha256 = canonicalSha256(manifest);
    stale.templateTwinFill!.fillManifest = manifest;
    stale.templateTwinFill!.manifestSha256 = staleManifestSha256;
    stale.templateTwinFill!.reviewedManifestSha256 = staleManifestSha256;
    stale.templateTwinFill!.outputObjectKey = createOutputArtifactKey({
      practiceId: stale.practiceId,
      visitId: stale.visitId,
      manifestSha256: staleManifestSha256,
      outputSha256: stale.templateTwinFill!.outputSha256!,
      idFactory: () => "synthetic-stale-output-artifact",
    });

    const assessment = assessTemplateTwinSigning(stale);
    expect(assessment.ready).toBe(false);
    expect(assessment.blockerCodes).toContain(
      "CUSTOM_EXTRACTION_PROVENANCE_INVALID",
    );
  });

  it.each([null, "f".repeat(64)])(
    "blocks signing when the immutable custom-example proof is %s",
    async (customExampleProofSha256) => {
      const context = await buildCustomSigningContext();
      const manifest = TemplateTwinFillManifestSchema.parse(
        context.templateTwinFill!.fillManifest,
      );
      manifest.customExampleProofSha256 = customExampleProofSha256;
      const manifestSha256 = canonicalSha256(manifest);
      context.templateTwinFill!.fillManifest = manifest;
      context.templateTwinFill!.manifestSha256 = manifestSha256;
      context.templateTwinFill!.reviewedManifestSha256 = manifestSha256;
      context.templateTwinFill!.outputObjectKey = createOutputArtifactKey({
        practiceId: context.practiceId,
        visitId: context.visitId,
        manifestSha256,
        outputSha256: context.templateTwinFill!.outputSha256!,
        idFactory: () => "synthetic-custom-proof-tamper",
      });

      expect(assessTemplateTwinSigning(context)).toMatchObject({
        ready: false,
        blockerCodes: expect.arrayContaining(["FILL_MANIFEST_VERSION_MISMATCH"]),
      });
    },
  );

  it("blocks signing when the compiled certification proof no longer matches the reviewed manifest", async () => {
    const context = await buildCustomSigningContext();
    context.noteTemplate!.templateTwinCompiledVersion!.certification!.approvedCustomExampleProofSha256 =
      "f".repeat(64);
    const assessment = assessTemplateTwinSigning(context);
    expect(assessment.ready).toBe(false);
    expect(assessment.blockerCodes).toEqual(
      expect.arrayContaining([
        "FILL_MANIFEST_VERSION_MISMATCH",
      ]),
    );
  });

  it("blocks signing when a coherently rehashed manifest disagrees with its custom outcome proof", async () => {
    const context = await buildCustomSigningContext();
    const manifest = TemplateTwinFillManifestSchema.parse(
      context.templateTwinFill!.fillManifest,
    );
    if (!manifest.customExtraction) {
      throw new Error("Synthetic custom signing manifest lacks outcomes.");
    }
    manifest.customExtraction.fields[0] = {
      ...manifest.customExtraction.fields[0]!,
      status: "ambiguous",
      reasonCode: "TT_CUSTOM_AMBIGUOUS_V1",
      needsClinicianReview: true,
      blocksSigning: true,
    };
    manifest.customExtraction.blocksSigning = true;
    const manifestSha256 = canonicalSha256(manifest);
    context.templateTwinFill!.fillManifest = manifest;
    context.templateTwinFill!.manifestSha256 = manifestSha256;
    context.templateTwinFill!.reviewedManifestSha256 = manifestSha256;
    context.templateTwinFill!.outputObjectKey = createOutputArtifactKey({
      practiceId: context.practiceId,
      visitId: context.visitId,
      manifestSha256,
      outputSha256: context.templateTwinFill!.outputSha256!,
      idFactory: () => "synthetic-outcome-mismatch-output",
    });

    expect(assessTemplateTwinSigning(context).blockerCodes).toContain(
      "CUSTOM_EXTRACTION_OUTCOME_INVALID",
    );
  });
});
