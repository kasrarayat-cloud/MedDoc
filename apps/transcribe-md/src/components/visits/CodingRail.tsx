'use client';

// ============================================================================
// CodingRail — Phase 5.2 v6 Coding Coach right rail.
// ----------------------------------------------------------------------------
// STUB FOR SOLO BUILD — Subagent C owns this file. The real implementation
// (header + time tracker + criteria checklist + bump CTA) lands in
// feature/phase5.2-soap-rail-v6 and REPLACES this stub at Stage 6 merge.
//
// Subagent A leaves a clean placeholder so the SOAP body's grid renders
// during the solo TS / build verification. The interface here is the
// minimum surface contract the body needs to thread props through;
// Subagent C will widen it (override callbacks, gap arrays, etc).
//
// Do NOT extend or copy this stub from Subagent A's branch — Subagent C's
// merge resolution is mechanical: their branch overwrites this file.
// ============================================================================

export interface CodingRailEmScore {
  /** AMA 2021 E&M code currently suggested by the engine. */
  suggestedCode: string;
  /** Pretty level label (e.g. "Level 3"). */
  level: string;
  /** Per-section gap hints — informs the SOAP body's section pulse dots.
   *  Subagent C populates this from the engine; Subagent A only forwards
   *  it via the parent SoapEditor. */
  boostHints?: Partial<Record<'S' | 'O' | 'A' | 'P', { tone: 'ok' | 'boost'; text: string }>>;
}

export interface CodingRailProps {
  emScore: CodingRailEmScore | null;
  visitId: string;
  readonly: boolean;
  /** Called when a doctor's interaction in the rail (override / bump / nudge)
   *  should update the SOAP body's per-section pulse dots. Subagent C wires
   *  the signal; Subagent A's parent SoapEditor exposes this callback. */
  onBoostHintsChange?: (
    hints: NonNullable<CodingRailEmScore['boostHints']>
  ) => void;
}

export function CodingRail({ visitId }: CodingRailProps) {
  return (
    <div
      data-stub="coding-rail"
      data-visit-id={visitId}
      aria-hidden
    />
  );
}
