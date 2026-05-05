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
import type { SoapSectionKey } from '@/lib/parse-soap-sections';

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
  letter: SoapSectionKey;
  label: 'Subjective' | 'Objective' | 'Assessment' | 'Plan';
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
  lines.forEach((raw, k) => {
    const l = raw.trimEnd();
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
  return <div className="qm-lin-soap-md">{out}</div>;
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
