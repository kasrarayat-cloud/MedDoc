import { describe, expect, it } from "vitest";

import { synchronizeCustomSyntheticExamples } from "../example-authoring";
import {
  TEMPLATE_FIELD_SPECIFICATION_VERSION,
  TemplateFieldSpecificationContentSchema,
  type CustomScalarDataType,
  type TemplateFieldSpecificationContent,
} from "../specification";

function draft(
  dataType: CustomScalarDataType,
): TemplateFieldSpecificationContent {
  return {
    specificationVersion: TEMPLATE_FIELD_SPECIFICATION_VERSION,
    templateLineageId: "synthetic-lineage",
    compiledVersionId: "synthetic-compiled",
    fieldId: `ttf_${"1".repeat(24)}`,
    conceptId: `ttcustom_${"2".repeat(24)}`,
    physicianName: "Synthetic custom field",
    physicianDescription: "Synthetic field used for deterministic QA only.",
    approvedEvidenceCues: ["synthetic custom field"],
    dataType,
    allowedOptions:
      dataType === "single_select"
        ? [
            { ordinal: 0, value: "Alpha", displayText: "Alpha" },
            { ordinal: 1, value: "Beta", displayText: "Beta" },
          ]
        : [],
    allowedUnits: dataType === "measurement" ? ["mm", "cm"] : [],
    permittedUnitConversions: [],
    allowedTemporalities: ["current"],
    allowedLateralities: ["not_applicable"],
    polarityPolicy: { allowExplicitDenial: false, exactDeniedOutput: null },
    required: true,
    unknownPolicy: "requires_input",
    maximumLength: dataType === "narrative_text" ? 120 : null,
    numericRange:
      dataType === "number" || dataType === "measurement"
        ? { minimum: 0, maximum: 100 }
        : null,
    evidenceRequirements: {
      minimumAnchors: 1,
      acceptedEvidenceQualities: ["direct"],
    },
    positiveSyntheticExamples: [],
    negativeSyntheticExamples: [],
    ambiguitySyntheticExamples: [],
  };
}

describe("custom synthetic-example authoring", () => {
  it.each([
    "narrative_text",
    "number",
    "measurement",
    "date",
    "boolean",
    "single_select",
  ] as const)("creates a schema-valid first-run %s corpus", (dataType) => {
    const synchronized = synchronizeCustomSyntheticExamples(draft(dataType));
    expect(() =>
      TemplateFieldSpecificationContentSchema.parse(synchronized),
    ).not.toThrow();
    expect(
      synchronized.negativeSyntheticExamples[0]?.syntheticEvidence,
    ).not.toContain(synchronized.approvedEvidenceCues[0]);
    expect(
      synchronized.ambiguitySyntheticExamples[0]?.syntheticEvidence,
    ).toContain(" or ");
  });

  it("creates one preserved positive test per option and exact unit", () => {
    const select = synchronizeCustomSyntheticExamples(draft("single_select"));
    expect(select.positiveSyntheticExamples.map((item) => item.expectedValue)).toEqual([
      "Alpha",
      "Beta",
    ]);
    const measurement = synchronizeCustomSyntheticExamples(draft("measurement"));
    expect(measurement.positiveSyntheticExamples.map((item) => item.expectedUnit)).toEqual([
      "mm",
      "cm",
    ]);
  });

  it("adds an explicit denial test and lets it cover the exact denied option", () => {
    const synchronized = synchronizeCustomSyntheticExamples({
      ...draft("single_select"),
      polarityPolicy: { allowExplicitDenial: true, exactDeniedOutput: "Alpha" },
    });
    expect(synchronized.positiveSyntheticExamples).toEqual(
      expect.arrayContaining([
        expect.objectContaining({
          expectedStatus: "explicitly_denied",
          expectedValue: "Alpha",
        }),
        expect.objectContaining({ expectedStatus: "supported", expectedValue: "Beta" }),
      ]),
    );
    expect(() =>
      TemplateFieldSpecificationContentSchema.parse(synchronized),
    ).not.toThrow();
  });

  it("chooses an in-range measurement value and preserves physician edits per unit", () => {
    const initial = synchronizeCustomSyntheticExamples({
      ...draft("measurement"),
      numericRange: { minimum: 10, maximum: 20 },
    });
    expect(initial.positiveSyntheticExamples.map((item) => item.expectedValue)).toEqual([
      10,
      10,
    ]);
    const edited = {
      ...initial,
      positiveSyntheticExamples: initial.positiveSyntheticExamples.map(
        (example, index) =>
          index === 0 ? { ...example, expectedValue: 12 } : example,
      ),
    };
    const synchronized = synchronizeCustomSyntheticExamples(edited);
    expect(synchronized.positiveSyntheticExamples[0]?.expectedValue).toBe(12);
    expect(() =>
      TemplateFieldSpecificationContentSchema.parse(synchronized),
    ).not.toThrow();
  });
});
