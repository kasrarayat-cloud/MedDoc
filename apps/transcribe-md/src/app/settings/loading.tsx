// ============================================================================
// Settings loading state.
// ----------------------------------------------------------------------------
// ⚠️ THE ROUNDS BRANCH IS A DIFFERENT SHAPE, NOT A DIFFERENT COLOUR — the same
// ruling `visits/[id]/loading.tsx` records, reached the same way.
//
// The flag-OFF skeleton below draws THREE header lines and FOUR stacked cards
// in a 720px column. The `:rounds` image builds `NEXT_PUBLIC_SKIN_BETA=true`
// (e2e.yml, docker-compose.qa.rounds.yml), so under Rounds `/settings` resolves
// to `page.tsx`'s `isSkinBeta()` branch: a TWO-line header, then
// `.qm-c3-set-body` — a 188px sticky rail beside exactly ONE panel, the pair
// capped at 1100px. Every other panel is `hidden`.
//
// So the old skeleton contradicts what arrives on three counts, and the
// horizontal one is the worst: its first card edge sits at x≈24 while the real
// panel edge lands at x≈244. It draws four cards where the doctor's eye should
// be on one, and promises a page subtitle the C3 branch never renders (the
// subtitles live INSIDE the panels, and the first panel — Profile — has none).
// That is C1-c's finding exactly: a skeleton whose shape contradicts what
// arrives is worse than no skeleton, and no colour bridge can fix it.
//
// The Rounds branch borrows the SHIPPED `qm-c3-set-*` layout classes rather
// than restating their geometry inline. That is deliberate: the skeleton's job
// is to agree with the page, and reusing the page's own grid is the only way
// that agreement survives whoever edits the page next.
//
// (The flag-OFF branch is UNCHANGED, deliberately — this item does not own it.
// Worth recording for whoever does: production also builds
// `NEXT_PUBLIC_SKIN_BETA` true by default (`docker-compose.yml:545`), so the
// three-line/four-card shape is already wrong against today's live settings
// page, skin flag or no skin flag.)
// ============================================================================

import { Skeleton, SkeletonSettingsRow } from '@/components/skeleton';
import { isSkinRounds } from '@/config/skin-rounds';

/** The six rail labels, as widths. Profile · Note format · Security ·
 *  Active session · Billing · Danger zone. */
const RAIL_TABS = ['w-10', 'w-20', 'w-14', 'w-24', 'w-10', 'w-20'];

export default function SettingsLoading() {
  if (isSkinRounds()) {
    return (
      <div
        className="qm-rounds-host qm-rounds-loading"
        data-testid="rounds-loading-settings"
        style={{ minHeight: '100vh', padding: '18px 24px 48px' }}
      >
        {/* Two header lines: the mono kicker and the 22px title. No subtitle. */}
        <Skeleton className="mb-2 h-2.5 w-14 rounded" />
        <Skeleton className="h-[26px] w-24 rounded" />

        <div
          className="qm-c3-set-body"
          style={{ marginTop: 20, maxWidth: 1100 }}
        >
          {/* The rail: six labels on a 188px column, which is what resolves. */}
          <div className="qm-c3-set-rail" aria-hidden>
            {RAIL_TABS.map((w, i) => (
              <div key={i} className="qm-c3-set-tab">
                <Skeleton className={`h-3 ${w} rounded`} />
              </div>
            ))}
          </div>

          {/* ONE panel — the other five arrive `hidden`. */}
          <div className="qm-c3-set-panels" aria-hidden>
            <div className="qm-c3-set-panel">
              <Skeleton className="h-[23px] w-20 rounded" />
              {/* Profile's form: two 2-up rows, one full-width field, a CTA. */}
              <div style={{ marginTop: 18, display: 'grid', gap: 14 }}>
                {Array.from({ length: 2 }).map((_, r) => (
                  <div
                    key={r}
                    style={{
                      display: 'grid',
                      gridTemplateColumns: '1fr 1fr',
                      gap: 14,
                    }}
                  >
                    {Array.from({ length: 2 }).map((_, c) => (
                      <div key={c}>
                        <Skeleton className="h-2.5 w-20 rounded" />
                        <Skeleton className="mt-1.5 h-8 w-full" />
                      </div>
                    ))}
                  </div>
                ))}
                <div>
                  <Skeleton className="h-2.5 w-16 rounded" />
                  <Skeleton className="mt-1.5 h-8 w-full" />
                </div>
                <Skeleton className="mt-1 h-[30px] w-28" />
              </div>
            </div>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div
      className="qm-lin-fade-in"
      style={{
        padding: '18px 24px 64px',
        maxWidth: 1200,
      }}
    >
      <Skeleton className="mb-3 h-3 w-16" />
      <Skeleton className="mb-2 h-7 w-32" />
      <Skeleton className="mb-8 h-3 w-72" />
      <div
        style={{
          display: 'flex',
          flexDirection: 'column',
          gap: 14,
          maxWidth: 720,
        }}
      >
        <SkeletonSettingsRow />
        <SkeletonSettingsRow />
        <SkeletonSettingsRow />
        <SkeletonSettingsRow />
      </div>
    </div>
  );
}
