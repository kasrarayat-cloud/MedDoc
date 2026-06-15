'use client';

// Shared review engine for the SOAP-review v2 concepts. Same blocker semantics as the v1 lab's
// useReview(), but the E/M change is modelled as ALREADY PENDING on load (the documentation
// supports 99214, a change from 99213) so the confirm-before-sign gate is VISIBLE immediately —
// mirroring the real app's emPendingChange. Both v2 concepts compose the SAME engine so a
// blocker can never differ between them or hide behind a tab. Static mockup, no real pipeline.
import { useState } from 'react';
import { LANE, RX, EM } from '../soap/data';

export type Attention = {
  kind: 'rx' | 'em' | 'review';
  // 'block' = a hard sign-blocker (fail-closed gate); 'review' = recommended, not gating.
  level: 'block' | 'review';
  target: string; // anchor id the summary/tab jumps to
  short: string; // badge label
  full: string; // sign-bar / summary line phrasing
};

export function useReviewV2() {
  const [adopted, setAdopted] = useState<Set<string>>(new Set());
  const [dismissed, setDismissed] = useState<Set<string>>(new Set());
  const [overrides, setOverrides] = useState<Set<string>>(new Set());
  // E/M level change is pending on load → must be confirmed before signing.
  const [emConfirmed, setEmConfirmed] = useState(false);
  const [signed, setSigned] = useState(false);

  const adopt = (id: string) => {
    setAdopted((s) => new Set(s).add(id));
    setDismissed((s) => {
      const n = new Set(s);
      n.delete(id);
      return n;
    });
  };
  const dismiss = (id: string) => {
    setDismissed((s) => new Set(s).add(id));
    setAdopted((s) => {
      const n = new Set(s);
      n.delete(id);
      return n;
    });
  };
  const override = (id: string) => setOverrides((s) => new Set(s).add(id));
  const laneState = (id: string): 'adopted' | 'dismissed' | undefined =>
    adopted.has(id) ? 'adopted' : dismissed.has(id) ? 'dismissed' : undefined;

  const pendingLane = LANE.filter((l) => !adopted.has(l.id) && !dismissed.has(l.id));
  const blockingRx = RX.filter((r) => r.blocking && !overrides.has(r.id));
  const emNeeded = !emConfirmed;

  // HARD blockers — these gate the Sign button (the fail-closed gates).
  const blockers: string[] = [
    ...blockingRx.map((r) => `Critical interaction ${r.id} — override to sign`),
    ...(emNeeded ? [`Coding ${EM.current} → ${EM.suggested} — confirm the level change`] : []),
  ];
  const canSign = blockers.length === 0;

  // Everything that needs the doctor's eyes — hard blockers FIRST, then the soft review item.
  // Used by both concepts to render the summary line / tab badges so nothing hides.
  const attention: Attention[] = [
    ...blockingRx.map(
      (r): Attention => ({
        kind: 'rx',
        level: 'block',
        target: 'v2-rx',
        short: 'Critical interaction',
        full: `Critical drug interaction (${r.id}) — override required to sign`,
      })
    ),
    ...(emNeeded
      ? [
          {
            kind: 'em' as const,
            level: 'block' as const,
            target: 'v2-coding',
            short: `Confirm ${EM.suggested}`,
            full: `Coding ${EM.current} → ${EM.suggested} — confirm before signing`,
          },
        ]
      : []),
    ...(pendingLane.length
      ? [
          {
            kind: 'review' as const,
            level: 'review' as const,
            target: 'v2-review',
            short: `${pendingLane.length} to review`,
            full: `${pendingLane.length} AI suggestion to review`,
          },
        ]
      : []),
  ];

  return {
    adopted, dismissed, overrides, emConfirmed, setEmConfirmed, signed, setSigned,
    adopt, dismiss, override, laneState,
    pendingLane, blockingRx, emNeeded, blockers, canSign, attention,
  };
}
