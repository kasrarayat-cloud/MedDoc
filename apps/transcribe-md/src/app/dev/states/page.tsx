// ============================================================================
// /dev/states — every error and loading surface, on demand.
// ----------------------------------------------------------------------------
// ⚠️ GATED ON A BUILD FLAG, NOT ON `NODE_ENV`, AND THAT IS THE ITEM.
//
// The obvious gate is `if (NODE_ENV === 'production') notFound()`, which is
// what `/dev/rx-warnings` uses. It is wrong for anything a TEST must reach: the
// QA stack runs a production build, so a NODE_ENV-gated route 404s exactly
// where Gate C's sweep runs. Measured on the running stack — `/dev/rx-warnings`
// returns 404 on QA against a `/login` control at 200, and no E2E references
// any `/dev/` route. The first draft of this route used NODE_ENV and would
// have been a door onto nothing.
//
// WHY THE ROUTE EXISTS AT ALL — narrowed from the plan's claim, by checking:
//   · both 404s are ALREADY reachable by navigation (a bad URL renders the
//     Rounds not-found surface), so they do NOT need this route;
//   · the ERROR BOUNDARY does — nothing navigates to it, and
//     `27-error-resilience.spec.ts` says as much in its own source;
//   · the LOADING states do — they paint for well under 100ms on QA, so a walk
//     catches them essentially never, and CDP throttling to widen the window is
//     a flake generator.
// Two of four state families, not four.
// ============================================================================

import type { Metadata } from 'next';
import Link from 'next/link';
import { notFound } from 'next/navigation';

import {
  Skeleton,
  SkeletonRoundsLane,
  SkeletonSettingsRow,
  SkeletonVisitCard,
  SkeletonVisitGrid,
} from '@/components/skeleton';
import { isDevStates } from '@/config/dev-states';
// The REAL loading components, imported rather than reimplemented — a preview
// of a second implementation proves nothing about the first.
import BoardLoadingPreview from '@/app/board/loading';
import SettingsLoadingPreview from '@/app/settings/loading';
import VisitLoadingPreview from '@/app/visits/[id]/loading';
import { DevErrorState } from './client';
import { DevTmplProcessing, DevTmplRejected } from './templates-preview';

export const metadata: Metadata = { title: 'States — preview' };

type SearchParams = Record<string, string | string[] | undefined>;

const STATES = [
  'error',
  'error-stale',
  'loading-visit',
  'loading-board',
  'skeletons',
  // C1-f. Two of the note-format machine's six views are unreachable by a
  // walk: `parsing` paints only while four server actions are in flight, and
  // `rejected` needs the parse-time PHI gate to fire, which on the QA stack
  // means a container env the Rounds image does not carry. Both are rendered
  // here from the REAL components and the REAL stage builder — a hand-written
  // copy would measure something the product never draws.
  'tmpl-processing',
  'tmpl-rejected',
  // C2 — the settings loading state had NO DOOR AT ALL. `/settings` resolves
  // fast enough that a walk never catches its `loading.tsx`, and unlike the
  // board and visit ones it was not even reachable here. Gate C asks for axe on
  // every restyled screen; a screen with no way to render it is not swept, it
  // is assumed.
  'loading-settings',
] as const;
type State = (typeof STATES)[number];

function resolveState(raw: string | undefined): State {
  return (STATES as readonly string[]).includes(raw ?? '') ? (raw as State) : 'error';
}

const H2: React.CSSProperties = {
  fontFamily: 'var(--font-mono)',
  fontSize: 10.5,
  letterSpacing: '0.08em',
  textTransform: 'uppercase',
  color: 'var(--color-linear-text-3)',
  marginBottom: 10,
};

export default async function DevStatesPage({
  searchParams,
}: {
  searchParams: Promise<SearchParams>;
}) {
  // Fails closed. Production's compose never passes the build arg, so this is
  // false there and the route does not exist — asserted against the compose
  // file by `gate-devstates`, rather than trusting the Dockerfile default.
  if (!isDevStates()) notFound();

  const params = await searchParams;
  const raw = params.state;
  const state = resolveState(Array.isArray(raw) ? raw[0] : raw);

  return (
    <div
      className="qm-rounds-host qm-rounds-devstates"
      data-testid="dev-states"
      data-state={state}
      style={{ minHeight: '100vh' }}
    >
      <nav
        aria-label="Preview state"
        style={{
          display: 'flex',
          flexWrap: 'wrap',
          gap: 8,
          padding: '14px 20px',
          borderBottom: '1px solid var(--color-linear-border)',
        }}
      >
        {STATES.map((s) => (
          <Link
            key={s}
            href={`/dev/states?state=${s}`}
            data-testid={`dev-state-${s}`}
            aria-current={s === state ? 'page' : undefined}
            style={{
              fontFamily: 'var(--font-mono)',
              fontSize: 11,
              padding: '5px 10px',
              borderRadius: 6,
              textDecoration: 'underline',
              border: '1px solid var(--color-linear-border)',
              color:
                s === state ? 'var(--color-linear-text)' : 'var(--color-linear-text-3)',
              background: s === state ? 'var(--color-linear-surface-2)' : 'transparent',
            }}
          >
            {s}
          </Link>
        ))}
      </nav>

      {state === 'error' ? <DevErrorState stale={false} /> : null}
      {state === 'error-stale' ? <DevErrorState stale /> : null}

      {state === 'loading-visit' ? (
        <div data-testid="dev-loading-visit">
          <VisitLoadingPreview />
        </div>
      ) : null}

      {state === 'loading-board' ? (
        <div data-testid="dev-loading-board">
          <BoardLoadingPreview />
        </div>
      ) : null}

      {state === 'loading-settings' ? (
        <div data-testid="dev-loading-settings">
          <SettingsLoadingPreview />
        </div>
      ) : null}

      {state === 'tmpl-processing' ? <DevTmplProcessing /> : null}
      {state === 'tmpl-rejected' ? <DevTmplRejected /> : null}

      {state === 'skeletons' ? (
        <div style={{ padding: 32, display: 'grid', gap: 28 }} data-testid="dev-skeletons">
          <section>
            <h2 style={H2}>Skeleton</h2>
            <Skeleton className="h-4 w-48" />
          </section>
          <section>
            <h2 style={H2}>SkeletonRoundsLane</h2>
            <SkeletonRoundsLane />
            <SkeletonRoundsLane />
          </section>
          <section>
            <h2 style={H2}>SkeletonVisitCard</h2>
            <SkeletonVisitCard />
          </section>
          <section>
            <h2 style={H2}>SkeletonVisitGrid</h2>
            <SkeletonVisitGrid />
          </section>
          <section>
            <h2 style={H2}>SkeletonSettingsRow</h2>
            <SkeletonSettingsRow />
          </section>
        </div>
      ) : null}
    </div>
  );
}
