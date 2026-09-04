'use client';

// ============================================================================
// SoapBody — left pane of the v6 Coding Coach grid.
// ----------------------------------------------------------------------------
// Phase 5.2 — replaces the legacy V3 split-pane "left side". Renders the
// four SOAP sections stacked + the bottom action strip (last-edit meta +
// Copy SOAP ghost button).
//
// This is a *display* component — all state (SOAP text, save flow, boost
// hints) lives in the parent <SoapEditor>. SoapBody just threads props
// down to each <SoapSection>.
// ============================================================================

import { Fragment, useMemo } from 'react';
import { Copy } from 'lucide-react';
import { toast } from 'sonner';
import { reportClipboardCopy } from '@/lib/clipboard-audit';

import { parseNoteSections, type NoteSection } from '@/lib/parse-note-sections';
import type { SoapSectionKey } from '@/lib/parse-soap-sections';
import { SoapSection, type SoapPulseHint, type SoapSectionStatus } from './SoapSection';

export interface SoapBodyProps {
  /** Full SOAP markdown blob — single source of truth, persisted byte-
   *  identically via saveSoapDraftAction. */
  text: string;
  /** Per-section status pill content; the parent computes from signedAt
   *  + body emptiness. Custom/imaging sections have no canonical SOAP key —
   *  the parent receives (null, body) and decides from the body alone. */
  statusFor: (key: SoapSectionKey | null, body?: string) => SoapSectionStatus;
  /** Per-section engine pulse hints (sage = ok, amber = boost-needed).
   *  Optional — sections render without a hint when missing. */
  pulseHints?: Partial<Record<SoapSectionKey, SoapPulseHint>>;
  /** Sections currently flashing the bump-CTA highlight. The parent
   *  flips this on bump-click and clears after the fade. Optional —
   *  no highlights when omitted. */
  highlightedSections?: SoapSectionKey[];
  /** Persists the full new SOAP blob; parent owns the saveSoapDraftAction
   *  call so error toasts stay centralised. */
  onEdit: (next: string) => Promise<{ ok: boolean; error?: string }>;
  readonly: boolean;
  /** Optional slot rendered directly BELOW a section's body, inside the same
   *  column. The pre-sign document view uses it to place a verifier-demoted
   *  claim where it would land if accepted, so reading the note and reviewing
   *  the suggestion are one act. Omitted everywhere else — the note renders
   *  byte-for-byte what it renders today. */
  afterSection?: (section: NoteSection) => React.ReactNode;
  /** Visit this note belongs to — required so the full-note copy can be
   *  audited as a PHI disclosure (S4b). */
  visitId: string;
  /** Pretty-printed last edit time — e.g. "4m ago". Optional; the foot
   *  shows just the section count when absent. */
  lastEditLabel?: string | null;
}

export function SoapBody({
  visitId,
  text,
  statusFor,
  pulseHints,
  highlightedSections,
  onEdit,
  readonly,
  lastEditLabel,
  afterSection,
}: SoapBodyProps) {
  // Custom-template + imaging notes render their OWN headings; classic SOAP
  // notes render byte-identically to the legacy parseSoapSections output
  // (custom-template QA 2026-07-02, finding F-1).
  const sections = useMemo(() => parseNoteSections(text), [text]);
  const highlightSet = useMemo(
    () => new Set(highlightedSections ?? []),
    [highlightedSections]
  );

  const onCopy = async () => {
    try {
      await navigator.clipboard.writeText(text);
      // Post-resolve only — see clipboard-audit.ts.
      reportClipboardCopy(visitId, 'full_note', 'Full note', text);
      toast.success('SOAP copied');
    } catch {
      toast.error('Copy failed — try again');
    }
  };

  return (
    /* C2-b — THE DEFAULT PAPER'S TYPE, finally worn.
       `docs/design-tokens.md` is the authority and says Source Serif 4 covers
       "ALL clinical prose, including the default QuillMD paper template", at
       15–16.5px/1.7. `.rounds-clinical` has carried exactly that since the
       tokens landed and had ZERO consumers — declared, never applied.

       This is the node: SoapBody is the clinical prose. The class is
       unconditional because every `.rounds-clinical` declaration is
       `[data-skin='rounds']`-scoped, so with the flag off it is inert.

       ⚠️ CORRECTED 2026-09-03, OWNER-REPORTED. This comment used to read
       "under Rounds it renders inside `.rounds-paper`, which is why the rule's
       `--rounds-ink` (dark) is the right colour here". THAT PREMISE WAS FALSE.
       `.rounds-paper` has exactly one consumer in the app — the signed document
       in `components/rounds/signed.tsx` — and this view is not inside it. The
       section card `.qm-lin-soap-section-v6` paints `--color-linear-surface-1`
       (#0d0e10) underneath, so the prose rendered #191e26 on #0d0e10:
       **1.15:1**, unreadable, and it stood for a month.

       `.rounds-clinical` no longer carries a colour at all — a font/size/
       leading class cannot know what surface it will be laid on. The ink comes
       from the SURFACE now: `.qm-lin-soap-body-v6` binds the dark-surface
       token, and `.rounds-paper` sets paper ink on itself. This class is kept
       here for the TYPE, which is what it was always for. */
    <div className="qm-lin-soap-body-v6 rounds-clinical">
      {sections.map((section) => {
        const node = (
          <SoapSection
            letter={section.letter}
            label={section.label}
            body={section.body}
            fullText={text}
            status={
              section.soapKey
                ? statusFor(section.soapKey)
                : statusFor(null, section.body)
            }
            pulseHint={section.soapKey ? pulseHints?.[section.soapKey] ?? null : null}
            highlight={section.soapKey ? highlightSet.has(section.soapKey) : false}
            onEdit={onEdit}
            readonly={readonly}
          />
        );
        // No slot → render EXACTLY what this component has always rendered.
        // Wrapping unconditionally would change the DOM of every surface that
        // does not use the slot, which is the opposite of what "additive" means.
        if (!afterSection) return <Fragment key={section.id}>{node}</Fragment>;
        return (
          <div key={section.id} className="qm-lin-soap-section-slot">
            {node}
            {afterSection(section)}
          </div>
        );
      })}

      <div className="qm-lin-soap-notebody-foot">
        <div className="qm-lin-soap-notebody-foot-meta">
          <span className="dot" aria-hidden />
          <span>
            {sections.length} section{sections.length === 1 ? '' : 's'}
            {lastEditLabel ? ` · last edit ${lastEditLabel}` : ''}
          </span>
        </div>
        <button type="button" className="qm-lin-btn" onClick={onCopy}>
          <Copy className="h-3.5 w-3.5" aria-hidden />
          Copy SOAP
        </button>
      </div>
    </div>
  );
}
