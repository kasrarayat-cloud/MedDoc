'use client';

// ============================================================================
// SoapEditor — visit-detail SOAP note pane (Phase 5.2 v6 Coding Coach).
// ----------------------------------------------------------------------------
// Mockup: docs/design-directions-v10-soap/soap-v6.html (left + right column).
//
// LAYOUT — 1fr / 340 px grid (.qm-lin-coach-grid). The left column is the
// new <SoapBody> (4 hairline-bordered S/O/A/P section blocks + bottom
// action strip). The right column is a SLOT that hosts <CodingRail> —
// owned by Subagent C. Subagent A renders the rail with a
// minimum-surface contract; Subagent C's branch widens it.
//
// At ≤1080 px the grid collapses to a single column (.qm-lin-coach-grid
// media query) and Subagent C's CodingRail handles its own bottom-drawer
// behaviour.
//
// PRESERVED CONTRACTS:
//   - saveSoapDraftAction(visitId, text) — server action unchanged
//   - SignAndSendModal trigger — unchanged
//   - signedAt gate — unchanged (Batch H)
//   - readonly behaviour — unchanged
//   - The single soapFinal markdown text remains the source of truth;
//     edits go to a textarea (full markdown blob) and persist back as
//     one blob, byte-identical to before.
//
// V3 "Sources rail" code path is DROPPED — v6 puts the source/transcript
// surface on the dedicated Transcript tab, which already has its own V3
// split-pane. The legacy `sources` prop is kept on the interface as
// optional so callers (visit-ready-view) compile without churn during
// the Phase 5.2 stage rollout.
// ============================================================================

import { useCallback, useMemo, useState, useTransition } from 'react';
import { Lock, Send } from 'lucide-react';
import { toast } from 'sonner';

import { saveSoapDraftAction } from '@/actions/soap';
import { parseSoapSections, type SoapSectionKey } from '@/lib/parse-soap-sections';
import { CodingRail, type CodingRailEmScore } from '@/components/visits/CodingRail';
import { SoapBody } from './soap/SoapBody';
import type { SoapPulseHint, SoapSectionStatus } from './soap/SoapSection';
import { SignAndSendModal } from './sign-and-send-modal';

type SoapEditorTheme = 'legacy' | 'clinician';

/** Source-rail entry — kept on the interface for caller back-compat
 *  (visit-ready-view still computes `soapSources` from utterances).
 *  v6 no longer renders these in the SOAP pane; the Transcript tab is
 *  where transcript turns live. */
export interface SoapSource {
  id: string;
  speaker: string;
  timestamp: string;
  text: string;
  isDoctor: boolean;
}

interface SoapEditorProps {
  visitId: string;
  /** Doctor's email — pre-filled in the Sign & Send modal. */
  doctorEmail: string;
  /** T-M9 — whether Email delivery is configured. */
  emailEnabled: boolean;
  initialText: string;
  /** Readonly when the visit is SIGNED. The signed copy lives in
   *  signedSoap; the client passes that value as initialText. */
  readonly?: boolean;
  /** Batch H — ISO 8601 UTC moment the doctor signed the note. */
  signedAt?: string | null;
  /** Phase 5.1 — kept for caller back-compat; v6 ignores. */
  sources?: SoapSource[];
  /** Phase 5.2 — initial E&M score from server-side scoring. Optional;
   *  when null the rail renders in fail-soft mode (Subagent B owns the
   *  scoring engine; Subagent C consumes it). */
  initialScore?: CodingRailEmScore | null;
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
  initialScore = null,
}: SoapEditorProps) {
  const [text, setText] = useState(initialText);
  const [, startSaving] = useTransition();
  // Subagent C will wire boost hints via this state; Subagent A just
  // exposes the API. The CodingRail stub doesn't call it — once
  // Subagent C lands their branch, their <CodingRail> invokes
  // `onBoostHintsChange` with per-section hints and the body re-renders
  // with sage/amber pulse dots in the section heads.
  const [boostHints, setBoostHints] = useState<
    Partial<Record<SoapSectionKey, SoapPulseHint>>
  >({});

  // Batch H — signedAt is the canonical signal that the note is locked,
  // independent of how the lifecycle status enum was set. A signed
  // visit MUST NOT show the Sign & Send CTA — that's the clinical-
  // safety bug Batch H exists to fix.
  const isSigned = signedAt !== null;
  const isReadonly = readonly || isSigned;

  // Parse once for status-pill computation; <SoapBody> re-parses for
  // its own render but the cost is trivial and keeps responsibilities
  // localised.
  const sections = useMemo(() => parseSoapSections(text), [text]);
  const statusFor = useCallback(
    (key: SoapSectionKey): SoapSectionStatus => {
      if (isSigned) return 'signed';
      const sec = sections.find((s) => s.key === key);
      return sec && sec.body.trim() ? 'reviewed' : 'drafted';
    },
    [sections, isSigned]
  );

  /** PROTECTED CONTRACT — saveSoapDraftAction signature + behaviour
   *  must remain byte-identical to Phase 5.1. We wrap it once here so
   *  every section's inline-edit calls the same path. */
  const onEdit = useCallback(
    async (next: string): Promise<{ ok: boolean; error?: string }> => {
      return await new Promise<{ ok: boolean; error?: string }>((resolve) => {
        startSaving(async () => {
          const res = await saveSoapDraftAction(visitId, next);
          if (!res.ok) {
            toast.error('Save failed — try again', { description: res.error });
            resolve({ ok: false, error: res.error });
            return;
          }
          setText(next);
          resolve({ ok: true });
        });
      });
    },
    [visitId]
  );

  return (
    <div className="space-y-4">
      <div className="qm-lin-coach-grid">
        {/* LEFT — v6 SOAP body (4 section blocks + bottom strip). */}
        <SoapBody
          text={text}
          statusFor={statusFor}
          pulseHints={boostHints}
          onEdit={onEdit}
          readonly={isReadonly}
        />

        {/* RIGHT — Coding Rail slot. Subagent C replaces the stub with
            the real implementation at Stage 6 merge. */}
        <aside className="qm-lin-coding-rail-slot" aria-label="Billing support">
          <CodingRail
            emScore={initialScore}
            visitId={visitId}
            readonly={isReadonly}
            onBoostHintsChange={setBoostHints}
          />
        </aside>
      </div>

      {/* Bottom action bar — Sign & Send / Export-again.
          The Copy SOAP button moved INTO <SoapBody>'s notebody-foot,
          per the v6 mockup. */}
      <div className="flex flex-wrap items-center justify-end gap-2 border-t border-linear-hairline pt-4">
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
