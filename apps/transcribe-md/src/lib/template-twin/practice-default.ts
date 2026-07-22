import { canonicalSha256 } from './canonical';
import type { SemanticMapping, TemplateField } from './ir';

/** Stable provenance identifiers for a physician-approved mapping default.
 * The value is intentionally part of the identity, so a changed default can
 * never reuse the prior manifest's fact or evidence anchor. */
export function approvedPracticeDefaultFactId(
  field: Pick<TemplateField, 'fieldId'>,
  mapping: Pick<SemanticMapping, 'clinicalConcept' | 'practiceDefault'>,
): string {
  return `ttfact_${canonicalSha256({
    kind: 'approved_practice_default',
    fieldId: field.fieldId,
    concept: mapping.clinicalConcept,
    value: mapping.practiceDefault,
  }).slice(0, 24)}`;
}

export function approvedPracticeDefaultAnchorId(
  field: Pick<TemplateField, 'fieldId'>,
  factId: string,
): string {
  return `ttpd_${canonicalSha256({ factId, fieldId: field.fieldId }).slice(0, 24)}`;
}
