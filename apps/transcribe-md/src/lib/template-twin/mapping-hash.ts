import type { SemanticMapping } from './ir';
import { canonicalSha256 } from './canonical';

/**
 * ⚠️ ONLY AN UNSET POLICY IS ELIDED. NULL means NO ONE RULED, which is the
 * state every pre-existing row is in and the state that must contribute
 * nothing — that is what held every certified `approvedMappingsSha256` still
 * when the column arrived. `fill-engine` compares this sha against the
 * certification and throws `TEMPLATE_PROVENANCE_MISMATCH` on a mismatch, so a
 * moved hash refuses a doctor's fill.
 *
 * ⚠️ AN EXPLICIT `'omit'` MUST MOVE IT. A doctor ruling a control blank changes
 * what the document says, and a certificate that did not notice would be
 * attesting to behaviour it never saw. Re-certification is the correct cost
 * there; it is not a cost anyone should pay for a value nobody set.
 *
 * ⚠️ #194 DELETED THE `'keep'` VALUE THIS COMMENT USED TO ARGUE ABOUT. The
 * argument is kept in the ruling, not here: a justification that names a value
 * the schema no longer admits is how somebody reintroduces it.
 */
function forAttestation(mapping: SemanticMapping): SemanticMapping {
  if (mapping.unmentionedPolicy == null) {
    const { unmentionedPolicy: _unset, ...rest } = mapping;
    return rest as SemanticMapping;
  }
  return mapping;
}

export function templateTwinMappingsSha256(
  mappings: readonly SemanticMapping[],
): string {
  return canonicalSha256(
    [...mappings]
      .sort((a, b) => a.fieldId.localeCompare(b.fieldId))
      .map(forAttestation),
  );
}
