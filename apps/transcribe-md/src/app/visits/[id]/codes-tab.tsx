'use client';

// ============================================================================
// CodesTab — ICD-10 / CPT codes panel for the visit-detail Codes tab
// ----------------------------------------------------------------------------
// Phase 2 (Clinician remodel) — Strategy A dual-theme via additive
// `theme` prop. Default `'legacy'` keeps the existing dark
// bg-bg-surface-1 / border-border-default cards verbatim. Migrated
// surfaces (visit-detail) pass `theme="clinician"` to render the
// .qm-cl-card surface + soft pill chips + cream-2 modifier rows that
// match the visit-detail mockup's coding tab.
// ============================================================================

import { useState } from 'react';
import { ChevronDown } from 'lucide-react';
import { cn } from '@/lib/cn';

type CodesTabTheme = 'legacy' | 'clinician';

// ---------------------------------------------------------------------------
// Shape mirrors Layer 7a / 7b output. Defined locally rather than imported
// from the worker module so this client component doesn't pull the worker
// bundle into the browser.
// ---------------------------------------------------------------------------

interface IcdCode {
  code: string;
  description: string;
  evidence_quote: string;
  confidence: number;
}

interface EmReasoning {
  problems: { description: string; status: string }[];
  data: string;
  risk: 'minimal' | 'low' | 'moderate' | 'high' | string;
}

interface EmCode {
  code: string;
  description: string;
  reasoning: EmReasoning;
  evidence_quote: string;
}

interface ProcedureCpt {
  code: string;
  description: string;
  evidence_quote: string;
}

interface Modifier {
  code: string;
  rationale: string;
}

export interface IcdBlob {
  codes?: IcdCode[];
}

export interface CptBlob {
  em?: EmCode | null;
  procedures?: ProcedureCpt[];
  modifiers?: Modifier[];
}

interface CodesTabProps {
  icd: unknown;
  cpt: unknown;
  theme?: CodesTabTheme;
}

export function CodesTab({ icd, cpt, theme = 'legacy' }: CodesTabProps) {
  const icdBlob = (icd as IcdBlob | null) ?? null;
  const cptBlob = (cpt as CptBlob | null) ?? null;
  const icdCodes = icdBlob?.codes ?? [];
  const em = cptBlob?.em ?? null;
  const procedures = cptBlob?.procedures ?? [];
  const modifiers = cptBlob?.modifiers ?? [];

  const everythingEmpty =
    icdCodes.length === 0 &&
    !em &&
    procedures.length === 0 &&
    modifiers.length === 0;

  if (everythingEmpty) {
    return (
      <EmptyBlock
        title="No codes were generated"
        body="The pipeline didn’t return any ICD-10 or CPT codes for this visit. You can retry the visit or add codes manually in your EHR."
        theme={theme}
      />
    );
  }

  return (
    <div className="space-y-8">
      {em && <EmSection em={em} theme={theme} />}
      {icdCodes.length > 0 && <IcdSection codes={icdCodes} theme={theme} />}
      {procedures.length > 0 && (
        <ProceduresSection items={procedures} theme={theme} />
      )}
      {modifiers.length > 0 && (
        <ModifiersSection items={modifiers} theme={theme} />
      )}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Sections
// ---------------------------------------------------------------------------

function EmSection({ em, theme }: { em: EmCode; theme: CodesTabTheme }) {
  const [showReasoning, setShowReasoning] = useState(false);
  const isClinician = theme === 'clinician';
  const riskTone = isClinician
    ? em.reasoning.risk === 'high'
      ? 'text-clinician-coral-deep'
      : em.reasoning.risk === 'moderate'
        ? 'text-clinician-amber-deep'
        : 'text-clinician-ink-3'
    : em.reasoning.risk === 'high'
      ? 'text-danger'
      : em.reasoning.risk === 'moderate'
        ? 'text-warning'
        : 'text-text-tertiary';

  return (
    <section>
      <h3
        className={cn(
          'mb-3 text-[11px] font-semibold uppercase tracking-wider',
          isClinician ? 'text-clinician-ink-3' : 'text-text-muted'
        )}
      >
        Evaluation &amp; Management
      </h3>
      <div
        className={cn(
          'p-5',
          isClinician
            ? 'qm-cl-card'
            : 'rounded-xl border border-border-default bg-bg-surface-1/60'
        )}
      >
        <div className="flex flex-wrap items-start justify-between gap-4">
          <div>
            <div
              className={cn(
                'font-mono text-[32px] font-semibold',
                isClinician ? 'text-clinician-ink' : 'text-text-primary'
              )}
            >
              {em.code}
            </div>
            <div
              className={cn(
                'mt-1 text-[13px]',
                isClinician ? 'text-clinician-ink-2' : 'text-text-tertiary'
              )}
            >
              {em.description}
            </div>
          </div>
          <button
            type="button"
            onClick={() => setShowReasoning((v) => !v)}
            className={cn(
              'inline-flex items-center gap-1.5 rounded-full px-3 py-1 text-[11px] font-medium transition-colors',
              isClinician
                ? 'border border-clinician-line bg-clinician-cream-card text-clinician-ink-3 hover:border-clinician-line-strong hover:text-clinician-ink-2 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-clinician-sage focus-visible:ring-offset-2 focus-visible:ring-offset-clinician-cream'
                : 'border border-border-subtle bg-bg-surface-2/60 text-text-tertiary hover:border-border-default hover:text-text-secondary focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-violet-500 focus-visible:ring-offset-2 focus-visible:ring-offset-bg-base'
            )}
          >
            {showReasoning ? 'Hide reasoning' : 'Show reasoning'}
            <ChevronDown
              className={cn(
                'h-3 w-3 transition-transform',
                showReasoning && 'rotate-180'
              )}
              aria-hidden
            />
          </button>
        </div>

        {showReasoning && (
          <div
            className={cn(
              'mt-4 space-y-3 border-t pt-4',
              isClinician ? 'border-clinician-line' : 'border-border-subtle'
            )}
          >
            <div>
              <div
                className={cn(
                  'mb-1.5 text-[11px] font-semibold uppercase tracking-wider',
                  isClinician ? 'text-clinician-ink-3' : 'text-text-muted'
                )}
              >
                Problems addressed
              </div>
              <ul
                className={cn(
                  'space-y-1 text-[13px]',
                  isClinician ? 'text-clinician-ink-2' : 'text-text-secondary'
                )}
              >
                {em.reasoning.problems.length === 0 ? (
                  <li
                    className={cn(
                      isClinician ? 'text-clinician-ink-4' : 'text-text-muted'
                    )}
                  >
                    None listed.
                  </li>
                ) : (
                  em.reasoning.problems.map((p, i) => (
                    <li key={i} className="flex items-center gap-2">
                      <span
                        className={cn(
                          'inline-block h-1.5 w-1.5 rounded-full',
                          isClinician ? 'bg-clinician-sage' : 'bg-violet-400'
                        )}
                      />
                      {p.description}
                      <span
                        className={cn(
                          'text-[11px]',
                          isClinician
                            ? 'text-clinician-ink-4'
                            : 'text-text-muted'
                        )}
                      >
                        ({p.status})
                      </span>
                    </li>
                  ))
                )}
              </ul>
            </div>
            <div>
              <div
                className={cn(
                  'mb-1.5 text-[11px] font-semibold uppercase tracking-wider',
                  isClinician ? 'text-clinician-ink-3' : 'text-text-muted'
                )}
              >
                Data reviewed
              </div>
              <div
                className={cn(
                  'text-[13px]',
                  isClinician ? 'text-clinician-ink-2' : 'text-text-secondary'
                )}
              >
                {em.reasoning.data || 'Not documented.'}
              </div>
            </div>
            <div>
              <div
                className={cn(
                  'mb-1.5 text-[11px] font-semibold uppercase tracking-wider',
                  isClinician ? 'text-clinician-ink-3' : 'text-text-muted'
                )}
              >
                Risk
              </div>
              <div
                className={cn(
                  'text-[13px] font-medium capitalize',
                  riskTone
                )}
              >
                {em.reasoning.risk}
              </div>
            </div>
          </div>
        )}

        <div
          className={cn(
            'mt-4 rounded-lg p-3 text-[12px] italic',
            isClinician
              ? 'border border-clinician-line bg-clinician-cream-2 text-clinician-ink-3'
              : 'border border-border-subtle bg-bg-surface-2/40 text-text-tertiary'
          )}
        >
          “{em.evidence_quote}”
        </div>
      </div>
    </section>
  );
}

function IcdSection({
  codes,
  theme,
}: {
  codes: IcdCode[];
  theme: CodesTabTheme;
}) {
  const isClinician = theme === 'clinician';
  return (
    <section>
      <h3
        className={cn(
          'mb-3 text-[11px] font-semibold uppercase tracking-wider',
          isClinician ? 'text-clinician-ink-3' : 'text-text-muted'
        )}
      >
        ICD-10 codes
      </h3>
      <div
        className={cn(
          'overflow-hidden rounded-xl border',
          isClinician
            ? 'border-clinician-line bg-clinician-cream-card'
            : 'border-border-default'
        )}
      >
        <table className="w-full border-collapse text-left text-[13px]">
          <thead
            className={cn(
              'text-[11px] uppercase tracking-wider',
              isClinician
                ? 'bg-clinician-cream-2 text-clinician-ink-3'
                : 'bg-bg-surface-2/60 text-text-muted'
            )}
          >
            <tr>
              <th className="px-3 py-2 font-medium">Code</th>
              <th className="px-3 py-2 font-medium">Description</th>
              <th className="px-3 py-2 font-medium">Evidence</th>
              <th className="px-3 py-2 font-medium text-right">Confidence</th>
            </tr>
          </thead>
          <tbody>
            {codes.map((c, i) => (
              <tr
                key={`${c.code}-${i}`}
                className={cn(
                  'border-t',
                  isClinician
                    ? 'border-clinician-line'
                    : 'border-border-subtle bg-bg-surface-1/40'
                )}
              >
                <td
                  className={cn(
                    'px-3 py-2 align-top font-mono',
                    isClinician ? 'text-clinician-ink' : 'text-text-primary'
                  )}
                >
                  {c.code}
                </td>
                <td
                  className={cn(
                    'px-3 py-2 align-top',
                    isClinician ? 'text-clinician-ink-2' : 'text-text-secondary'
                  )}
                >
                  {c.description}
                </td>
                <td
                  className={cn(
                    'px-3 py-2 align-top text-[12px] italic',
                    isClinician ? 'text-clinician-ink-3' : 'text-text-tertiary'
                  )}
                >
                  “{c.evidence_quote}”
                </td>
                <td className="px-3 py-2 align-top text-right">
                  <ConfidenceChip value={c.confidence} theme={theme} />
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </section>
  );
}

function ProceduresSection({
  items,
  theme,
}: {
  items: ProcedureCpt[];
  theme: CodesTabTheme;
}) {
  const isClinician = theme === 'clinician';
  return (
    <section>
      <h3
        className={cn(
          'mb-3 text-[11px] font-semibold uppercase tracking-wider',
          isClinician ? 'text-clinician-ink-3' : 'text-text-muted'
        )}
      >
        Procedure CPT codes
      </h3>
      <ul className="space-y-2">
        {items.map((p, i) => (
          <li
            key={`${p.code}-${i}`}
            className={cn(
              'rounded-lg px-4 py-3',
              isClinician
                ? 'border border-clinician-line bg-clinician-cream-card'
                : 'border border-border-subtle bg-bg-surface-1/40'
            )}
          >
            <div className="flex items-start justify-between gap-3">
              <div>
                <div
                  className={cn(
                    'font-mono text-[14px] font-semibold',
                    isClinician ? 'text-clinician-ink' : 'text-text-primary'
                  )}
                >
                  {p.code}
                </div>
                <div
                  className={cn(
                    'mt-1 text-[12px]',
                    isClinician
                      ? 'text-clinician-ink-2'
                      : 'text-text-secondary'
                  )}
                >
                  {p.description}
                </div>
              </div>
            </div>
            <div
              className={cn(
                'mt-2 text-[11px] italic',
                isClinician ? 'text-clinician-ink-3' : 'text-text-muted'
              )}
            >
              “{p.evidence_quote}”
            </div>
          </li>
        ))}
      </ul>
    </section>
  );
}

function ModifiersSection({
  items,
  theme,
}: {
  items: Modifier[];
  theme: CodesTabTheme;
}) {
  const isClinician = theme === 'clinician';
  return (
    <section>
      <h3
        className={cn(
          'mb-3 text-[11px] font-semibold uppercase tracking-wider',
          isClinician ? 'text-clinician-ink-3' : 'text-text-muted'
        )}
      >
        Suggested modifiers
      </h3>
      <ul className="flex flex-wrap gap-2">
        {items.map((m, i) => (
          <li
            key={`${m.code}-${i}`}
            className={cn(
              'inline-flex items-center gap-2 rounded-full px-3 py-1',
              isClinician
                ? 'border border-clinician-line bg-clinician-cream-card'
                : 'border border-border-default bg-bg-surface-2/60'
            )}
          >
            <span
              className={cn(
                'font-mono text-[12px] font-semibold',
                isClinician ? 'text-clinician-ink' : 'text-text-primary'
              )}
            >
              -{m.code}
            </span>
            <span
              className={cn(
                'text-[12px]',
                isClinician ? 'text-clinician-ink-2' : 'text-text-tertiary'
              )}
            >
              {m.rationale}
            </span>
          </li>
        ))}
      </ul>
    </section>
  );
}

// ---------------------------------------------------------------------------
// Atoms
// ---------------------------------------------------------------------------

function ConfidenceChip({
  value,
  theme,
}: {
  value: number;
  theme: CodesTabTheme;
}) {
  const isClinician = theme === 'clinician';
  // Clinician maps the three confidence bands to .qm-cl-pill-* tones —
  // sage = high, amber = mid, coral = low. Same semantic ordering as
  // the legacy success/warning/danger triad.
  const tone = isClinician
    ? value > 0.8
      ? { cls: 'qm-cl-pill qm-cl-pill-sage', dot: 'qm-cl-pill-dot' }
      : value >= 0.5
        ? { cls: 'qm-cl-pill qm-cl-pill-amber', dot: 'qm-cl-pill-dot' }
        : { cls: 'qm-cl-pill qm-cl-pill-coral', dot: 'qm-cl-pill-dot' }
    : value > 0.8
      ? { cls: 'bg-success/15 text-success', dot: 'bg-success' }
      : value >= 0.5
        ? { cls: 'bg-warning/15 text-warning', dot: 'bg-warning' }
        : { cls: 'bg-danger/15 text-danger', dot: 'bg-danger' };

  if (isClinician) {
    return (
      <span className={cn(tone.cls, 'tabular-nums')}>
        <span className={tone.dot} />
        {(value * 100).toFixed(0)}%
      </span>
    );
  }

  return (
    <span
      className={cn(
        'inline-flex items-center gap-1.5 rounded-full px-2 py-0.5 text-[11px] font-medium tabular-nums',
        tone.cls
      )}
    >
      <span className={cn('inline-block h-1.5 w-1.5 rounded-full', tone.dot)} />
      {(value * 100).toFixed(0)}%
    </span>
  );
}

function EmptyBlock({
  title,
  body,
  theme,
}: {
  title: string;
  body: string;
  theme: CodesTabTheme;
}) {
  const isClinician = theme === 'clinician';
  return (
    <div
      className={cn(
        'rounded-xl p-8 text-center',
        isClinician
          ? 'border border-dashed border-clinician-line bg-clinician-cream-card'
          : 'border border-dashed border-border-subtle bg-bg-surface-1/30'
      )}
    >
      <div
        className={cn(
          'text-[14px] font-medium',
          isClinician ? 'text-clinician-ink' : 'text-text-primary'
        )}
      >
        {title}
      </div>
      <div
        className={cn(
          'mt-2 text-[13px]',
          isClinician ? 'text-clinician-ink-2' : 'text-text-tertiary'
        )}
      >
        {body}
      </div>
    </div>
  );
}

// Exported helper: given the confidence-scores blob, tell the Tabs bar
// whether the Codes tab should show a warning badge.
export function codesTabHasWarnings(confidenceScores: unknown): boolean {
  const cs =
    (confidenceScores as Record<string, { status?: string }> | null) ?? {};
  return (
    cs.icd_coding?.status === 'failed' || cs.cpt_coding?.status === 'failed'
  );
}
