'use client';

// ============================================================================
// CodesTab — Phase 5.1 Linear V1 V2 Power Table
// ----------------------------------------------------------------------------
// Two dense, hairline-bordered tables (ICD-10-CM and CPT-4) on the
// dark canvas. Sticky 36px header; 32px tight body rows; mono codes;
// 4px-tall sage progress bar in the Confidence column; italic short
// quote + "view source" affordance in the Evidence column. Click a
// row to expand inline → reveals the full evidence quote and a row
// of secondary action chips. Low-confidence rows (<70%) carry a 2px
// amber left bar + amber confidence band.
//
// Read-only mode: when `readonly` is true (visit SIGNED), the Add
// row, hover-revealed icon buttons, and the expand-row Edit/Remove
// chips are suppressed. Sort affordances stay enabled regardless —
// they only re-order the projection.
//
// Wire shapes are byte-identical to the worker output (see
// 07a-icd-coding.ts / 07b-cpt-coding.ts).
// ============================================================================

import { useMemo, useState } from 'react';
import { projectEmForDisplay } from '@/lib/visit-export';
import { cn } from '@/lib/cn';
import { Ic } from '@/components/ui/icon';
import { CodeEvidencePopover } from './code-evidence-popover';

type CodesTabTheme = 'legacy' | 'clinician';

// ---------------------------------------------------------------------------
// Wire shapes — mirror Layer 7a / 7b output. Defined locally to keep the
// worker bundle out of the browser.
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
  /** Optional by design — see procedureProvenanceNote() in visit-export.ts. */
  provenance?: 'dictated' | 'coach_suggested';
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
  /** Visit is SIGNED → suppress mutation affordances. */
  readonly?: boolean;
  /** @deprecated kept for back-compat; Linear V1 is single-theme. */
  theme?: CodesTabTheme;
}

type IcdSortKey = 'code' | 'description' | 'confidence';
type CptSortKey = 'code' | 'description';

// ---------------------------------------------------------------------------
// Public component
// ---------------------------------------------------------------------------

export function CodesTab({ icd, cpt, readonly = false }: CodesTabProps) {
  const icdBlob = (icd as IcdBlob | null) ?? null;
  const cptBlob = (cpt as CptBlob | null) ?? null;
  const icdCodes = icdBlob?.codes ?? [];
  // #315 obs#2: render the displayed E/M code (signed → frozen, else
  // override ?? raw), the same projection every export surface uses.
  const em = projectEmForDisplay(cptBlob?.em ?? null, readonly);
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

  // Average ICD confidence + needs-review count drive the toolbar.
  const totalCodes =
    icdCodes.length + (em ? 1 : 0) + procedures.length;
  const avgConfidence = icdCodes.length
    ? icdCodes.reduce((s, c) => s + (c.confidence ?? 0), 0) / icdCodes.length
    : null;
  const lowConfCount = icdCodes.filter((c) => (c.confidence ?? 0) < 0.7).length;

  return (
    <div className="qm-lin-codes-frame">
      <Toolbar
        totalCodes={totalCodes}
        avgConfidence={avgConfidence}
        lowConfCount={lowConfCount}
        proceduresCount={procedures.length}
        readonly={readonly}
      />

      {icdCodes.length > 0 && (
        <IcdTable codes={icdCodes} readonly={readonly} />
      )}

      <CptTable
        em={em}
        procedures={procedures}
        modifiers={modifiers}
        readonly={readonly}
      />

      <TotalsStrip
        totalCodes={totalCodes}
        proceduresCount={procedures.length + (em ? 1 : 0)}
      />
    </div>
  );
}

// ---------------------------------------------------------------------------
// Toolbar
// ---------------------------------------------------------------------------

function Toolbar({
  totalCodes,
  avgConfidence,
  lowConfCount,
  readonly,
}: {
  totalCodes: number;
  avgConfidence: number | null;
  lowConfCount: number;
  proceduresCount: number;
  readonly: boolean;
}) {
  return (
    <div className="qm-lin-codes-toolbar">
      <div className="qm-lin-codes-toolbar-totals">
        <span>
          <span>Codes</span>
          <span aria-hidden> · </span>
          <span className="v">{totalCodes}</span>
        </span>
        {avgConfidence !== null && (
          <span>
            <span>Avg conf</span>
            <span aria-hidden> · </span>
            <span className="v">{(avgConfidence * 100).toFixed(0)}%</span>
          </span>
        )}
        {lowConfCount > 0 && (
          <span style={{ color: 'var(--color-linear-warning)' }}>
            <span>Review</span>
            <span aria-hidden> · </span>
            <span className="v">{lowConfCount}</span>
          </span>
        )}
      </div>
      <div style={{ flex: 1 }} />
      {!readonly && (
        <button
          type="button"
          className="qm-lin-codes-filter"
          aria-label="Filter (placeholder)"
          disabled
          title="Filter coming in T-M21"
        >
          Conf · all
        </button>
      )}
    </div>
  );
}

// ---------------------------------------------------------------------------
// ICD-10 power table
// ---------------------------------------------------------------------------

function IcdTable({
  codes,
  readonly,
}: {
  codes: IcdCode[];
  readonly: boolean;
}) {
  const [sortKey, setSortKey] = useState<IcdSortKey>('confidence');
  const [sortDir, setSortDir] = useState<'asc' | 'desc'>('desc');
  const [expandedIx, setExpandedIx] = useState<number | null>(null);

  const sorted = useMemo(() => {
    const arr = codes.map((c, i) => ({ ...c, _ix: i }));
    arr.sort((a, b) => {
      let cmp = 0;
      if (sortKey === 'code') cmp = a.code.localeCompare(b.code);
      else if (sortKey === 'description')
        cmp = a.description.localeCompare(b.description);
      else cmp = (a.confidence ?? 0) - (b.confidence ?? 0);
      return sortDir === 'asc' ? cmp : -cmp;
    });
    return arr;
  }, [codes, sortKey, sortDir]);

  const toggleSort = (key: IcdSortKey) => {
    if (sortKey === key) {
      setSortDir((d) => (d === 'asc' ? 'desc' : 'asc'));
    } else {
      setSortKey(key);
      setSortDir(key === 'confidence' ? 'desc' : 'asc');
    }
  };

  const lowCount = codes.filter((c) => (c.confidence ?? 0) < 0.7).length;

  return (
    <section className="qm-lin-table-block">
      <div className="qm-lin-table-head">
        <div className="qm-lin-table-head-l">
          <div className="qm-lin-table-title">ICD-10-CM · Diagnoses</div>
          <div className="qm-lin-table-sub">
            <strong>{codes.length}</strong> code{codes.length === 1 ? '' : 's'}
            {lowCount > 0 && ` · ${lowCount} need${lowCount === 1 ? 's' : ''} review`}
          </div>
        </div>
        <div className="qm-lin-table-sub" style={{ color: 'var(--color-linear-text-3)' }}>
          click row to expand
        </div>
      </div>

      <table className="qm-lin-codes-table" role="grid">
        <thead>
          <tr>
            <th
              style={{ width: '14%' }}
              className={cn(sortKey === 'code' && 'sorted')}
              onClick={() => toggleSort('code')}
              role="columnheader"
            >
              Code <SortArrow active={sortKey === 'code'} dir={sortDir} />
            </th>
            <th
              style={{ width: '40%' }}
              className={cn(sortKey === 'description' && 'sorted')}
              onClick={() => toggleSort('description')}
              role="columnheader"
            >
              Description{' '}
              <SortArrow active={sortKey === 'description'} dir={sortDir} />
            </th>
            <th
              style={{ width: '14%' }}
              className={cn(
                'qm-lin-codes-col-conf',
                sortKey === 'confidence' && 'sorted'
              )}
              onClick={() => toggleSort('confidence')}
              role="columnheader"
            >
              Confidence{' '}
              <SortArrow active={sortKey === 'confidence'} dir={sortDir} />
            </th>
            <th
              style={{ width: '24%' }}
              className="qm-lin-codes-col-evidence"
              role="columnheader"
            >
              Evidence
            </th>
            <th
              style={{ width: '8%' }}
              className="qm-lin-codes-col-actions"
              role="columnheader"
            >
              <span className="sr-only">Actions</span>
            </th>
          </tr>
        </thead>
        <tbody>
          {sorted.map((c) => {
            const conf = c.confidence ?? 0;
            const isLow = conf < 0.7;
            const isOpen = expandedIx === c._ix;
            const rowKey = `${c.code}-${c._ix}`;
            return (
              <RowGroup key={rowKey}>
                <tr
                  data-row-ix={c._ix}
                  className={cn(
                    'qm-lin-codes-row',
                    isLow && 'qm-lin-codes-row-low',
                    isOpen && 'qm-lin-codes-row-expanded'
                  )}
                  onClick={(e) => {
                    if ((e.target as HTMLElement).closest('button')) return;
                    setExpandedIx(isOpen ? null : c._ix);
                  }}
                  aria-expanded={isOpen}
                >
                  <td>
                    <span className="qm-lin-codes-cell-code">{c.code}</span>
                  </td>
                  <td>
                    <span className="qm-lin-codes-cell-desc" title={c.description}>
                      {c.description}
                    </span>
                  </td>
                  <td className="qm-lin-codes-col-conf">
                    <ConfidenceBar value={conf} />
                  </td>
                  <td className="qm-lin-codes-col-evidence">
                    <span
                      className="qm-lin-codes-cell-evidence"
                      title={c.evidence_quote}
                    >
                      {c.evidence_quote
                        ? `“${truncate(c.evidence_quote, 70)}”`
                        : '—'}
                    </span>
                  </td>
                  <td className="qm-lin-codes-col-actions">
                    {!readonly && (
                      <div className="qm-lin-codes-row-actions">
                        <button
                          type="button"
                          className="qm-lin-codes-icon-btn"
                          onClick={(e) => {
                            e.stopPropagation();
                          }}
                          aria-label={`Edit code ${c.code}`}
                          title="Edit (coming in T-M21)"
                          disabled
                        >
                          <Ic.edit width={13} height={13} aria-hidden />
                        </button>
                        <button
                          type="button"
                          className="qm-lin-codes-icon-btn qm-lin-codes-icon-btn-danger"
                          onClick={(e) => {
                            e.stopPropagation();
                          }}
                          aria-label={`Remove code ${c.code}`}
                          title="Remove (coming in T-M21)"
                          disabled
                        >
                          <Ic.close width={13} height={13} aria-hidden />
                        </button>
                      </div>
                    )}
                  </td>
                </tr>
                {isOpen && (
                  <tr className="qm-lin-codes-expand-row">
                    <td colSpan={5}>
                      <CodeEvidencePopover
                        quote={c.evidence_quote}
                        tone={isLow ? 'warning' : 'sage'}
                        label={
                          isLow
                            ? 'Low confidence · review before sign'
                            : 'Evidence · transcript'
                        }
                        actions={
                          <>
                            {!readonly && (
                              <button
                                type="button"
                                className="qm-lin-codes-ghost"
                                disabled
                              >
                                Edit
                              </button>
                            )}
                            <button type="button" className="qm-lin-codes-ghost" disabled>
                              View transcript
                            </button>
                            {isLow && !readonly && (
                              <button type="button" className="qm-lin-codes-ghost" disabled>
                                See alternatives
                              </button>
                            )}
                            {!readonly && (
                              <button
                                type="button"
                                className="qm-lin-codes-ghost qm-lin-codes-ghost-danger"
                                disabled
                              >
                                Remove
                              </button>
                            )}
                          </>
                        }
                      />
                    </td>
                  </tr>
                )}
              </RowGroup>
            );
          })}
        </tbody>
      </table>

      {!readonly && (
        <div className="qm-lin-codes-table-foot">
          <button type="button" className="qm-lin-codes-add" disabled title="Add ICD-10 code (coming in T-M21)">
            <span className="plus" aria-hidden>+</span>
            <span>Add ICD-10 code</span>
          </button>
        </div>
      )}
    </section>
  );
}

// ---------------------------------------------------------------------------
// CPT power table — combines E&M (single row, no confidence) with
// procedural CPT codes. Modifiers render as a chip tray below.
// ---------------------------------------------------------------------------

function CptTable({
  em,
  procedures,
  modifiers,
  readonly,
}: {
  em: EmCode | null;
  procedures: ProcedureCpt[];
  modifiers: Modifier[];
  readonly: boolean;
}) {
  const [sortKey, setSortKey] = useState<CptSortKey>('code');
  const [sortDir, setSortDir] = useState<'asc' | 'desc'>('asc');
  const [expandedKey, setExpandedKey] = useState<string | null>(em ? 'em' : null);

  // Build a unified row list. The E&M row is anchored first; procedural
  // rows follow, sorted by the active key.
  const procRows = useMemo(() => {
    const arr = procedures.map((p, i) => ({ ...p, _ix: i }));
    arr.sort((a, b) => {
      const cmp =
        sortKey === 'code'
          ? a.code.localeCompare(b.code)
          : a.description.localeCompare(b.description);
      return sortDir === 'asc' ? cmp : -cmp;
    });
    return arr;
  }, [procedures, sortKey, sortDir]);

  const total = (em ? 1 : 0) + procedures.length;

  const toggleSort = (key: CptSortKey) => {
    if (sortKey === key) setSortDir((d) => (d === 'asc' ? 'desc' : 'asc'));
    else {
      setSortKey(key);
      setSortDir('asc');
    }
  };

  if (total === 0 && modifiers.length === 0) return null;

  return (
    <section className="qm-lin-table-block">
      <div className="qm-lin-table-head">
        <div className="qm-lin-table-head-l">
          <div className="qm-lin-table-title">CPT-4 · Procedures &amp; E&amp;M</div>
          <div className="qm-lin-table-sub">
            <strong>{total}</strong> code{total === 1 ? '' : 's'}
            {modifiers.length > 0 && ` · ${modifiers.length} modifier${modifiers.length === 1 ? '' : 's'}`}
          </div>
        </div>
        <div className="qm-lin-table-sub" style={{ color: 'var(--color-linear-text-3)' }}>
          click row to expand
        </div>
      </div>

      <table className="qm-lin-codes-table" role="grid">
        <thead>
          <tr>
            <th
              style={{ width: '14%' }}
              className={cn(sortKey === 'code' && 'sorted')}
              onClick={() => toggleSort('code')}
              role="columnheader"
            >
              Code <SortArrow active={sortKey === 'code'} dir={sortDir} />
            </th>
            <th
              style={{ width: '52%' }}
              className={cn(sortKey === 'description' && 'sorted')}
              onClick={() => toggleSort('description')}
              role="columnheader"
            >
              Description{' '}
              <SortArrow active={sortKey === 'description'} dir={sortDir} />
            </th>
            <th
              style={{ width: '12%' }}
              className="qm-lin-codes-col-center"
              role="columnheader"
            >
              Type
            </th>
            <th
              style={{ width: '14%' }}
              className="qm-lin-codes-col-evidence"
              role="columnheader"
            >
              Evidence
            </th>
            <th
              style={{ width: '8%' }}
              className="qm-lin-codes-col-actions"
              role="columnheader"
            >
              <span className="sr-only">Actions</span>
            </th>
          </tr>
        </thead>
        <tbody>
          {em && (
            <RowGroup key="em">
              <tr
                className={cn(
                  'qm-lin-codes-row',
                  expandedKey === 'em' && 'qm-lin-codes-row-expanded'
                )}
                onClick={(e) => {
                  if ((e.target as HTMLElement).closest('button')) return;
                  setExpandedKey(expandedKey === 'em' ? null : 'em');
                }}
                aria-expanded={expandedKey === 'em'}
              >
                <td>
                  <span className="qm-lin-codes-cell-code">{em.code}</span>
                </td>
                <td>
                  <span
                    className="qm-lin-codes-cell-desc"
                    title={em.description}
                  >
                    {em.description}
                  </span>
                </td>
                <td className="qm-lin-codes-col-center">
                  <span className="qm-lin-codes-cell-mono">E&amp;M</span>
                </td>
                <td className="qm-lin-codes-col-evidence">
                  <span
                    className="qm-lin-codes-cell-evidence"
                    title={em.evidence_quote}
                  >
                    “{truncate(em.evidence_quote, 60)}”
                  </span>
                </td>
                <td className="qm-lin-codes-col-actions">
                  {!readonly && (
                    <div className="qm-lin-codes-row-actions">
                      <button
                        type="button"
                        className="qm-lin-codes-icon-btn"
                        onClick={(e) => e.stopPropagation()}
                        aria-label="Edit E&M code"
                        title="Edit (coming in T-M21)"
                        disabled
                      >
                        <Ic.edit width={13} height={13} aria-hidden />
                      </button>
                    </div>
                  )}
                </td>
              </tr>
              {expandedKey === 'em' && (
                <tr className="qm-lin-codes-expand-row">
                  <td colSpan={5}>
                    <EmReasoningPanel em={em} />
                  </td>
                </tr>
              )}
            </RowGroup>
          )}
          {procRows.map((p) => {
            const key = `cpt-${p.code}-${p._ix}`;
            const isOpen = expandedKey === key;
            return (
              <RowGroup key={key}>
                <tr
                  className={cn(
                    'qm-lin-codes-row',
                    isOpen && 'qm-lin-codes-row-expanded'
                  )}
                  onClick={(e) => {
                    if ((e.target as HTMLElement).closest('button')) return;
                    setExpandedKey(isOpen ? null : key);
                  }}
                  aria-expanded={isOpen}
                >
                  <td>
                    <span className="qm-lin-codes-cell-code">{p.code}</span>
                  </td>
                  <td>
                    <span className="qm-lin-codes-cell-desc" title={p.description}>
                      {p.description}
                    </span>
                  </td>
                  <td className="qm-lin-codes-col-center">
                    <span className="qm-lin-codes-cell-mono qm-lin-codes-cell-mono-muted">
                      Procedure
                      {p.provenance === 'dictated' && (
                        <>
                          {' · '}
                          <span title="You said this code aloud during the visit">
                            dictated
                          </span>
                        </>
                      )}
                    </span>
                  </td>
                  <td className="qm-lin-codes-col-evidence">
                    <span
                      className="qm-lin-codes-cell-evidence"
                      title={p.evidence_quote}
                    >
                      “{truncate(p.evidence_quote, 60)}”
                    </span>
                  </td>
                  <td className="qm-lin-codes-col-actions">
                    {!readonly && (
                      <div className="qm-lin-codes-row-actions">
                        <button
                          type="button"
                          className="qm-lin-codes-icon-btn"
                          onClick={(e) => e.stopPropagation()}
                          aria-label={`Edit code ${p.code}`}
                          title="Edit (coming in T-M21)"
                          disabled
                        >
                          <Ic.edit width={13} height={13} aria-hidden />
                        </button>
                        <button
                          type="button"
                          className="qm-lin-codes-icon-btn qm-lin-codes-icon-btn-danger"
                          onClick={(e) => e.stopPropagation()}
                          aria-label={`Remove code ${p.code}`}
                          title="Remove (coming in T-M21)"
                          disabled
                        >
                          <Ic.close width={13} height={13} aria-hidden />
                        </button>
                      </div>
                    )}
                  </td>
                </tr>
                {isOpen && (
                  <tr className="qm-lin-codes-expand-row">
                    <td colSpan={5}>
                      <CodeEvidencePopover
                        quote={p.evidence_quote}
                        label="Justification · transcript"
                        actions={
                          <>
                            {!readonly && (
                              <button type="button" className="qm-lin-codes-ghost" disabled>
                                Edit
                              </button>
                            )}
                            <button type="button" className="qm-lin-codes-ghost" disabled>
                              View transcript
                            </button>
                            {!readonly && (
                              <button
                                type="button"
                                className="qm-lin-codes-ghost qm-lin-codes-ghost-danger"
                                disabled
                              >
                                Remove
                              </button>
                            )}
                          </>
                        }
                      />
                    </td>
                  </tr>
                )}
              </RowGroup>
            );
          })}
        </tbody>
      </table>

      {!readonly && (
        <div className="qm-lin-codes-table-foot">
          <button
            type="button"
            className="qm-lin-codes-add"
            disabled
            title="Add CPT code (coming in T-M21)"
          >
            <span className="plus" aria-hidden>+</span>
            <span>Add CPT code</span>
          </button>
        </div>
      )}

      {modifiers.length > 0 && <ModifiersTray modifiers={modifiers} />}
    </section>
  );
}

function ModifiersTray({ modifiers }: { modifiers: Modifier[] }) {
  return (
    <div className="qm-lin-codes-modifiers">
      <div className="qm-lin-codes-modifiers-label">Modifiers</div>
      <div className="qm-lin-codes-modifiers-chips">
        {modifiers.map((m, i) => (
          <span
            key={`${m.code}-${i}`}
            className="qm-lin-codes-modifier-chip"
            title={m.rationale}
          >
            <span className="qm-lin-codes-modifier-code">-{m.code}</span>
            <span className="qm-lin-codes-modifier-rationale">{m.rationale}</span>
          </span>
        ))}
      </div>
    </div>
  );
}

function EmReasoningPanel({ em }: { em: EmCode }) {
  const riskColor =
    em.reasoning.risk === 'high'
      ? 'var(--color-linear-danger)'
      : em.reasoning.risk === 'moderate'
        ? 'var(--color-linear-warning)'
        : 'var(--color-linear-text-2)';
  return (
    <div className="qm-lin-code-evidence">
      <div className="qm-lin-code-evidence-label">
        <span
          aria-hidden
          className="qm-lin-code-evidence-dot"
          style={{ background: 'var(--color-linear-sage)' }}
        />
        Justification · MDM time
      </div>
      <blockquote
        className="qm-lin-code-evidence-quote"
        style={{ borderLeftColor: 'var(--color-linear-sage)' }}
      >
        “{em.evidence_quote}”
      </blockquote>
      <div className="qm-lin-em-reasoning-grid">
        <div>
          <div className="qm-lin-em-reasoning-label">Problems</div>
          {em.reasoning.problems.length === 0 ? (
            <div className="qm-lin-em-reasoning-value qm-lin-em-reasoning-empty">
              None listed.
            </div>
          ) : (
            <ul className="qm-lin-em-reasoning-list">
              {em.reasoning.problems.map((p, i) => (
                <li key={i}>
                  <span className="qm-lin-em-reasoning-bullet" aria-hidden />
                  {p.description}
                  <span className="qm-lin-em-reasoning-tag">({p.status})</span>
                </li>
              ))}
            </ul>
          )}
        </div>
        <div>
          <div className="qm-lin-em-reasoning-label">Data reviewed</div>
          <div className="qm-lin-em-reasoning-value">
            {em.reasoning.data || (
              <span className="qm-lin-em-reasoning-empty">Not documented.</span>
            )}
          </div>
        </div>
        <div>
          <div className="qm-lin-em-reasoning-label">Risk</div>
          <div
            className="qm-lin-em-reasoning-value"
            style={{ color: riskColor, textTransform: 'capitalize' }}
          >
            {em.reasoning.risk}
          </div>
        </div>
      </div>
    </div>
  );
}

function TotalsStrip({
  totalCodes,
  proceduresCount,
}: {
  totalCodes: number;
  proceduresCount: number;
}) {
  return (
    <div className="qm-lin-codes-totals-strip">
      <span>
        Total · {totalCodes} code{totalCodes === 1 ? '' : 's'}
      </span>
      <span>
        Procedure{proceduresCount === 1 ? '' : 's'} ·{' '}
        <span className="v">{proceduresCount}</span>
      </span>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Atoms
// ---------------------------------------------------------------------------

function ConfidenceBar({ value }: { value: number }) {
  const pct = Math.max(0, Math.min(1, value));
  const isLow = pct < 0.7;
  return (
    <span
      className={cn('qm-lin-codes-conf', isLow && 'qm-lin-codes-conf-low')}
      style={{ ['--qm-conf-w' as string]: `${(pct * 100).toFixed(0)}%` }}
    >
      <span className="qm-lin-codes-conf-bar" aria-hidden />
      <span className="qm-lin-codes-conf-v">{(pct * 100).toFixed(0)}%</span>
    </span>
  );
}

function SortArrow({
  active,
  dir,
}: {
  active: boolean;
  dir: 'asc' | 'desc';
}) {
  if (!active) {
    return (
      <span className="qm-lin-codes-sort-arrow" aria-hidden>
        ·
      </span>
    );
  }
  return (
    <span className="qm-lin-codes-sort-arrow active" aria-hidden>
      {dir === 'asc' ? '▲' : '▼'}
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

// React doesn't allow direct fragments inside <tbody> across rows when the
// child key needs to bubble up. Wrap each (row + expand-row) pair so we
// can keep keyed siblings.
function RowGroup({
  children,
}: {
  children: React.ReactNode;
}) {
  return <>{children}</>;
}

function truncate(s: string, max: number): string {
  if (!s) return s;
  if (s.length <= max) return s;
  return s.slice(0, max - 1).trimEnd() + '…';
}

// ---------------------------------------------------------------------------
// Exported helper kept for back-compat with the visit-ready-view.
// ---------------------------------------------------------------------------

export function codesTabHasWarnings(confidenceScores: unknown): boolean {
  const cs =
    (confidenceScores as Record<string, { status?: string }> | null) ?? {};
  return (
    cs.icd_coding?.status === 'failed' || cs.cpt_coding?.status === 'failed'
  );
}
