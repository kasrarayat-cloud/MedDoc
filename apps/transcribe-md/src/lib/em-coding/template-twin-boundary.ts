import {
  hasDurableTemplateTwinVisitProvenance,
  type TemplateTwinDurableVisitProvenance,
} from "@/lib/template-twin/durable-visit-provenance";

/**
 * Durable Template Twin provenance used by generic E/M provider boundaries.
 *
 * A current NoteTemplate row is not sufficient provenance: it can be retired,
 * replaced, or detached while the immutable fill/admission lineage remains.
 * Any one of these relations keeps the visit on the fail-closed Twin path.
 */
export function hasTemplateTwinProvenance(
  visit: TemplateTwinDurableVisitProvenance,
): boolean {
  return hasDurableTemplateTwinVisitProvenance(visit);
}

/**
 * Executes a generic provider-backed E/M operation only for a provenance-
 * proven ordinary visit. The same linearizable ordinary-provenance fence runs
 * immediately before provider egress and again after return; a provenance
 * transition therefore prevents the call or prevents its result from being
 * returned. Kept here so server-render callers cannot regress to an
 * unguarded cold-cache model call through a future condition refactor.
 */
export async function runProviderBackedEmForOrdinaryVisit<T>(
  templateTwinProvenance: boolean,
  ordinaryProvenanceFence: () => Promise<void>,
  operation: () => Promise<T>,
): Promise<T | null> {
  if (templateTwinProvenance) return null;
  await ordinaryProvenanceFence();
  const result = await operation();
  await ordinaryProvenanceFence();
  return result;
}
