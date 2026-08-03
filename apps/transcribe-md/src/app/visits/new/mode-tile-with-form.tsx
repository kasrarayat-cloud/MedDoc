'use client';

// ============================================================================
// Capture-mode tile (Step 2 of /visits/new).
// ----------------------------------------------------------------------------
// Phase 5 — Linear V1 Faithful. Renders as a hairline-bordered
// surface-1 card with a sage icon chip, Inter title, text-2 body
// description. Sage hover-glow on the border + a subtle row-active
// surface bump. The TiltCard / GlowCard chrome is dropped — no
// theatrical motion in Linear V1. The `theme` prop is preserved as
// a no-op.
// ============================================================================

import { Mic, Radio, PenLine } from 'lucide-react';

export type ModeIconKey = 'mic' | 'radio' | 'pen-line';
type ModeTileTheme = 'legacy' | 'clinician';

interface Props {
  formId: string;
  /** String key — NOT a component reference. */
  icon: ModeIconKey;
  title: string;
  description: string;
  value: 'audio_upload' | 'voice_dictation' | 'text_notes';
  /** @deprecated kept for back-compat; Linear V1 is single-theme. */
  theme?: ModeTileTheme;
}

const ICON_MAP = {
  mic: Mic,
  radio: Radio,
  'pen-line': PenLine,
} as const;

/** Submit button that targets the /visits/new form via the HTML `form`
 *  attribute. */
export function ModeTileWithForm({
  formId,
  icon,
  title,
  description,
  value,
}: Props) {
  const Icon = ICON_MAP[icon];

  return (
    <button
      type="submit"
      form={formId}
      name="inputMode"
      value={value}
      /* ⚠️ R3.7 — `qm-rounds-modetile` CARRIES THE HOVER AND FOCUS, and the two
         Tailwind utilities it replaces are why hosting alone was not enough
         here. `hover:border-[rgba(122,166,140,0.45)]` is a LITERAL rgba — the
         legacy sage written out, not a custom property — so `.qm-rounds-host`
         cannot retint it, and `focus-visible:ring-linear-sage` is the same
         colour on the focus ring. Those are the "legacy green buttons" this
         item kills. Layout stays Tailwind; only the two state colours move, and
         the tile gains the same lift the board and roster cards use. */
      className="qm-rounds-modetile group block w-full rounded-lg border border-linear-border bg-linear-surface-1 p-6 text-left transition-colors focus-visible:outline-none"
      style={{ minHeight: 132, cursor: 'pointer' }}
    >
      <span
        aria-hidden
        className="mb-4 inline-flex h-11 w-11 items-center justify-center rounded-md"
        style={{
          background: 'var(--color-linear-sage-tint)',
          color: 'var(--color-linear-sage-bright)',
          border: '1px solid rgba(122,166,140,0.32)',
        }}
      >
        <Icon className="h-5 w-5" aria-hidden />
      </span>
      <div
        style={{
          fontFamily: 'var(--font-sans)',
          fontSize: 16,
          fontWeight: 600,
          color: 'var(--color-linear-text)',
          letterSpacing: '-0.01em',
          marginBottom: 4,
        }}
      >
        {title}
      </div>
      <div
        style={{
          fontSize: 13,
          lineHeight: 1.5,
          color: 'var(--color-linear-text-2)',
        }}
      >
        {description}
      </div>
    </button>
  );
}
