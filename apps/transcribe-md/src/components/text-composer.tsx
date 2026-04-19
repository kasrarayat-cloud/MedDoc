'use client';

import { useCallback, useState, useTransition } from 'react';
import { useRouter } from 'next/navigation';
import { PenLine, ArrowRight, Loader2 } from 'lucide-react';
import { toast } from 'sonner';

import { cn } from '@/lib/cn';
import { SpecularButton } from '@/components/specular-button';

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

interface TextComposerProps {
  visitId: string;
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

  return (
    <div className="mx-auto w-full max-w-2xl">
      <div className="mb-6 text-center">
        <h2 className="type-h1 text-text-primary">Text to SOAP</h2>
        <p className="mt-2 text-[14px] text-text-tertiary">
          Paste bullet points or shorthand. We&apos;ll expand them into a
          complete SOAP note.
        </p>
      </div>

      <div
        className={cn(
          'rounded-2xl border border-border-default bg-bg-surface-1/60 p-4',
          'transition-colors duration-200 focus-within:border-violet-500',
          'focus-within:ring-2 focus-within:ring-violet-500/30'
        )}
      >
        <textarea
          value={text}
          onChange={(e) => setText(e.target.value)}
          placeholder={PLACEHOLDER}
          maxLength={MAX_CHARS}
          spellCheck
          className="min-h-[320px] w-full resize-y bg-transparent p-2 font-mono text-[13px] leading-relaxed text-text-primary placeholder:text-text-muted/70 outline-none"
          aria-label="Clinical shorthand"
        />
        <div className="mt-2 flex flex-wrap items-center justify-between gap-2 px-2 text-[11px] text-text-muted">
          <div>
            Use bullets, abbreviations, or shorthand. Common expansions:{' '}
            <span className="text-text-tertiary">
              yo, f/u, RTC, ROS -, BP 148/92, A1c 6.8.
            </span>
          </div>
          <div
            className={cn(
              'tabular-nums',
              len < MIN_CHARS
                ? 'text-text-muted'
                : len > MAX_CHARS - 100
                  ? 'text-warning'
                  : 'text-text-tertiary'
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
        <p role="alert" className="mt-3 text-[13px] text-danger">
          {error}
        </p>
      )}

      <div className="mt-6 flex items-center justify-center">
        <SpecularButton
          variant="primary"
          size="lg"
          onClick={submit}
          disabled={!canSubmit}
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
        </SpecularButton>
      </div>
    </div>
  );
}
