import { describe, expect, it } from "vitest";

import type { SemanticMapping, TemplateField } from "../ir";
import { validateTemplateTwinClinicalDetail } from "../mapping-validation";

const FIELD_ID = `ttf_${"a".repeat(24)}`;

function field(bindingType: "ordinary_placeholder" | "content_control") {
  return {
    fieldId: FIELD_ID,
    displayOrder: 2,
    originalLabel: "Synthetic clinical detail",
    kind: "narrative_text",
    allowedOptions: [],
    detectionStatus: "needs_confirmation",
    labelSource: "preceding_text",
    clinicallyMaterial: true,
    criticality: "routine",
    required: true,
    unknownPolicy: "requires_input",
    tableId: null,
    rowPrototype: false,
    rendererBinding: {
      bindingType,
      bindingProfile:
        bindingType === "ordinary_placeholder"
          ? "ORDINARY_PLACEHOLDER_TOKEN_V1"
          : "CONTENT_CONTROL_TEXT_V1",
      partName: "word/document.xml",
      tableIndex: null,
      rowIndex: null,
      cellIndex: null,
      paragraphIndex: 0,
      runIndex: 0,
      controlId: bindingType === "content_control" ? 4101 : null,
      controlTag: null,
      controlAlias: null,
      legacyName: null,
      placeholderToken:
        bindingType === "ordinary_placeholder" ? "<<synthetic detail>>" : null,
    },
  } as unknown as TemplateField;
}

function mapping(clinicalConcept: string | null): SemanticMapping {
  return {
    fieldId: FIELD_ID,
    clinicalConcept,
    expectedDataType: "text",
    polarityBehavior: "value_only",
    temporality: "any",
    laterality: "not_applicable",
    unitPolicy: "not_applicable",
    approvedSynonyms: [],
    required: true,
    blankPolicy: "requires_input",
    unknownPolicy: "requires_input",
    practiceDefault: null,
    status: "certified",
  };
}

describe("Template Twin clinical-detail validation", () => {
  it("rejects a confirmed supported-concept intent with no selected detail", () => {
    expect(
      validateTemplateTwinClinicalDetail({
        field: field("ordinary_placeholder"),
        mapping: mapping(null),
        intent: {
          fieldId: FIELD_ID,
          intentKind: "supported_concept",
          supportedConcept: "",
        },
      }),
    ).toEqual({
      fieldId: FIELD_ID,
      fieldLabel: "Synthetic clinical detail",
      fieldNumber: 3,
      setting: "clinicalDetail",
      message: "Choose a clinical detail before confirming this field.",
    });
  });

  it("rejects a native confirmed field without a selected detail", () => {
    expect(
      validateTemplateTwinClinicalDetail({
        field: field("content_control"),
        mapping: mapping(null),
      }),
    ).toMatchObject({
      fieldId: FIELD_ID,
      setting: "clinicalDetail",
    });
  });

  it("accepts a confirmed supported intent only when intent and mapping match", () => {
    expect(
      validateTemplateTwinClinicalDetail({
        field: field("ordinary_placeholder"),
        mapping: mapping("hpi.context"),
        intent: {
          fieldId: FIELD_ID,
          intentKind: "supported_concept",
          supportedConcept: "hpi.context",
        },
      }),
    ).toBeNull();
  });

  it("allows an explicitly static field to remain conceptless", () => {
    expect(
      validateTemplateTwinClinicalDetail({
        field: field("ordinary_placeholder"),
        mapping: mapping(null),
        intent: {
          fieldId: FIELD_ID,
          intentKind: "static",
        },
      }),
    ).toBeNull();
  });
});
