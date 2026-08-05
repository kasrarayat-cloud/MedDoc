// ============================================================================
// Settings loading state.
// ----------------------------------------------------------------------------
// ⚠️ THIS SKELETON IS A SHAPE, NOT A COLOUR — the same ruling
// `visits/[id]/loading.tsx` records, reached the same way.
//
// `NEXT_PUBLIC_SKIN_BETA=true` is what builds (e2e.yml,
// docker-compose.qa.rounds.yml, and production by default at
// `docker-compose.yml:545`), so `/settings` resolves to `page.tsx`'s
// `isSkinBeta()` branch: a TWO-line header, then `.qm-c3-set-body` — a 188px
// sticky rail beside exactly ONE panel, the pair capped at 1100px. Every other
// panel is `hidden`. The skeleton below draws that, and nothing else.
//
// Do not let it drift back towards a three-line header and four stacked cards
// in a 720px column. That shape contradicts what arrives on three counts, and
// the horizontal one is the worst: its first card edge sits at x≈24 while the
// real panel edge lands at x≈244. It draws four cards where the doctor's eye
// should be on one, and promises a page subtitle the C3 branch never renders
// (the subtitles live INSIDE the panels, and the first panel — Profile — has
// none). That is C1-c's finding exactly: a skeleton whose shape contradicts
// what arrives is worse than no skeleton, and no colour bridge can fix it.
//
// The skeleton borrows the SHIPPED `qm-c3-set-*` layout classes rather than
// restating their geometry inline. That is deliberate: the skeleton's job is
// to agree with the page, and reusing the page's own grid is the only way that
// agreement survives whoever edits the page next.
// ============================================================================

import { Skeleton } from '@/components/skeleton';

/** The six rail labels, as widths. Profile · Note format · Security ·
 *  Active session · Billing · Danger zone. */
const RAIL_TABS = ['w-10', 'w-20', 'w-14', 'w-24', 'w-10', 'w-20'];

export default function SettingsLoading() {
  return (
    <div
      className="qm-rounds-host qm-rounds-loading"
      data-testid="rounds-loading-settings"
      style={{ minHeight: '100vh', padding: '18px 24px 48px' }}
    >
      {/* Two header lines: the mono kicker and the 22px title. No subtitle. */}
      <Skeleton className="mb-2 h-2.5 w-14 rounded" />
      <Skeleton className="h-[26px] w-24 rounded" />

      <div className="qm-c3-set-body" style={{ marginTop: 20, maxWidth: 1100 }}>
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
