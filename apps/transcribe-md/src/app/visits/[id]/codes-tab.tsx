'use client';

// ============================================================================
// CodesTab — ICD-10 / CPT codes panel for the visit-detail Codes tab
// ----------------------------------------------------------------------------
// Phase 5 — Linear V1 Faithful. Hairline-bordered surface-1 cards on
// the dark canvas. ICD pills tinted sage; CPT pills tinted sky. Code
// numbers in JetBrains Mono; descriptions in Inter. The `theme` prop
// is retained on the public API as a no-op for caller back-compat.
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
  /** @deprecated kept for back-compat; Linear V1 is single-theme. */
  theme?: CodesTabTheme;
}

const SECTION_LABEL = 'mb-3 text-[10.5px] font-medium uppercase tracking-[0.07em] font-mono text-linear-text-3';

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
      ? 'text-linear-danger'
      : em.reasoning.risk === 'moderate'
        ? 'text-linear-warning'
        : 'text-linear-text-3';

  return (
    <section>
      <h3 className={SECTION_LABEL}>Evaluation &amp; Management</h3>
      <div className="rounded-lg border border-linear-border bg-linear-surface-1 p-5">
        <div className="flex flex-wrap items-start justify-between gap-4">
          <div>
            <div className="font-mono text-[28px] font-semibold tracking-tight text-linear-text">
              {em.code}
            </div>
            <div className="mt-1 text-[13px] text-linear-text-2">
              {em.description}
            </div>
          </div>
          <button
            type="button"
            onClick={() => setShowReasoning((v) => !v)}
            className="qm-lin-btn"
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
          <div className="mt-4 space-y-3 border-t border-linear-hairline pt-4">
            <div>
              <div className={SECTION_LABEL}>Problems addressed</div>
              <ul className="space-y-1 text-[13px] text-linear-text-2">
                {em.reasoning.problems.length === 0 ? (
                  <li className="text-linear-text-3">None listed.</li>
                ) : (
                  em.reasoning.problems.map((p, i) => (
                    <li key={i} className="flex items-center gap-2">
                      <span className="inline-block h-1.5 w-1.5 rounded-full bg-linear-sage" />
                      {p.description}
                      <span className="text-[11px] text-linear-text-3">
                        ({p.status})
                      </span>
                    </li>
                  ))
                )}
              </ul>
            </div>
            <div>
              <div className={SECTION_LABEL}>Data reviewed</div>
              <div className="text-[13px] text-linear-text-2">
                {em.reasoning.data || 'Not documented.'}
              </div>
            </div>
            <div>
              <div className={SECTION_LABEL}>Risk</div>
              <div className={cn('text-[13px] font-medium capitalize', riskTone)}>
                {em.reasoning.risk}
              </div>
            </div>
          </div>
        )}

        <div className="mt-4 rounded-md border border-linear-hairline bg-linear-surface-2 p-3 text-[12px] italic text-linear-text-3">
          “{em.evidence_quote}”
        </div>
      </div>
    </section>
  );
}

function IcdSection({ codes }: { codes: IcdCode[] }) {
  return (
    <section>
      <h3 className={SECTION_LABEL}>ICD-10 codes</h3>
      <div className="overflow-hidden rounded-lg border border-linear-border bg-linear-surface-1">
        <table className="w-full border-collapse text-left text-[13px]">
          <thead className="bg-linear-surface-2 font-mono text-[10.5px] uppercase tracking-[0.07em] text-linear-text-3">
            <tr>
              <th className="px-3 py-2 font-medium">Code</th>
              <th className="px-3 py-2 font-medium">Description</th>
              <th className="px-3 py-2 font-medium">Evidence</th>
              <th className="px-3 py-2 text-right font-medium">Confidence</th>
            </tr>
          </thead>
          <tbody>
            {codes.map((c, i) => (
              <tr
                key={`${c.code}-${i}`}
                className="border-t border-linear-hairline"
              >
                <td className="px-3 py-2 align-top font-mono text-linear-text">
                  {c.code}
                </td>
                <td className="px-3 py-2 align-top text-linear-text-2">
                  {c.description}
                </td>
                <td className="px-3 py-2 align-top text-[12px] italic text-linear-text-3">
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
      <h3 className={SECTION_LABEL}>Procedure CPT codes</h3>
      <ul className="space-y-2">
        {items.map((p, i) => (
          <li
            key={`${p.code}-${i}`}
            className="rounded-lg border border-linear-border bg-linear-surface-1 px-4 py-3"
          >
            <div className="flex items-start justify-between gap-3">
              <div>
                <div className="font-mono text-[14px] font-semibold text-linear-text">
                  {p.code}
                </div>
                <div className="mt-1 text-[12px] text-linear-text-2">
                  {p.description}
                </div>
              </div>
            </div>
            <div className="mt-2 text-[11px] italic text-linear-text-3">
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
      <h3 className={SECTION_LABEL}>Suggested modifiers</h3>
      <ul className="flex flex-wrap gap-2">
        {items.map((m, i) => (
          <li
            key={`${m.code}-${i}`}
            className="inline-flex items-center gap-2 rounded-md border border-linear-border bg-linear-surface-2 px-3 py-1"
          >
            <span className="font-mono text-[12px] font-semibold text-linear-text">
              -{m.code}
            </span>
            <span className="text-[12px] text-linear-text-2">{m.rationale}</span>
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
  // Linear V1 maps the three confidence bands to sage / warning /
  // danger tints. Same semantic ordering as before.
  const tone =
    value > 0.8
      ? { bg: 'bg-linear-sage-tint', fg: 'text-linear-sage-bright' }
      : value >= 0.5
        ? {
            bg: 'bg-linear-warning/15',
            fg: 'text-linear-warning',
          }
        : {
            bg: 'bg-linear-danger/15',
            fg: 'text-linear-danger',
          };

  return (
    <span
      className={cn(
        'inline-flex items-center gap-1.5 rounded-md px-2 py-0.5 font-mono text-[11px] font-medium tabular-nums',
        tone.bg,
        tone.fg
      )}
    >
      {(value * 100).toFixed(0)}%
    </span>
  );
}

function EmptyBlock({ title, body }: { title: string; body: string }) {
  return (
    <div className="rounded-lg border border-dashed border-linear-border bg-linear-surface-1 p-8 text-center">
      <div className="text-[14px] font-medium text-linear-text">{title}</div>
      <div className="mt-2 text-[13px] text-linear-text-2">{body}</div>
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
