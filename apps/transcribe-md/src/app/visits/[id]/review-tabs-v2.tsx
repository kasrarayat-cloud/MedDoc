"use client";

// ============================================================================
// ReviewTabsV2 — "Tabbed sign-gate workspace" review skin (skin-only, flag-gated)
// ----------------------------------------------------------------------------
// Built from the locked concept at staging.quillmd.com/concepts/soap-v2?v=2.
// Replaces BOTH the C3 review drawer AND the side coding rail: the note and
// every secondary surface (Review / Rx / Billing / Codes / Extras / Input)
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
// the gate-bearing children (SuggestionsLane, RxTab, BillingCardC3, CodesTab …)
// and the ONE Sign action (SignAndSendModal — with the E/M confirm gate intact)
// are all passed in / reused byte-for-byte. The two fail-closed sign gates keep
// their authoritative server enforcement:
//   • critical-Rx override — server POST /sign → 422. VISIBLE half here: the
//     Sign trigger is disabled until `rxResolved` (mirrors criticalWarningRefs).
//   • E/M confirm-before-sign — lives INSIDE SignAndSendModal (Sign & Deliver
//     disabled until confirmed). We only surface it on the readiness meter /
//     Billing tab; the modal stays untouched.
// ============================================================================

import { useCallback, useRef, useState } from "react";
import { Lock, Send } from "lucide-react";
import { PlaceholderAdvisoryDialog } from "@/components/placeholder-advisory-dialog";
import { SignAndSendModal } from "./sign-and-send-modal";

export type V2BadgeTone = "danger" | "warn" | "info" | "ok";

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
  /** Whether the visit carries any critical Rx warning at all (drives the
   *  readiness pip + the bottom-bar gate copy). */
  rxCritical: boolean;
  /** Live: every critical Rx warning has an override (mirrors the server gate).
   *  Disables the Sign trigger until true — the VISIBLE half of the Rx gate. */
  rxResolved: boolean;
  /** Unacknowledged E/M level change ({from,to}) — surfaced as an "at sign"
   *  readiness item; the actual confirm happens inside SignAndSendModal. */
  pendingEmChange: { from: string; to: string } | null;
  /** Tab key to jump to when the Rx blocker is tapped from the bottom bar. */
  rxTabKey: string;
  // ── Sign bar (the ONE Sign action) ──
  visitId: string;
  doctorEmail: string;
  emailEnabled: boolean;
  originalTemplateDocxAvailable?: boolean;
  /** Synthetic staging visits expose only the verified source-template clone. */
  originalTemplateOnly?: boolean;
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
  const [active, setActive] = useState<string>(props.tabs[0]?.key ?? "note");
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
    [hasPlaceholders],
  );

  const onTabKey = useCallback(
    (e: React.KeyboardEvent) => {
      const order = props.tabs.map((t) => t.key);
      const i = order.indexOf(active);
      let next = i;
      if (e.key === "ArrowRight" || e.key === "ArrowDown")
        next = (i + 1) % order.length;
      else if (e.key === "ArrowLeft" || e.key === "ArrowUp")
        next = (i - 1 + order.length) % order.length;
      else if (e.key === "Home") next = 0;
      else if (e.key === "End") next = order.length - 1;
      else return;
      e.preventDefault();
      const key = order[next];
      setActive(key);
      tabRefs.current[key]?.focus();
    },
    [active, props.tabs],
  );

  // ── Readiness model — honest two-stage gate. Rx is a PRE-SIGN gate (clears
  //    on the Rx tab → enables the Sign trigger); E/M is an AT-SIGN gate
  //    (confirmed inside SignAndSendModal). Both stay visible. ──
  const items: { label: string; done: boolean; atSign?: boolean }[] = [];
  if (props.rxCritical)
    items.push({ label: "Rx safety", done: props.rxResolved });
  if (props.pendingEmChange)
    items.push({ label: "Coding confirm", done: false, atSign: true });
  const total = items.length;
  const cleared = items.filter((it) => it.done).length;
  const rxBlocking = props.rxCritical && !props.rxResolved;

  const readyText = props.signed
    ? "This note is signed"
    : total === 0
      ? "Ready to sign"
      : rxBlocking
        ? "Resolve the critical interaction to sign"
        : props.pendingEmChange
          ? `Ready — you'll confirm the ${props.pendingEmChange.from} → ${props.pendingEmChange.to} coding change as you sign`
          : "Ready to sign";

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
                ? "Ready to sign"
                : `Sign readiness: ${cleared} of ${total} checks cleared`
            }
          >
            <span
              className={`qm-c3-rev2-dot ${rxBlocking ? "warn" : "ok"}`}
              aria-hidden
            />
            <span className="qm-c3-rev2-ready-text">
              {total === 0
                ? "Ready to sign"
                : `${cleared} of ${total} checks cleared`}
            </span>
            {total > 0 && (
              <span className="qm-c3-rev2-pips" aria-hidden>
                {items.map((it, i) => (
                  <span
                    key={i}
                    className={`qm-c3-rev2-pip ${it.done ? "on" : it.atSign ? "atsign" : "off"}`}
                    title={
                      it.atSign
                        ? `${it.label} — confirm at sign`
                        : it.done
                          ? `${it.label} — cleared`
                          : `${it.label} — resolve to sign`
                    }
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
              className={`qm-c3-rev2-tab qm-tap-44 ${active === t.key ? "on" : ""}`}
              onClick={() => setActive(t.key)}
            >
              {t.icon}
              <span className="qm-c3-rev2-tab-label">{t.label}</span>
              {t.badge && (
                <span className={`qm-c3-rev2-tab-badge ${t.badge.tone}`}>
                  {t.badge.text}
                </span>
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
              <Lock
                className="h-3.5 w-3.5 flex-none"
                aria-hidden
                style={{ color: "var(--color-linear-sage-bright)" }}
              />
              <span className="qm-c3-rev2-sign-msg">{readyText}</span>
            </div>
          ) : rxBlocking ? (
            <button
              type="button"
              className="qm-c3-rev2-sign-status qm-c3-rev2-jump qm-tap-44"
              onClick={() => setActive(props.rxTabKey)}
              aria-label="Resolve the critical interaction — go to the Rx tab"
            >
              <span className="qm-c3-rev2-dot warn" aria-hidden />
              <span className="qm-c3-rev2-sign-msg">
                {readyText}{" "}
                <span className="qm-c3-rev2-go" aria-hidden>
                  →
                </span>
              </span>
            </button>
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
                originalTemplateDocxAvailable={
                  props.originalTemplateDocxAvailable
                }
                originalTemplateOnly={props.originalTemplateOnly}
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
                  originalTemplateDocxAvailable={
                    props.originalTemplateDocxAvailable
                  }
                  originalTemplateOnly={props.originalTemplateOnly}
                  signOnSubmit
                  triggerLabel="Sign & Send"
                  triggerIcon={<Lock className="h-3.5 w-3.5" aria-hidden />}
                  emPendingChange={props.pendingEmChange}
                  // VISIBLE half of the critical-Rx gate — can't open the sign
                  // flow until every critical interaction is overridden. The
                  // server POST /sign → 422 remains the authoritative enforcement.
                  disabled={rxBlocking}
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
                />
              </>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
