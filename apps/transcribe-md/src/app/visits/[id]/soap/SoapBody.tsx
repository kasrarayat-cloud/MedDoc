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

import { useMemo } from 'react';
import { Copy } from 'lucide-react';
import { toast } from 'sonner';

import { parseSoapSections, type SoapSectionKey } from '@/lib/parse-soap-sections';
import { SoapSection, type SoapPulseHint, type SoapSectionStatus } from './SoapSection';

export interface SoapBodyProps {
  /** Full SOAP markdown blob — single source of truth, persisted byte-
   *  identically via saveSoapDraftAction. */
  text: string;
  /** Per-section status pill content; the parent computes from signedAt
   *  + body emptiness. */
  statusFor: (key: SoapSectionKey) => SoapSectionStatus;
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
  /** Pretty-printed last edit time — e.g. "4m ago". Optional; the foot
   *  shows just the section count when absent. */
  lastEditLabel?: string | null;
}

export function SoapBody({
  text,
  statusFor,
  pulseHints,
  highlightedSections,
  onEdit,
  readonly,
  lastEditLabel,
}: SoapBodyProps) {
  const sections = useMemo(() => parseSoapSections(text), [text]);
  const highlightSet = useMemo(
    () => new Set(highlightedSections ?? []),
    [highlightedSections]
  );

  const onCopy = async () => {
    try {
      await navigator.clipboard.writeText(text);
      toast.success('SOAP copied');
    } catch {
      toast.error('Copy failed — try again');
    }
  };

  return (
    <div className="qm-lin-soap-body-v6">
      {sections.map((section) => (
        <SoapSection
          key={section.key}
          letter={section.letter}
          label={section.label}
          body={section.body}
          fullText={text}
          status={statusFor(section.key)}
          pulseHint={pulseHints?.[section.key] ?? null}
          highlight={highlightSet.has(section.key)}
          onEdit={onEdit}
          readonly={readonly}
        />
      ))}

      <div className="qm-lin-soap-notebody-foot">
        <div className="qm-lin-soap-notebody-foot-meta">
          <span className="dot" aria-hidden />
          <span>
            4 sections{lastEditLabel ? ` · last edit ${lastEditLabel}` : ''}
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
