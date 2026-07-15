'use client';

import { useRouter } from 'next/navigation';
import { type FormEvent, useMemo, useState } from 'react';
import {
  AlertTriangle,
  Check,
  Clock3,
  FileCheck2,
  ListFilter,
  PencilLine,
} from 'lucide-react';
import { toast } from 'sonner';

import type { TemplateTwinFieldCorrectionRequest } from '@/lib/template-twin/contracts';

import type {
  TemplateTwinReviewData,
  TemplateTwinReviewField,
} from './template-twin-review-data';

export interface TemplateTwinReviewProps {
  data: TemplateTwinReviewData;
  visitId: string;
  readonly?: boolean;
}

const ATTENTION_STATUSES = new Set<TemplateTwinReviewField['status']>([
  'needs_review',
  'conflict',
]);

const STATUS_COPY: Record<
  TemplateTwinReviewField['status'],
  { label: string; color: string; background: string; border: string }
> = {
  verified: {
    label: 'Verified',
    color: 'var(--color-linear-sage-bright)',
    background: 'color-mix(in srgb, var(--color-linear-sage) 10%, transparent)',
    border: 'color-mix(in srgb, var(--color-linear-sage) 30%, transparent)',
  },
  needs_review: {
    label: 'Needs review',
    color: 'var(--color-linear-amber)',
    background: 'color-mix(in srgb, var(--color-linear-amber) 9%, transparent)',
    border: 'color-mix(in srgb, var(--color-linear-amber) 32%, transparent)',
  },
  not_mentioned: {
    label: 'Not mentioned',
    color: 'var(--color-linear-text-3)',
    background: 'var(--color-linear-surface-2)',
    border: 'var(--color-linear-border)',
  },
  conflict: {
    label: 'Conflict',
    color: 'var(--color-linear-danger)',
    background: 'color-mix(in srgb, var(--color-linear-danger) 9%, transparent)',
    border: 'color-mix(in srgb, var(--color-linear-danger) 32%, transparent)',
  },
  practice_default: {
    label: 'Practice default',
    color: 'var(--color-linear-text-2)',
    background: 'var(--color-linear-surface-2)',
    border: 'var(--color-linear-border)',
  },
};

const REASON_COPY: Record<string, string> = {
  approved_practice_default: 'Uses the physician-approved practice default.',
  fact_not_mentioned: 'This field was not stated in the encounter.',
  required_fact_not_mentioned: 'This required field was not stated in the encounter.',
  semantic_mapping_missing: 'This field does not have an approved clinical mapping.',
  semantic_mapping_type_mismatch: 'The mapped value type does not match this Word field.',
  field_or_mapping_not_certified: 'The field or its mapping is not certified.',
  field_or_mapping_unsupported: 'This field cannot be populated safely by this compiler version.',
  clinical_concept_unmapped: 'No approved clinical concept is mapped to this field.',
  temporality_not_approved: 'The evidence refers to a different time period than this field allows.',
  experiencer_not_approved: 'The evidence may refer to someone other than the patient.',
  source_evidence_conflict: 'The encounter contains conflicting evidence for this field.',
  source_evidence_needs_review: 'The supporting evidence or transcription is unclear.',
  select_value_not_exact_option: 'The evidence did not match one exact approved dropdown option.',
  multi_select_value_not_exact_option:
    'At least one value did not match an exact approved option.',
  checkbox_polarity_unresolved: 'The encounter did not clearly support checking or clearing this box.',
  measurement_unit_missing: 'A number was stated without the required unit.',
  required_laterality_missing: 'The required side was not stated clearly.',
  evidence_fact_missing:
    'A referenced encounter-evidence record is missing. This value cannot be verified.',
  resolution_missing: 'No field resolution was recorded. Signing must remain blocked.',
};

function sentenceFromCode(code: string): string {
  const known = REASON_COPY[code];
  if (known) return known;
  const text = code.replaceAll('_', ' ').trim();
  if (!text) return 'This field needs clinician review.';
  return `${text[0].toUpperCase()}${text.slice(1)}.`;
}

function fieldTypeLabel(kind: TemplateTwinReviewField['fieldKind']): string {
  const labels: Record<TemplateTwinReviewField['fieldKind'], string> = {
    static: 'Fixed content',
    narrative_text: 'Text',
    single_select: 'Dropdown',
    multi_select: 'Multi-select',
    checkbox: 'Checkbox',
    date: 'Date',
    number: 'Number',
    measurement: 'Measurement',
    fixed_table: 'Table',
    repeating_table: 'Repeating table',
    conditional_block: 'Conditional section',
    unsupported: 'Unsupported',
    unknown: 'Unknown field',
  };
  return labels[kind];
}

function criticalityLabel(
  criticality: TemplateTwinReviewField['criticality'],
): string | null {
  const labels: Partial<Record<TemplateTwinReviewField['criticality'], string>> = {
    medication: 'Medication',
    allergy: 'Allergy',
    number_unit: 'Number + unit',
    laterality: 'Laterality',
    date_duration: 'Date / duration',
  };
  return labels[criticality] ?? null;
}

function fieldPriority(field: TemplateTwinReviewField): number {
  let score = 0;
  if (field.status === 'conflict') score += 100;
  else if (field.status === 'needs_review') score += 80;
  if (field.criticality === 'medication' || field.criticality === 'allergy') score += 30;
  else if (field.criticality !== 'routine' && field.criticality !== 'unknown') score += 20;
  if (field.required) score += 5;
  return score;
}

function formatTimestamp(seconds: number): string {
  const whole = Math.max(0, Math.floor(seconds));
  const hours = Math.floor(whole / 3600);
  const minutes = Math.floor((whole % 3600) / 60);
  const remainder = whole % 60;
  return hours > 0
    ? `${hours}:${String(minutes).padStart(2, '0')}:${String(remainder).padStart(2, '0')}`
    : `${minutes}:${String(remainder).padStart(2, '0')}`;
}

function compactValue(field: TemplateTwinReviewField): string {
  const value = field.value;
  if (value === null) return 'Blank';
  if (typeof value === 'boolean') return value ? 'Checked' : 'Not checked';
  if (Array.isArray(value)) {
    if (value.length === 0) return 'Blank';
    if (typeof value[0] === 'string') return (value as string[]).join(', ');
    return `${value.length} ${value.length === 1 ? 'row' : 'rows'}`;
  }
  return String(value);
}

function DetailedValue({ field }: { field: TemplateTwinReviewField }) {
  const value = field.value;
  if (!Array.isArray(value) || value.length === 0 || typeof value[0] === 'string') {
    return (
      <p className="mt-2 whitespace-pre-wrap break-words text-[15px] font-medium leading-6 text-linear-text">
        {compactValue(field)}
      </p>
    );
  }

  return (
    <div className="mt-3 overflow-x-auto rounded-lg border border-linear-border">
      <table className="w-full border-collapse text-left text-[12px]">
        <tbody>
          {(value as Array<Record<string, string | null>>).map((row, rowIndex) => {
            const visible = Object.entries(row).filter(
              ([key]) =>
                key !== 'sourceFactId' &&
                key !== 'evidenceAnchorId' &&
                key !== 'optionOrdinal',
            );
            return (
              <tr key={rowIndex} className="border-b border-linear-hairline last:border-b-0">
                <th className="w-14 bg-linear-surface-2 px-3 py-2 font-mono font-medium text-linear-text-3">
                  {rowIndex + 1}
                </th>
                <td className="px-3 py-2 text-linear-text-2">
                  {visible.length > 0
                    ? visible.map(([key, cell]) => `${key}: ${cell ?? 'Blank'}`).join(' · ')
                    : 'Blank row'}
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}

function StatusPill({ status }: { status: TemplateTwinReviewField['status'] }) {
  const tone = STATUS_COPY[status];
  return (
    <span
      className="inline-flex min-h-6 items-center rounded-full border px-2 font-mono text-[10px] font-medium uppercase tracking-[0.06em]"
      style={{ color: tone.color, background: tone.background, borderColor: tone.border }}
    >
      {tone.label}
    </span>
  );
}

export function TemplateTwinReview({
  data,
  visitId,
  readonly = false,
}: TemplateTwinReviewProps) {
  const router = useRouter();
  const [onlyAttention, setOnlyAttention] = useState(false);
  const [reviewPending, setReviewPending] = useState(false);
  const [reviewError, setReviewError] = useState<string | null>(null);
  const [selectedFieldId, setSelectedFieldId] = useState<string | null>(
    data.fields.find((field) => ATTENTION_STATUSES.has(field.status))?.fieldId ??
      data.fields[0]?.fieldId ??
      null,
  );

  const orderedFields = useMemo(
    () =>
      [...data.fields].sort(
        (a, b) => fieldPriority(b) - fieldPriority(a) || a.displayOrder - b.displayOrder,
      ),
    [data.fields],
  );
  const visibleFields = onlyAttention
    ? orderedFields.filter((field) => ATTENTION_STATUSES.has(field.status))
    : orderedFields;
  const selected =
    visibleFields.find((field) => field.fieldId === selectedFieldId) ??
    visibleFields[0] ??
    null;
  const attentionCount = data.counts.needsReview;
  const canConfirmWholeReview =
    !readonly &&
    data.processingStatus.toLowerCase() !== 'signed' &&
    !data.dataIntegrityError &&
    data.roundTripVerified &&
    data.counts.needsReview === 0 &&
    data.counts.conflicts === 0 &&
    data.counts.criticalUnresolved === 0;

  async function confirmWholeReview() {
    setReviewPending(true);
    setReviewError(null);
    try {
      const response = await fetch(
        `/api/visits/${encodeURIComponent(visitId)}/template-twin/review`,
        {
          method: 'POST',
          credentials: 'same-origin',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            expectedManifestVersion: data.manifestVersion,
            expectedManifestSha256: data.manifestSha256,
          }),
        },
      );
      const body = (await response.json().catch(() => null)) as
        | { ok?: boolean; error?: string }
        | null;
      if (!response.ok || !body?.ok) {
        throw new Error(body?.error ?? 'The review confirmation could not be saved.');
      }
      toast.success('Original Template DOCX review confirmed');
      router.refresh();
    } catch (caught) {
      setReviewError(
        caught instanceof Error
          ? caught.message
          : 'The review confirmation could not be saved.',
      );
    } finally {
      setReviewPending(false);
    }
  }

  return (
    <section aria-labelledby="template-twin-review-title" className="space-y-5">
      <header className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <div className="flex items-center gap-2">
            <FileCheck2 className="h-4 w-4 text-linear-sage-bright" aria-hidden />
            <h2
              id="template-twin-review-title"
              className="text-[16px] font-semibold tracking-[-0.01em] text-linear-text"
            >
              Original Template DOCX
            </h2>
          </div>
          <p className="mt-1 text-[12.5px] leading-5 text-linear-text-3">
            {data.templateName}
            {data.templateVersion !== null ? ` · version ${data.templateVersion}` : ''}
            {' · '}review every populated value against its encounter evidence
          </p>
        </div>
        <span className="font-mono text-[10px] uppercase tracking-[0.07em] text-linear-text-3">
          {data.roundTripVerified ? 'DOCX verified' : 'DOCX verification pending'}
        </span>
      </header>

      {data.layoutWarningCodes.length > 0 && (
        <div
          role="alert"
          className="flex gap-3 rounded-lg border border-linear-warning/30 bg-linear-warning/5 px-4 py-3 text-[13px] leading-5 text-linear-text-2"
        >
          <AlertTriangle className="mt-0.5 h-4 w-4 flex-none text-linear-warning" aria-hidden />
          <p>
            Word layout review is required for unusually long populated text or repeated table rows. Inspect pagination, row styles, and spacing in the downloaded DOCX before signing.
          </p>
        </div>
      )}

      {data.dataIntegrityError ? (
        <div
          role="alert"
          className="flex gap-3 rounded-lg border px-4 py-3 text-[13px] leading-5"
          style={{
            borderColor: 'color-mix(in srgb, var(--color-linear-danger) 35%, transparent)',
            background: 'color-mix(in srgb, var(--color-linear-danger) 8%, transparent)',
            color: 'var(--color-linear-danger)',
          }}
        >
          <AlertTriangle className="mt-0.5 h-4 w-4 flex-none" aria-hidden />
          <p>
            The field manifest could not be verified. No field values are shown, and this
            visit must not be signed until the manifest is regenerated.
          </p>
        </div>
      ) : data.counts.criticalUnresolved > 0 ? (
        <div
          role="status"
          className="flex gap-3 rounded-lg border px-4 py-3 text-[13px] leading-5"
          style={{
            borderColor: 'color-mix(in srgb, var(--color-linear-danger) 35%, transparent)',
            background: 'color-mix(in srgb, var(--color-linear-danger) 8%, transparent)',
            color: 'var(--color-linear-danger)',
          }}
        >
          <AlertTriangle className="mt-0.5 h-4 w-4 flex-none" aria-hidden />
          <p>
            {data.counts.criticalUnresolved}{' '}
            {data.counts.criticalUnresolved === 1 ? 'critical field requires' : 'critical fields require'}{' '}
            clinician review before signing.
          </p>
        </div>
      ) : null}

      <dl className="grid grid-cols-2 border-y border-linear-hairline lg:grid-cols-4">
        {[
          { label: 'Fields filled', value: data.counts.filled, tone: 'text-linear-sage-bright' },
          { label: 'Need review', value: data.counts.needsReview, tone: 'text-linear-amber' },
          { label: 'Not mentioned', value: data.counts.notMentioned, tone: 'text-linear-text-2' },
          { label: 'Conflicts', value: data.counts.conflicts, tone: 'text-linear-danger' },
        ].map((item, index) => (
          <div
            key={item.label}
            className={`px-3 py-3 ${index % 2 === 0 ? '' : 'border-l border-linear-hairline'} ${index === 2 ? 'border-t border-linear-hairline lg:border-l lg:border-t-0' : ''} ${index === 3 ? 'border-t border-linear-hairline lg:border-t-0' : ''}`}
          >
            <dt className="font-mono text-[9.5px] uppercase tracking-[0.08em] text-linear-text-3">
              {item.label}
            </dt>
            <dd className={`mt-1 text-[20px] font-semibold tabular-nums ${item.tone}`}>
              {item.value}
            </dd>
          </div>
        ))}
      </dl>

      {!readonly && !data.physicianReviewConfirmed && (
        <div className="rounded-lg border border-linear-border bg-linear-surface-1 px-4 py-4">
          <p className="text-[13px] font-medium text-linear-text">
            Whole-document physician review required
          </p>
          <p className="mt-1 text-[12px] leading-5 text-linear-text-3">
            Confirm only after reviewing every populated value, blank field, allowed option,
            and supporting encounter quote in this generated document.
          </p>
          {canConfirmWholeReview ? (
            <button
              type="button"
              disabled={reviewPending}
              onClick={confirmWholeReview}
              className="qm-tap-44 mt-3 inline-flex items-center gap-2 rounded-lg bg-linear-sage px-3 py-2 text-[12.5px] font-semibold text-white disabled:cursor-not-allowed disabled:opacity-60 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2"
            >
              <FileCheck2 className="h-4 w-4" aria-hidden />
              {reviewPending ? 'Saving confirmation…' : 'I reviewed every Template Twin field'}
            </button>
          ) : (
            <p className="mt-3 text-[12px] font-medium text-linear-amber">
              Resolve every item needing attention and regenerate the DOCX before confirming.
            </p>
          )}
          {reviewError && (
            <p role="alert" className="mt-2 text-[12px] text-linear-danger">
              {reviewError}
            </p>
          )}
        </div>
      )}

      {data.physicianReviewConfirmed && (
        <p className="inline-flex items-center gap-2 text-[12px] font-medium text-linear-sage-bright">
          <Check className="h-4 w-4" aria-hidden />
          Physician review confirmed for this exact generated document
        </p>
      )}

      {!data.dataIntegrityError && (
        <div className="overflow-hidden rounded-xl border border-linear-border bg-linear-surface-1 lg:grid lg:min-h-[440px] lg:grid-cols-[minmax(260px,0.78fr)_minmax(0,1.22fr)]">
          <div className="border-b border-linear-border lg:border-b-0 lg:border-r">
            <div className="flex min-h-14 flex-wrap items-center justify-between gap-2 border-b border-linear-hairline px-3 py-2">
              <span className="font-mono text-[10px] uppercase tracking-[0.08em] text-linear-text-3">
                {visibleFields.length} {visibleFields.length === 1 ? 'field' : 'fields'}
              </span>
              <label className="qm-tap-44 inline-flex cursor-pointer items-center gap-2 text-[12px] text-linear-text-2">
                <input
                  type="checkbox"
                  checked={onlyAttention}
                  onChange={(event) => setOnlyAttention(event.target.checked)}
                  className="h-4 w-4 accent-[var(--color-linear-sage)] focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2"
                />
                <ListFilter className="h-3.5 w-3.5" aria-hidden />
                Needs attention{attentionCount > 0 ? ` (${attentionCount})` : ''}
              </label>
            </div>

            <ul className="max-h-[520px] overflow-y-auto" aria-label="Template fields">
              {visibleFields.length === 0 ? (
                <li className="px-5 py-10 text-center text-[13px] leading-5 text-linear-text-3">
                  No fields need attention.
                </li>
              ) : (
                visibleFields.map((field) => {
                  const active = selected?.fieldId === field.fieldId;
                  const priority = criticalityLabel(field.criticality);
                  return (
                    <li key={field.fieldId} className="border-b border-linear-hairline last:border-b-0">
                      <button
                        type="button"
                        aria-current={active ? 'true' : undefined}
                        onClick={() => setSelectedFieldId(field.fieldId)}
                        className="qm-tap-44 w-full px-4 py-3 text-left transition-colors hover:bg-linear-row-hover focus-visible:z-10 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-[-2px]"
                        style={
                          active
                            ? { background: 'var(--color-linear-surface-2)' }
                            : undefined
                        }
                      >
                        <div className="flex items-start justify-between gap-3">
                          <span className="min-w-0 truncate text-[13px] font-medium text-linear-text">
                            {field.originalLabel}
                          </span>
                          <StatusPill status={field.status} />
                        </div>
                        <div className="mt-1.5 flex min-w-0 items-center gap-2 text-[11px] text-linear-text-3">
                          {priority && (
                            <span className="font-medium text-linear-text-2">{priority}</span>
                          )}
                          <span className="truncate">{compactValue(field)}</span>
                        </div>
                      </button>
                    </li>
                  );
                })
              )}
            </ul>
          </div>

          <div className="min-w-0 p-5 sm:p-6" aria-live="polite">
            {selected ? (
              <FieldDetail
                field={selected}
                visitId={visitId}
                manifestVersion={data.manifestVersion}
                canCorrect={
                  !readonly && data.processingStatus.toLowerCase() !== 'signed'
                }
              />
            ) : (
              <div className="flex min-h-64 items-center justify-center text-[13px] text-linear-text-3">
                Select a field to inspect its evidence.
              </div>
            )}
          </div>
        </div>
      )}
    </section>
  );
}

function FieldDetail({
  field,
  visitId,
  manifestVersion,
  canCorrect,
}: {
  field: TemplateTwinReviewField;
  visitId: string;
  manifestVersion: number;
  canCorrect: boolean;
}) {
  const tone = STATUS_COPY[field.status];
  const priority = criticalityLabel(field.criticality);
  const selectedOption = field.allowedOptions.find(
    (option) => option.ordinal === field.selectedOptionOrdinal,
  );
  const hasReviewReason = ATTENTION_STATUSES.has(field.status) || field.validationIssues.length > 0;

  return (
    <article aria-labelledby={`template-twin-field-${field.fieldId}`}>
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div className="min-w-0">
          <p className="font-mono text-[9.5px] uppercase tracking-[0.08em] text-linear-text-3">
            {fieldTypeLabel(field.fieldKind)}
            {field.required ? ' · required' : ''}
          </p>
          <h3
            id={`template-twin-field-${field.fieldId}`}
            className="mt-1 text-balance text-[18px] font-semibold tracking-[-0.015em] text-linear-text"
          >
            {field.originalLabel}
          </h3>
        </div>
        <StatusPill status={field.status} />
      </div>

      {priority && (
        <div className="mt-3 inline-flex items-center gap-1.5 text-[11px] font-medium text-linear-text-2">
          <AlertTriangle className="h-3.5 w-3.5 text-linear-amber" aria-hidden />
          Clinical priority: {priority}
        </div>
      )}

      <div className="mt-6 border-t border-linear-hairline pt-4">
        <p className="font-mono text-[9.5px] uppercase tracking-[0.08em] text-linear-text-3">
          Filled value
        </p>
        <DetailedValue field={field} />
      </div>

      {field.allowedOptions.length > 0 && (
        <div className="mt-6 border-t border-linear-hairline pt-4">
          <p className="font-mono text-[9.5px] uppercase tracking-[0.08em] text-linear-text-3">
            {selectedOption ? 'Selected dropdown option' : 'Allowed dropdown options'}
          </p>
          {selectedOption && (
            <p className="mt-2 flex items-center gap-2 text-[14px] font-medium text-linear-text">
              <Check className="h-4 w-4 text-linear-sage-bright" aria-hidden />
              {selectedOption.displayText}
            </p>
          )}
          <ol className="mt-3 flex flex-wrap gap-2" aria-label="Allowed options">
            {field.allowedOptions.map((option) => {
              const chosen = option.ordinal === field.selectedOptionOrdinal;
              return (
                <li
                  key={`${option.ordinal}-${option.value}`}
                  className="rounded-md border px-2.5 py-1.5 text-[11.5px]"
                  style={{
                    borderColor: chosen
                      ? 'color-mix(in srgb, var(--color-linear-sage) 35%, transparent)'
                      : 'var(--color-linear-border)',
                    background: chosen
                      ? 'color-mix(in srgb, var(--color-linear-sage) 9%, transparent)'
                      : 'transparent',
                    color: chosen
                      ? 'var(--color-linear-sage-bright)'
                      : 'var(--color-linear-text-2)',
                  }}
                >
                  {option.displayText}
                  {chosen ? ' · selected' : ''}
                </li>
              );
            })}
          </ol>
        </div>
      )}

      <div className="mt-6 border-t border-linear-hairline pt-4">
        <p className="font-mono text-[9.5px] uppercase tracking-[0.08em] text-linear-text-3">
          Supporting encounter evidence
        </p>
        {field.evidence.length === 0 ? (
          <p className="mt-2 text-[13px] leading-5 text-linear-text-3">
            No supporting encounter evidence is attached to this value.
          </p>
        ) : (
          <div className="mt-3 space-y-3">
            {field.evidence.map((evidence) => (
              <figure
                key={evidence.factId}
                className="border-l-2 pl-4"
                style={{ borderColor: tone.border }}
              >
                <blockquote className="text-pretty text-[13px] leading-5 text-linear-text-2">
                  “{evidence.quote}”
                </blockquote>
                {(evidence.audioTimestampSeconds !== null || evidence.speaker) && (
                  <figcaption className="mt-2 flex flex-wrap items-center gap-x-3 gap-y-1 font-mono text-[10px] text-linear-text-3">
                    {evidence.audioTimestampSeconds !== null && (
                      <span className="inline-flex items-center gap-1">
                        <Clock3 className="h-3 w-3" aria-hidden />
                        Audio {formatTimestamp(evidence.audioTimestampSeconds)}
                      </span>
                    )}
                    {evidence.speaker && <span>{evidence.speaker}</span>}
                  </figcaption>
                )}
              </figure>
            ))}
          </div>
        )}
      </div>

      {hasReviewReason && (
        <div
          className="mt-6 rounded-lg border px-4 py-3"
          style={{ borderColor: tone.border, background: tone.background }}
        >
          <p className="font-mono text-[9.5px] uppercase tracking-[0.08em]" style={{ color: tone.color }}>
            Why this needs review
          </p>
          <p className="mt-1.5 text-[12.5px] leading-5 text-linear-text-2">
            {sentenceFromCode(field.reasonCode)}
          </p>
          {field.validationIssues.length > 0 && (
            <ul className="mt-2 space-y-1 text-[12px] leading-5 text-linear-text-2">
              {field.validationIssues.map((issue) => (
                <li key={`${issue.code}-${issue.message}`}>• {issue.message}</li>
              ))}
            </ul>
          )}
        </div>
      )}

      {canCorrect && (
        <FieldCorrectionForm
          key={`${field.fieldId}:${manifestVersion}`}
          field={field}
          visitId={visitId}
          manifestVersion={manifestVersion}
        />
      )}
    </article>
  );
}

const EDITABLE_FIELD_KINDS = new Set<TemplateTwinReviewField['fieldKind']>([
  'narrative_text',
  'single_select',
  'multi_select',
  'checkbox',
  'date',
  'number',
  'measurement',
]);

function correctionReason(
  field: TemplateTwinReviewField,
): TemplateTwinFieldCorrectionRequest['reasonCode'] {
  if (field.criticality === 'medication') return 'corrected_medication';
  if (field.criticality === 'allergy') return 'corrected_allergy';
  if (field.criticality === 'laterality') return 'corrected_laterality';
  if (field.fieldKind === 'checkbox') return 'clarified_checkbox';
  if (field.fieldKind === 'number' || field.fieldKind === 'measurement') {
    return 'clarified_number_or_unit';
  }
  if (field.fieldKind === 'single_select' || field.fieldKind === 'multi_select') {
    return 'selected_exact_option';
  }
  return 'physician_review_correction';
}

function initialTextValue(field: TemplateTwinReviewField): string {
  if (field.rowPrototype && Array.isArray(field.value)) {
    return field.value
      .flatMap((row) => {
        if (typeof row !== 'object' || row === null || Array.isArray(row)) return [];
        const value = row.value;
        return typeof value === 'string' ? [value] : [];
      })
      .join('\n');
  }
  return typeof field.value === 'string' || typeof field.value === 'number'
    ? String(field.value)
    : '';
}

function initialMultiValue(field: TemplateTwinReviewField): string[] {
  return Array.isArray(field.value) &&
    field.value.every((value) => typeof value === 'string')
    ? [...field.value]
    : [];
}

function repeatingHint(field: TemplateTwinReviewField): string {
  if (field.fieldKind === 'checkbox') return 'Use true or false on each line.';
  if (field.fieldKind === 'date') return 'Use YYYY-MM-DD on each line.';
  if (field.fieldKind === 'number') return 'Use one finite number per line.';
  if (field.fieldKind === 'measurement') {
    return 'Use one number with its stated unit per line, for example 12 mg.';
  }
  if (field.fieldKind === 'single_select' || field.fieldKind === 'multi_select') {
    return 'Use one exact allowed option per line.';
  }
  return 'Use one table-row value per line.';
}

interface CorrectionRouteResponse {
  ok?: boolean;
  error?: string;
  result?: {
    certificationUrl?: string | null;
  };
}

function FieldCorrectionForm({
  field,
  visitId,
  manifestVersion,
}: {
  field: TemplateTwinReviewField;
  visitId: string;
  manifestVersion: number;
}) {
  const router = useRouter();
  const [editing, setEditing] = useState(false);
  const [pending, setPending] = useState(false);
  const [clearField, setClearField] = useState(false);
  const [createMappingRule, setCreateMappingRule] = useState(false);
  const [textValue, setTextValue] = useState(() => initialTextValue(field));
  const [checkboxValue, setCheckboxValue] = useState<'' | 'true' | 'false'>(() =>
    typeof field.value === 'boolean' ? String(field.value) as 'true' | 'false' : '',
  );
  const [multiValue, setMultiValue] = useState<string[]>(() =>
    initialMultiValue(field),
  );
  const [error, setError] = useState<string | null>(null);
  const [certificationUrl, setCertificationUrl] = useState<string | null>(null);
  const editable = EDITABLE_FIELD_KINDS.has(field.fieldKind);

  if (!editable) return null;

  function correctionValue(): TemplateTwinFieldCorrectionRequest['value'] {
    if (clearField) return null;
    if (field.rowPrototype) {
      const rows = textValue
        .split(/\r?\n/)
        .map((value) => value.trim())
        .filter(Boolean);
      if (rows.length === 0) {
        throw new Error('Enter at least one repeating-row value or clear the field.');
      }
      return rows.map((value) => ({ value }));
    }
    if (field.fieldKind === 'checkbox') {
      if (checkboxValue === '') {
        throw new Error('Choose checked or not checked.');
      }
      return checkboxValue === 'true';
    }
    if (field.fieldKind === 'multi_select') {
      if (multiValue.length === 0) {
        throw new Error('Choose at least one exact allowed option.');
      }
      return multiValue;
    }
    const trimmed = textValue.trim();
    if (!trimmed) throw new Error('Enter a value or clear the field.');
    if (field.fieldKind === 'number') {
      if (!/^[+-]?(?:\d+(?:\.\d+)?|\.\d+)$/.test(trimmed)) {
        throw new Error('Enter a finite number without a unit.');
      }
      const value = Number(trimmed);
      if (!Number.isFinite(value)) throw new Error('Enter a finite number.');
      return value;
    }
    if (
      field.fieldKind === 'date' &&
      !/^\d{4}-\d{2}-\d{2}$/.test(trimmed)
    ) {
      throw new Error('Enter a date in YYYY-MM-DD format.');
    }
    return trimmed;
  }

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError(null);
    let value: TemplateTwinFieldCorrectionRequest['value'];
    try {
      value = correctionValue();
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : 'Check the corrected value.');
      return;
    }

    setPending(true);
    try {
      const response = await fetch(
        `/api/visits/${encodeURIComponent(visitId)}/template-twin/corrections`,
        {
          method: 'PATCH',
          credentials: 'same-origin',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            expectedManifestVersion: manifestVersion,
            fieldId: field.fieldId,
            value,
            sourceFactIds: [...new Set(field.evidence.map((item) => item.factId))],
            reasonCode: correctionReason(field),
            createMappingRule,
          } satisfies TemplateTwinFieldCorrectionRequest),
        },
      );
      const body = (await response.json().catch(() => null)) as
        | CorrectionRouteResponse
        | null;
      if (!response.ok || !body?.ok) {
        throw new Error(body?.error ?? 'The correction could not be verified.');
      }
      const draftUrl = body.result?.certificationUrl ?? null;
      setCertificationUrl(draftUrl);
      setEditing(false);
      toast.success('Template field correction verified');
      if (draftUrl) router.push(draftUrl);
      else router.refresh();
    } catch (caught) {
      setError(
        caught instanceof Error
          ? caught.message
          : 'The correction could not be verified.',
      );
    } finally {
      setPending(false);
    }
  }

  if (!editing) {
    return (
      <div className="mt-6 border-t border-linear-hairline pt-4">
        <button
          type="button"
          onClick={() => setEditing(true)}
          className="qm-tap-44 inline-flex items-center gap-2 rounded-lg border border-linear-border px-3 py-2 text-[12.5px] font-medium text-linear-text transition-colors hover:bg-linear-row-hover focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2"
        >
          <PencilLine className="h-3.5 w-3.5" aria-hidden />
          Correct this field
        </button>
        {certificationUrl && (
          <p className="mt-3 text-[12px] leading-5 text-linear-text-2">
            A new uncertified mapping-rule draft was created.{' '}
            <a
              href={certificationUrl}
              className="font-medium text-linear-sage-bright underline underline-offset-2"
            >
              Review and certify the draft
            </a>
          </p>
        )}
      </div>
    );
  }

  const controlId = `template-twin-correction-${field.fieldId}`;
  return (
    <form
      onSubmit={submit}
      className="mt-6 space-y-4 border-t border-linear-hairline pt-4"
      aria-label={`Correct ${field.originalLabel}`}
    >
      <div>
        <p className="font-mono text-[9.5px] uppercase tracking-[0.08em] text-linear-text-3">
          Physician correction
        </p>
        <p className="mt-1 text-[12px] leading-5 text-linear-text-3">
          This creates a labeled review delta and re-verifies the original DOCX.
        </p>
      </div>

      {!clearField && field.rowPrototype ? (
        <div>
          <label htmlFor={controlId} className="text-[12px] font-medium text-linear-text-2">
            Repeating table row values
          </label>
          <textarea
            id={controlId}
            value={textValue}
            onChange={(event) => setTextValue(event.target.value)}
            rows={5}
            className="mt-1.5 w-full rounded-lg border border-linear-border bg-linear-surface-0 px-3 py-2 font-mono text-[12px] leading-5 text-linear-text outline-none focus:border-linear-sage"
          />
          <p className="mt-1 text-[11px] leading-4 text-linear-text-3">
            {repeatingHint(field)}
          </p>
          {field.allowedOptions.length > 0 && (
            <p className="mt-1 text-[11px] leading-4 text-linear-text-3">
              Exact options: {field.allowedOptions.map((option) => option.displayText).join(' · ')}
            </p>
          )}
        </div>
      ) : !clearField && field.fieldKind === 'single_select' ? (
        <div>
          <label htmlFor={controlId} className="text-[12px] font-medium text-linear-text-2">
            Exact dropdown option
          </label>
          <select
            id={controlId}
            value={textValue}
            onChange={(event) => setTextValue(event.target.value)}
            className="mt-1.5 min-h-11 w-full rounded-lg border border-linear-border bg-linear-surface-0 px-3 text-[13px] text-linear-text outline-none focus:border-linear-sage"
          >
            <option value="">Choose an option</option>
            {field.allowedOptions.map((option) => (
              <option key={`${option.ordinal}-${option.value}`} value={option.value}>
                {option.displayText}
              </option>
            ))}
          </select>
        </div>
      ) : !clearField && field.fieldKind === 'multi_select' ? (
        <fieldset>
          <legend className="text-[12px] font-medium text-linear-text-2">
            Exact allowed options
          </legend>
          <div className="mt-2 grid gap-2 sm:grid-cols-2">
            {field.allowedOptions.map((option) => (
              <label
                key={`${option.ordinal}-${option.value}`}
                className="qm-tap-44 flex items-center gap-2 rounded-lg border border-linear-border px-3 py-2 text-[12px] text-linear-text-2"
              >
                <input
                  type="checkbox"
                  checked={multiValue.includes(option.value)}
                  onChange={(event) =>
                    setMultiValue((current) =>
                      event.target.checked
                        ? [...current, option.value]
                        : current.filter((value) => value !== option.value),
                    )
                  }
                  className="h-4 w-4 accent-[var(--color-linear-sage)]"
                />
                {option.displayText}
              </label>
            ))}
          </div>
        </fieldset>
      ) : !clearField && field.fieldKind === 'checkbox' ? (
        <div>
          <label htmlFor={controlId} className="text-[12px] font-medium text-linear-text-2">
            Checkbox state
          </label>
          <select
            id={controlId}
            value={checkboxValue}
            onChange={(event) =>
              setCheckboxValue(event.target.value as '' | 'true' | 'false')
            }
            className="mt-1.5 min-h-11 w-full rounded-lg border border-linear-border bg-linear-surface-0 px-3 text-[13px] text-linear-text outline-none focus:border-linear-sage"
          >
            <option value="">Choose a state</option>
            <option value="true">Checked</option>
            <option value="false">Not checked</option>
          </select>
        </div>
      ) : !clearField ? (
        <div>
          <label htmlFor={controlId} className="text-[12px] font-medium text-linear-text-2">
            {field.fieldKind === 'measurement'
              ? 'Number and stated unit'
              : field.fieldKind === 'number'
                ? 'Finite number'
                : field.fieldKind === 'date'
                  ? 'Date'
                  : 'Corrected value'}
          </label>
          {field.fieldKind === 'narrative_text' ? (
            <textarea
              id={controlId}
              value={textValue}
              onChange={(event) => setTextValue(event.target.value)}
              rows={4}
              className="mt-1.5 w-full rounded-lg border border-linear-border bg-linear-surface-0 px-3 py-2 text-[13px] leading-5 text-linear-text outline-none focus:border-linear-sage"
            />
          ) : (
            <input
              id={controlId}
              type={field.fieldKind === 'date' ? 'date' : 'text'}
              inputMode={field.fieldKind === 'number' ? 'decimal' : undefined}
              value={textValue}
              onChange={(event) => setTextValue(event.target.value)}
              placeholder={field.fieldKind === 'measurement' ? 'For example: 12 mg' : undefined}
              className="mt-1.5 min-h-11 w-full rounded-lg border border-linear-border bg-linear-surface-0 px-3 text-[13px] text-linear-text outline-none focus:border-linear-sage"
            />
          )}
        </div>
      ) : null}

      <label className="qm-tap-44 flex items-start gap-2 text-[12px] leading-5 text-linear-text-2">
        <input
          type="checkbox"
          checked={clearField}
          onChange={(event) => setClearField(event.target.checked)}
          className="mt-1 h-4 w-4 accent-[var(--color-linear-sage)]"
        />
        Leave this field blank. Required fields will remain blocked for review.
      </label>
      <label className="qm-tap-44 flex items-start gap-2 text-[12px] leading-5 text-linear-text-2">
        <input
          type="checkbox"
          checked={createMappingRule}
          onChange={(event) => setCreateMappingRule(event.target.checked)}
          className="mt-1 h-4 w-4 accent-[var(--color-linear-sage)]"
        />
        Create an uncertified mapping-rule draft from this correction. The active template will not change.
      </label>

      {error && (
        <p role="alert" className="text-[12px] leading-5 text-linear-danger">
          {error}
        </p>
      )}

      <div className="flex flex-wrap gap-2">
        <button
          type="submit"
          disabled={pending}
          className="qm-tap-44 rounded-lg bg-linear-sage px-4 py-2 text-[12.5px] font-semibold text-white disabled:cursor-not-allowed disabled:opacity-60"
        >
          {pending ? 'Verifying…' : 'Save and verify correction'}
        </button>
        <button
          type="button"
          disabled={pending}
          onClick={() => {
            setEditing(false);
            setError(null);
          }}
          className="qm-tap-44 rounded-lg border border-linear-border px-4 py-2 text-[12.5px] font-medium text-linear-text-2 disabled:opacity-60"
        >
          Cancel
        </button>
      </div>
    </form>
  );
}
