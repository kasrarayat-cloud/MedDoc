'use client';

// ============================================================================
// TextComposer — bullet/shorthand → SOAP entry surface.
// ----------------------------------------------------------------------------
// Phase 5 — Linear V1 Faithful. Hairline-bordered surface-1 textarea
// frame with a sage focus ring and a mono shorthand body. CTA is
// `.qm-lin-btn-primary`. The fetch contract (POST /api/visits/[id]/text),
// MIN/MAX char gates, and form submit semantics are preserved
// byte-for-byte. The `theme` prop is preserved as a no-op.
// ============================================================================

import { useCallback, useState, useTransition } from 'react';
import { useRouter } from 'next/navigation';
import { PenLine, ArrowRight, Loader2 } from 'lucide-react';
import { toast } from 'sonner';

import { cn } from '@/lib/cn';
import { isSkinBeta } from '@/config/skin-beta';

const MIN_CHARS = 30;
const MAX_CHARS = 5000;

const PLACEHOLDER = [
  'e.g.',
  '- 45yo F, HTN, on lisinopril 10mg',
  '- Routine follow-up, no complaints',
  '- BP 148/92, HR 72',
  '- Incr lisinopril to 20mg',
  '- RTC 3mo',
  '- A1c ordered',
].join('\n');

type TextComposerTheme = 'legacy' | 'clinician';

interface TextComposerProps {
  visitId: string;
  /** @deprecated kept for back-compat; Linear V1 is single-theme. */
  theme?: TextComposerTheme;
}

export function TextComposer({ visitId }: TextComposerProps) {
  const router = useRouter();
  const [text, setText] = useState('');
  const [submitting, startTransition] = useTransition();
  const [error, setError] = useState<string | null>(null);

  const len = text.length;
  const canSubmit = len >= MIN_CHARS && len <= MAX_CHARS && !submitting;

  const submit = useCallback(() => {
    startTransition(async () => {
      setError(null);
      try {
        const res = await fetch(`/api/visits/${visitId}/text`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ text }),
        });
        if (!res.ok) {
          let msg = `Submit failed (${res.status}).`;
          try {
            const body = await res.json();
            if (body?.error) msg = `Submit failed: ${body.error}`;
          } catch {
            /* ignore */
          }
          setError(msg);
          toast.error('Could not expand to SOAP', { description: msg });
          return;
        }
        toast.success('Expanding to SOAP', {
          description: 'Your note is being generated now.',
        });
        router.refresh();
      } catch (err) {
        console.error('[text-composer] submit failed:', err);
        setError('Network error.');
        toast.error('Could not expand to SOAP', {
          description: 'Network error.',
        });
      }
    });
  }, [visitId, text, router]);

  // C3 calm skin (flag-gated) — same textarea + same POST /api/visits/[id]/text
  // submit, presented as the calm single card with an honest "written after you
  // submit" tone. Flag OFF → the centered Linear V1 layout below renders.
  const c3 = isSkinBeta();

  return (
    <div className={c3 ? 'qm-c3-cap' : 'mx-auto w-full max-w-2xl'}>
      <div className={c3 ? 'qm-c3-cap-head' : 'mb-6 text-center'}>
        {c3 && <span className="qm-c3-cap-kicker">Text note</span>}
        <h2
          style={
            c3
              ? undefined
              : {
                  margin: 0,
                  fontFamily: 'var(--font-sans)',
                  fontSize: 28,
                  fontWeight: 500,
                  lineHeight: 1.15,
                  letterSpacing: '-0.015em',
                  color: 'var(--color-linear-text)',
                }
          }
          className={c3 ? 'qm-c3-cap-h' : undefined}
        >
          {c3 ? 'Type the visit' : 'Text to SOAP'}
        </h2>
        <p
          className={c3 ? 'qm-c3-cap-p' : 'mt-2'}
          style={
            c3
              ? undefined
              : { fontSize: 14, lineHeight: 1.55, color: 'var(--color-linear-text-2)' }
          }
        >
          Paste bullet points or shorthand. We&apos;ll expand them into a
          complete SOAP note after you submit.
        </p>
      </div>

      <div className="rounded-lg border border-linear-border bg-linear-surface-1 p-4 transition-colors duration-150 focus-within:border-linear-sage focus-within:ring-2 focus-within:ring-linear-sage/30">
        <textarea
          value={text}
          onChange={(e) => setText(e.target.value)}
          placeholder={PLACEHOLDER}
          maxLength={MAX_CHARS}
          spellCheck
          className="min-h-[320px] w-full resize-y bg-transparent p-2 font-mono text-[13px] leading-relaxed text-linear-text outline-none placeholder:text-linear-text-3/70"
          aria-label="Clinical shorthand"
        />
        <div className="mt-2 flex flex-wrap items-center justify-between gap-2 px-2 text-[11px] text-linear-text-3">
          <div>
            Use bullets, abbreviations, or shorthand. Common expansions:{' '}
            <span className="text-linear-text-2">
              yo, f/u, RTC, ROS -, BP 148/92, A1c 6.8.
            </span>
          </div>
          <div
            className={cn(
              'tabular-nums',
              len < MIN_CHARS
                ? 'text-linear-text-3'
                : len > MAX_CHARS - 100
                  ? 'text-linear-warning'
                  : 'text-linear-text-2'
            )}
          >
            {len} / {MAX_CHARS}
            {len < MIN_CHARS && (
              <span className="ml-2">· min {MIN_CHARS}</span>
            )}
          </div>
        </div>
      </div>

      {error && (
        <p role="alert" className="mt-3 text-[13px] text-linear-danger">
          {error}
        </p>
      )}

      <div className="mt-6 flex items-center justify-center">
        <button
          type="button"
          onClick={submit}
          disabled={!canSubmit}
          className="qm-lin-btn-primary"
          style={{ padding: '10px 18px', height: 38 }}
        >
          <PenLine className="h-4 w-4" aria-hidden />
          {submitting ? (
            <>
              <Loader2 className="h-3.5 w-3.5 animate-spin" aria-hidden />
              Expanding…
            </>
          ) : (
            <>
              Expand to SOAP
              <ArrowRight className="h-4 w-4" aria-hidden />
            </>
          )}
        </button>
      </div>
    </div>
  );
}
