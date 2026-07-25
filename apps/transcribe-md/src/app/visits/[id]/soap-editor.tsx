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

import { useCallback, useEffect, useMemo, useRef, useState, useTransition } from 'react';
import { Lock, Send } from 'lucide-react';
import { toast } from 'sonner';

import { saveSoapDraftAction } from '@/actions/soap';
import { parseSoapSections, type SoapSectionKey } from '@/lib/parse-soap-sections';
import { placeholderSections } from '@/lib/parse-note-sections';
import { PlaceholderAdvisoryDialog } from '@/components/placeholder-advisory-dialog';
import { isSkinBeta } from '@/config/skin-beta';
import { CodingRail } from '@/components/visits/CodingRail';
import { CodingRailSkeleton } from '@/components/visits/CodingRailSkeleton';
import type {
  EmCode,
  EmScore,
  SoapSectionKey as EmSoapSectionKey,
} from '@/lib/em-coding-ui/types';
import { SoapBody } from './soap/SoapBody';
import type { SoapPulseHint, SoapSectionStatus } from './soap/SoapSection';
import { SignAndSendModal } from './sign-and-send-modal';

/** Engine `SoapSectionKey` (long form: 'subjective' | …) → the SOAP
 *  body's letter-form key ('S' | 'O' | 'A' | 'P'). The two key sets
 *  exist for historical reasons (parser uses letters; em-coding-ui
 *  predates that). */
const EM_KEY_TO_LETTER: Record<EmSoapSectionKey, SoapSectionKey> = {
  subjective: 'S',
  objective: 'O',
  assessment: 'A',
  plan: 'P',
};

/** EmCriterion id prefix → SOAP section letter. Mirrors
 *  `lib/em-coding/criterion-to-section.ts`'s table; inline here so the
 *  bump-CTA highlight handler stays self-contained. */
const CRITERION_TO_SECTION: Record<string, SoapSectionKey> = {
  'hpi.elements': 'S',
  'ros.systems': 'S',
  'pfsh.categories': 'S',
  'exam.systems': 'O',
  'mdm.problems': 'A',
  'mdm.data': 'P',
  'mdm.risk': 'A',
};

/** Length of the highlight pulse on bump-CTA click — long enough for
 *  the doctor's eye to land on the section, short enough that it
 *  doesn't linger as background visual noise. */
const HIGHLIGHT_DURATION_MS = 2500;

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
  /**
   * Round 3 PR-E (A09-P0-003) — optimistic-concurrency token. The
   * server-side RSC loads `transcribe_visits.soapVersion` and passes
   * it here. We track it client-side, send with each save, and bump
   * on success. A conflict response triggers a "another edit
   * happened — reload to see" toast.
   */
  initialSoapVersion: number;
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
  initialScore?: EmScore | null;
  /** E/M visible-confirm (prod smoke #311) — unacknowledged suggestion-
   *  caused level change for the Sign & Send modal's confirm control.
   *  Null/undefined = nothing to confirm. */
  emPendingChange?: { from: string; to: string } | null;
  /** V2 tabbed review (skin-only, flag-gated) — when true, render the note
   *  body ONLY and suppress this editor's own bottom action bar (the E/M chip
   *  + the Sign & Send / Export-again modal). The V2 shell hosts the ONE Sign
   *  action in its persistent bottom bar instead (same SignAndSendModal, same
   *  gate, same props). Presentation-only: no save/sign/E-M logic changes. */
  chromeless?: boolean;
  /** @deprecated kept for back-compat; Linear V1 is single-theme. */
  theme?: SoapEditorTheme;
}

export function SoapEditor({
  visitId,
  doctorEmail,
  emailEnabled,
  initialText,
  initialSoapVersion,
  readonly = false,
  signedAt = null,
  initialScore = null,
  emPendingChange = null,
  chromeless = false,
}: SoapEditorProps) {
  const [text, setText] = useState(initialText);
  const [soapVersion, setSoapVersion] = useState(initialSoapVersion);
  const [, startSaving] = useTransition();
  // Phase 5.2 stub completion — lifted SignAndSendModal open state.
  // Both the bottom-action "Sign & Send" Dialog.Trigger and the
  // CodingRail "Confirm <code> · sign" button drive this single
  // controlled state; the modal honors `controlledOpen` when these
  // are passed in. Pre-fix the rail dispatched a `qm:request-sign`
  // window event that no listener consumed.
  const [signModalOpen, setSignModalOpen] = useState(false);
  // F-7 (2026-07-02): every open request funnels through requestSignOpen —
  // sections still carrying the verifier's set-aside placeholder get an
  // ADVISORY confirm before the sign modal (server sign route unchanged;
  // the fail-closed gates stay the authority). Detection runs on the LIVE
  // client text (`text` state), so an inline edit that removes the
  // placeholder clears the advisory immediately.
  const [signAdvisoryOpen, setSignAdvisoryOpen] = useState(false);
  const requestSignOpen = useCallback(
    (next: boolean) => {
      if (next && placeholderSections(text).length > 0) {
        setSignAdvisoryOpen(true);
        return;
      }
      setSignModalOpen(next);
    },
    [text]
  );
  // Local mirror of the rail's score so apply-additions / override
  // responses can update the rail-rendered tier without a full page
  // reload. The initial value is the server-rendered score; the rail's
  // internal useEffect re-syncs from props when the parent re-renders.
  const [emScore, setEmScore] = useState<EmScore | null>(initialScore);
  useEffect(() => {
    setEmScore(initialScore);
  }, [initialScore]);

  // Boost hints — pure derived value from emScore.sectionPulseHints.
  // Phase 5.2 originally used a `qm:em-boost-hints` window CustomEvent
  // for this; the listener was orphan because no dispatcher existed.
  // The score's sectionPulseHints field carries the same data and
  // already round-trips through engineToUiScore (server-rendered + on
  // every rescore), so the UI just reads it directly. Translate from
  // the engine's long-form keys to the SOAP body's letter-form keys.
  const boostHints = useMemo<
    Partial<Record<SoapSectionKey, SoapPulseHint>>
  >(() => {
    const lean = emScore?.sectionPulseHints;
    if (!lean) return {};
    const out: Partial<Record<SoapSectionKey, SoapPulseHint>> = {};
    for (const [emKey, tone] of Object.entries(lean) as Array<
      [EmSoapSectionKey, 'ok' | 'boost']
    >) {
      const letter = EM_KEY_TO_LETTER[emKey];
      if (!letter) continue;
      out[letter] = {
        tone,
        text: tone === 'boost' ? 'gap to next tier' : 'criteria satisfied',
      };
    }
    return out;
  }, [emScore?.sectionPulseHints]);

  // Highlighted sections — flashed when the doctor clicks the bump CTA
  // so they can see at a glance which S/O/A/P block contains the
  // missing criteria. Auto-clears after HIGHLIGHT_DURATION_MS.
  const [highlightedSections, setHighlightedSections] = useState<
    SoapSectionKey[]
  >([]);
  const highlightTimerRef = useRef<number | null>(null);
  const handleHighlightCriteria = useCallback(
    (criterionIds: string[]) => {
      if (typeof window === 'undefined') return;
      const targets = new Set<SoapSectionKey>();
      for (const id of criterionIds) {
        const section = CRITERION_TO_SECTION[id];
        if (section) targets.add(section);
      }
      if (targets.size === 0) return;
      setHighlightedSections(Array.from(targets));
      if (highlightTimerRef.current !== null) {
        window.clearTimeout(highlightTimerRef.current);
      }
      highlightTimerRef.current = window.setTimeout(() => {
        highlightTimerRef.current = null;
        setHighlightedSections([]);
      }, HIGHLIGHT_DURATION_MS);
    },
    []
  );
  useEffect(() => {
    return () => {
      if (typeof window !== 'undefined' && highlightTimerRef.current !== null) {
        window.clearTimeout(highlightTimerRef.current);
        highlightTimerRef.current = null;
      }
    };
  }, []);

  // Override persistence — calls the new POST /em-score/override route
  // and threads the refreshed score back into local state. The rail's
  // success/failure toast handling lives inside CodingRail itself.
  const handleApplyOverride = useCallback(
    async (
      code: EmCode,
      reason?: string
    ): Promise<{ ok: boolean; error?: string; newScore?: EmScore }> => {
      try {
        const res = await fetch(
          `/api/visits/${visitId}/em-score/override`,
          {
            method: 'POST',
            headers: { 'content-type': 'application/json' },
            body: JSON.stringify({ overrideToCode: code, reason }),
          }
        );
        if (!res.ok) {
          const body = (await res.json().catch(() => ({}))) as {
            error?: string;
          };
          return {
            ok: false,
            error: body.error ?? `Override failed (${res.status}).`,
          };
        }
        const data = (await res.json()) as {
          ok: boolean;
          newScore?: EmScore;
        };
        if (data.ok && data.newScore) {
          setEmScore(data.newScore);
        }
        return { ok: data.ok, newScore: data.newScore };
      } catch (err) {
        return {
          ok: false,
          error:
            err instanceof Error
              ? err.message
              : 'Network error applying override.',
        };
      }
    },
    [visitId]
  );

  // Batch H — signedAt is the canonical signal that the note is locked,
  // independent of how the lifecycle status enum was set. A signed
  // visit MUST NOT show the Sign & Send CTA — that's the clinical-
  // safety bug Batch H exists to fix.
  const isSigned = signedAt !== null;
  const isReadonly = readonly || isSigned;

  // Parse once for status-pill computation; <SoapBody> re-parses for
  // its own render but the cost is trivial and keeps responsibilities
  // localised. Custom-template/imaging sections have no canonical SOAP
  // key — SoapBody passes (null, body) and the pill derives from the
  // body alone (parse-note-sections, finding F-1).
  const sections = useMemo(() => parseSoapSections(text), [text]);
  const statusFor = useCallback(
    (key: SoapSectionKey | null, body?: string): SoapSectionStatus => {
      if (isSigned) return 'signed';
      if (key === null) return body && body.trim() ? 'reviewed' : 'drafted';
      const sec = sections.find((s) => s.key === key);
      return sec && sec.body.trim() ? 'reviewed' : 'drafted';
    },
    [sections, isSigned]
  );

  /** PROTECTED CONTRACT — saveSoapDraftAction signature evolved in
   *  Round 3 PR-E to accept an optional `expectedVersion` for
   *  optimistic concurrency (A09-P0-003). The wrapper keeps the
   *  per-section onEdit shape identical for callers; conflict-handling
   *  is internal. */
  const onEdit = useCallback(
    async (next: string): Promise<{ ok: boolean; error?: string }> => {
      return await new Promise<{ ok: boolean; error?: string }>((resolve) => {
        startSaving(async () => {
          const res = await saveSoapDraftAction(visitId, next, soapVersion);
          if (!res.ok) {
            // Conflict-shape result: another save landed first. Show a
            // distinct toast and offer reload — do NOT silently
            // overwrite the conflicting copy.
            if (res.error === 'conflict' && res.conflict) {
              toast.error(
                'Another edit happened on this note — reload to see the latest version before saving again.',
                {
                  description: 'Your unsaved changes are still in this tab; reloading will replace them.',
                  action: {
                    label: 'Reload',
                    onClick: () => window.location.reload(),
                  },
                  duration: 10_000,
                }
              );
              resolve({ ok: false, error: 'conflict' });
              return;
            }
            toast.error('Save failed — try again', { description: res.error });
            resolve({ ok: false, error: res.error });
            return;
          }
          setText(next);
          if (res.newVersion !== undefined) setSoapVersion(res.newVersion);
          resolve({ ok: true });
        });
      });
    },
    [visitId, soapVersion]
  );

  // C3 billing-simplify (flag-gated): the dense permanent coding rail moves
  // into the review drawer (BillingCardC3) and a calm confirm chip sits next to
  // Sign, so the note runs FULL-WIDTH (fixes the cramped narrow-viewport rail).
  // SKIN-ONLY: only the rail's PRESENTATION location changes; the Sign & Send
  // modal + the emPendingChange E/M confirm gate below are untouched. Flag OFF
  // → the original 1fr/340px rail layout renders verbatim.
  const c3 = isSkinBeta();
  const displayedEmCode = emScore
    ? emScore.override?.code ?? emScore.suggestedCode
    : null;

  return (
    <div className="space-y-4">
      <div className={c3 ? 'qm-lin-coach-grid qm-lin-coach-grid--solo' : 'qm-lin-coach-grid'}>
        {/* LEFT — v6 SOAP body (4 section blocks + bottom strip). */}
        <SoapBody
          visitId={visitId}
          text={text}
          statusFor={statusFor}
          pulseHints={boostHints}
          highlightedSections={highlightedSections}
          onEdit={onEdit}
          readonly={isReadonly}
        />

        {/* RIGHT — Coding Rail slot. Phase 5.2 stub completion: now
            wires `onConfirmSign` (opens the lifted SignAndSendModal)
            and `onApplyAdditions` (POSTs to the bump-additions
            persistence endpoint). The rail's `emScore` prop is the
            local state mirror so apply-additions responses update
            the displayed tier without a page reload. */}
        {/* C3 hides the permanent rail (its content moves to the drawer's
            BillingCardC3); flag OFF renders the rail verbatim. */}
        {!c3 && (
        <aside className="qm-lin-coding-rail-slot" aria-label="Billing support">
          {emScore ? (
            <CodingRail
              emScore={emScore}
              visitId={visitId}
              readonly={isReadonly}
              currentSoapText={text}
              onConfirmSign={
                isReadonly || isSigned
                  ? undefined
                  : () => requestSignOpen(true)
              }
              onApplyOverride={
                isReadonly || isSigned ? undefined : handleApplyOverride
              }
              onHighlightCriteria={handleHighlightCriteria}
              onApplyAdditions={async (additions) => {
                try {
                  const res = await fetch(
                    `/api/visits/${visitId}/em-score/apply-additions`,
                    {
                      method: 'POST',
                      headers: { 'content-type': 'application/json' },
                      body: JSON.stringify({ additions }),
                    }
                  );
                  if (!res.ok) {
                    const body = (await res.json().catch(() => ({}))) as {
                      error?: string;
                    };
                    return {
                      ok: false,
                      error:
                        body.error ?? `Apply failed (${res.status}).`,
                    };
                  }
                  const data = (await res.json()) as {
                    ok: boolean;
                    newScore?: EmScore;
                  };
                  if (data.ok && data.newScore) {
                    setEmScore(data.newScore);
                  }
                  return { ok: data.ok, newScore: data.newScore };
                } catch (err) {
                  return {
                    ok: false,
                    error:
                      err instanceof Error
                        ? err.message
                        : 'Network error applying additions.',
                  };
                }
              }}
            />
          ) : (
            <CodingRailSkeleton />
          )}
        </aside>
        )}
      </div>

      {/* Bottom action bar — Sign & Send / Export-again.
          The Copy SOAP button moved INTO <SoapBody>'s notebody-foot,
          per the v6 mockup. V2 chromeless: the shell's persistent bottom
          Sign bar hosts this instead, so suppress it here. */}
      {!chromeless && (
      <div className="flex flex-wrap items-center justify-end gap-2 border-t border-linear-hairline pt-4">
        {/* C3 billing-simplify — a calm confirmable code chip next to Sign so
            the doctor sees the E/M code at the moment of signing without the
            dense rail. Amber + "confirm" when a level change is pending; it
            just opens the sign modal — the actual E/M confirm GATE stays in
            <SignAndSendModal>. Flag OFF → no chip (the rail showed the code). */}
        {c3 && !readonly && !isSigned && displayedEmCode && (
          <button
            type="button"
            className={`qm-c3-bill-chip ${emPendingChange ? 'pending' : ''} qm-tap-44`}
            onClick={() => requestSignOpen(true)}
            aria-label={
              emPendingChange
                ? `Billing code ${emPendingChange.to} — confirm at sign`
                : `Billing code ${displayedEmCode}`
            }
          >
            <span className="qm-c3-bill-chip-code">
              {emPendingChange ? emPendingChange.to : displayedEmCode}
            </span>
            <span className="qm-c3-bill-chip-tag">
              {emPendingChange ? 'confirm' : 'E/M'}
            </span>
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
            controlledOpen={signModalOpen}
            onControlledOpenChange={requestSignOpen}
            emPendingChange={emPendingChange}
          />
        )}
        {!readonly && !isSigned && (
          <PlaceholderAdvisoryDialog
            open={signAdvisoryOpen}
            onOpenChange={setSignAdvisoryOpen}
            sections={placeholderSections(text)}
            // Legacy path renders the lane outside this component — the
            // advisory copy degrades gracefully without a count.
            suggestionCount={0}
            onContinue={() => {
              setSignAdvisoryOpen(false);
              setSignModalOpen(true);
            }}
            onReviewNow={() => {
              // Legacy renders the suggestions lane inline — close + scroll to it.
              setSignAdvisoryOpen(false);
              setTimeout(() => {
                document
                  .querySelector('#suggestions-lane, [data-testid="suggestions-lane"]')
                  ?.scrollIntoView({ behavior: 'smooth', block: 'start' });
              }, 80);
            }}
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
      )}
    </div>
  );
}
