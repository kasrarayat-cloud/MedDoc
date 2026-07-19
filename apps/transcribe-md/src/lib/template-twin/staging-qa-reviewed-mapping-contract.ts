import type { TemplateTwinFieldIntentInput } from "./field-intent";
import type { SemanticMapping, TemplateField } from "./ir";

export const TEMPLATE_TWIN_STAGING_QA_REVIEWED_MAPPING_CONTRACT_VERSION =
  "template-twin-staging-reviewed-mappings/1.0.0" as const;

/**
 * Reviewed mapping decisions for the one byte-allowlisted synthetic fixture.
 *
 * Field IDs and source binding identities are deliberately pinned alongside
 * the physician-facing mapping. A matching label or display order is never
 * enough to make another template eligible for these decisions.
 */
export const TEMPLATE_TWIN_STAGING_QA_REVIEWED_FIELD_CONTRACT = [
  {
    fieldId: "ttf_84fbcf2cfb5de6857c466071",
    fieldLabel: "Synthetic chief concern",
    physicianDetailLabel: "Chief concern",
    displayOrder: 1,
    fieldKind: "narrative_text",
    bindingType: "content_control",
    sourceBindingIdentitySha256:
      "be06e3a7c3bcad82d56d3e16875b7a0854977897bc8c3d6011f38b3ff91627e2",
    clinicalConcept: "chief_complaint",
    expectedDataType: "text",
    polarityBehavior: "not_applicable",
  },
  {
    fieldId: "ttf_4a81056d9d100e65475b703b",
    fieldLabel: "Synthetic smoking status",
    physicianDetailLabel: "Smoking status",
    displayOrder: 2,
    fieldKind: "single_select",
    bindingType: "content_control",
    sourceBindingIdentitySha256:
      "dfeabe81e4b74f71820eaff77f6399ad231c61043966dd8b4487ab2cd60fb628",
    clinicalConcept: "social_history.smoking",
    expectedDataType: "single_select",
    polarityBehavior: "not_applicable",
  },
  {
    fieldId: "ttf_f4d4d71389d7c00898c93d37",
    fieldLabel: "Synthetic encounter category",
    physicianDetailLabel: "Assessment discussed",
    displayOrder: 3,
    fieldKind: "single_select",
    bindingType: "content_control",
    sourceBindingIdentitySha256:
      "bed4f7b523044464fa8f69d59e479e304a6a5b0ee51c38b66078b0a7612127fe",
    clinicalConcept: "assessment",
    expectedDataType: "single_select",
    polarityBehavior: "not_applicable",
  },
  {
    fieldId: "ttf_c2e2b13d35067ae09375aa59",
    fieldLabel: "Synthetic encounter date",
    physicianDetailLabel: "Symptom onset",
    displayOrder: 4,
    fieldKind: "date",
    bindingType: "content_control",
    sourceBindingIdentitySha256:
      "ec6c6b28ce956dd3dd7f5e780e8a05ca907b01b174abe8ef45ae38036a01c517",
    clinicalConcept: "hpi.onset",
    expectedDataType: "date",
    polarityBehavior: "not_applicable",
  },
  {
    fieldId: "ttf_3ce3822e83b131ee504d4306",
    fieldLabel: "Synthetic respiratory symptom",
    physicianDetailLabel: "Review of systems — respiratory",
    displayOrder: 5,
    fieldKind: "checkbox",
    bindingType: "content_control",
    sourceBindingIdentitySha256:
      "c52ff918f1cdae90e41f8690518d496bce23fe965159f54d478bd0c38235d068",
    clinicalConcept: "ros.respiratory",
    expectedDataType: "boolean",
    polarityBehavior: "affirmative_only",
  },
  {
    fieldId: "ttf_fc97c91bb580f2fab3f795a7",
    fieldLabel: "Synthetic plan item",
    physicianDetailLabel: "Plan discussed",
    displayOrder: 8,
    fieldKind: "narrative_text",
    bindingType: "content_control",
    sourceBindingIdentitySha256:
      "7c4e2d60b6482954fea755aa9b985bd2996da3db3da3fc53a4f386640be20994",
    clinicalConcept: "plan",
    expectedDataType: "text",
    polarityBehavior: "not_applicable",
  },
  {
    fieldId: "ttf_16c5bfae4982bdaee48e56c6",
    fieldLabel: "Plan detail",
    physicianDetailLabel: "Plan discussed",
    displayOrder: 10,
    fieldKind: "narrative_text",
    bindingType: "table_cell",
    sourceBindingIdentitySha256:
      "6226be45b394fc18a5b50eb12beeecdcc01967acfc02762154764499602f23b3",
    clinicalConcept: "plan",
    expectedDataType: "text",
    polarityBehavior: "not_applicable",
  },
  {
    fieldId: "ttf_471aee4f349042e2d7e10237",
    fieldLabel: "insert synthetic detail",
    physicianDetailLabel: "Symptom context",
    displayOrder: 11,
    fieldKind: "narrative_text",
    bindingType: "ordinary_placeholder",
    sourceBindingIdentitySha256:
      "efce63201630a45b5b32271158c0f7a36524d45fe10745e7346c70e3cb8a1e9b",
    clinicalConcept: "hpi.context",
    expectedDataType: "text",
    polarityBehavior: "not_applicable",
  },
] as const satisfies ReadonlyArray<{
  readonly fieldId: string;
  readonly fieldLabel: string;
  readonly physicianDetailLabel: string;
  readonly displayOrder: number;
  readonly fieldKind: TemplateField["kind"];
  readonly bindingType: TemplateField["rendererBinding"]["bindingType"];
  readonly sourceBindingIdentitySha256: string;
  readonly clinicalConcept: string;
  readonly expectedDataType: SemanticMapping["expectedDataType"];
  readonly polarityBehavior: SemanticMapping["polarityBehavior"];
}>;

export const TEMPLATE_TWIN_STAGING_QA_REVIEWED_STRUCTURE_CONTRACT = {
  totalFields: 8,
  dropdowns: 1,
  comboBoxes: 1,
  checkboxes: 1,
  dateControls: 1,
  tables: 1,
  repeatingTables: 0,
  headers: 1,
  footers: 1,
  unsupported: 0,
  blockingUnsupported: 0,
} as const;

export interface TemplateTwinStagingQaPhysicianReviewFieldSummary {
  readonly fieldId: string;
  readonly fieldLabel: string;
  readonly clinicalConcept: string;
  readonly clinicalDetailLabel: string;
  readonly settings: {
    readonly expectedDataType: SemanticMapping["expectedDataType"];
    readonly polarityBehavior: SemanticMapping["polarityBehavior"];
    readonly temporality: "any";
    readonly laterality: "not_applicable";
    readonly unitPolicy: "not_applicable";
    readonly whenNotStated: "requires_input";
    readonly requiredBeforeSigning: true;
  };
}

export interface TemplateTwinStagingQaPhysicianReviewSummary {
  readonly title: "Physician review of the synthetic mapping set";
  readonly fixtureLabel: "Template Twin Synthetic QA Fixture";
  readonly fieldCount: 8;
  readonly fields: readonly TemplateTwinStagingQaPhysicianReviewFieldSummary[];
  readonly settings: {
    readonly approvedSynonyms: "none";
    readonly practiceDefaults: "none";
    readonly blankPolicy: "blank";
    readonly missingClinicalDetail: "requires_input";
    readonly requiredBeforeSigning: true;
  };
  readonly explicitConfirmationRequired: true;
  readonly activationPerformed: false;
}

export interface TemplateTwinStagingQaReviewedMappingDraft {
  readonly contractVersion: typeof TEMPLATE_TWIN_STAGING_QA_REVIEWED_MAPPING_CONTRACT_VERSION;
  readonly fixture: {
    readonly sha256: string;
    readonly sizeBytes: number;
  };
  readonly template: {
    readonly id: string;
    readonly version: number;
  };
  readonly expectedMappingsSha256: string;
  readonly expectedFieldIntentsSha256: string;
  readonly mappings: readonly SemanticMapping[];
  readonly fieldIntents: readonly TemplateTwinFieldIntentInput[];
  readonly physicianReviewSummary: TemplateTwinStagingQaPhysicianReviewSummary;
}

export interface TemplateTwinStagingQaReviewedMappingsResponse {
  readonly ok: true;
  readonly reviewed: TemplateTwinStagingQaReviewedMappingDraft;
}
