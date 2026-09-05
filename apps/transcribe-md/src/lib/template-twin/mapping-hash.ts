import type { SemanticMapping } from './ir';
import { canonicalSha256 } from './canonical';

/**
 * ⚠️ #191 — A POLICY EQUAL TO THE DEFAULT CONTRIBUTES NOTHING TO THE
 * ATTESTATION, AND THAT IS CONSISTENCY RATHER THAN CONVENIENCE.
 *
 * `unmentionedPolicy` is `.optional()` in `ir.ts` PRECISELY BECAUSE absent and
 * `'keep'` are the same thing — both readers in the resolver test only for
 * `'omit'`, so neither can tell them apart. This normalisation makes the
 * certified hash agree with the schema's own semantics.
 *
 * ⚠️ WITHOUT IT, CARRYING THE COLUMN IS A PRODUCTION OUTAGE. `fill-engine`
 * compares this sha against `certification.approvedMappingsSha256` and throws
 * `TEMPLATE_PROVENANCE_MISMATCH` on a mismatch. Every row in production holds
 * the DB default `'keep'` — nothing could write anything else until this
 * commit — so simply projecting the new column would have moved every sha and
 * REFUSED EVERY CERTIFIED TEMPLATE, including the one active form this
 * programme exists to serve. Measured before the fix: the same mapping hashed
 * `a8267455…` without the key and `bb8b8bb7…` with it.
 *
 * ⚠️ AND `'omit'` DELIBERATELY DOES MOVE THE SHA. A doctor changing a
 * scaffolded field from "keep my sentence" to "clear it" has changed what the
 * document says, and a certification that did not notice would be attesting to
 * behaviour it never saw. Re-certification is the correct cost there; it is
 * not a cost anyone should pay for a value identical to the default.
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
