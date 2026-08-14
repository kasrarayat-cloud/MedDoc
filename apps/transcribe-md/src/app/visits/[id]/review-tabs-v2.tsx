'use client';

// ============================================================================
// ReviewTabsV2 — "Tabbed sign-gate workspace" review skin (skin-only, flag-gated)
// ----------------------------------------------------------------------------
// Built from the locked concept at staging.quillmd.com/concepts/soap-v2?v=2.
// Replaces BOTH the C3 review drawer AND the side coding rail: the note and
// every secondary surface (Review / Billing / Codes / Extras / Input)
// each live on their OWN full-width tab, so nothing is ever beside the note —
// no side-by-side collision at any screen size.
//
// The tab risk ("a blocker hides one tap away") is answered by THREE signals
// that stay on screen no matter which tab is open:
//   1. a count/warning BADGE on each tab label,
//   2. a "X of N checks cleared" readiness meter, and
//   3. a persistent bottom Sign bar that names + jumps to the top blocker.
//
// SKIN-ONLY: this is a presentational shell. The note (SoapEditor, chromeless),
// the gate-bearing children (SuggestionsLane, BillingCardC3, CodesTab …)
// and the ONE Sign action (SignAndSendModal — with the E/M confirm gate intact)
// are all passed in / reused byte-for-byte. The two fail-closed sign gates keep
// their authoritative server enforcement:
//   • E/M confirm-before-sign — lives INSIDE SignAndSendModal (Sign & Deliver
//     disabled until confirmed). We only surface it on the readiness meter /
//     Billing tab; the modal stays untouched.
// ============================================================================

import { useCallback, useRef, useState } from 'react';
import { Lock, Send } from 'lucide-react';
import { PlaceholderAdvisoryDialog } from '@/components/placeholder-advisory-dialog';
import { SignAndSendModal } from './sign-and-send-modal';

export type V2BadgeTone = 'danger' | 'warn' | 'info' | 'ok';

export interface V2Tab {
  key: string;
  label: string;
  icon?: React.ReactNode;
  /** Count/warning chip on the tab label — keeps blockers visible cross-tab. */
  badge?: { tone: V2BadgeTone; text: string } | null;
  node: React.ReactNode;
}

export interface ReviewTabsV2Props {
  tabs: V2Tab[];
  // ⚠️ `rxCritical`, `rxResolved` and `rxTabKey` were REMOVED here with the
  // prescription-safety surface (owner ruling #109). They drove the readiness
  // pip, the bottom-bar gate copy and the disabled Sign trigger — the VISIBLE
  // half of a server gate that no longer exists either.
  /** Unacknowledged E/M level change ({from,to}) — surfaced as an "at sign"
   *  readiness item; the actual confirm happens inside SignAndSendModal. */
  pendingEmChange: { from: string; to: string } | null;
  /** Tab key of the review/suggestions lane — the "Review now" jump target from
   *  the set-aside advisory. Undefined when the lane isn't shown. */
  reviewTabKey?: string;
  // ── Sign bar (the ONE Sign action) ──
  visitId: string;
  doctorEmail: string;
  emailEnabled: boolean;
  /** readonly || signedAt !== null. */
  signed: boolean;
  /** F-7 (2026-07-02): section labels still carrying the anchored-verifier
   *  set-aside placeholder. Non-empty → opening the Sign flow first shows an
   *  ADVISORY confirm listing them ("Sign anyway" continues). Server sign
   *  route unchanged — the fail-closed gates stay the authority. */
  placeholderSections?: string[];
  /** Review-suggestion count for the advisory copy. */
  suggestionCount?: number;
}

export function ReviewTabsV2(props: ReviewTabsV2Props) {
  const [active, setActive] = useState<string>(props.tabs[0]?.key ?? 'note');
  const tabRefs = useRef<Record<string, HTMLButtonElement | null>>({});
  // F-7: the unsigned Sign modal runs in CONTROLLED mode so every open
  // request (its own trigger button included) routes through one gatekeeper:
  // placeholders present → advisory first; "Sign anyway" → the real modal.
  const [signOpen, setSignOpen] = useState(false);
  const [advisoryOpen, setAdvisoryOpen] = useState(false);
  const placeholderLabels = props.placeholderSections ?? [];
  const hasPlaceholders = placeholderLabels.length > 0;
  const requestSignOpen = useCallback(
    (next: boolean) => {
      if (next && hasPlaceholders) {
        setAdvisoryOpen(true);
        return;
      }
      setSignOpen(next);
    },
    [hasPlaceholders]
  );

  const onTabKey = useCallback(
    (e: React.KeyboardEvent) => {
      const order = props.tabs.map((t) => t.key);
      const i = order.indexOf(active);
      let next = i;
      if (e.key === 'ArrowRight' || e.key === 'ArrowDown') next = (i + 1) % order.length;
      else if (e.key === 'ArrowLeft' || e.key === 'ArrowUp') next = (i - 1 + order.length) % order.length;
      else if (e.key === 'Home') next = 0;
      else if (e.key === 'End') next = order.length - 1;
      else return;
      e.preventDefault();
      const key = order[next];
      setActive(key);
      tabRefs.current[key]?.focus();
    },
    [active, props.tabs]
  );

  // ── Readiness model — ONE stage since ruling #109. E/M is an AT-SIGN gate
  //    (confirmed inside SignAndSendModal). The PRE-SIGN stage was the Rx one,
  //    and it went with its surface; nothing else was pre-sign, so the two-stage
  //    shape is gone rather than left with an empty first stage. ──
  const items: { label: string; done: boolean; atSign?: boolean }[] = [];
  if (props.pendingEmChange) items.push({ label: 'Coding confirm', done: false, atSign: true });
  const total = items.length;
  const cleared = items.filter((it) => it.done).length;

  const readyText = props.signed
    ? 'This note is signed'
    : total === 0
      ? 'Ready to sign'
      : props.pendingEmChange
          ? `Ready — you'll confirm the ${props.pendingEmChange.from} → ${props.pendingEmChange.to} coding change as you sign`
          : 'Ready to sign';

  const activeTab = props.tabs.find((t) => t.key === active) ?? props.tabs[0];

  return (
    <div className="qm-c3-rev2">
      {/* Sticky header — readiness meter + badged tab strip. */}
      <div className="qm-c3-rev2-bar">
        {!props.signed && (
          <div
            className="qm-c3-rev2-ready"
            aria-label={
              total === 0
                ? 'Ready to sign'
                : `Sign readiness: ${cleared} of ${total} checks cleared`
            }
          >
            <span className="qm-c3-rev2-dot ok" aria-hidden />
            <span className="qm-c3-rev2-ready-text">
              {total === 0 ? 'Ready to sign' : `${cleared} of ${total} checks cleared`}
            </span>
            {total > 0 && (
              <span className="qm-c3-rev2-pips" aria-hidden>
                {items.map((it, i) => (
                  <span
                    key={i}
                    className={`qm-c3-rev2-pip ${it.done ? 'on' : it.atSign ? 'atsign' : 'off'}`}
                    title={it.atSign ? `${it.label} — confirm at sign` : it.done ? `${it.label} — cleared` : `${it.label} — resolve to sign`}
                  />
                ))}
              </span>
            )}
          </div>
        )}

        <div
          className="qm-c3-rev2-tabs"
          role="tablist"
          aria-label="Review sections"
          onKeyDown={onTabKey}
        >
          {props.tabs.map((t) => (
            <button
              key={t.key}
              id={`qm-c3-rev2-tab-${t.key}`}
              ref={(el) => {
                tabRefs.current[t.key] = el;
              }}
              role="tab"
              type="button"
              aria-selected={active === t.key}
              aria-controls="qm-c3-rev2-panel"
              tabIndex={active === t.key ? 0 : -1}
              className={`qm-c3-rev2-tab qm-tap-44 ${active === t.key ? 'on' : ''}`}
              onClick={() => setActive(t.key)}
            >
              {t.icon}
              <span className="qm-c3-rev2-tab-label">{t.label}</span>
              {t.badge && (
                <span className={`qm-c3-rev2-tab-badge ${t.badge.tone}`}>{t.badge.text}</span>
              )}
            </button>
          ))}
        </div>
      </div>

      {/* Full-width tab panel — exactly one section, always full width. */}
      <div
        className="qm-c3-rev2-panel"
        id="qm-c3-rev2-panel"
        role="tabpanel"
        aria-labelledby={`qm-c3-rev2-tab-${active}`}
        tabIndex={0}
        key={active}
      >
        {activeTab?.node}
      </div>

      {/* Persistent bottom Sign bar — the ONE Sign action; names + jumps to the
          top blocker; always on screen across every tab. */}
      <div className="qm-c3-rev2-signbar">
        <div className="qm-c3-rev2-signbar-in">
          {props.signed ? (
            <div className="qm-c3-rev2-sign-status">
              <Lock className="h-3.5 w-3.5 flex-none" aria-hidden style={{ color: 'var(--color-linear-sage-bright)' }} />
              <span className="qm-c3-rev2-sign-msg">{readyText}</span>
            </div>
          ) : (
            <div className="qm-c3-rev2-sign-status">
              <span className="qm-c3-rev2-dot ok" aria-hidden />
              <span className="qm-c3-rev2-sign-msg">{readyText}</span>
            </div>
          )}

          <div className="qm-c3-rev2-sign-action">
            {props.signed ? (
              <SignAndSendModal
                visitId={props.visitId}
                doctorEmail={props.doctorEmail}
                emailEnabled={props.emailEnabled}
                signOnSubmit={false}
                triggerLabel="Export again"
                triggerIcon={<Send className="h-3.5 w-3.5" aria-hidden />}
                triggerVariant="secondary"
              />
            ) : (
              <>
                <SignAndSendModal
                  visitId={props.visitId}
                  doctorEmail={props.doctorEmail}
                  emailEnabled={props.emailEnabled}
                  signOnSubmit
                  triggerLabel="Sign & Send"
                  triggerIcon={<Lock className="h-3.5 w-3.5" aria-hidden />}
                  emPendingChange={props.pendingEmChange}
                  // ⚠️ `disabled={rxBlocking}` stood here — the VISIBLE half of
                  // the critical-Rx gate. Both halves went together under owner
                  // ruling #109, so nothing disables this trigger now. It is NOT
                  // that the visible half was dropped and a server refusal left
                  // behind: `POST /sign` no longer refuses on Rx either.
                  controlledOpen={signOpen}
                  onControlledOpenChange={requestSignOpen}
                />
                <PlaceholderAdvisoryDialog
                  open={advisoryOpen}
                  onOpenChange={setAdvisoryOpen}
                  sections={placeholderLabels}
                  suggestionCount={props.suggestionCount ?? 0}
                  onContinue={() => {
                    setAdvisoryOpen(false);
                    setSignOpen(true);
                  }}
                  onReviewNow={() => {
                    setAdvisoryOpen(false);
                    // Jump to the Review/suggestions tab (or the note tab if the
                    // lane isn't present — e.g. every suggestion was dismissed but
                    // the placeholder remains), then scroll the lane into view.
                    const key =
                      props.reviewTabKey && props.tabs.some((t) => t.key === props.reviewTabKey)
                        ? props.reviewTabKey
                        : props.tabs[0]?.key ?? 'note';
                    setActive(key);
                    setTimeout(() => {
                      document
                        .querySelector('#suggestions-lane, [data-testid="suggestions-lane"]')
                        ?.scrollIntoView({ behavior: 'smooth', block: 'start' });
                    }, 80);
                  }}
                />
              </>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
