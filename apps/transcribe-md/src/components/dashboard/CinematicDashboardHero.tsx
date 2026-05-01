'use client';

// ============================================================================
// Phase 4 — CinematicDashboardHero
// ----------------------------------------------------------------------------
// Time-of-day photo hero band rendered above the existing 4-stat-card
// row on /dashboard. Visual reference: docs/design-directions-v6/
// studio-variations/dashboard-{02,03,04}.html. Animation reference:
// docs/design-directions-v6/studio-variations/landing-11-anim-1.html.
//
// CREATIVE TWIST — TIME-BASED HERO
// --------------------------------
// The doctor's local-time bucket (US/Pacific) selects one of three
// stacked photos and the matching greeting word:
//
//   Pacific hour 5 – 11   → 'morning'    (dashboard-morning.webp)
//   Pacific hour 12 – 17  → 'afternoon'  (dashboard-afternoon.webp)
//   Pacific hour 18 – 4   → 'evening'    (dashboard-evening.webp)
//
// All three photos are stacked in the DOM (absolute-positioned),
// preloaded via <link rel="preload" as="image"> tags so the swap is
// silent. Only the active one carries .qm-cin-bg-active (opacity 1);
// the others sit at opacity 0 and the 1200ms ease-out transition on
// .qm-cin-bg covers any mid-session bucket flip with a slow crossfade.
//
// SSR vs CLIENT
// -------------
// The `initialBucket` prop is computed on the SERVER from the same
// PT-time formula and renders a hydration-safe first paint. Once
// mounted, a `setInterval(checkBucket, 60_000)` recomputes the bucket
// from the client wall clock (still PT) and re-targets the active
// layer + the greeting word. There's no full-page rerender; we drive
// the swap via React state inside this component.
//
// REDUCED-MOTION
// --------------
// CSS transition collapses to 0 ms via the global @media rule. The
// greeting word DOM swap remains, just without the crossfade.
//
// PROTECTED_CONTRACTS: this component is JSX-only. It doesn't call
// any server actions, API routes, or auth machinery. The dashboard
// page reads `firstName` from a Prisma query in its server component;
// this client wrapper just renders that name in the greeting.
// ============================================================================

import { useEffect, useState, type ReactNode } from 'react';

export type DashboardTimeBucket = 'morning' | 'afternoon' | 'evening';

interface CinematicDashboardHeroProps {
  /** Server-computed bucket from the page server component. Used for
   *  the SSR + first-paint render so hydration matches. The client
   *  effect overwrites it on mount with the live PT bucket. */
  initialBucket: DashboardTimeBucket;
  /** Doctor's first name for "Good morning, Dr. {firstName}.". When
   *  null, falls back to "Good morning, doctor.". */
  firstName: string | null;
  /** Optional sub-line under the greeting (e.g., "5 patients · 11
   *  total visits"). Passed as ReactNode so the page can mix sage
   *  highlights for "awaiting your review" pings. */
  subtitle?: ReactNode;
}

const BUCKET_TO_PHOTO: Record<DashboardTimeBucket, { webp: string; jpg: string }> = {
  morning: {
    webp: '/images/cinematic/dashboard-morning.webp',
    jpg: '/images/cinematic/dashboard-morning.jpg',
  },
  afternoon: {
    webp: '/images/cinematic/dashboard-afternoon.webp',
    jpg: '/images/cinematic/dashboard-afternoon.jpg',
  },
  evening: {
    webp: '/images/cinematic/dashboard-evening.webp',
    jpg: '/images/cinematic/dashboard-evening.jpg',
  },
};

const ALL_BUCKETS: DashboardTimeBucket[] = ['morning', 'afternoon', 'evening'];

/** Compute the time-of-day bucket from a PT (US/Pacific) hour.
 *  Inclusive ranges: 5–11 → morning, 12–17 → afternoon, 18–4 → evening
 *  (the wrap-around overnight is handled by the else branch). */
function bucketFromPtHour(ptHour: number): DashboardTimeBucket {
  if (ptHour >= 5 && ptHour < 12) return 'morning';
  if (ptHour >= 12 && ptHour < 18) return 'afternoon';
  return 'evening';
}

/** Read the current PT (America/Los_Angeles) hour from the client
 *  clock using Intl.DateTimeFormat. Returns 0–23. */
function getCurrentPtHour(): number {
  try {
    const fmt = new Intl.DateTimeFormat('en-US', {
      timeZone: 'America/Los_Angeles',
      hour: 'numeric',
      hour12: false,
    });
    const parts = fmt.format(new Date());
    // Some browsers emit "0" for midnight, others emit "24" — coerce
    // either to 0 to keep the bucket logic simple.
    const n = parseInt(parts, 10);
    return Number.isFinite(n) ? n % 24 : 0;
  } catch {
    // If Intl falls over (very old browsers), fall back to local hour.
    return new Date().getHours();
  }
}

export function CinematicDashboardHero({
  initialBucket,
  firstName,
  subtitle,
}: CinematicDashboardHeroProps) {
  // Bucket state — starts on the SSR-computed value to match the
  // server payload exactly (zero hydration mismatch). The client
  // effect re-checks the live PT clock on mount + every 60 s.
  const [bucket, setBucket] = useState<DashboardTimeBucket>(initialBucket);
  const [hydrated, setHydrated] = useState(false);

  useEffect(() => {
    setHydrated(true);
    // Initial client-side check: if the SSR was generated minutes ago
    // and the bucket has rolled over, this will catch it on mount.
    const ptHour = getCurrentPtHour();
    const live = bucketFromPtHour(ptHour);
    if (live !== bucket) {
      setBucket(live);
    }

    // Recheck every 60 s so a doctor leaving the dashboard open
    // through 18:00 PT sees the photo + greeting word transition to
    // 'evening' without a refresh. We use setInterval rather than a
    // timeout-to-next-bucket because the cost is trivial and the
    // 1-minute granularity is well below the per-bucket duration
    // (6 hours each). Cleared on unmount.
    const id = window.setInterval(() => {
      const liveHour = getCurrentPtHour();
      const liveBucket = bucketFromPtHour(liveHour);
      setBucket((prev) => (liveBucket === prev ? prev : liveBucket));
    }, 60_000);

    return () => window.clearInterval(id);
    // We deliberately omit `bucket` from deps — the interval reads
    // the latest value via the functional setState above. Including
    // it would tear down + rebuild the interval every minute.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const namePart = firstName ? `Dr. ${firstName}` : 'doctor';

  // Words for the headline. Pre = "Good ", em = bucket word, post =
  // ", Dr. {firstName}.". The em span carries .em.glow modifiers so
  // the italic sage glow lands on the time-of-day word per spec.
  const headlinePre = 'Good ';
  const headlineEm = bucket;
  const headlinePost = `, ${namePart}.`;

  // Eyebrow: local date in mono uppercase. Mirrors the studio
  // reference (dashboard-02 L167). Computed client-side so the locale
  // matches the doctor, not the server's TZ.
  const [eyebrow, setEyebrow] = useState<string | null>(null);
  useEffect(() => {
    const now = new Date();
    const dow = now.toLocaleDateString('en-US', { weekday: 'long' });
    const month = now.toLocaleDateString('en-US', { month: 'long' });
    const day = now.getDate();
    const m = now.getMonth();
    let season = 'Spring';
    if (m === 11 || m === 0 || m === 1) season = 'Winter';
    else if (m >= 2 && m <= 4) season = 'Spring';
    else if (m >= 5 && m <= 7) season = 'Summer';
    else if (m >= 8 && m <= 10) season = 'Autumn';
    setEyebrow(`${dow}, ${month} ${day} · ${season}`);
  }, []);

  // anim-1 reveal sequence — applied once on hydration. The bucket
  // crossfade itself is CSS-only (1200 ms transition on .qm-cin-bg's
  // opacity), so re-targeting the active layer doesn't need a JS
  // animation timeline.
  useEffect(() => {
    if (!hydrated) return;
    const reduce = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
    const root = document.querySelector<HTMLElement>('[data-cin-dash-root]');
    if (!root) return;
    if (reduce) {
      root
        .querySelectorAll('.av1-word, .av1-fade')
        .forEach((el) => el.classList.add('show'));
      return;
    }
    const timers: number[] = [];
    const eb = root.querySelector<HTMLElement>('[data-cin-eyebrow]');
    if (eb) {
      timers.push(window.setTimeout(() => eb.classList.add('show'), 120));
    }
    root.querySelectorAll<HTMLElement>('.av1-word').forEach((w) => {
      const d = parseInt(w.dataset.d ?? '0', 10);
      timers.push(window.setTimeout(() => w.classList.add('show'), d + 80));
    });
    const deck = root.querySelector<HTMLElement>('[data-cin-deck]');
    if (deck) {
      timers.push(window.setTimeout(() => deck.classList.add('show'), 900));
    }
    return () => timers.forEach((t) => window.clearTimeout(t));
  }, [hydrated]);

  return (
    <>
      {/* Preload all three photos — the silent crossfade depends on
         the next photo being already decoded when its layer flips
         opacity. Webp first since the browser will use the format it
         supports; the jpg fallback is only fetched if webp isn't. */}
      {ALL_BUCKETS.map((b) => (
        <link
          key={b}
          rel="preload"
          as="image"
          href={BUCKET_TO_PHOTO[b].webp}
          // type hint helps Chrome skip if webp isn't supported,
          // though most modern browsers support it.
          type="image/webp"
        />
      ))}
      <div className="qm-cin-dash-band" data-cin-dash-root>
        {/* Crossfade stack — all three photos in DOM at once, only
           the active one at opacity 1. The CSS transition handles
           the fade automatically when the active class moves between
           layers. */}
        <div className="qm-cin-bg-stack" aria-hidden>
          {ALL_BUCKETS.map((b) => {
            const photo = BUCKET_TO_PHOTO[b];
            const active = b === bucket;
            return (
              <div
                key={b}
                className={`qm-cin-bg${active ? ' qm-cin-bg-active' : ''}`}
                style={{
                  // image-set webp + jpg fallback for older browsers.
                  backgroundImage: `image-set(url('${photo.webp}') type('image/webp'), url('${photo.jpg}') type('image/jpeg'))`,
                }}
              />
            );
          })}
          {/* Plain-jpg fallback layer — covers older Firefox /
             webview targets that don't support image-set. Sits below
             the stack so when image-set works, the better image
             draws on top. */}
          <div
            className="qm-cin-bg qm-cin-bg-active"
            style={{
              backgroundImage: `url('${BUCKET_TO_PHOTO[bucket].jpg}')`,
              zIndex: -1,
            }}
            aria-hidden
          />
        </div>
        <div className="qm-cin-inner">
          {eyebrow && (
            <div className="qm-cin-eyebrow av1-fade" data-cin-eyebrow>
              <span className="dot" />
              {eyebrow.toUpperCase()}
            </div>
          )}
          <h1
            className="qm-cin-headline"
            aria-label={`${headlinePre}${headlineEm}${headlinePost}`.trim()}
            // The italic word's text content swaps when `bucket`
            // changes. We rely on React's reconciliation + the CSS
            // photo crossfade to make the swap feel like a single
            // gesture. No additional JS animation is needed.
          >
            <span className="av1-word" data-d="0">
              {headlinePre}
            </span>
            <span className="av1-word em glow" data-d="120">
              {headlineEm}
            </span>
            <span className="av1-word" data-d="240">
              {headlinePost}
            </span>
          </h1>
          {subtitle && (
            <p className="qm-cin-deck av1-fade" data-cin-deck>
              {subtitle}
            </p>
          )}
        </div>
      </div>
    </>
  );
}
