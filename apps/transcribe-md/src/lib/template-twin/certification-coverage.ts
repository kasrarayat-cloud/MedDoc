import {
  type SemanticMapping,
  type TemplateField,
  type TemplateTwinFillManifest,
} from './ir';

export const TEMPLATE_TWIN_CERTIFICATION_COVERAGE_VERSION =
  'template-twin-certification-coverage/1.0.0' as const;

export interface TemplateTwinFieldTestWaiverEvidence {
  fieldId: string;
  mappingsSha256: string;
  waivedById: string;
  reason: string;
  waivedAt: Date | string;
}
export interface TemplateTwinCoverageIssue {
  fieldId: string | null;
  code:
    | 'CERT_REQUIRED_FIELD_UNTESTED'
    | 'CERT_MATERIAL_FIELD_UNTESTED'
    | 'CERT_OPTIONAL_FIELD_NEEDS_WAIVER'
    | 'CERT_WAIVER_NOT_ALLOWED'
    | 'CERT_WAIVER_STALE_MAPPING'
    | 'CERT_WAIVER_ACTOR_MISMATCH'
    | 'CERT_WAIVER_REASON_INVALID'
    | 'CERT_WAIVER_FIELD_UNKNOWN'
    | 'CERT_WAIVER_DUPLICATE'
    | 'CERT_EXERCISE_INVALID';
  message: string;
}

export interface TemplateTwinFieldCoverageResult {
  fieldId: string;
  disposition: 'exercised' | 'waived' | 'blocking';
  checks: readonly string[];
}

export interface TemplateTwinCertificationCoverageResult {
  version: typeof TEMPLATE_TWIN_CERTIFICATION_COVERAGE_VERSION;
  ready: boolean;
  fields: TemplateTwinFieldCoverageResult[];
  issues: TemplateTwinCoverageIssue[];
}

function strictIsoDate(value: string): boolean {
  const match = /^(\d{4})-(\d{2})-(\d{2})$/.exec(value);
  if (!match) return false;
  const date = new Date(
    Date.UTC(Number(match[1]), Number(match[2]) - 1, Number(match[3])),
  );
  return (
    date.getUTCFullYear() === Number(match[1]) &&
    date.getUTCMonth() === Number(match[2]) - 1 &&
    date.getUTCDate() === Number(match[3])
  );
}

function isExercised(input: {
  field: TemplateField;
  mapping: SemanticMapping;
  manifest: TemplateTwinFillManifest;
}): { exercised: boolean; checks: string[] } {
  const resolution = input.manifest.fields.find(
    (candidate) => candidate.fieldId === input.field.fieldId,
  );
  if (!resolution || resolution.value === null) {
    return { exercised: false, checks: [] };
  }
  if (
    !['supported', 'explicitly_denied', 'approved_practice_default'].includes(
      resolution.status,
    ) ||
    input.manifest.validation.issues.some(
      (issue) =>
        issue.fieldId === input.field.fieldId && issue.severity === 'blocking',
    )
  ) {
    return { exercised: false, checks: [] };
  }
  const facts = resolution.sourceFactIds
    .map((factId) =>
      input.manifest.facts.find((candidate) => candidate.factId === factId),
    )
    .filter((fact): fact is TemplateTwinFillManifest['facts'][number] => Boolean(fact));
  if (
    facts.length !== resolution.sourceFactIds.length ||
    facts.length === 0 ||
    resolution.evidenceAnchorIds.length === 0
  ) {
    return { exercised: false, checks: [] };
  }

  const checks = ['evidence_anchored', `polarity_${facts[0]!.polarity}`];
  switch (input.field.kind) {
    case 'single_select': {
      if (typeof resolution.value !== 'string') return { exercised: false, checks };
      const option = input.field.allowedOptions.find(
        (candidate) =>
          candidate.value === resolution.value &&
          candidate.ordinal === resolution.selectedOptionOrdinal,
      );
      if (!option) return { exercised: false, checks };
      checks.push(`exact_option_${option.ordinal}`);
      break;
    }
    case 'multi_select': {
      if (
        !Array.isArray(resolution.value) ||
        resolution.value.length === 0 ||
        resolution.value.some((value) => typeof value !== 'string')
      ) {
        return { exercised: false, checks };
      }
      const allowed = new Set(input.field.allowedOptions.map((option) => option.value));
      if (resolution.value.some((value) => !allowed.has(value as string))) {
        return { exercised: false, checks };
      }
      checks.push('exact_options');
      break;
    }
    case 'checkbox':
      if (typeof resolution.value !== 'boolean') return { exercised: false, checks };
      if (
        resolution.value === false &&
        (resolution.status !== 'explicitly_denied' ||
          input.mapping.polarityBehavior !== 'explicit_denial_allowed' ||
          !facts.some((fact) => fact.polarity === 'denied'))
      ) {
        return { exercised: false, checks };
      }
      if (
        resolution.value === true &&
        !facts.some((fact) => fact.polarity === 'affirmed')
      ) {
        return { exercised: false, checks };
      }
      checks.push(resolution.value ? 'checkbox_checked' : 'checkbox_explicit_false');
      break;
    case 'date':
      if (typeof resolution.value !== 'string' || !strictIsoDate(resolution.value)) {
        return { exercised: false, checks };
      }
      checks.push('unambiguous_date');
      break;
    case 'number':
      if (typeof resolution.value !== 'number' || !Number.isFinite(resolution.value)) {
        return { exercised: false, checks };
      }
      checks.push('explicit_number');
      break;
    case 'measurement':
      if (
        input.mapping.unitPolicy === 'required' &&
        facts.some((fact) => fact.unit === null)
      ) {
        return { exercised: false, checks };
      }
      checks.push(
        input.mapping.unitPolicy === 'required'
          ? 'explicit_number_and_unit'
          : 'explicit_measurement',
      );
      break;
    case 'narrative_text':
      if (
        !input.field.rowPrototype &&
        typeof resolution.value !== 'string'
      ) {
        return { exercised: false, checks };
      }
      checks.push(input.field.rowPrototype ? 'repeating_rows' : 'direct_text');
      break;
  }
  if (input.field.rowPrototype) {
    if (!Array.isArray(resolution.value) || resolution.value.length === 0) {
      return { exercised: false, checks };
    }
    checks.push('table_row_behavior');
  }
  if (input.mapping.laterality === 'required') {
    if (
      facts.some(
        (fact) =>
          fact.laterality === 'unknown' ||
          fact.laterality === 'not_applicable',
      )
    ) {
      return { exercised: false, checks };
    }
    checks.push('explicit_laterality');
  }
  return { exercised: true, checks };
}

export function evaluateTemplateTwinCertificationCoverage(input: {
  fields: readonly TemplateField[];
  mappings: readonly SemanticMapping[];
  manifest: TemplateTwinFillManifest;
  /** Physician-designated static placeholder regions are proven preserved by
   * renderer/readback/static-invariance checks, not by encounter evidence. */
  staticFieldIds?: readonly string[];
  waivers: readonly TemplateTwinFieldTestWaiverEvidence[];
  currentMappingsSha256: string;
  actorUserId: string;
}): TemplateTwinCertificationCoverageResult {
  const issues: TemplateTwinCoverageIssue[] = [];
  const mappingById = new Map(input.mappings.map((mapping) => [mapping.fieldId, mapping]));
  const fieldById = new Map(input.fields.map((field) => [field.fieldId, field]));
  const waiverByFieldId = new Map<string, TemplateTwinFieldTestWaiverEvidence>();
  const staticFieldIds = new Set(input.staticFieldIds ?? []);

  for (const waiver of input.waivers) {
    if (waiverByFieldId.has(waiver.fieldId)) {
      issues.push({
        fieldId: waiver.fieldId,
        code: 'CERT_WAIVER_DUPLICATE',
        message: 'This optional field has more than one waiver.',
      });
      continue;
    }
    waiverByFieldId.set(waiver.fieldId, waiver);
    const field = fieldById.get(waiver.fieldId);
    if (!field) {
      issues.push({
        fieldId: waiver.fieldId,
        code: 'CERT_WAIVER_FIELD_UNKNOWN',
        message: 'A waiver references a field outside this template version.',
      });
      continue;
    }
    if (field.required || field.clinicallyMaterial || mappingById.get(field.fieldId)?.required) {
      issues.push({
        fieldId: waiver.fieldId,
        code: 'CERT_WAIVER_NOT_ALLOWED',
        message: 'Required or clinically meaningful fields must be exercised and cannot be waived.',
      });
    }
    if (waiver.mappingsSha256 !== input.currentMappingsSha256) {
      issues.push({
        fieldId: waiver.fieldId,
        code: 'CERT_WAIVER_STALE_MAPPING',
        message: 'This waiver predates the current field mappings and must be reviewed again.',
      });
    }
    if (waiver.waivedById !== input.actorUserId) {
      issues.push({
        fieldId: waiver.fieldId,
        code: 'CERT_WAIVER_ACTOR_MISMATCH',
        message: 'The authenticated physician must personally approve each waiver.',
      });
    }
    if (waiver.reason.trim().length < 10 || waiver.reason.trim().length > 500) {
      issues.push({
        fieldId: waiver.fieldId,
        code: 'CERT_WAIVER_REASON_INVALID',
        message: 'Explain why this optional field was not exercised.',
      });
    }
  }

  const results = input.fields.map((field): TemplateTwinFieldCoverageResult => {
    if (staticFieldIds.has(field.fieldId)) {
      return {
        fieldId: field.fieldId,
        disposition: 'exercised',
        checks: ['physician_designated_static_preserved'],
      };
    }
    const mapping = mappingById.get(field.fieldId);
    const coverage = mapping
      ? isExercised({ field, mapping, manifest: input.manifest })
      : { exercised: false, checks: [] };
    if (coverage.exercised) {
      return { fieldId: field.fieldId, disposition: 'exercised', checks: coverage.checks };
    }
    const material = field.clinicallyMaterial;
    const required = field.required || mapping?.required === true;
    if (required || material) {
      issues.push({
        fieldId: field.fieldId,
        code: required
          ? 'CERT_REQUIRED_FIELD_UNTESTED'
          : 'CERT_MATERIAL_FIELD_UNTESTED',
        message: required
          ? 'This required field must be exercised with synthetic evidence before certification.'
          : 'This clinically meaningful field must be exercised with synthetic evidence before certification.',
      });
      return { fieldId: field.fieldId, disposition: 'blocking', checks: [] };
    }
    const waiver = waiverByFieldId.get(field.fieldId);
    const waiverHasIssue = issues.some((issue) => issue.fieldId === field.fieldId);
    if (!waiver || waiverHasIssue) {
      if (!waiver) {
        issues.push({
          fieldId: field.fieldId,
          code: 'CERT_OPTIONAL_FIELD_NEEDS_WAIVER',
          message: 'Exercise this optional field or provide a physician waiver with a reason.',
        });
      }
      return { fieldId: field.fieldId, disposition: 'blocking', checks: [] };
    }
    return { fieldId: field.fieldId, disposition: 'waived', checks: ['physician_waiver'] };
  });

  return {
    version: TEMPLATE_TWIN_CERTIFICATION_COVERAGE_VERSION,
    ready: issues.length === 0,
    fields: results,
    issues,
  };
}
