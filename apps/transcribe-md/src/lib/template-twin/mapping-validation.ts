import type { SemanticMapping, TemplateField } from "./ir";

export type TemplateTwinMappingSetting =
  | "clinicalDetail"
  | "fieldIntent"
  | "mappingStatus"
  | "expectedDataType"
  | "approvedSynonyms"
  | "practiceDefault"
  | "customConcept"
  | "staticField"
  | "fieldSet";

export interface TemplateTwinMappingFieldError {
  fieldId: string;
  fieldLabel: string;
  fieldNumber: number;
  setting: TemplateTwinMappingSetting;
  message: string;
}

interface MappingIntent {
  fieldId: string;
  intentKind: "supported_concept" | "static" | "custom_concept" | "unresolved";
  supportedConcept?: string | null;
}

export function templateTwinMappingFieldError(input: {
  field: TemplateField;
  setting: TemplateTwinMappingSetting;
  message: string;
}): TemplateTwinMappingFieldError {
  return {
    fieldId: input.field.fieldId,
    fieldLabel: input.field.originalLabel,
    fieldNumber: input.field.displayOrder + 1,
    setting: input.setting,
    message: input.message,
  };
}

/**
 * Shared fail-closed rule for the defect where choosing the
 * `supported_concept` intent without choosing its concrete clinical detail
 * could be rendered as confirmed by the client. The lifecycle service calls
 * this again under its write transaction; client state is never trusted.
 */
export function validateTemplateTwinClinicalDetail(input: {
  field: TemplateField;
  mapping: SemanticMapping;
  intent?: MappingIntent;
}): TemplateTwinMappingFieldError | null {
  if (input.mapping.status !== "certified") return null;

  const requiresIntent =
    input.field.rendererBinding.bindingType === "ordinary_placeholder";
  const intent = input.intent;
  if (requiresIntent && (!intent || intent.intentKind === "unresolved")) {
    return templateTwinMappingFieldError({
      field: input.field,
      setting: "fieldIntent",
      message:
        "Choose what information belongs in this field before confirming it.",
    });
  }

  if (intent?.intentKind === "static") return null;

  if (intent?.intentKind === "supported_concept") {
    const selected = intent.supportedConcept?.trim() ?? "";
    if (!selected) {
      return templateTwinMappingFieldError({
        field: input.field,
        setting: "clinicalDetail",
        message: "Choose a clinical detail before confirming this field.",
      });
    }
    if (input.mapping.clinicalConcept !== selected) {
      return templateTwinMappingFieldError({
        field: input.field,
        setting: "clinicalDetail",
        message:
          "The confirmed clinical detail does not match this field's selected intent.",
      });
    }
    return null;
  }

  if (!input.mapping.clinicalConcept?.trim()) {
    return templateTwinMappingFieldError({
      field: input.field,
      setting: "clinicalDetail",
      message: "Choose a clinical detail before confirming this field.",
    });
  }

  return null;
}
