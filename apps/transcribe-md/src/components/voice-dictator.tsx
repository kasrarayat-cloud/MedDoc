'use client';

// ============================================================================
// VoiceDictator — live mic capture with MediaRecorder + AudioContext analyser.
// ----------------------------------------------------------------------------
// Phase 2 (Clinician remodel) — Strategy A dual-theme via additive
// `theme` prop. Default `'legacy'` keeps the dark cinematic VioletOrb +
// violet halo background byte-for-byte. `theme="clinician"` replaces
// the Three.js orb with the calm class-driven chrome from
// landing-and-recording.html: `.qm-cl-halo` breathing rings + sage
// `.qm-cl-mic-dot` mic chip + `.qm-cl-wave-bar` VU meter (per CL-5: no
// theatrical motion, no Three.js orbs in Clinician).
//
// 🔴 PROTECTED: All MediaRecorder / AudioContext / analyser /
// streamRef / chunksRef / finalizeAndUpload / stopRecording /
// startRecording lifecycle code is preserved byte-for-byte. Only the
// JSX rendered surface (and props/imports needed to wire it) changes.
// ============================================================================

import {
  useCallback,
  useEffect,
  useRef,
  useState,
} from 'react';
import { useRouter } from 'next/navigation';
import dynamic from 'next/dynamic';
import { Mic, Square, Loader2 } from 'lucide-react';
import { toast } from 'sonner';

import { cn } from '@/lib/cn';
import { SpecularButton } from '@/components/specular-button';
import type { OrbState } from '@/components/violet-orb';

const VioletOrb = dynamic(
  () => import('@/components/violet-orb').then((m) => m.VioletOrb),
  { ssr: false, loading: () => <div className="h-64 w-64" /> }
);

type Phase = 'idle' | 'requesting' | 'listening' | 'uploading' | 'error';
type VoiceDictatorTheme = 'legacy' | 'clinician';

const MIME = 'audio/webm;codecs=opus';
// 250 ms chunks, same cadence scribe's live path uses — keeps memory
// bounded without losing audio if the user stops mid-buffer.
const CHUNK_MS = 250;
const MAX_SECONDS = 10 * 60; // 10 minutes

interface VoiceDictatorProps {
  visitId: string;
  /** Phase 2 (Clinician remodel) — additive theme prop. */
  theme?: VoiceDictatorTheme;
}

export function VoiceDictator({ visitId, theme = 'legacy' }: VoiceDictatorProps) {
  const router = useRouter();
  const [phase, setPhase] = useState<Phase>('idle');
  const [elapsed, setElapsed] = useState(0);
  const [error, setError] = useState<string | null>(null);
  const [level, setLevel] = useState(0); // 0-1 amplitude, drives orb reactivity

  const recorderRef = useRef<MediaRecorder | null>(null);
  const streamRef = useRef<MediaStream | null>(null);
  const chunksRef = useRef<Blob[]>([]);
  const analyserRef = useRef<AnalyserNode | null>(null);
  const audioCtxRef = useRef<AudioContext | null>(null);
  const rafRef = useRef<number | null>(null);
  const tickRef = useRef<ReturnType<typeof setInterval> | null>(null);
  // Guard against double-firing the final upload — onstop() and the
  // max-length timeout both can call through.
  const finalizingRef = useRef(false);

  // ── cleanup on unmount ──────────────────────────────────────────────
  useEffect(() => {
    return () => {
      if (tickRef.current) clearInterval(tickRef.current);
      if (rafRef.current) cancelAnimationFrame(rafRef.current);
      if (recorderRef.current?.state === 'recording') {
        try {
          recorderRef.current.stop();
        } catch {
          /* ignore */
        }
      }
      streamRef.current?.getTracks().forEach((t) => t.stop());
      audioCtxRef.current?.close().catch(() => {});
    };
  }, []);

  // Declared up front so startRecording below can close over it without
  // TDZ. React Compiler's lint rejects forward references across
  // useCallback declarations even though JS would permit them via the
  // component's render ordering.
  const finalizeAndUpload = useCallback(async () => {
    if (finalizingRef.current) return;
    finalizingRef.current = true;
    setPhase('uploading');

    const blob = new Blob(chunksRef.current, { type: MIME });
    chunksRef.current = [];
    if (blob.size === 0) {
      setError('No audio captured. Please try again.');
      setPhase('error');
      finalizingRef.current = false;
      return;
    }

    try {
      const res = await fetch(`/api/visits/${visitId}/dictation/upload`, {
        method: 'POST',
        headers: { 'Content-Type': MIME },
        body: blob,
      });
      if (!res.ok) {
        let msg = `Upload failed (${res.status}).`;
        try {
          const body = await res.json();
          if (body?.error) msg = `Upload failed: ${body.error}`;
        } catch {
          /* ignore */
        }
        setError(msg);
        setPhase('error');
        toast.error('Dictation upload failed', { description: msg });
        finalizingRef.current = false;
        return;
      }
      toast.success('Dictation uploaded', {
        description: 'Processing into a SOAP note now.',
      });
      router.refresh();
    } catch (err) {
      setError('Network error during upload.');
      setPhase('error');
      toast.error('Dictation upload failed', {
        description: 'Network error.',
      });
      finalizingRef.current = false;
      console.error('[voice-dictator] upload failed:', err);
    }
  }, [visitId, router]);

  const stopRecording = useCallback(() => {
    if (tickRef.current) clearInterval(tickRef.current);
    tickRef.current = null;
    if (rafRef.current) cancelAnimationFrame(rafRef.current);
    rafRef.current = null;
    const rec = recorderRef.current;
    if (rec && rec.state === 'recording') {
      try {
        rec.stop();
      } catch {
        /* ignore — the onstop will still fire for "inactive" */
      }
    }
    streamRef.current?.getTracks().forEach((t) => t.stop());
    audioCtxRef.current?.close().catch(() => {});
    audioCtxRef.current = null;
    setLevel(0);
  }, []);

  const startRecording = useCallback(async () => {
    setError(null);
    if (typeof MediaRecorder === 'undefined') {
      setError('Your browser does not support audio recording.');
      setPhase('error');
      return;
    }
    if (!MediaRecorder.isTypeSupported(MIME)) {
      setError('Your browser does not support the webm/opus audio format.');
      setPhase('error');
      return;
    }

    setPhase('requesting');
    let stream: MediaStream;
    try {
      stream = await navigator.mediaDevices.getUserMedia({ audio: true });
    } catch (err) {
      setError(
        err instanceof DOMException && err.name === 'NotAllowedError'
          ? 'Microphone access was denied. Enable it in your browser to dictate.'
          : 'Could not access the microphone.'
      );
      setPhase('error');
      return;
    }
    streamRef.current = stream;

    // Wire a tiny analyser so the orb's reactive prop reflects the mic
    // amplitude — makes the recording feel alive rather than frozen.
    const AudioCtx =
      // eslint-disable-next-line @typescript-eslint/no-explicit-any
      (window.AudioContext as any) ||
      // eslint-disable-next-line @typescript-eslint/no-explicit-any
      (window as any).webkitAudioContext;
    const ctx: AudioContext = new AudioCtx();
    const source = ctx.createMediaStreamSource(stream);
    const analyser = ctx.createAnalyser();
    analyser.fftSize = 512;
    source.connect(analyser);
    audioCtxRef.current = ctx;
    analyserRef.current = analyser;

    const data = new Uint8Array(analyser.frequencyBinCount);
    const tick = () => {
      analyser.getByteFrequencyData(data);
      let sum = 0;
      for (const v of data) sum += v;
      const avg = sum / data.length / 255; // 0-1
      setLevel(Math.min(1, avg * 2.5));
      rafRef.current = requestAnimationFrame(tick);
    };
    rafRef.current = requestAnimationFrame(tick);

    const recorder = new MediaRecorder(stream, { mimeType: MIME });
    recorderRef.current = recorder;
    chunksRef.current = [];

    recorder.ondataavailable = (e) => {
      if (e.data.size > 0) chunksRef.current.push(e.data);
    };
    recorder.onstop = () => {
      void finalizeAndUpload();
    };

    recorder.start(CHUNK_MS);
    setPhase('listening');
    setElapsed(0);
    tickRef.current = setInterval(() => {
      setElapsed((s) => {
        const next = s + 1;
        if (next >= MAX_SECONDS) {
          // Hit the 10-min ceiling — stop recording; onstop handles
          // the upload via finalizeAndUpload.
          stopRecording();
        }
        return next;
      });
    }, 1000);
  }, [stopRecording, finalizeAndUpload]);

  const orbState: OrbState =
    phase === 'listening' ? 'listening' : phase === 'uploading' ? 'processing' : 'idle';

  const mm = Math.floor(elapsed / 60);
  const ss = (elapsed % 60).toString().padStart(2, '0');

  if (theme === 'clinician') {
    return (
      <ClinicianVoiceDictatorView
        phase={phase}
        elapsed={elapsed}
        mm={mm}
        ss={ss}
        level={level}
        error={error}
        onStart={startRecording}
        onStop={stopRecording}
        onRetry={() => {
          setError(null);
          setPhase('idle');
        }}
      />
    );
  }

  return (
    <div className="mx-auto flex max-w-xl flex-col items-center py-12 text-center sm:py-20">
      <div className="relative mb-10 h-72 w-72">
        <div
          aria-hidden
          className={cn(
            'orb-pulse pointer-events-none absolute inset-0 -z-10 rounded-full transition-opacity duration-300',
            phase === 'listening'
              ? 'opacity-100'
              : phase === 'uploading'
                ? 'opacity-90'
                : 'opacity-70'
          )}
          style={{
            background:
              phase === 'listening'
                ? 'radial-gradient(ellipse at center, rgba(6,182,212,0.45) 0%, rgba(6,182,212,0.12) 40%, transparent 72%)'
                : 'radial-gradient(ellipse at center, rgba(139,92,246,0.4) 0%, rgba(139,92,246,0.1) 40%, transparent 72%)',
            filter: 'blur(28px)',
          }}
        />
        <VioletOrb
          radius={1.4}
          state={orbState}
          // When idle, pulse is just ambient (0.3). When listening,
          // the analyser amplitude drives the reactive factor so the
          // orb breathes with the doctor's voice.
          reactive={phase === 'listening' ? Math.max(0.3, level) : 0.3}
        />
      </div>

      {phase === 'idle' || phase === 'requesting' ? (
        <>
          <h2 className="type-h1 text-text-primary">
            Dictate a quick summary
          </h2>
          <p className="mt-3 max-w-md text-[15px] leading-relaxed text-text-tertiary">
            Tap below and speak. Keep it natural — we&apos;ll turn your
            dictation into a structured SOAP note.
          </p>
          <div className="mt-8">
            <SpecularButton
              onClick={startRecording}
              variant="primary"
              size="lg"
              disabled={phase === 'requesting'}
            >
              <Mic className="h-4 w-4" aria-hidden />
              {phase === 'requesting' ? 'Getting mic ready…' : 'Start dictating'}
            </SpecularButton>
          </div>
          <p className="mt-6 text-[12px] text-text-muted">
            Up to 10 minutes. WebM/Opus — stays private.
          </p>
        </>
      ) : phase === 'listening' ? (
        <>
          <div
            className="font-mono text-[28px] tabular-nums text-text-primary"
            aria-live="polite"
          >
            {mm}:{ss}
          </div>
          <p className="mt-2 text-[13px] text-text-tertiary">
            Recording… speak in whatever order you like.
          </p>
          <div className="mt-8">
            <SpecularButton
              onClick={stopRecording}
              variant="secondary"
              size="lg"
              sweep={false}
            >
              <Square className="h-3.5 w-3.5 fill-current" aria-hidden />
              Stop &amp; process
            </SpecularButton>
          </div>
          <p className="mt-6 text-[12px] text-text-muted">
            Auto-stops at 10:00.
          </p>
        </>
      ) : phase === 'uploading' ? (
        <>
          <h2 className="type-h1 text-text-primary">
            Processing your dictation
          </h2>
          <p className="mt-3 flex items-center justify-center gap-2 text-[14px] text-text-tertiary">
            <Loader2 className="h-3.5 w-3.5 animate-spin" aria-hidden />
            Uploading and queuing for SOAP generation…
          </p>
        </>
      ) : (
        <>
          <h2 className="type-h1 text-text-primary">Something went wrong</h2>
          <p className="mt-3 max-w-md text-[14px] text-danger">
            {error ?? 'Unknown error.'}
          </p>
          <div className="mt-8">
            <SpecularButton
              onClick={() => {
                setError(null);
                setPhase('idle');
              }}
              variant="primary"
              size="md"
            >
              Try again
            </SpecularButton>
          </div>
        </>
      )}
    </div>
  );
}

// ----------------------------------------------------------------------------
// Clinician variant — calm halo + sage mic-dot + class-driven waveform.
// Replaces the Three.js VioletOrb with the landing-and-recording.html
// idiom (per CL-5: no theatrical motion). The level [0-1] from the
// AudioContext analyser drives a per-bar height multiplier so the
// waveform breathes with the doctor's voice.
// ----------------------------------------------------------------------------

function ClinicianVoiceDictatorView({
  phase,
  elapsed: _elapsed,
  mm,
  ss,
  level,
  error,
  onStart,
  onStop,
  onRetry,
}: {
  phase: Phase;
  elapsed: number;
  mm: number;
  ss: string;
  level: number;
  error: string | null;
  onStart: () => void;
  onStop: () => void;
  onRetry: () => void;
}) {
  const isListening = phase === 'listening';
  const isUploading = phase === 'uploading';
  const isError = phase === 'error';

  // Twelve bars with hand-tuned peaks so the waveform reads as alive
  // rather than uniform. The `level` ref scales the peak so quiet
  // moments collapse the meter and louder moments push it up.
  const peaks = [12, 18, 14, 20, 16, 22, 12, 18, 14, 10, 17, 13];
  const delays = [0, 0.1, 0.2, 0.3, 0.05, 0.15, 0.25, 0.4, 0.5, 0.35, 0.6, 0.55];
  const livePeak = (basePeak: number) =>
    isListening
      ? Math.max(8, basePeak * (0.6 + level * 0.8))
      : basePeak * 0.5;

  return (
    <div className="mx-auto flex max-w-xl flex-col items-center py-12 text-center sm:py-20">
      {/* Halo + mic centerpiece */}
      <div
        style={{
          position: 'relative',
          width: 220,
          height: 220,
          marginBottom: 24,
        }}
      >
        {(isListening || isUploading) && (
          <>
            <div className="qm-cl-halo" aria-hidden />
            <div className="qm-cl-halo qm-cl-halo-delayed" aria-hidden />
          </>
        )}
        <div
          className={cn(isListening && 'qm-cl-mic-dot')}
          style={{
            position: 'absolute',
            inset: 0,
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
          }}
        >
          <div
            style={{
              width: 96,
              height: 96,
              borderRadius: 999,
              background: 'var(--cream-card)',
              border: `1.5px solid ${isError ? 'var(--coral)' : 'var(--sage)'}`,
              boxShadow: 'var(--shadow-card)',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
            }}
          >
            {isUploading ? (
              <Loader2
                className="h-9 w-9 animate-spin"
                style={{ color: 'var(--sage)' }}
                aria-hidden
              />
            ) : (
              <Mic
                className="h-9 w-9"
                style={{
                  color: isError ? 'var(--coral)' : 'var(--sage)',
                }}
                aria-hidden
              />
            )}
          </div>
        </div>
      </div>

      {/* Waveform — quiet, present, sage-tinted */}
      {isListening && (
        <div
          className="flex items-end gap-[3px]"
          style={{ height: 24, marginBottom: 18 }}
          aria-hidden
        >
          {peaks.map((p, i) => (
            <span
              key={i}
              className="qm-cl-wave-bar"
              style={
                {
                  '--peak': `${livePeak(p)}px`,
                  animationDelay: `${delays[i]}s`,
                } as React.CSSProperties
              }
            />
          ))}
        </div>
      )}

      {/* Phase-specific copy + controls */}
      {phase === 'idle' || phase === 'requesting' ? (
        <>
          <h2
            className="qm-cl-serif"
            style={{
              fontSize: 32,
              fontWeight: 400,
              lineHeight: 1.15,
              letterSpacing: '-0.015em',
              color: 'var(--ink)',
              margin: 0,
            }}
          >
            Dictate a quick summary
          </h2>
          <p
            className="qm-cl-serif"
            style={{
              marginTop: 12,
              maxWidth: 460,
              fontSize: 16,
              lineHeight: 1.65,
              color: 'var(--ink-2)',
              fontStyle: 'italic',
            }}
          >
            Tap below and speak. Keep it natural — we&apos;ll turn your
            dictation into a structured SOAP note.
          </p>
          <div className="mt-8">
            <SpecularButton
              onClick={onStart}
              variant="primary"
              size="lg"
              disabled={phase === 'requesting'}
              theme="clinician"
            >
              <Mic className="h-4 w-4" aria-hidden />
              {phase === 'requesting' ? 'Getting mic ready…' : 'Start dictating'}
            </SpecularButton>
          </div>
          <p
            className="mt-6 text-[12px]"
            style={{ color: 'var(--ink-3)' }}
          >
            Up to 10 minutes. WebM/Opus — stays private.
          </p>
        </>
      ) : isListening ? (
        <>
          <div
            className="qm-cl-pill qm-cl-pill-sage"
            style={{
              padding: '6px 14px',
              fontSize: 13,
              marginBottom: 10,
            }}
          >
            <span className="qm-cl-pill-dot" />
            Recording · {mm}:{ss}
          </div>
          <p
            className="qm-cl-serif"
            style={{
              marginTop: 4,
              fontSize: 15,
              fontStyle: 'italic',
              color: 'var(--ink-3)',
            }}
          >
            Listening. You can speak as you would in any other visit.
          </p>
          <div className="mt-8">
            <SpecularButton
              onClick={onStop}
              variant="secondary"
              size="lg"
              sweep={false}
              theme="clinician"
            >
              <Square className="h-3.5 w-3.5 fill-current" aria-hidden />
              Stop &amp; process
            </SpecularButton>
          </div>
          <p
            className="mt-6 text-[12px]"
            style={{ color: 'var(--ink-3)' }}
          >
            Auto-stops at 10:00.
          </p>
        </>
      ) : isUploading ? (
        <>
          <h2
            className="qm-cl-serif"
            style={{
              fontSize: 28,
              fontWeight: 400,
              lineHeight: 1.2,
              letterSpacing: '-0.01em',
              color: 'var(--ink)',
              margin: 0,
            }}
          >
            Processing your dictation
          </h2>
          <p
            className="qm-cl-serif mt-3"
            style={{
              fontSize: 15,
              fontStyle: 'italic',
              color: 'var(--ink-2)',
            }}
          >
            Uploading and queuing for SOAP generation…
          </p>
        </>
      ) : (
        <>
          <h2
            className="qm-cl-serif"
            style={{
              fontSize: 28,
              fontWeight: 400,
              lineHeight: 1.2,
              letterSpacing: '-0.01em',
              color: 'var(--ink)',
              margin: 0,
            }}
          >
            Something went wrong
          </h2>
          <p
            className="mt-3 max-w-md text-[14px]"
            style={{ color: 'var(--coral-deep)' }}
          >
            {error ?? 'Unknown error.'}
          </p>
          <div className="mt-8">
            <SpecularButton
              onClick={onRetry}
              variant="primary"
              size="md"
              theme="clinician"
            >
              Try again
            </SpecularButton>
          </div>
        </>
      )}
    </div>
  );
}
