import {
  RendererBindingSchema,
  TemplateOptionSchema,
  TemplateTwinFillManifestSchema,
  type FieldResolution,
  type TemplateTwinFillManifest,
  type TemplateTwinFieldKind,
} from '@/lib/template-twin/ir';
import type { TemplateTwinReviewStatus } from '@/lib/template-twin/client-types';

export interface TemplateTwinReviewRow {
  id: string;
  status: string;
  manifestVersion: number;
  manifestSha256: string;
  fillManifest: unknown;
  filledCount: number;
  needsReviewCount: number;
  notMentionedCount: number;
  conflictCount: number;
  criticalUnresolvedCount: number;
  roundTripVerified: boolean;
  roundTripVerification?: unknown;
  reviewedAt: Date | null;
  reviewedManifestVersion: number | null;
  reviewedManifestSha256: string | null;
  compiledVersion: {
    noteTemplate: { name: string };
    fields: Array<{
      id: string;
      fieldId: string;
      displayOrder: number;
      originalLabel: string;
      fieldKind: string;
      allowedOptions: unknown;
      rendererBinding: unknown;
      criticality: string;
      required: boolean;
    }>;
  };
}

export interface TemplateTwinReviewEvidence {
  factId: string;
  quote: string;
  audioTimestampSeconds: number | null;
  speaker: string | null;
  evidenceAnchorIds: string[];
}

export interface TemplateTwinReviewField {
  definitionId: string;
  fieldId: string;
  displayOrder: number;
  originalLabel: string;
  fieldKind: TemplateTwinFieldKind | 'unknown';
  criticality:
    | 'routine'
    | 'medication'
    | 'allergy'
    | 'number_unit'
    | 'laterality'
    | 'date_duration'
    | 'unknown';
  required: boolean;
  allowedOptions: Array<{
    ordinal: number;
    displayText: string;
    value: string;
  }>;
  rowPrototype: boolean;
  status: TemplateTwinReviewStatus;
  resolutionStatus: FieldResolution['status'] | 'missing';
  value: FieldResolution['value'];
  selectedOptionOrdinal: number | null;
  reasonCode: string;
  clinicianReviewed: boolean;
  evidence: TemplateTwinReviewEvidence[];
  validationIssues: Array<{
    code: string;
    severity: 'warning' | 'blocking';
    message: string;
  }>;
}

export interface TemplateTwinReviewData {
  fillManifestId: string;
  manifestVersion: number;
  manifestSha256: string;
  templateName: string;
  templateVersion: number | null;
  processingStatus: string;
  roundTripVerified: boolean;
  physicianReviewConfirmed: boolean;
  layoutWarningCodes: string[];
  dataIntegrityError: boolean;
  counts: {
    filled: number;
    needsReview: number;
    notMentioned: number;
    conflicts: number;
    criticalUnresolved: number;
  };
  fields: TemplateTwinReviewField[];
}

const FIELD_KINDS = new Set<TemplateTwinFieldKind>([
  'static',
  'narrative_text',
  'single_select',
  'multi_select',
  'checkbox',
  'date',
  'number',
  'measurement',
  'fixed_table',
  'repeating_table',
  'conditional_block',
  'unsupported',
]);

const CRITICALITIES = new Set<TemplateTwinReviewField['criticality']>([
  'routine',
  'medication',
  'allergy',
  'number_unit',
  'laterality',
  'date_duration',
]);

function reviewStatus(
  resolution: FieldResolution | undefined,
): TemplateTwinReviewStatus {
  switch (resolution?.status) {
    case 'supported':
    case 'explicitly_denied':
      return 'verified';
    case 'approved_practice_default':
      return 'practice_default';
    case 'not_mentioned':
      return 'not_mentioned';
    case 'conflict':
      return 'conflict';
    case 'ambiguous':
    case 'needs_clinician_input':
    default:
      return 'needs_review';
  }
}

function storedCounts(row: TemplateTwinReviewRow): TemplateTwinReviewData['counts'] {
  return {
    filled: Math.max(0, row.filledCount),
    needsReview: Math.max(0, row.needsReviewCount),
    notMentioned: Math.max(0, row.notMentionedCount),
    conflicts: Math.max(0, row.conflictCount),
    criticalUnresolved: Math.max(0, row.criticalUnresolvedCount),
  };
}

function invalidManifestReview(row: TemplateTwinReviewRow): TemplateTwinReviewData {
  return {
    fillManifestId: row.id,
    manifestVersion: row.manifestVersion,
    manifestSha256: row.manifestSha256,
    templateName: row.compiledVersion.noteTemplate.name,
    templateVersion: null,
    processingStatus: row.status.toLowerCase(),
    roundTripVerified: false,
    physicianReviewConfirmed: false,
    layoutWarningCodes: [],
    dataIntegrityError: true,
    counts: {
      ...storedCounts(row),
      needsReview: Math.max(1, row.needsReviewCount),
      criticalUnresolved: Math.max(1, row.criticalUnresolvedCount),
    },
    fields: [],
  };
}

/**
 * Converts the visit-scoped database row into the smallest client DTO needed
 * for physician review. Only the manifest's non-secret optimistic-lock hash is
 * exposed; storage keys, model payloads, and unrelated encounter data never
 * cross the RSC boundary.
 */
export function serializeTemplateTwinReview(
  row: TemplateTwinReviewRow | null,
): TemplateTwinReviewData | null {
  if (!row) return null;

  const parsed = TemplateTwinFillManifestSchema.safeParse(row.fillManifest);
  if (!parsed.success) return invalidManifestReview(row);

  const manifest: TemplateTwinFillManifest = parsed.data;
  const proof =
    row.roundTripVerification &&
    typeof row.roundTripVerification === 'object' &&
    !Array.isArray(row.roundTripVerification)
      ? (row.roundTripVerification as Record<string, unknown>)
      : null;
  const layoutWarningCodes = Array.isArray(proof?.warningCodes)
    ? proof.warningCodes.filter(
        (code): code is string =>
          code === 'LAYOUT_OVERFLOW_REVIEW_RECOMMENDED' ||
          code === 'REPEATING_TABLE_LAYOUT_REVIEW_RECOMMENDED',
      )
    : [];
  const resolutions = new Map(
    manifest.fields.map((resolution) => [resolution.fieldId, resolution]),
  );
  const facts = new Map(manifest.facts.map((fact) => [fact.factId, fact]));

  const definitionIds = new Set(
    row.compiledVersion.fields.map((definition) => definition.fieldId),
  );
  const resolvedIds = new Set(manifest.fields.map((resolution) => resolution.fieldId));
  if (
    definitionIds.size !== row.compiledVersion.fields.length ||
    resolvedIds.size !== manifest.fields.length ||
    definitionIds.size !== resolvedIds.size ||
    [...definitionIds].some((fieldId) => !resolvedIds.has(fieldId))
  ) {
    return invalidManifestReview(row);
  }

  const fields = row.compiledVersion.fields
    .map((definition): TemplateTwinReviewField => {
      const resolution = resolutions.get(definition.fieldId);
      const options = Array.isArray(definition.allowedOptions)
        ? definition.allowedOptions.flatMap((option) => {
            const parsedOption = TemplateOptionSchema.safeParse(option);
            return parsedOption.success ? [parsedOption.data] : [];
          })
        : [];
      const rendererBinding = RendererBindingSchema.safeParse(
        definition.rendererBinding,
      );

      const validationIssues = manifest.validation.issues
        .filter((issue) => issue.fieldId === definition.fieldId)
        .map(({ code, severity, message }) => ({ code, severity, message }));
      const missingEvidence = (resolution?.sourceFactIds ?? []).some(
        (factId) => !facts.has(factId),
      );
      if (missingEvidence) {
        validationIssues.push({
          code: 'evidence_fact_missing',
          severity: 'blocking',
          message: 'A referenced supporting evidence record is missing.',
        });
      }
      const baseStatus = reviewStatus(resolution);

      return {
        definitionId: definition.id,
        fieldId: definition.fieldId,
        displayOrder: definition.displayOrder,
        originalLabel: definition.originalLabel,
        fieldKind: FIELD_KINDS.has(definition.fieldKind as TemplateTwinFieldKind)
          ? (definition.fieldKind as TemplateTwinFieldKind)
          : 'unknown',
        criticality: CRITICALITIES.has(
          definition.criticality as TemplateTwinReviewField['criticality'],
        )
          ? (definition.criticality as TemplateTwinReviewField['criticality'])
          : 'unknown',
        required: definition.required,
        allowedOptions: options,
        rowPrototype:
          rendererBinding.success &&
          rendererBinding.data.repeatAncestorPath !== null,
        status:
          baseStatus === 'verified' && validationIssues.length > 0
            ? 'needs_review'
            : baseStatus,
        resolutionStatus: resolution?.status ?? 'missing',
        value: resolution?.value ?? null,
        selectedOptionOrdinal: resolution?.selectedOptionOrdinal ?? null,
        reasonCode: missingEvidence
          ? 'evidence_fact_missing'
          : (resolution?.reasonCode ?? 'resolution_missing'),
        clinicianReviewed: resolution?.clinicianReviewed ?? false,
        evidence: (resolution?.sourceFactIds ?? []).flatMap((factId) => {
          const fact = facts.get(factId);
          return fact
            ? [
                {
                  factId: fact.factId,
                  quote: fact.evidenceQuote,
                  audioTimestampSeconds: fact.audioTimestampSeconds,
                  speaker: fact.speaker,
                  evidenceAnchorIds: fact.evidenceAnchorIds,
                },
              ]
            : [];
        }),
        validationIssues,
      };
    })
    .sort((a, b) => a.displayOrder - b.displayOrder);

  const attention = fields.filter((field) =>
    field.status === 'needs_review' || field.status === 'conflict',
  );
  const counts: TemplateTwinReviewData['counts'] = {
    filled: fields.filter((field) => field.value !== null).length,
    needsReview: attention.length,
    notMentioned: fields.filter((field) => field.status === 'not_mentioned').length,
    conflicts: fields.filter((field) => field.status === 'conflict').length,
    criticalUnresolved: attention.filter(
      (field) => field.criticality !== 'routine' && field.criticality !== 'unknown',
    ).length,
  };

  return {
    fillManifestId: row.id,
    manifestVersion: row.manifestVersion,
    manifestSha256: row.manifestSha256,
    templateName: row.compiledVersion.noteTemplate.name,
    templateVersion: manifest.noteTemplateVersion,
    processingStatus: row.status.toLowerCase(),
    roundTripVerified: row.roundTripVerified,
    physicianReviewConfirmed:
      row.reviewedAt !== null &&
      row.reviewedManifestVersion === row.manifestVersion &&
      row.reviewedManifestSha256 === row.manifestSha256,
    layoutWarningCodes,
    dataIntegrityError: false,
    counts,
    fields,
  };
}
