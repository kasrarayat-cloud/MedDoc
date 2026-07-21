import type {
  SemanticMapping,
  TemplateField,
  TemplateTwinFieldKind,
} from "../ir";

/**
 * Pure structural compatibility helpers shared by runtime code and the
 * synthetic Office evidence CLI. Keep this module free of provider, database,
 * and server-only imports so evidence generation cannot acquire a live-provider
 * dependency merely by resolving a certified field.
 */
export function expectedDataTypeForFieldKind(
  kind: TemplateTwinFieldKind,
): SemanticMapping["expectedDataType"] | null {
  switch (kind) {
    case "narrative_text":
      return "text";
    case "single_select":
      return "single_select";
    case "multi_select":
      return "multi_select";
    case "checkbox":
      return "boolean";
    case "date":
      return "date";
    case "number":
      return "number";
    case "measurement":
      return "measurement";
    case "fixed_table":
    case "repeating_table":
      return "table";
    case "static":
    case "conditional_block":
    case "unsupported":
      return null;
  }
}

export function isMappingTypeCompatible(
  field: TemplateField,
  mapping: SemanticMapping,
): boolean {
  return expectedDataTypeForFieldKind(field.kind) === mapping.expectedDataType;
}
