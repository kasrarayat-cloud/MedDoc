'use client';

// ============================================================================
// SoapEditor — visit-detail SOAP note editor pane (Phase 5.1 V3 Split Pane).
// ----------------------------------------------------------------------------
// Mockup: docs/design-directions-v9-tabs/soap-note-v3.html.
//
// LAYOUT — left ~62% / 1px hairline / right ~38%.
//   Left pane:  S / O / A / P sections stacked. Each section has a mono
//               eyebrow ("S · SUBJECTIVE"), an Inter title, a status pill,
//               and a click-target body block. Clicking a section makes
//               that section the "active" one; the right rail filters
//               its source list to the matching turns. A pencil hover
//               affordance reveals a "Click to edit" hint that opens a
//               raw-markdown textarea inline (legacy edit flow). Save
//               persists soapFinal via saveSoapDraftAction unchanged.
//   Right rail: Sources list. Each source is a 1-2 line excerpt with a
//               mono timestamp + speaker chip (sage when Doctor). Title
//               is "SOURCES · N TURNS". When `utterances` is empty (i.e.
//               voice_dictation / text_notes) we show an empty-state hint
//               and skip the right rail.
//
// CITATIONS FALLBACK — the SOAP schema is currently plain markdown; no
// per-section citation IDs are stored on the visit. Until that data
// model lands (TODO: Phase 5.2 schema extension), the right rail simply
// shows ALL transcript turns and the "active section" highlight is a
// visual cue only. The click handler is wired so once citation IDs land
// we just thread them in.
//
// PRESERVED CONTRACTS:
//   - saveSoapDraftAction(visitId, text) — server action unchanged
//   - SignAndSendModal trigger — unchanged
//   - signedAt gate — unchanged (Batch H)
//   - readonly behaviour — unchanged
//   - The single soapFinal markdown text remains the source of truth;
//     edits go to the textarea (full markdown) and persist back as one
//     blob, byte-identical to before.
// ============================================================================

import { useMemo, useState, useTransition } from 'react';
import { Lock, Loader2, Check, PencilLine, Send } from 'lucide-react';
import { toast } from 'sonner';

import { cn } from '@/lib/cn';
import { saveSoapDraftAction } from '@/actions/soap';
import { parseSoapSections, type SoapSection, type SoapSectionKey } from '@/lib/parse-soap-sections';
import { SignAndSendModal } from './sign-and-send-modal';

type SoapEditorTheme = 'legacy' | 'clinician';

/** Source-rail entry — abstracted from `Utterance` so this file doesn't
 *  pull in the worker speakerMap shape; the consumer adapts. */
export interface SoapSource {
  id: string;
  /** Display label, e.g. "Doctor", "Patient". */
  speaker: string;
  /** mm:ss timestamp string. */
  timestamp: string;
  /** 1-3 sentences of source text. */
  text: string;
  /** Whether this source counts as the doctor's voice (sage-tinted
   *  speaker chip). */
  isDoctor: boolean;
}

interface SoapEditorProps {
  visitId: string;
  /** Doctor's email — pre-filled in the Sign & Send modal. */
  doctorEmail: string;
  /** T-M9 — whether Email delivery is configured. Hides the checkbox
   *  from Sign & Send when false so users can't request an
   *  un-shippable destination. */
  emailEnabled: boolean;
  initialText: string;
  /** Readonly when the visit is SIGNED. The signed copy lives in
   *  signedSoap; the client passes that value as initialText. */
  readonly?: boolean;
  /** Batch H — ISO 8601 UTC moment the doctor signed the note, or
   *  null while still drafting. The Sign & Send CTA is hidden when
   *  this is set so a doctor can't re-sign a locked note. */
  signedAt?: string | null;
  /** Phase 5.1 — transcript turns shown in the right rail. Until the
   *  citations field lands, all turns are displayed regardless of
   *  active section. */
  sources?: SoapSource[];
  /** @deprecated kept for back-compat; Linear V1 is single-theme. */
  theme?: SoapEditorTheme;
}

export function SoapEditor({
  visitId,
  doctorEmail,
  emailEnabled,
  initialText,
  readonly = false,
  signedAt = null,
  sources = [],
}: SoapEditorProps) {
  const [text, setText] = useState(initialText);
  const [editing, setEditing] = useState(false);
  const [saving, startSaving] = useTransition();
  // Active section drives the right-rail filter. Subjective by default
  // because it's the section a doctor most often re-checks first.
  const [activeKey, setActiveKey] = useState<SoapSectionKey>('S');
  // Batch H — the signed-state visual gate. Used directly (over the
  // existing `readonly` flag) per the brief: signedAt is the canonical
  // signal that the note is locked, regardless of how the lifecycle
  // status enum was set. A signed visit MUST NOT show the Sign & Send
  // CTA — that's the clinical-safety bug Batch H exists to fix.
  const isSigned = signedAt !== null;

  const sections = useMemo(() => parseSoapSections(text), [text]);

  const onSave = () => {
    startSaving(async () => {
      const res = await saveSoapDraftAction(visitId, text);
      if (!res.ok) {
        toast.error('Could not save', { description: res.error });
        return;
      }
      toast.success('Saved');
      setEditing(false);
    });
  };

  // When editing, fall back to the textarea — same flow as Phase 5.
  if (editing && !readonly) {
    return (
      <div className="space-y-4">
        <textarea
          value={text}
          onChange={(e) => setText(e.target.value)}
          className="min-h-[40vh] w-full resize-y rounded-lg border border-linear-border bg-linear-surface-1 p-4 font-mono text-[13px] leading-relaxed text-linear-text outline-none focus:border-linear-sage focus:ring-2 focus:ring-linear-sage/30"
          aria-label="Edit SOAP note"
        />
        <div className="flex flex-wrap items-center justify-end gap-2">
          <button
            type="button"
            className="qm-lin-btn"
            onClick={() => {
              setEditing(false);
              setText(initialText);
            }}
            disabled={saving}
          >
            Cancel
          </button>
          <button
            type="button"
            className="qm-lin-btn-primary"
            onClick={onSave}
            disabled={saving}
          >
            {saving ? (
              <>
                <Loader2 className="h-3.5 w-3.5 animate-spin" aria-hidden />
                Saving…
              </>
            ) : (
              <>
                <Check className="h-3.5 w-3.5" aria-hidden />
                Save edits
              </>
            )}
          </button>
        </div>
      </div>
    );
  }

  // Display mode — V3 split pane.
  return (
    <div className="space-y-4">
      <div className="qm-lin-split">
        {/* LEFT — SOAP sections */}
        <div className="qm-lin-split-left">
          {sections.map((section) => (
            <SoapSectionBlock
              key={section.key}
              section={section}
              isActive={activeKey === section.key}
              isSigned={isSigned}
              readonly={readonly}
              onClick={() => setActiveKey(section.key)}
              onEdit={() => !readonly && setEditing(true)}
            />
          ))}
        </div>

        <div className="qm-lin-split-divider" aria-hidden />

        {/* RIGHT — Sources rail */}
        <aside className="qm-lin-split-right" aria-label="Source transcript turns">
          <SourcesRail
            sources={sources}
            sectionLabel={
              sections.find((s) => s.key === activeKey)?.label ?? 'Subjective'
            }
          />
        </aside>
      </div>

      {/* Bottom action bar — Sign & Send / Export-again. */}
      <div className="flex flex-wrap items-center justify-end gap-2 border-t border-linear-hairline pt-4">
        {!readonly && (
          <button
            type="button"
            className="qm-lin-btn"
            onClick={() => setEditing(true)}
          >
            <PencilLine className="h-3.5 w-3.5" aria-hidden />
            Edit markdown
          </button>
        )}

        {/* Batch H — the Sign & Send CTA renders ONLY when the visit
            is unsigned (signedAt == null). Once a note has a sign
            timestamp it's locked. */}
        {!readonly && !isSigned && (
          <SignAndSendModal
            visitId={visitId}
            doctorEmail={doctorEmail}
            emailEnabled={emailEnabled}
            signOnSubmit
            triggerLabel="Sign & Send"
            triggerIcon={<Lock className="h-3.5 w-3.5" aria-hidden />}
          />
        )}

        {/* Batch H — Export again stays available on signed visits
            so the doctor can still re-send a copy of the locked note. */}
        {(readonly || isSigned) && (
          <SignAndSendModal
            visitId={visitId}
            doctorEmail={doctorEmail}
            emailEnabled={emailEnabled}
            signOnSubmit={false}
            triggerLabel="Export again"
            triggerIcon={<Send className="h-3.5 w-3.5" aria-hidden />}
            triggerVariant="secondary"
          />
        )}
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// SoapSectionBlock — one of the four S/O/A/P blocks in the left pane.
// ---------------------------------------------------------------------------
function SoapSectionBlock({
  section,
  isActive,
  isSigned,
  readonly,
  onClick,
  onEdit,
}: {
  section: SoapSection;
  isActive: boolean;
  isSigned: boolean;
  readonly: boolean;
  onClick: () => void;
  onEdit: () => void;
}) {
  const status: 'reviewed' | 'drafted' | 'signed' = isSigned
    ? 'signed'
    : section.body.trim()
      ? 'reviewed'
      : 'drafted';

  return (
    <section className="qm-lin-soap-section" data-section={section.key}>
      <div className="qm-lin-soap-section-head">
        <div>
          <div className="qm-lin-soap-eyebrow">
            <span className="qm-lin-soap-letter">{section.letter}</span>
            <span>
              {section.key === 'S'
                ? '01'
                : section.key === 'O'
                  ? '02'
                  : section.key === 'A'
                    ? '03'
                    : '04'}{' '}
              · {section.label}
            </span>
          </div>
          <h3 className="qm-lin-soap-title">{section.label}</h3>
        </div>
        <span
          className={cn(
            'qm-lin-sec-status',
            status === 'reviewed' && 'qm-lin-sec-status--reviewed',
            status === 'drafted' && 'qm-lin-sec-status--drafted',
            status === 'signed' && 'qm-lin-sec-status--signed'
          )}
        >
          {status === 'reviewed'
            ? 'Reviewed'
            : status === 'drafted'
              ? 'Drafted'
              : 'Signed'}
        </span>
      </div>

      <button
        type="button"
        onClick={(e) => {
          // Section click selects the section; we only open the editor
          // via the explicit pencil affordance to avoid losing scroll
          // when toggling between sections.
          if ((e.target as HTMLElement).closest('[data-edit-affordance]')) {
            onEdit();
            return;
          }
          onClick();
        }}
        className={cn(
          'qm-lin-soap-body group block w-full text-left',
          isActive && 'qm-lin-soap-body--active'
        )}
        aria-pressed={isActive}
        aria-label={`${section.label} section`}
      >
        {section.body.trim() ? (
          <SoapMarkdown text={section.body} />
        ) : (
          <span className="text-linear-text-3 italic">
            {section.label} section is empty.
          </span>
        )}

        {!readonly && (
          <span
            data-edit-affordance
            className="mt-3 inline-flex items-center gap-1.5 font-mono text-[10px] uppercase tracking-[0.08em] text-linear-text-3 opacity-0 transition-opacity group-hover:opacity-100"
          >
            <PencilLine className="h-3 w-3" aria-hidden />
            Click to edit
          </span>
        )}
      </button>
    </section>
  );
}

// ---------------------------------------------------------------------------
// SourcesRail — the right pane. Until the SOAP citation field lands the
// rail shows all turns; the active-section banner up top still updates.
// ---------------------------------------------------------------------------
function SourcesRail({
  sources,
  sectionLabel,
}: {
  sources: SoapSource[];
  sectionLabel: string;
}) {
  return (
    <>
      <div className="qm-lin-rail-head">
        <span className="qm-lin-rail-title">Sources</span>
        <span className="qm-lin-rail-meta">
          {sources.length} turn{sources.length === 1 ? '' : 's'}
        </span>
      </div>

      <div className="mb-3 font-mono text-[10px] uppercase tracking-[0.1em] text-linear-text-3">
        Active · {sectionLabel}
      </div>

      {sources.length === 0 ? (
        <div className="rounded-md border border-dashed border-linear-border p-4 text-center font-mono text-[10px] uppercase tracking-[0.1em] text-linear-text-3">
          No transcript turns
        </div>
      ) : (
        <div>
          {sources.map((s) => (
            <div key={s.id} className="qm-lin-source-card">
              <div className="qm-lin-source-meta">
                <span className="qm-lin-source-time">{s.timestamp}</span>
                <span
                  className={cn(
                    'qm-lin-source-speaker',
                    s.isDoctor && 'qm-lin-source-speaker--doctor'
                  )}
                >
                  {s.speaker}
                </span>
              </div>
              <div className="qm-lin-source-text">{s.text}</div>
            </div>
          ))}
        </div>
      )}
    </>
  );
}

/** Very lightweight markdown renderer — bold, headings, bullets, line
 *  breaks. We deliberately avoid a full library: clinicians rarely
 *  need tables/images here and a 30-line shim preserves bundle size.
 *  Linear V1 — Inter for prose, JetBrains Mono for the H2 eyebrow. */
function SoapMarkdown({ text }: { text: string }) {
  const lines = text.split('\n');
  const out: React.ReactNode[] = [];
  let listBuffer: string[] = [];
  const flushList = (k: number) => {
    if (listBuffer.length === 0) return;
    out.push(
      <ul
        key={`ul-${k}`}
        className="my-2 list-disc space-y-1 pl-5 text-[14px] text-linear-text-2"
      >
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
        <h2
          key={k}
          className="mt-4 font-mono text-[10.5px] font-medium uppercase tracking-[0.07em] text-linear-sage-bright"
        >
          {l.slice(3)}
        </h2>
      );
      return;
    }
    if (l.startsWith('# ')) {
      flushList(k);
      out.push(
        <h1
          key={k}
          className="mt-4 text-[16px] font-semibold tracking-tight text-linear-text"
        >
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
      out.push(<div key={k} className="h-2" />);
      return;
    }
    out.push(
      <p
        key={k}
        className="text-[14px] leading-relaxed text-linear-text"
      >
        {renderInline(l)}
      </p>
    );
  });
  flushList(lines.length);
  return <div className="space-y-0.5">{out}</div>;
}

/** Inline markdown: **bold** only. Everything else stays verbatim. */
function renderInline(s: string): React.ReactNode {
  const parts = s.split(/(\*\*[^*]+\*\*)/g);
  return parts.map((p, i) =>
    p.startsWith('**') && p.endsWith('**') ? (
      <strong key={i} className="font-semibold text-linear-text">
        {p.slice(2, -2)}
      </strong>
    ) : (
      <span key={i}>{p}</span>
    )
  );
}
