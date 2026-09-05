import type { SemanticMapping } from './ir';
import { canonicalSha256 } from './canonical';

/**
 * ⚠️ ONLY AN UNSET POLICY IS ELIDED. `null`/absent means NO ONE DECLARED, which
 * is the state every pre-existing row is in and the state that must contribute
 * nothing — that is what holds every certified `approvedMappingsSha256` still
 * when the column arrives. `fill-engine` compares this sha against the
 * certification and throws `TEMPLATE_PROVENANCE_MISMATCH` on a mismatch, so a
 * moved hash refuses a doctor's fill.
 *
 * ⚠️ AND `'keep'` MUST *NOT* BE ELIDED, WHICH IS THE OPPOSITE OF WHAT THIS
 * COMMENT SAID UNDER #191. Then, `keep` and absent were semantically identical
 * — both readers tested only for `'omit'` — so collapsing them was consistency.
 * #192 makes them OPPOSITES: absent clears, `keep` keeps. Eliding `'keep'`
 * would let a doctor's DECLARED keep be removed from a certified mapping
 * WITHOUT MOVING THE ATTESTATION, so the certificate would attest to behaviour
 * it never saw. Both explicit values move the sha, and that is correct: each is
 * a declaration that changes what the document says, and changing it is exactly
 * what should demand re-certification.
 *
 * ⚠️ THE STALE VERSION OF THIS PARAGRAPH WAS FOUND BY THE ADVERSARIAL PASS,
 * NOT BY A TEST. The code was already right; its stated reason was not, and a
 * maintainer following the reason would have widened the elision to `'keep'`
 * and silently broken the attestation. An exemption's justification decays
 * separately from the code it justifies.
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
