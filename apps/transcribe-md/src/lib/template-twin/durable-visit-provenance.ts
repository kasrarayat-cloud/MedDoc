import { isTemplateTwinSyntheticQaPatient } from "./synthetic-qa-patient";

export interface TemplateTwinDurableVisitProvenance {
  readonly patient: { readonly externalId: string | null } | null;
  readonly noteTemplate: {
    readonly templateKind: string;
    readonly templateTwinCompiledVersion: unknown | null;
  } | null;
  readonly templateTwinFill: unknown | null;
  readonly templateTwinSyntheticQaRun: unknown | null;
  readonly templateTwinSyntheticQaAdmission: unknown | null;
  readonly templateTwinProviderExecutions: readonly unknown[];
}

const REQUIRED_PROVENANCE_KEYS = [
  "patient",
  "noteTemplate",
  "templateTwinFill",
  "templateTwinSyntheticQaRun",
  "templateTwinSyntheticQaAdmission",
  "templateTwinProviderExecutions",
] as const;

/**
 * Classifies the complete durable visit census used by generic provider and
 * mutation boundaries. An incomplete select is itself unsafe: treating a
 * missing relation as ordinary would let a stale or detached Twin lineage
 * escape through a legacy provider path.
 */
export function hasDurableTemplateTwinVisitProvenance(
  visit: TemplateTwinDurableVisitProvenance,
): boolean {
  if (
    REQUIRED_PROVENANCE_KEYS.some(
      (key) => !Object.prototype.hasOwnProperty.call(visit, key),
    ) ||
    visit.patient === null ||
    !Object.prototype.hasOwnProperty.call(visit.patient, "externalId") ||
    (visit.patient.externalId !== null &&
      typeof visit.patient.externalId !== "string") ||
    (visit.noteTemplate !== null &&
      (!Object.prototype.hasOwnProperty.call(visit.noteTemplate, "templateKind") ||
        typeof visit.noteTemplate.templateKind !== "string" ||
        visit.noteTemplate.templateKind.trim().length === 0 ||
        !Object.prototype.hasOwnProperty.call(
          visit.noteTemplate,
          "templateTwinCompiledVersion",
        ))) ||
    !Array.isArray(visit.templateTwinProviderExecutions)
  ) {
    return true;
  }

  return Boolean(
    isTemplateTwinSyntheticQaPatient(visit.patient) ||
    visit.noteTemplate?.templateKind === "template_twin_docx" ||
    visit.noteTemplate?.templateTwinCompiledVersion != null ||
    visit.templateTwinFill ||
    visit.templateTwinSyntheticQaRun ||
    visit.templateTwinSyntheticQaAdmission ||
    visit.templateTwinProviderExecutions.length > 0,
  );
}
