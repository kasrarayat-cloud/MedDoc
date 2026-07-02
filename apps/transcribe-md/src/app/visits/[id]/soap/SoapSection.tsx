'use client';

// ============================================================================
// SoapSection — single S/O/A/P section block in the v6 SOAP body.
// ----------------------------------------------------------------------------
// Phase 5.2 — replaces the legacy SoapSectionBlock from Phase 5.1's V3
// split-pane. Layout adapts the v6 mockup (lines 178-249 of soap-v6.html):
//   - Hairline-bordered card on --surface-1 with 14/16 px padding
//   - Header row: letter chip + mono uppercase eyebrow + status pill
//   - Optional pulse hint (sage = ok / amber = boost-needed) — fed from
//     the engine via the parent SoapEditor; this component is pure UI.
//   - Body: Inter 14 px / 1.6 line-height. Inline edit affordance is
//     delegated to <SoapInlineEdit>.
//
// The pulseHint prop is OPTIONAL. Subagent C's CodingRail will eventually
// inform the parent SoapEditor of which sections are "boost-needed" via
// a callback; the parent threads that down to each section. Until that
// wiring lands, sections render without a pulse dot.
// ============================================================================

import { cn } from '@/lib/cn';
import { SoapInlineEdit } from './SoapInlineEdit';

export type SoapSectionStatus = 'drafted' | 'reviewed' | 'signed';

export interface SoapPulseHint {
  /** sage when this section's content satisfies its E&M criteria;
   *  amber when this section is the gating constraint for a higher
   *  E&M code (e.g. PFSH gap on Subjective). */
  tone: 'ok' | 'boost';
  /** Mono micro-meta — e.g. "HPI · 4 elements" or "MDM · moderate w/ gap". */
  text: string;
}

export interface SoapSectionProps {
  /** Eyebrow chip — canonical 'S'/'O'/'A'/'P', or the section number for
   *  custom-template / imaging sections (parse-note-sections). */
  letter: string;
  /** Section heading verbatim — canonical SOAP label, a doctor's custom
   *  template label, or an imaging-report section name. */
  label: string;
  /** Markdown / plain text body of just this section, for display. */
  body: string;
  /** Full SOAP markdown blob — passed through to SoapInlineEdit so the
   *  textarea operates on the whole soapFinal byte-identically. */
  fullText: string;
  status: SoapSectionStatus;
  /** Optional engine-fed micro-meta. Renders in the section header. */
  pulseHint?: SoapPulseHint | null;
  /** When true, applies the bump-highlight CSS class so this section
   *  shows a sage edge-glow that fades over ~2.5s. Drives the doctor's
   *  eye to the S/O/A/P block containing the gap criteria when the
   *  bump CTA is clicked. Parent (SoapEditor) toggles + auto-clears. */
  highlight?: boolean;
  /** Persists `next` (full SOAP blob) via saveSoapDraftAction. The
   *  parent SoapEditor owns the action call so error toasts remain
   *  centralised. */
  onEdit: (next: string) => Promise<{ ok: boolean; error?: string }>;
  readonly: boolean;
}

const STATUS_LABEL: Record<SoapSectionStatus, string> = {
  drafted: 'DRAFTED',
  reviewed: 'REVIEWED',
  signed: 'SIGNED',
};

const STATUS_PILL_CLASS: Record<SoapSectionStatus, string> = {
  drafted: 'qm-lin-pill--draft',
  reviewed: 'qm-lin-pill--sage',
  signed: 'qm-lin-pill--signed',
};

export function SoapSection({
  letter,
  label,
  body,
  fullText,
  status,
  pulseHint,
  highlight,
  onEdit,
  readonly,
}: SoapSectionProps) {
  return (
    <article
      className={cn(
        'qm-lin-soap-section-v6',
        highlight && 'qm-lin-soap-section-v6--highlight'
      )}
      data-section={letter}
    >
      <header className="qm-lin-soap-section-head">
        <div className="qm-lin-soap-section-head-left">
          <span className="qm-lin-soap-section-eyebrow">
            <span className="qm-lin-soap-section-letter">{letter}</span>
            <span className="lbl">{label.toUpperCase()}</span>
          </span>
          <span className={cn('qm-lin-pill', STATUS_PILL_CLASS[status])}>
            {STATUS_LABEL[status]}
          </span>
        </div>
        {pulseHint ? (
          <span
            className={cn(
              'qm-lin-soap-section-pulse',
              pulseHint.tone === 'boost' && 'qm-lin-soap-section-pulse--boost'
            )}
          >
            <span className="pulse-dot" aria-hidden />
            <span>{pulseHint.text}</span>
          </span>
        ) : null}
      </header>

      <SoapInlineEdit text={fullText} readonly={readonly} onSave={onEdit}>
        {body.trim() ? (
          <SoapMarkdown text={body} />
        ) : (
          <span className="qm-lin-soap-section-empty">{label} section is empty.</span>
        )}
      </SoapInlineEdit>
    </article>
  );
}

// ---------------------------------------------------------------------------
// SoapMarkdown — minimal markdown renderer (H1/H2/bullets/bold/paragraphs).
// Carried over from soap-editor.tsx Phase 5.1 unchanged so the rendered
// output matches the existing read-mode pixel-for-pixel where possible.
// We deliberately avoid a full markdown lib: clinicians rarely need
// tables/images here and a 30-line shim preserves bundle size.
// ---------------------------------------------------------------------------
function SoapMarkdown({ text }: { text: string }) {
  const lines = text.split('\n');
  const out: React.ReactNode[] = [];
  let listBuffer: string[] = [];
  let tableBuffer: string[] = [];
  const flushList = (k: number) => {
    if (listBuffer.length === 0) return;
    out.push(
      <ul key={`ul-${k}`} className="qm-lin-soap-md-ul">
        {listBuffer.map((l, i) => (
          <li key={i}>{renderInline(l)}</li>
        ))}
      </ul>
    );
    listBuffer = [];
  };
  // Structure-aware notes: consecutive GitHub-style pipe rows collect in
  // tableBuffer, then flush as a real <table>. Separator rows (|---|---|)
  // are dropped; the first remaining row becomes the header. Prose-only
  // notes never populate the buffer, so their output is byte-identical.
  const flushTable = (k: number) => {
    if (tableBuffer.length === 0) return;
    const rows = tableBuffer
      .filter((r) => !TABLE_SEPARATOR_ROW_RE.test(r))
      .map(splitTableRow);
    tableBuffer = [];
    if (rows.length === 0) return;
    const [header, ...body] = rows;
    out.push(
      // overflow-x scroll container must be keyboard-reachable
      // (axe scrollable-region-focusable)
      <div
        key={`tbl-${k}`}
        className="qm-lin-soap-md-table-wrap"
        tabIndex={0}
        role="region"
        aria-label={header.map((c) => c.replace(/⟦[\s\S]*?⟧/g, '').trim()).filter(Boolean).join(' / ') || 'Table'}
      >
        <table className="qm-lin-soap-md-table">
          <thead>
            <tr>
              {header.map((cell, i) => (
                <th key={i}>{renderInline(cell)}</th>
              ))}
            </tr>
          </thead>
          {body.length > 0 ? (
            <tbody>
              {body.map((cells, ri) => (
                <tr key={ri}>
                  {cells.map((cell, ci) => (
                    <td key={ci}>{renderInline(cell)}</td>
                  ))}
                </tr>
              ))}
            </tbody>
          ) : null}
        </table>
      </div>
    );
  };
  lines.forEach((raw, k) => {
    const l = raw.trimEnd();
    // Table rows buffer until the first non-pipe line ends the run.
    if (TABLE_ROW_RE.test(l)) {
      flushList(k);
      tableBuffer.push(l);
      return;
    }
    flushTable(k);
    // ### sub-headings (F-9): parse-note-sections folds them into the parent
    // section body (ultrasound `### Right`/`### Left`), so render them as
    // sub-heads instead of literal `###` text. Checked before `## `.
    if (l.startsWith('### ')) {
      flushList(k);
      out.push(
        <h3 key={k} className="qm-lin-soap-md-h2">
          {l.slice(4)}
        </h3>
      );
      return;
    }
    if (l.startsWith('## ')) {
      flushList(k);
      out.push(
        <h2 key={k} className="qm-lin-soap-md-h2">
          {l.slice(3)}
        </h2>
      );
      return;
    }
    if (l.startsWith('# ')) {
      flushList(k);
      out.push(
        <h1 key={k} className="qm-lin-soap-md-h1">
          {l.slice(2)}
        </h1>
      );
      return;
    }
    // Task-list rows (- [x] / - [ ] / * [x]) — checked BEFORE the bullet
    // branch so they don't render as disc bullets with literal brackets.
    const task = l.match(TASK_LINE_RE);
    if (task) {
      flushList(k);
      const checked = task[1].toLowerCase() === 'x';
      out.push(
        <div key={k} className="qm-lin-soap-md-task">
          {/* Checked state must survive screen readers: ballot glyphs are
              skipped by some SR punctuation settings, so the glyph is
              aria-hidden and an sr-only prefix carries the state. */}
          <span
            aria-hidden="true"
            className={cn(
              'qm-lin-soap-md-task-glyph',
              checked && 'qm-lin-soap-md-task-glyph--checked'
            )}
          >
            {checked ? '☒' : '☐'}
          </span>
          <span className="sr-only">{checked ? 'Checked:' : 'Not checked:'}</span>
          <span className="qm-lin-soap-md-task-text">{renderInline(task[2])}</span>
        </div>
      );
      return;
    }
    if (/^\s*[-*]\s+/.test(l)) {
      listBuffer.push(l.replace(/^\s*[-*]\s+/, ''));
      return;
    }
    flushList(k);
    if (l.trim() === '') {
      out.push(<div key={k} className="qm-lin-soap-md-spacer" />);
      return;
    }
    out.push(
      <p key={k} className="qm-lin-soap-md-p">
        {renderInline(l)}
      </p>
    );
  });
  flushList(lines.length);
  flushTable(lines.length);
  return <div className="qm-lin-soap-md">{out}</div>;
}

// Structure-aware note line shapes. A table row is any line that starts and
// ends with a pipe; a separator row is the |---|:---| divider under the
// header. Task lines are GitHub-style checklist items.
const TABLE_ROW_RE = /^\s*\|.*\|\s*$/;
const TABLE_SEPARATOR_ROW_RE = /^\s*\|[\s:|-]+\|\s*$/;
const TASK_LINE_RE = /^\s*[-*]\s+\[( |x|X)\]\s+(.*)$/;

/** `| a | b |` → `['a', 'b']` — trims the outer pipes + per-cell whitespace. */
function splitTableRow(line: string): string[] {
  return line
    .trim()
    .replace(/^\|/, '')
    .replace(/\|$/, '')
    .split('|')
    .map((c) => c.trim());
}

/** Inline markdown: **bold** only. Everything else renders verbatim. */
function renderInline(s: string): React.ReactNode {
  const parts = s.split(/(\*\*[^*]+\*\*)/g);
  return parts.map((p, i) =>
    p.startsWith('**') && p.endsWith('**') ? (
      <strong key={i}>{p.slice(2, -2)}</strong>
    ) : (
      <span key={i}>{p}</span>
    )
  );
}
