'use client';

// ============================================================================
// Capture-mode tile (Step 2 of /visits/new). Phase 2 (Clinician remodel) —
// Strategy A dual-theme via additive `theme` prop. Default `'legacy'` keeps
// the violet glow + tilt-card chrome verbatim. `theme="clinician"` swaps
// to a soft cream `.qm-cl-card-soft` with a sage line-art icon chip + serif
// title — no tilt, no glow, no gradient (per CL-5: no theatrical motion).
// ============================================================================

import { Mic, Radio, PenLine } from 'lucide-react';
import { TiltCard } from '@/components/tilt-card';
import { GlowCard } from '@/components/glow-card';

export type ModeIconKey = 'mic' | 'radio' | 'pen-line';
type ModeTileTheme = 'legacy' | 'clinician';

interface Props {
  formId: string;
  /** String key — NOT a component reference. The server page renders this
   *  inside the client tree via the ICON_MAP lookup below, avoiding
   *  Next 16's "Functions cannot be passed to Client Components" error
   *  that a ComponentType prop would trigger (digest 1109689143). */
  icon: ModeIconKey;
  title: string;
  description: string;
  value: 'audio_upload' | 'voice_dictation' | 'text_notes';
  /** Phase 2 (Clinician remodel) — additive theme prop. */
  theme?: ModeTileTheme;
}

const ICON_MAP = {
  mic: Mic,
  radio: Radio,
  'pen-line': PenLine,
} as const;

/** Submit button that targets the /visits/new form via the HTML `form`
 *  attribute. Kept separate from the generic ModeTile so the generic
 *  component stays free of form-specific wiring. */
export function ModeTileWithForm({
  formId,
  icon,
  title,
  description,
  value,
  theme = 'legacy',
}: Props) {
  const Icon = ICON_MAP[icon];

  if (theme === 'clinician') {
    // Calm Clinician variant — soft cream card with sage icon chip,
    // Source Serif 4 title, ink-2 body. No tilt, no glow.
    return (
      <button
        type="submit"
        form={formId}
        name="inputMode"
        value={value}
        className="qm-cl-card-soft group block w-full text-left transition focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-clinician-sage focus-visible:ring-offset-2 focus-visible:ring-offset-clinician-cream"
        style={{ padding: 24, minHeight: 132, cursor: 'pointer' }}
      >
        <span
          aria-hidden
          className="inline-flex h-11 w-11 items-center justify-center rounded-2xl"
          style={{
            background: 'var(--sage-tint-strong)',
            color: 'var(--sage-deep)',
            marginBottom: 14,
          }}
        >
          <Icon className="h-5 w-5" aria-hidden />
        </span>
        <div
          className="qm-cl-serif"
          style={{
            fontSize: 17,
            fontWeight: 500,
            color: 'var(--ink)',
            letterSpacing: '-0.005em',
            marginBottom: 4,
          }}
        >
          {title}
        </div>
        <div
          style={{
            fontSize: 13,
            lineHeight: 1.5,
            color: 'var(--ink-2)',
          }}
        >
          {description}
        </div>
      </button>
    );
  }

  return (
    <button
      type="submit"
      form={formId}
      name="inputMode"
      value={value}
      className="group block w-full text-left focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-violet-500 focus-visible:ring-offset-2 focus-visible:ring-offset-bg-base rounded-xl"
    >
      <TiltCard className="h-full">
        <GlowCard className="h-full">
          <div className="flex h-full flex-col gap-4 rounded-xl border border-border-default bg-bg-surface-1/60 p-6 transition-colors duration-300 ease-[cubic-bezier(0.4,0,0.2,1)] group-hover:border-violet-500/50">
            <span
              aria-hidden
              className="inline-flex h-11 w-11 items-center justify-center rounded-lg bg-[linear-gradient(135deg,#4C1D95_0%,#7C3AED_100%)] shadow-[0_0_0_1px_rgba(167,139,250,0.3)]"
            >
              <Icon className="h-5 w-5 text-white" aria-hidden />
            </span>
            <div>
              <div className="text-[16px] font-semibold text-text-primary">
                {title}
              </div>
              <div className="mt-1.5 text-[13px] leading-relaxed text-text-tertiary">
                {description}
              </div>
            </div>
          </div>
        </GlowCard>
      </TiltCard>
    </button>
  );
}
