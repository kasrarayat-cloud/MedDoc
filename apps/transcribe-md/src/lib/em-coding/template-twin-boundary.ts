/**
 * Durable Template Twin provenance used by generic E/M provider boundaries.
 *
 * A current NoteTemplate row is not sufficient provenance: it can be retired,
 * replaced, or detached while the immutable fill/admission lineage remains.
 * Any one of these relations keeps the visit on the fail-closed Twin path.
 */
export function hasTemplateTwinProvenance(visit: {
  noteTemplate?: { templateKind?: string | null } | null;
  templateTwinFill?: unknown | null;
  templateTwinSyntheticQaRun?: unknown | null;
  templateTwinSyntheticQaAdmission?: unknown | null;
}): boolean {
  return Boolean(
    visit.noteTemplate?.templateKind === "template_twin_docx" ||
    visit.templateTwinFill ||
    visit.templateTwinSyntheticQaRun ||
    visit.templateTwinSyntheticQaAdmission,
  );
}

/**
 * Executes a generic provider-backed E/M operation only for a provenance-
 * proven ordinary visit. Kept here so server-render callers cannot regress to
 * an unguarded cold-cache model call through a future condition refactor.
 */
export async function runProviderBackedEmForOrdinaryVisit<T>(
  templateTwinProvenance: boolean,
  operation: () => Promise<T>,
): Promise<T | null> {
  if (templateTwinProvenance) return null;
  return operation();
}
