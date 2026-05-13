'use client';

// ============================================================================
// RateLimitNotice — friendly countdown shown when a 429 fires
// ----------------------------------------------------------------------------
// Surface for the patient-create rate-limit recovery UX (2026-05-13).
// The doctor sees this when they've burst past PATIENT_CREATE's 10/30s
// or 20/5min window. Two design intents:
//
//   1. Non-scary copy. "Try again later" reads as platform-broken. The
//      copy here frames the situation as "you're working faster than
//      the system allows" — same factual content, but the locus of
//      control sits with the workflow, not with a fragile platform.
//
//   2. Live countdown + auto-clear. The notice itself decrements the
//      seconds digit each second; `onExpire` fires when it hits zero
//      so the parent form can re-enable its submit button without a
//      page reload.
//
// Aesthetic: matches the existing Linear V1 "qm-lin-*" tokens —
// hairline-bordered warm-tinted surface, restrained amber accent,
// tabular-nums monospace digit so the number doesn't jiggle as it
// counts down. No motion beyond a tiny CSS fade-in.
// ============================================================================

import { Clock } from 'lucide-react';
import { useEffect, useRef, useState } from 'react';

interface RateLimitNoticeProps {
  /** Seconds to count down from. The notice unmounts itself at 0,
   *  but the parent should ALSO listen via `onExpire` so it can
   *  re-enable submit affordances. */
  retryAfterSec: number;
  /** Optional 1-2 word label hint (`burst`, `sustained_5min`, …) — if
   *  provided we use it to fine-tune the secondary copy. */
  limitType?: string | null;
  /** Headline noun for the resource (e.g., "patients", "visits").
   *  Intentionally REQUIRED so a copy-paste of this component into
   *  another form doesn't silently say "patients" by default. */
  resource: string;
  /** Fires exactly once when the countdown reaches 0. */
  onExpire?: () => void;
}

function formatSec(sec: number): string {
  if (sec <= 0) return '0 s';
  if (sec < 60) return `${sec} s`;
  const m = Math.floor(sec / 60);
  const s = sec % 60;
  return s === 0 ? `${m} min` : `${m} min ${s} s`;
}

export function RateLimitNotice({
  retryAfterSec,
  limitType,
  resource,
  onExpire,
}: RateLimitNoticeProps) {
  const [remaining, setRemaining] = useState(Math.max(0, Math.ceil(retryAfterSec)));

  // Stash the latest onExpire in a ref so the tick effect doesn't
  // re-run on every parent re-render (the patient picker re-renders
  // on every keystroke; without this, the 1-second timer would be
  // continually reset and the countdown would stall).
  const onExpireRef = useRef(onExpire);
  useEffect(() => {
    onExpireRef.current = onExpire;
  }, [onExpire]);

  // Guard against StrictMode-induced double-effect-fires + repeated
  // parent re-renders at remaining===0 — onExpire must fire exactly
  // once per countdown reaching zero.
  const firedRef = useRef(false);

  // Reset the countdown if a fresh 429 with a different retryAfterSec
  // lands while the notice is still mounted.
  useEffect(() => {
    setRemaining(Math.max(0, Math.ceil(retryAfterSec)));
    firedRef.current = false;
  }, [retryAfterSec]);

  useEffect(() => {
    if (remaining <= 0) {
      if (!firedRef.current) {
        firedRef.current = true;
        onExpireRef.current?.();
      }
      return;
    }
    const t = setTimeout(() => setRemaining((s) => s - 1), 1000);
    return () => clearTimeout(t);
  }, [remaining]);

  if (remaining <= 0) return null;

  // Burst-window rejections get the "pause briefly" framing; longer-
  // window rejections (5min, hourly) get a "wait for the window to
  // clear" framing because "briefly" reads weird at >60 s.
  const isLongWait = remaining > 60 || limitType === 'hourly';

  return (
    <div
      role="status"
      aria-live="polite"
      className="qm-rate-limit-notice flex items-start gap-2.5 rounded-md border border-linear-warning/40 bg-linear-warning/[0.07] px-3.5 py-3 text-[13px] text-linear-warning"
    >
      <Clock
        className="mt-[1px] h-3.5 w-3.5 flex-none"
        aria-hidden
        strokeWidth={2}
      />
      <div className="min-w-0 flex-1 leading-[1.4]">
        <div className="font-medium">
          You&apos;re creating {resource} faster than the system allows.
        </div>
        <div className="mt-0.5 text-[12px] text-linear-text-3">
          {isLongWait ? (
            <>
              The form will re-enable in{' '}
              <span className="font-mono tabular-nums font-medium text-linear-warning">
                {formatSec(remaining)}
              </span>
              .
            </>
          ) : (
            <>
              Pause briefly — the form will re-enable in{' '}
              <span className="font-mono tabular-nums font-medium text-linear-warning">
                {remaining} s
              </span>
              .
            </>
          )}
        </div>
      </div>
    </div>
  );
}
