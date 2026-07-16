import { createHash, randomUUID } from "node:crypto";

import type { ModelClient } from "@meddoc/ai";

import { canonicalSha256 } from "../canonical";
import {
  buildCanonicalCustomConceptEvidence,
  computeCustomExtractionSchemaHash,
  computeTemplateFieldSpecificationContentSha256,
  extractCertifiedCustomConcepts,
  TEMPLATE_CUSTOM_EXTRACTION_SCHEMA_VERSION,
  TEMPLATE_CUSTOM_EXTRACTION_VERSION,
  assertTemplateFieldSpecificationSetWithinLimits,
  templateFieldSpecificationAuthoredText,
  type CertifiedCustomConceptExtractionResult,
  type CertifiedTemplateFieldSpecification,
  type CustomConceptFieldOutcome,
  type CustomScalarValue,
} from "./index";
import { assertTemplateTwinAuthoredCorpusPhiFree } from "../synthetic-evidence-gate";

export const TEMPLATE_TWIN_CUSTOM_EXAMPLE_CONTRACT_VERSION =
  "template-twin-custom-example-proof/1.0.0" as const;

export type TemplateTwinCustomExampleKind =
  | "positive"
  | "negative"
  | "ambiguity";

export interface TemplateTwinCustomExampleDefinition {
  readonly fieldId: string;
  readonly conceptId: string;
  readonly physicianName: string;
  readonly approvedEvidenceCues: readonly string[];
  readonly allowedUnits: readonly string[];
  readonly kind: TemplateTwinCustomExampleKind;
  readonly exampleId: string;
  readonly syntheticEvidence: string;
  readonly expectedValue: CustomScalarValue | null;
  readonly expectedUnit: string | null;
  readonly expectedStatus: "supported" | "explicitly_denied" | null;
  readonly prohibitedValue: CustomScalarValue | null;
  readonly possibleValues: readonly CustomScalarValue[];
  readonly definitionSha256: string;
  readonly evidenceSha256: string;
  readonly specificationSha256: string;
}

export interface TemplateTwinCustomExampleExecution {
  readonly id: string;
  readonly batchId: string;
  readonly definition: TemplateTwinCustomExampleDefinition;
  readonly contractVersion: typeof TEMPLATE_TWIN_CUSTOM_EXAMPLE_CONTRACT_VERSION;
  readonly specificationSetSha256: string;
  readonly extractionSchemaSha256: string;
  readonly extractorVersion: string;
  readonly extractionSchemaVersion: string;
  readonly provider: string;
  readonly providerSha256: string;
  readonly model: string;
  readonly modelSha256: string;
  readonly resultStatus: string;
  readonly resultValue: CustomScalarValue | null;
  readonly resultUnit: string | null;
  readonly resultFactCount: number;
  readonly resultSummary: Record<string, unknown>;
  readonly resultSha256: string;
  readonly passed: boolean;
  readonly failureCode: string | null;
}

export interface ExecuteTemplateTwinCustomExamplesInput {
  readonly specifications: readonly CertifiedTemplateFieldSpecification[];
  readonly practiceId: string;
  readonly userId: string;
  readonly noteTemplateId: string;
  readonly model: string;
  readonly client?: Pick<ModelClient, "complete">;
  readonly privacyClient?: Pick<ModelClient, "complete">;
  readonly batchId?: string;
}

function sha256(value: string): string {
  return createHash("sha256").update(value, "utf8").digest("hex");
}

function scalarEquals(
  left: CustomScalarValue | null,
  right: CustomScalarValue | null,
): boolean {
  return canonicalSha256(left) === canonicalSha256(right);
}

function definitionSha256(
  definition: Omit<
    TemplateTwinCustomExampleDefinition,
    "definitionSha256" | "evidenceSha256"
  >,
): string {
  const { syntheticEvidence, ...safeDefinition } = definition;
  return canonicalSha256({
    contractVersion: TEMPLATE_TWIN_CUSTOM_EXAMPLE_CONTRACT_VERSION,
    ...safeDefinition,
    syntheticEvidenceSha256: sha256(syntheticEvidence),
  });
}

/** Expands every immutable physician-authored example into one exact,
 * independently addressable execution definition. Raw example text never
 * enters audit metadata; its digest and the enclosing specification digest do. */
export function templateTwinCustomExampleDefinitions(
  specifications: readonly CertifiedTemplateFieldSpecification[],
): TemplateTwinCustomExampleDefinition[] {
  return [...specifications]
    .sort((left, right) => left.conceptId.localeCompare(right.conceptId))
    .flatMap((specification) => {
      const specificationSha256 =
        computeTemplateFieldSpecificationContentSha256(specification);
      const common = {
        fieldId: specification.fieldId,
        conceptId: specification.conceptId,
        physicianName: specification.physicianName,
        approvedEvidenceCues: specification.approvedEvidenceCues,
        allowedUnits: specification.allowedUnits,
        specificationSha256,
      };
      return [
        ...specification.positiveSyntheticExamples.map((example) => ({
          ...common,
          kind: "positive" as const,
          exampleId: example.exampleId,
          syntheticEvidence: example.syntheticEvidence,
          expectedValue: example.expectedValue,
          expectedUnit: example.expectedUnit,
          expectedStatus: example.expectedStatus ?? "supported",
          prohibitedValue: null,
          possibleValues: [] as const,
        })),
        ...specification.negativeSyntheticExamples.map((example) => ({
          ...common,
          kind: "negative" as const,
          exampleId: example.exampleId,
          syntheticEvidence: example.syntheticEvidence,
          expectedValue: null,
          expectedUnit: null,
          expectedStatus: null,
          prohibitedValue: example.prohibitedValue,
          possibleValues: [] as const,
        })),
        ...specification.ambiguitySyntheticExamples.map((example) => ({
          ...common,
          kind: "ambiguity" as const,
          exampleId: example.exampleId,
          syntheticEvidence: example.syntheticEvidence,
          expectedValue: null,
          expectedUnit: null,
          expectedStatus: null,
          prohibitedValue: null,
          possibleValues: example.possibleValues,
        })),
      ].map((definition) => ({
        ...definition,
        evidenceSha256: sha256(definition.syntheticEvidence),
        definitionSha256: definitionSha256(definition),
      }));
    });
}

export function templateTwinCustomSpecificationSetSha256(
  specifications: readonly CertifiedTemplateFieldSpecification[],
): string {
  return canonicalSha256(
    [...specifications]
      .sort((left, right) => left.conceptId.localeCompare(right.conceptId))
      .map((specification) => ({
        fieldId: specification.fieldId,
        conceptId: specification.conceptId,
        specificationSha256:
          computeTemplateFieldSpecificationContentSha256(specification),
      })),
  );
}

function isRenderable(outcome: CustomConceptFieldOutcome): boolean {
  return (
    (outcome.status === "supported" ||
      outcome.status === "explicitly_denied") &&
    outcome.value !== null &&
    !outcome.blocksSigning
  );
}

function scalarSetEquals(
  left: readonly CustomScalarValue[],
  right: readonly CustomScalarValue[],
): boolean {
  const normalized = (values: readonly CustomScalarValue[]) =>
    [...new Set(values.map((value) => canonicalSha256(value)))].sort();
  return canonicalSha256(normalized(left)) === canonicalSha256(normalized(right));
}

function normalizedVisibleText(value: string): string {
  return value.normalize("NFKC").replace(/\s+/gu, " ").trim().toLowerCase();
}

function containsBoundedLiteral(haystack: string, needle: string): boolean {
  if (!needle) return false;
  let start = 0;
  while (start <= haystack.length - needle.length) {
    const index = haystack.indexOf(needle, start);
    if (index < 0) return false;
    const before = haystack[index - 1] ?? "";
    const after = haystack[index + needle.length] ?? "";
    if (
      !/^[\p{L}\p{N}]$/u.test(before) &&
      !/^[\p{L}\p{N}]$/u.test(after)
    ) {
      return true;
    }
    start = index + 1;
  }
  return false;
}

function boundedLiteralCount(haystack: string, needle: string): number {
  if (!needle) return 0;
  let count = 0;
  let start = 0;
  while (start <= haystack.length - needle.length) {
    const index = haystack.indexOf(needle, start);
    if (index < 0) break;
    const before = haystack[index - 1] ?? "";
    const after = haystack[index + needle.length] ?? "";
    const startsWord = /^[\p{L}\p{N}]$/u.test(needle[0] ?? "");
    const endsWord = /^[\p{L}\p{N}]$/u.test(needle.at(-1) ?? "");
    if (
      (!startsWord || !/^[\p{L}\p{N}]$/u.test(before)) &&
      (!endsWord || !/^[\p{L}\p{N}]$/u.test(after))
    ) {
      count += 1;
    }
    start = index + 1;
  }
  return count;
}

function negativeExampleHasNoCertifiedCue(
  definition: TemplateTwinCustomExampleDefinition,
): boolean {
  const evidence = normalizedVisibleText(definition.syntheticEvidence);
  return definition.approvedEvidenceCues.every(
    (cue) => !containsBoundedLiteral(evidence, normalizedVisibleText(cue)),
  );
}

function ambiguityEvidenceAnchorIds(
  definition: TemplateTwinCustomExampleDefinition,
): readonly string[] {
  const evidence = buildCanonicalCustomConceptEvidence({
    mode: "text",
    contextText: definition.syntheticEvidence,
  });
  const possibleValues = definition.possibleValues.map((value) =>
    normalizedVisibleText(String(value)),
  );
  return evidence.anchors.flatMap((anchor) => {
    // Association is proven within one bounded clause. Never let a later
    // semicolon/comma clause donate unrelated candidate values to a cue.
    const clauses = anchor.quote
      .split(/[;,\n]+/u)
      .map(normalizedVisibleText)
      .filter(Boolean);
    const supports = clauses.some((clause) => {
      const cueOccurrenceCount = definition.approvedEvidenceCues.reduce(
        (count, rawCue) =>
          count +
          boundedLiteralCount(clause, normalizedVisibleText(rawCue)),
        0,
      );
      if (cueOccurrenceCount !== 1) return false;
      return definition.approvedEvidenceCues.some((rawCue) => {
        const cue = normalizedVisibleText(rawCue);
        const cueIndex = clause.indexOf(cue);
        if (cueIndex < 0) return false;
        const after = clause.slice(cueIndex + cue.length);
        const connector = after.match(
          /^\s*(?:(?::|=|\u2013|\u2014|-)\s*|(?:is|was|are|were|may\s+be|might\s+be)\s+)/u,
        );
        if (!connector) return false;
        const candidateRegion = after
          .slice(connector[0].length)
          .replace(/[.!?]\s*$/u, "")
          .trim();
        const observedCandidates = candidateRegion
          .split(/\s+(?:or|versus|vs\.?)\s+|\s*\/\s*/iu)
          .map((value) => value.trim())
          .filter(Boolean)
          .map((candidate) => {
            const matchingUnit = definition.allowedUnits.find((unit) =>
              candidate.endsWith(` ${normalizedVisibleText(unit)}`),
            );
            return matchingUnit
              ? candidate
                  .slice(0, -(` ${normalizedVisibleText(matchingUnit)}`).length)
                  .trim()
              : candidate;
          });
        return (
          observedCandidates.length === possibleValues.length &&
          scalarSetEquals(observedCandidates, possibleValues)
        );
      });
    });
    return supports ? [anchor.evidenceAnchorId] : [];
  });
}

interface ReclassifiableExampleResult {
  readonly status: string;
  readonly value: CustomScalarValue | null;
  readonly unit: string | null;
  readonly sourceFactCount: number;
  readonly evidenceAnchorCount: number;
  readonly candidateValues: readonly CustomScalarValue[];
  readonly unexpectedUnsafeOutcome: boolean;
  readonly evidenceAnchorIds: readonly string[];
}

function classifyResult(
  definition: TemplateTwinCustomExampleDefinition,
  observed: ReclassifiableExampleResult,
): { passed: boolean; failureCode: string | null } {
  if (observed.unexpectedUnsafeOutcome) {
    return {
      passed: false,
      failureCode: "TT_CUSTOM_EXAMPLE_CROSS_FIELD_UNSAFE_OUTCOME",
    };
  }
  if (definition.kind === "positive") {
    const passed =
      observed.status === (definition.expectedStatus ?? "supported") &&
      scalarEquals(observed.value, definition.expectedValue) &&
      observed.unit === definition.expectedUnit &&
      observed.sourceFactCount > 0 &&
      observed.evidenceAnchorCount > 0;
    return {
      passed,
      failureCode: passed ? null : "TT_CUSTOM_EXAMPLE_POSITIVE_MISMATCH",
    };
  }
  if (definition.kind === "negative") {
    // A negative example is a false-positive gate, not an invitation to emit a
    // different usable value. Only a clean no-observation result can pass.
    const passed =
      observed.status === "not_mentioned" &&
      observed.value === null &&
      observed.unit === null &&
      observed.sourceFactCount === 0;
    const independentlyClean = negativeExampleHasNoCertifiedCue(definition);
    return {
      passed: passed && independentlyClean,
      failureCode:
        passed && independentlyClean
          ? null
          : "TT_CUSTOM_EXAMPLE_NEGATIVE_FALSE_POSITIVE",
    };
  }
  const independentlyBoundAnchors = ambiguityEvidenceAnchorIds(definition);
  const citedOnlyBoundEvidence =
    observed.evidenceAnchorIds.length > 0 &&
    observed.evidenceAnchorIds.every((evidenceAnchorId) =>
      independentlyBoundAnchors.includes(evidenceAnchorId),
    );
  const passed =
    (observed.status === "ambiguous" || observed.status === "conflict") &&
    observed.value === null &&
    observed.unit === null &&
    scalarSetEquals(observed.candidateValues, definition.possibleValues) &&
    citedOnlyBoundEvidence;
  return {
    passed,
    failureCode: passed ? null : "TT_CUSTOM_EXAMPLE_AMBIGUITY_MISMATCH",
  };
}

function classifyExecution(input: {
  definition: TemplateTwinCustomExampleDefinition;
  extraction: CertifiedCustomConceptExtractionResult;
}): Pick<
  TemplateTwinCustomExampleExecution,
  | "resultStatus"
  | "resultValue"
  | "resultUnit"
  | "resultFactCount"
  | "resultSummary"
  | "passed"
  | "failureCode"
> {
  const target = input.extraction.fields.find(
    (field) => field.conceptId === input.definition.conceptId,
  );
  const unexpectedRenderable = input.extraction.fields.some(
    (field) =>
      field.conceptId !== input.definition.conceptId && isRenderable(field),
  );
  const unexpectedUnsafeOutcome = input.extraction.fields.some(
    (field) =>
      field.conceptId !== input.definition.conceptId &&
      (isRenderable(field) ||
        field.status === "ambiguous" ||
        field.status === "conflict" ||
        field.status === "unknown"),
  );
  if (!target) {
    return {
      resultStatus: "missing",
      resultValue: null,
      resultUnit: null,
      resultFactCount: input.extraction.facts.length,
      resultSummary: { targetPresent: false, unexpectedRenderable },
      passed: false,
      failureCode: "TT_CUSTOM_EXAMPLE_TARGET_MISSING",
    };
  }

  const candidateValues = target.candidateValues ?? [];
  const classified = classifyResult(input.definition, {
    status: target.status,
    value: target.value,
    unit: target.unit,
    sourceFactCount: target.sourceFactIds.length,
    evidenceAnchorCount: target.evidenceAnchorIds.length,
    candidateValues,
    unexpectedUnsafeOutcome,
    evidenceAnchorIds: target.evidenceAnchorIds,
  });

  return {
    resultStatus: target.status,
    resultValue: target.value,
    resultUnit: target.unit,
    resultFactCount: input.extraction.facts.length,
    resultSummary: {
      targetPresent: true,
      status: target.status,
      needsClinicianReview: target.needsClinicianReview,
      blocksSigning: target.blocksSigning,
      sourceFactCount: target.sourceFactIds.length,
      evidenceAnchorCount: target.evidenceAnchorIds.length,
      unexpectedRenderable,
      unexpectedUnsafeOutcome,
      candidateValues,
      evidenceAnchorIds: target.evidenceAnchorIds,
    },
    ...classified,
  };
}

/** Executes every exact example through the same bounded custom extractor used
 * by typed and voice encounters. Each target example is tested against the
 * complete current specification set so cross-field false positives fail. */
export async function executeTemplateTwinCustomExamples(
  input: ExecuteTemplateTwinCustomExamplesInput,
): Promise<TemplateTwinCustomExampleExecution[]> {
  const definitions = templateTwinCustomExampleDefinitions(
    input.specifications,
  );
  if (definitions.length === 0) return [];
  assertTemplateFieldSpecificationSetWithinLimits(input.specifications);
  // One fail-closed, bounded privacy call covers every physician-authored
  // string that will enter the extraction prompt. The shared helper performs
  // deterministic checks on each original fragment before batching it.
  await assertTemplateTwinAuthoredCorpusPhiFree({
    fragments: input.specifications.flatMap(
      templateFieldSpecificationAuthoredText,
    ),
    practiceId: input.practiceId,
    userId: input.userId,
    client: input.privacyClient,
  });
  const specificationSetSha256 =
    templateTwinCustomSpecificationSetSha256(input.specifications);
  const extractionSchemaSha256 = computeCustomExtractionSchemaHash(
    input.specifications,
  );
  const batchId = input.batchId ?? randomUUID();
  const executions: TemplateTwinCustomExampleExecution[] = [];

  for (const definition of definitions) {
    try {
      const extraction = await extractCertifiedCustomConcepts({
        specifications: input.specifications,
        evidence: buildCanonicalCustomConceptEvidence({
          mode: "text",
          contextText: definition.syntheticEvidence,
        }),
        practiceId: input.practiceId,
        visitId: `template-custom-example:${input.noteTemplateId}:${batchId}`,
        userId: input.userId,
        model: input.model,
        client: input.client,
      });
      const classified = classifyExecution({ definition, extraction });
      const core = {
        id: randomUUID(),
        batchId,
        definition,
        contractVersion: TEMPLATE_TWIN_CUSTOM_EXAMPLE_CONTRACT_VERSION,
        specificationSetSha256,
        extractionSchemaSha256,
        extractorVersion: extraction.extractorVersion,
        extractionSchemaVersion: extraction.extractionSchemaVersion,
        provider: extraction.provider,
        providerSha256: sha256(extraction.provider),
        model: extraction.model,
        modelSha256: sha256(extraction.model),
        ...classified,
      };
      executions.push({
        ...core,
        resultSha256: canonicalSha256(core),
      });
    } catch (error) {
      const provider = "anthropic";
      const failureCode =
        error instanceof Error && "code" in error && typeof error.code === "string"
          ? `TT_CUSTOM_EXAMPLE_${error.code}`
          : "TT_CUSTOM_EXAMPLE_EXTRACTION_REJECTED";
      const core = {
        id: randomUUID(),
        batchId,
        definition,
        contractVersion: TEMPLATE_TWIN_CUSTOM_EXAMPLE_CONTRACT_VERSION,
        specificationSetSha256,
        extractionSchemaSha256,
        extractorVersion: TEMPLATE_CUSTOM_EXTRACTION_VERSION,
        extractionSchemaVersion: TEMPLATE_CUSTOM_EXTRACTION_SCHEMA_VERSION,
        provider,
        providerSha256: sha256(provider),
        model: input.model,
        modelSha256: sha256(input.model),
        resultStatus: "extraction_rejected",
        resultValue: null,
        resultUnit: null,
        resultFactCount: 0,
        resultSummary: { targetPresent: false, extractionRejected: true },
        passed: false,
        failureCode,
      };
      executions.push({
        ...core,
        resultSha256: canonicalSha256(core),
      });
    }
  }
  return executions;
}

export interface PersistedTemplateTwinCustomExampleExecution {
  readonly id: string;
  readonly batchId: string;
  readonly fieldId: string;
  readonly conceptId: string;
  readonly exampleKind: string;
  readonly exampleId: string;
  readonly exampleDefinitionSha256: string;
  readonly specificationSha256: string;
  readonly specificationSetSha256: string;
  readonly mappingsSha256: string;
  readonly fieldIntentsSha256: string;
  readonly contractVersion: string;
  readonly extractionSchemaSha256: string;
  readonly extractorVersion: string;
  readonly extractionSchemaVersion: string;
  readonly provider: string;
  readonly providerSha256: string;
  readonly model: string;
  readonly modelSha256: string;
  readonly resultStatus: string;
  readonly resultValue: CustomScalarValue | null;
  readonly resultUnit: string | null;
  readonly resultFactCount: number;
  readonly resultSummary: Record<string, unknown>;
  readonly resultSha256: string;
  readonly passed: boolean;
  readonly failureCode: string | null;
  readonly acknowledgedById: string | null;
  readonly acknowledgedAt: Date | null;
}

export interface TemplateTwinCustomExampleCoverage {
  readonly requiredCount: number;
  readonly passedCount: number;
  readonly acknowledgedCount: number;
  readonly ready: boolean;
  readonly stale: boolean;
  readonly latestBatchId: string | null;
  readonly proofSha256: string | null;
  readonly examples: ReadonlyArray<{
    fieldId: string;
    conceptId: string;
    physicianName: string;
    exampleKind: TemplateTwinCustomExampleKind;
    exampleId: string;
    syntheticEvidence: string;
    expectedValue: CustomScalarValue | null;
    expectedUnit: string | null;
    expectedStatus: "supported" | "explicitly_denied" | null;
    prohibitedValue: CustomScalarValue | null;
    possibleValues: readonly CustomScalarValue[];
    actualStatus: string | null;
    actualValue: CustomScalarValue | null;
    actualUnit: string | null;
    actualEvidenceAnchorCount: number;
    actualSourceFactCount: number;
    passed: boolean;
    acknowledged: boolean;
    failureCode: string | null;
  }>;
}

/** Validates a persisted batch without trusting row counts or a prior `passed`
 * aggregate. Changing a spec, mapping, extractor contract, provider/model
 * identity, example definition, or acknowledgement makes the batch stale. */
export function evaluateTemplateTwinCustomExampleCoverage(input: {
  specifications: readonly CertifiedTemplateFieldSpecification[];
  mappingsSha256: string;
  fieldIntentsSha256: string;
  physicianUserId: string;
  rows: readonly PersistedTemplateTwinCustomExampleExecution[];
}): TemplateTwinCustomExampleCoverage {
  const definitions = templateTwinCustomExampleDefinitions(
    input.specifications,
  );
  if (definitions.length === 0) {
    return {
      requiredCount: 0,
      passedCount: 0,
      acknowledgedCount: 0,
      ready: true,
      stale: false,
      latestBatchId: null,
      proofSha256: canonicalSha256([]),
      examples: [],
    };
  }
  if (input.rows.length === 0) {
    return {
      requiredCount: definitions.length,
      passedCount: 0,
      acknowledgedCount: 0,
      ready: false,
      stale: false,
      latestBatchId: null,
      proofSha256: null,
      examples: definitions.map((definition) => ({
        fieldId: definition.fieldId,
        conceptId: definition.conceptId,
        physicianName: definition.physicianName,
        exampleKind: definition.kind,
        exampleId: definition.exampleId,
        syntheticEvidence: definition.syntheticEvidence,
        expectedValue: definition.expectedValue,
        expectedUnit: definition.expectedUnit,
        expectedStatus: definition.expectedStatus,
        prohibitedValue: definition.prohibitedValue,
        possibleValues: definition.possibleValues,
        actualStatus: null,
        actualValue: null,
        actualUnit: null,
        actualEvidenceAnchorCount: 0,
        actualSourceFactCount: 0,
        passed: false,
        acknowledged: false,
        failureCode: null,
      })),
    };
  }

  const batchIds = new Set(input.rows.map((row) => row.batchId));
  const latestBatchId = batchIds.size === 1 ? input.rows[0]!.batchId : null;
  const definitionByKey = new Map(
    definitions.map((definition) => [
      `${definition.fieldId}:${definition.kind}:${definition.exampleId}`,
      definition,
    ]),
  );
  const specificationSetSha256 =
    templateTwinCustomSpecificationSetSha256(input.specifications);
  const expectedExtractionSchemaSha256 = computeCustomExtractionSchemaHash(
    input.specifications,
  );
  const seen = new Set<string>();
  let stale = latestBatchId === null || input.rows.length !== definitions.length;
  const examples = input.rows.map((row) => {
    const key = `${row.fieldId}:${row.exampleKind}:${row.exampleId}`;
    const definition = definitionByKey.get(key);
    const duplicate = seen.has(key);
    seen.add(key);
    const persistedCandidateValues = Array.isArray(
      row.resultSummary.candidateValues,
    )
      ? row.resultSummary.candidateValues.filter(
          (value): value is CustomScalarValue =>
            typeof value === "string" ||
            typeof value === "number" ||
            typeof value === "boolean",
        )
      : [];
    const independentlyClassified = definition
      ? classifyResult(definition, {
          status: row.resultStatus,
          value: row.resultValue,
          unit: row.resultUnit,
          sourceFactCount:
            typeof row.resultSummary.sourceFactCount === "number"
              ? row.resultSummary.sourceFactCount
              : -1,
          evidenceAnchorCount:
            typeof row.resultSummary.evidenceAnchorCount === "number"
              ? row.resultSummary.evidenceAnchorCount
              : -1,
          candidateValues: persistedCandidateValues,
          unexpectedUnsafeOutcome:
            row.resultSummary.unexpectedUnsafeOutcome !== false,
          evidenceAnchorIds: Array.isArray(
            row.resultSummary.evidenceAnchorIds,
          )
            ? row.resultSummary.evidenceAnchorIds.filter(
                (value): value is string => typeof value === "string",
              )
            : [],
        })
      : null;
    const resultCore = definition
      ? {
          id: row.id,
          batchId: row.batchId,
          definition,
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
        }
      : null;
    const rowCurrent = Boolean(
      definition &&
        !duplicate &&
        row.conceptId === definition.conceptId &&
        row.exampleDefinitionSha256 === definition.definitionSha256 &&
        row.specificationSha256 === definition.specificationSha256 &&
        row.specificationSetSha256 === specificationSetSha256 &&
        row.mappingsSha256 === input.mappingsSha256 &&
        row.fieldIntentsSha256 === input.fieldIntentsSha256 &&
        row.contractVersion === TEMPLATE_TWIN_CUSTOM_EXAMPLE_CONTRACT_VERSION &&
        row.extractionSchemaSha256 === expectedExtractionSchemaSha256 &&
        row.extractorVersion === TEMPLATE_CUSTOM_EXTRACTION_VERSION &&
        row.extractionSchemaVersion ===
          TEMPLATE_CUSTOM_EXTRACTION_SCHEMA_VERSION &&
        row.providerSha256 === sha256(row.provider) &&
        row.model.trim().length > 0 &&
        row.modelSha256 === sha256(row.model) &&
        independentlyClassified !== null &&
        row.passed === independentlyClassified.passed &&
        row.failureCode === independentlyClassified.failureCode &&
        resultCore &&
        canonicalSha256(resultCore) === row.resultSha256,
    );
    if (!rowCurrent) stale = true;
    return {
      fieldId: row.fieldId,
      conceptId: row.conceptId,
      physicianName: definition?.physicianName ?? "Unknown custom field",
      exampleKind: (definition?.kind ?? "positive") as TemplateTwinCustomExampleKind,
      exampleId: row.exampleId,
      syntheticEvidence: definition?.syntheticEvidence ?? "",
      expectedValue: definition?.expectedValue ?? null,
      expectedUnit: definition?.expectedUnit ?? null,
      expectedStatus: definition?.expectedStatus ?? null,
      prohibitedValue: definition?.prohibitedValue ?? null,
      possibleValues: definition?.possibleValues ?? [],
      actualStatus: row.resultStatus,
      actualValue: row.resultValue,
      actualUnit: row.resultUnit,
      actualEvidenceAnchorCount:
        typeof row.resultSummary.evidenceAnchorCount === "number"
          ? row.resultSummary.evidenceAnchorCount
          : 0,
      actualSourceFactCount:
        typeof row.resultSummary.sourceFactCount === "number"
          ? row.resultSummary.sourceFactCount
          : 0,
      passed: rowCurrent && independentlyClassified?.passed === true,
      acknowledged:
        rowCurrent &&
        row.acknowledgedById === input.physicianUserId &&
        row.acknowledgedAt !== null,
      failureCode:
        independentlyClassified?.failureCode ?? row.failureCode,
    };
  });
  if (seen.size !== definitionByKey.size) stale = true;
  const passedCount = examples.filter((example) => example.passed).length;
  const acknowledgedCount = examples.filter(
    (example) => example.acknowledged,
  ).length;
  const ready =
    !stale &&
    passedCount === definitions.length &&
    acknowledgedCount === definitions.length;
  return {
    requiredCount: definitions.length,
    passedCount,
    acknowledgedCount,
    ready,
    stale,
    latestBatchId,
    proofSha256: ready
      ? canonicalSha256(
          [...input.rows]
            .sort((left, right) => left.id.localeCompare(right.id))
            .map((row) => ({
              id: row.id,
              resultSha256: row.resultSha256,
              acknowledgedById: row.acknowledgedById,
              acknowledgedAt: row.acknowledgedAt?.toISOString(),
            })),
        )
      : null,
    examples,
  };
}
