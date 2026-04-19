'use client';

import { useState } from 'react';
import { ChevronDown } from 'lucide-react';
import { cn } from '@/lib/cn';

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
}

export function CodesTab({ icd, cpt }: CodesTabProps) {
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
      />
    );
  }

  return (
    <div className="space-y-8">
      {em && <EmSection em={em} />}
      {icdCodes.length > 0 && <IcdSection codes={icdCodes} />}
      {procedures.length > 0 && <ProceduresSection items={procedures} />}
      {modifiers.length > 0 && <ModifiersSection items={modifiers} />}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Sections
// ---------------------------------------------------------------------------

function EmSection({ em }: { em: EmCode }) {
  const [showReasoning, setShowReasoning] = useState(false);
  const riskTone =
    em.reasoning.risk === 'high'
      ? 'text-danger'
      : em.reasoning.risk === 'moderate'
        ? 'text-warning'
        : 'text-text-tertiary';
  return (
    <section>
      <h3 className="mb-3 text-[11px] font-semibold uppercase tracking-wider text-text-muted">
        Evaluation &amp; Management
      </h3>
      <div className="rounded-xl border border-border-default bg-bg-surface-1/60 p-5">
        <div className="flex flex-wrap items-start justify-between gap-4">
          <div>
            <div className="font-mono text-[32px] font-semibold text-text-primary">
              {em.code}
            </div>
            <div className="mt-1 text-[13px] text-text-tertiary">
              {em.description}
            </div>
          </div>
          <button
            type="button"
            onClick={() => setShowReasoning((v) => !v)}
            className="inline-flex items-center gap-1.5 rounded-full border border-border-subtle bg-bg-surface-2/60 px-3 py-1 text-[11px] font-medium text-text-tertiary hover:border-border-default hover:text-text-secondary focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-violet-500 focus-visible:ring-offset-2 focus-visible:ring-offset-bg-base"
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
          <div className="mt-4 space-y-3 border-t border-border-subtle pt-4">
            <div>
              <div className="mb-1.5 text-[11px] font-semibold uppercase tracking-wider text-text-muted">
                Problems addressed
              </div>
              <ul className="space-y-1 text-[13px] text-text-secondary">
                {em.reasoning.problems.length === 0 ? (
                  <li className="text-text-muted">None listed.</li>
                ) : (
                  em.reasoning.problems.map((p, i) => (
                    <li key={i} className="flex items-center gap-2">
                      <span className="inline-block h-1.5 w-1.5 rounded-full bg-violet-400" />
                      {p.description}
                      <span className="text-[11px] text-text-muted">
                        ({p.status})
                      </span>
                    </li>
                  ))
                )}
              </ul>
            </div>
            <div>
              <div className="mb-1.5 text-[11px] font-semibold uppercase tracking-wider text-text-muted">
                Data reviewed
              </div>
              <div className="text-[13px] text-text-secondary">
                {em.reasoning.data || 'Not documented.'}
              </div>
            </div>
            <div>
              <div className="mb-1.5 text-[11px] font-semibold uppercase tracking-wider text-text-muted">
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

        <div className="mt-4 rounded-lg border border-border-subtle bg-bg-surface-2/40 p-3 text-[12px] italic text-text-tertiary">
          “{em.evidence_quote}”
        </div>
      </div>
    </section>
  );
}

function IcdSection({ codes }: { codes: IcdCode[] }) {
  return (
    <section>
      <h3 className="mb-3 text-[11px] font-semibold uppercase tracking-wider text-text-muted">
        ICD-10 codes
      </h3>
      <div className="overflow-hidden rounded-xl border border-border-default">
        <table className="w-full border-collapse text-left text-[13px]">
          <thead className="bg-bg-surface-2/60 text-[11px] uppercase tracking-wider text-text-muted">
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
                className="border-t border-border-subtle bg-bg-surface-1/40"
              >
                <td className="px-3 py-2 align-top font-mono text-text-primary">
                  {c.code}
                </td>
                <td className="px-3 py-2 align-top text-text-secondary">
                  {c.description}
                </td>
                <td className="px-3 py-2 align-top text-[12px] italic text-text-tertiary">
                  “{c.evidence_quote}”
                </td>
                <td className="px-3 py-2 align-top text-right">
                  <ConfidenceChip value={c.confidence} />
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </section>
  );
}

function ProceduresSection({ items }: { items: ProcedureCpt[] }) {
  return (
    <section>
      <h3 className="mb-3 text-[11px] font-semibold uppercase tracking-wider text-text-muted">
        Procedure CPT codes
      </h3>
      <ul className="space-y-2">
        {items.map((p, i) => (
          <li
            key={`${p.code}-${i}`}
            className="rounded-lg border border-border-subtle bg-bg-surface-1/40 px-4 py-3"
          >
            <div className="flex items-start justify-between gap-3">
              <div>
                <div className="font-mono text-[14px] font-semibold text-text-primary">
                  {p.code}
                </div>
                <div className="mt-1 text-[12px] text-text-secondary">
                  {p.description}
                </div>
              </div>
            </div>
            <div className="mt-2 text-[11px] italic text-text-muted">
              “{p.evidence_quote}”
            </div>
          </li>
        ))}
      </ul>
    </section>
  );
}

function ModifiersSection({ items }: { items: Modifier[] }) {
  return (
    <section>
      <h3 className="mb-3 text-[11px] font-semibold uppercase tracking-wider text-text-muted">
        Suggested modifiers
      </h3>
      <ul className="flex flex-wrap gap-2">
        {items.map((m, i) => (
          <li
            key={`${m.code}-${i}`}
            className="inline-flex items-center gap-2 rounded-full border border-border-default bg-bg-surface-2/60 px-3 py-1"
          >
            <span className="font-mono text-[12px] font-semibold text-text-primary">
              -{m.code}
            </span>
            <span className="text-[12px] text-text-tertiary">{m.rationale}</span>
          </li>
        ))}
      </ul>
    </section>
  );
}

// ---------------------------------------------------------------------------
// Atoms
// ---------------------------------------------------------------------------

function ConfidenceChip({ value }: { value: number }) {
  const tone =
    value > 0.8
      ? { cls: 'bg-success/15 text-success', dot: 'bg-success' }
      : value >= 0.5
        ? { cls: 'bg-warning/15 text-warning', dot: 'bg-warning' }
        : { cls: 'bg-danger/15 text-danger', dot: 'bg-danger' };
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

function EmptyBlock({ title, body }: { title: string; body: string }) {
  return (
    <div className="rounded-xl border border-dashed border-border-subtle bg-bg-surface-1/30 p-8 text-center">
      <div className="text-[14px] font-medium text-text-primary">{title}</div>
      <div className="mt-2 text-[13px] text-text-tertiary">{body}</div>
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
