'use client';

// ============================================================================
// SuggestionsLane — "Suggested by AI — not stated in this visit".
// ----------------------------------------------------------------------------
// Hybrid anchored generation (2026-06-11). The L4b fail-closed verifier
// demotes claims it can't ground in the transcript to
// transcribe_visits.suggestedClaims; this lane renders them below the SOAP
// editor on READY (unsigned) visits for EXPLICIT doctor adoption:
//
//   [Adopt into note] → adoptSuggestionAction appends the claim text verbatim
//   to soapFinal under its section heading + audits SUGGESTION_ADOPTED. The
//   parent (VisitReadyView) remounts the editor with the returned text so the
//   note updates in place; router.refresh() re-syncs the RSC payload.
//   [Dismiss] → dismissSuggestionAction removes it from the lane + audits.
//
// Visual family: the amber review-reason-banner (same border/background
// color-mix recipe) — this is a "review me" surface, not an error. The lane
// keeps its own claims state, replaced from each action's response, so the
// rendered indices always match the DB array's indices.
// ============================================================================

import { useState } from 'react';
import { useRouter } from 'next/navigation';
import { Sparkles } from 'lucide-react';
import { toast } from 'sonner';

import {
  adoptSuggestionAction,
  dismissSuggestionAction,
} from '@/actions/suggestion-actions';

/** Lane view of a verifier-demoted claim (mirror of the worker's
 *  SuggestedClaim / the action's SuggestedClaimDto). */
export interface SuggestedClaimView {
  text: string;
  reason: string;
  section: string;
  /** The anchor quote(s) the model offered, joined — or 'no anchor'. */
  anchor: string;
}

/** DemotionReason → human-readable chip. Unknown reasons (future verifier
 *  classes) fall back to "couldn't verify" — never render a raw enum. */
const REASON_LABELS: Record<string, string> = {
  model_suggested: 'not stated',
  no_anchor: 'not stated',
  anchor_not_in_transcript: 'quote not in transcript',
  anchor_overlaps_unclear: 'unclear audio',
  digits_unsupported: 'numbers not supported',
  negation_mismatch: 'negation mismatch',
  gloss_unsupported: 'explanation not in transcript',
  process_assertion_unsupported: 'reasoning not stated',
  form_route_unsupported: 'form/route not stated',
  not_entailed: "couldn't verify",
  verifier_failed: "couldn't verify",
};

function reasonLabel(reason: string): string {
  return REASON_LABELS[reason] ?? "couldn't verify";
}

interface SuggestionsLaneProps {
  visitId: string;
  claims: SuggestedClaimView[];
  /** Fired after a successful adopt with the server's new note state so the
   *  parent can remount the SOAP editor with the appended text. */
  onAdopted: (r: { soapFinal: string; soapVersion: number }) => void;
}

export function SuggestionsLane({
  visitId,
  claims: initialClaims,
  onAdopted,
}: SuggestionsLaneProps) {
  const router = useRouter();
  // Authoritative within this mount: replaced wholesale from each action's
  // response so indices never drift from the DB array.
  const [claims, setClaims] = useState<SuggestedClaimView[]>(initialClaims);
  const [pending, setPending] = useState<{
    index: number;
    kind: 'adopt' | 'dismiss';
  } | null>(null);

  if (claims.length === 0) return null;

  async function handle(index: number, kind: 'adopt' | 'dismiss') {
    setPending({ index, kind });
    try {
      // The rendered claim text rides along as a content-identity check —
      // the server refuses if the DB array shifted under a stale tab.
      const expectedText = claims[index].text;
      const res =
        kind === 'adopt'
          ? await adoptSuggestionAction(visitId, index, expectedText)
          : await dismissSuggestionAction(visitId, index, expectedText);
      if (!res.ok) {
        toast.error(
          kind === 'adopt'
            ? 'Could not adopt the suggestion'
            : 'Could not dismiss the suggestion',
          { description: res.error }
        );
        return;
      }
      setClaims(res.suggestedClaims ?? []);
      if (
        kind === 'adopt' &&
        typeof res.soapFinal === 'string' &&
        typeof res.soapVersion === 'number'
      ) {
        onAdopted({ soapFinal: res.soapFinal, soapVersion: res.soapVersion });
        toast.success('Added to the note', {
          description: 'Adopted as your own attestation — review before signing.',
        });
      }
      // Re-sync the RSC payload (lane props, copy buttons, exports).
      router.refresh();
    } finally {
      setPending(null);
    }
  }

  return (
    <section
      role="region"
      aria-label="AI suggestions not stated in this visit"
      data-testid="suggestions-lane"
      className="rounded-lg border"
      style={{
        borderColor:
          'color-mix(in srgb, var(--color-linear-amber) 35%, transparent)',
        background:
          'color-mix(in srgb, var(--color-linear-amber) 8%, transparent)',
      }}
    >
      <header className="flex items-center gap-2 px-4 pt-3">
        <Sparkles
          className="h-3.5 w-3.5 flex-none"
          aria-hidden
          style={{ color: 'var(--color-linear-amber)' }}
        />
        <span
          className="text-[13px] font-medium"
          style={{ color: 'var(--color-linear-amber)' }}
        >
          Suggested by AI — not stated in this visit
        </span>
        <span
          className="font-mono text-[10.5px] font-medium uppercase"
          style={{ color: 'var(--color-linear-text-3)', letterSpacing: '0.07em' }}
        >
          {claims.length}
        </span>
      </header>
      <p
        className="px-4 pb-3 pt-1 text-[12px] leading-relaxed"
        style={{ color: 'var(--color-linear-text-3)' }}
      >
        The verifier couldn&apos;t ground these in the transcript, so they were
        kept out of the note. Adopting one adds it to the note as your own
        attestation.
      </p>

      <ul className="m-0 list-none p-0">
        {claims.map((claim, index) => {
          const isPending = pending?.index === index;
          return (
            <li
              key={`${index}-${claim.text.slice(0, 32)}`}
              data-testid="suggestion-item"
              className="border-t px-4 py-3"
              style={{
                borderColor:
                  'color-mix(in srgb, var(--color-linear-amber) 18%, transparent)',
              }}
            >
              <div
                className="text-[13px] leading-relaxed"
                style={{ color: 'var(--color-linear-text)' }}
              >
                {claim.text}
              </div>

              <div className="mt-1.5 flex flex-wrap items-center gap-1.5">
                <Chip tone="neutral">{claim.section}</Chip>
                <Chip tone="amber">{reasonLabel(claim.reason)}</Chip>
              </div>

              {claim.anchor !== 'no anchor' && (
                <div
                  className="mt-1.5 text-[11px] leading-relaxed"
                  style={{
                    fontFamily: 'var(--font-mono)',
                    color: 'var(--color-linear-text-3)',
                  }}
                >
                  &ldquo;{claim.anchor}&rdquo;
                </div>
              )}

              <div className="mt-2.5 flex flex-wrap items-center gap-2">
                <button
                  type="button"
                  className="qm-tap-44 rounded-md border px-2.5 py-1 text-[12px] font-medium transition-colors disabled:cursor-not-allowed disabled:opacity-50"
                  style={{
                    borderColor:
                      'color-mix(in srgb, var(--color-linear-amber) 45%, transparent)',
                    color: 'var(--color-linear-amber)',
                    background: 'transparent',
                    cursor: 'pointer',
                  }}
                  disabled={pending !== null}
                  onClick={() => void handle(index, 'adopt')}
                  aria-label={`Adopt suggestion ${index + 1} into the note`}
                >
                  {isPending && pending?.kind === 'adopt'
                    ? 'Adopting…'
                    : 'Adopt into note'}
                </button>
                <button
                  type="button"
                  className="qm-tap-44 rounded-md px-2.5 py-1 text-[12px] transition-colors disabled:cursor-not-allowed disabled:opacity-50"
                  style={{
                    color: 'var(--color-linear-text-3)',
                    background: 'transparent',
                    border: 0,
                    cursor: 'pointer',
                  }}
                  disabled={pending !== null}
                  onClick={() => void handle(index, 'dismiss')}
                  aria-label={`Dismiss suggestion ${index + 1}`}
                >
                  {isPending && pending?.kind === 'dismiss'
                    ? 'Dismissing…'
                    : 'Dismiss'}
                </button>
              </div>
            </li>
          );
        })}
      </ul>
    </section>
  );
}

function Chip({
  children,
  tone,
}: {
  children: React.ReactNode;
  tone: 'neutral' | 'amber';
}) {
  return (
    <span
      className="inline-flex items-center rounded px-1.5 py-0.5 font-mono text-[10px] font-medium uppercase"
      style={{
        letterSpacing: '0.07em',
        color:
          tone === 'amber'
            ? 'var(--color-linear-amber)'
            : 'var(--color-linear-text-2)',
        background:
          tone === 'amber'
            ? 'color-mix(in srgb, var(--color-linear-amber) 14%, transparent)'
            : 'var(--color-linear-surface-2)',
      }}
    >
      {children}
    </span>
  );
}
