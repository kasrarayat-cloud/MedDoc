'use client';

// ============================================================================
// VoiceDictator — live mic capture with MediaRecorder + AudioContext analyser.
// ----------------------------------------------------------------------------
// Phase 5 — Linear V1 Faithful re-skin.
// Reference: docs/design-directions-v8-linear/voice-add.html
//
// Centered panel: 96px sage-haloed mic chip, 16-bar live waveform driven
// by the AudioContext analyser amplitude, JetBrains Mono uppercase
// status sentence, and qm-lin-btn-primary "Stop & process" CTA. The
// Phase 2 dual-theme branch (legacy VioletOrb vs clinician halo) is
// collapsed — Linear V1 is single-theme. The `theme` prop stays in the
// signature as a deprecated no-op so existing call sites
// (visits/[id]/page.tsx) keep working without edits.
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
import { Mic, Square, Loader2 } from 'lucide-react';
import { toast } from 'sonner';

import { isSkinBeta } from '@/config/skin-beta';

type Phase = 'idle' | 'requesting' | 'listening' | 'uploading' | 'error';
type VoiceDictatorTheme = 'legacy' | 'clinician';

const MIME = 'audio/webm;codecs=opus';
// 250 ms chunks, same cadence scribe's live path uses — keeps memory
// bounded without losing audio if the user stops mid-buffer.
const CHUNK_MS = 250;
const MAX_SECONDS = 10 * 60; // 10 minutes

interface VoiceDictatorProps {
  visitId: string;
  /** @deprecated kept for back-compat; Linear V1 is single-theme. */
  theme?: VoiceDictatorTheme;
}

export function VoiceDictator({ visitId }: VoiceDictatorProps) {
  const router = useRouter();
  const [phase, setPhase] = useState<Phase>('idle');
  const [elapsed, setElapsed] = useState(0);
  const [error, setError] = useState<string | null>(null);
  const [level, setLevel] = useState(0); // 0-1 amplitude, drives waveform reactivity
  const [reducedMotion, setReducedMotion] = useState<boolean>(() => {
    if (typeof window === 'undefined') return false;
    return window.matchMedia('(prefers-reduced-motion: reduce)').matches;
  });

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

  // Reduced-motion subscription — disable halo pulse + waveform animation
  // when the user opts out at the OS level.
  useEffect(() => {
    if (typeof window === 'undefined') return;
    const mq = window.matchMedia('(prefers-reduced-motion: reduce)');
    const handler = () => setReducedMotion(mq.matches);
    mq.addEventListener('change', handler);
    return () => mq.removeEventListener('change', handler);
  }, []);

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

    // Wire a tiny analyser so the waveform's reactive prop reflects the
    // mic amplitude — makes the recording feel alive rather than frozen.
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

  const mm = Math.floor(elapsed / 60);
  const ss = (elapsed % 60).toString().padStart(2, '0');

  const isListening = phase === 'listening';
  const isUploading = phase === 'uploading';
  const isError = phase === 'error';
  const isRequesting = phase === 'requesting';

  // ── C3 calm-skin dictation (Stage-1 capture-finish, flag-gated) ────────────
  // SKIN-ONLY: the 🔴 PROTECTED MediaRecorder / AudioContext / analyser /
  // finalizeAndUpload / start/stopRecording lifecycle above is untouched. This
  // branch only re-skins the presentation into the calm C3 capture card (the
  // same qm-c3-rec-* language as the record screen), reusing the SAME handlers
  // (startRecording / stopRecording / error-reset), the SAME {mm}:{ss} binding,
  // the SAME phase booleans, and the SAME analyser-driven <Waveform level>.
  // Flag OFF → the original Linear V1 render below runs verbatim.
  if (isSkinBeta()) {
    return (
      <div style={{ maxWidth: 520, margin: '40px auto 64px', padding: '0 20px' }}>
        <div className="qm-c3-rec-card" style={{ margin: '0 auto' }}>
          {phase === 'idle' || isRequesting ? (
            <>
              <span className="qm-c3-rec-kicker">Voice note</span>
              <h1 className="qm-c3-rec-h">Dictate the visit</h1>
              <p className="qm-c3-rec-p">
                Tap start and speak naturally — we&apos;ll turn your dictation
                into a structured SOAP note after you stop. Nothing is processed
                until you do.
              </p>
              <button
                type="button"
                onClick={startRecording}
                disabled={isRequesting}
                className="qm-c3-rec-go"
              >
                <span className="qm-c3-rec-go-dot" aria-hidden />
                {isRequesting ? 'Getting mic ready…' : 'Start dictating'}
              </button>
              <p className="qm-c3-rec-hint">
                Up to 10 minutes · WebM/Opus · stays private
              </p>
            </>
          ) : isListening ? (
            <>
              <div className="qm-c3-rec-statusline" aria-live="polite">
                <span
                  className={
                    reducedMotion
                      ? 'qm-c3-rec-dot live'
                      : 'qm-c3-rec-dot live qm-lin-mic-dot'
                  }
                  aria-hidden
                />
                <span>Recording</span>
              </div>
              <div className="qm-c3-rec-timer">
                {mm}:{ss}
              </div>
              <div className="qm-c3-rec-wave" aria-hidden>
                <Waveform
                  active={isListening}
                  processing={false}
                  level={level}
                  reducedMotion={reducedMotion}
                />
              </div>
              <p className="qm-c3-rec-honest">
                Listening to your dictation. The note is written after you stop —
                there&apos;s no live transcript to watch.
              </p>
              <div className="qm-c3-rec-controls">
                <button
                  type="button"
                  onClick={stopRecording}
                  className="qm-c3-rec-stop"
                >
                  <Square style={{ width: 13, height: 13, fill: 'currentColor' }} aria-hidden />
                  Stop &amp; process
                </button>
              </div>
              <p className="qm-c3-rec-hint">Auto-stops at 10:00</p>
            </>
          ) : isUploading ? (
            <>
              <div
                className={reducedMotion ? 'qm-c3-rec-spin done' : 'qm-c3-rec-spin'}
                aria-hidden
              />
              <h1 className="qm-c3-rec-h" aria-live="polite">
                Processing your dictation…
              </h1>
              <p className="qm-c3-rec-hint" aria-live="polite">
                Uploading and queuing for SOAP generation — you can leave; it&apos;ll
                be ready on your dashboard.
              </p>
            </>
          ) : (
            <>
              <h1 className="qm-c3-rec-h">Something went wrong</h1>
              <p className="qm-c3-rec-error" role="alert">
                {error ?? 'Unknown error.'}
              </p>
              <button
                type="button"
                onClick={() => {
                  setError(null);
                  setPhase('idle');
                }}
                className="qm-c3-rec-go"
              >
                Try again
              </button>
            </>
          )}
        </div>
      </div>
    );
  }

  return (
    <div
      style={{
        margin: '0 auto',
        maxWidth: 560,
        padding: '48px 24px 64px',
        display: 'flex',
        flexDirection: 'column',
        alignItems: 'center',
        textAlign: 'center',
      }}
    >
      {/* Halo + mic centerpiece */}
      <div
        style={{
          position: 'relative',
          width: 200,
          height: 200,
          marginBottom: 24,
          display: 'grid',
          placeItems: 'center',
        }}
      >
        {/* concentric sage rings */}
        <span
          aria-hidden
          style={{
            position: 'absolute',
            inset: 0,
            borderRadius: '50%',
            border: '1px solid rgba(122,166,140,0.18)',
          }}
        />
        <span
          aria-hidden
          style={{
            position: 'absolute',
            inset: 24,
            borderRadius: '50%',
            border: '1px solid rgba(122,166,140,0.26)',
          }}
        />
        <span
          aria-hidden
          style={{
            position: 'absolute',
            inset: 48,
            borderRadius: '50%',
            border: '1px solid rgba(122,166,140,0.36)',
          }}
        />
        {/* Pulsing sage glow halo (active during listening / uploading) */}
        {(isListening || isUploading) && !reducedMotion && (
          <span
            aria-hidden
            className="qm-lin-mic-halo"
            style={{
              position: 'absolute',
              inset: 36,
              borderRadius: '50%',
              background:
                'radial-gradient(closest-side, rgba(155,196,168,0.32), rgba(122,166,140,0) 70%)',
            }}
          />
        )}
        {/* Mic chip */}
        <div
          aria-hidden
          className={isListening && !reducedMotion ? 'qm-lin-mic-dot' : undefined}
          style={{
            position: 'relative',
            width: 96,
            height: 96,
            borderRadius: '50%',
            background: 'var(--color-linear-surface-2)',
            border: `1.5px solid ${
              isError
                ? 'var(--color-linear-danger)'
                : 'var(--color-linear-sage)'
            }`,
            boxShadow:
              '0 0 0 1px var(--color-linear-hairline-strong), 0 8px 24px rgba(0,0,0,0.35)',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
          }}
        >
          {isUploading ? (
            <Loader2
              className={reducedMotion ? undefined : 'animate-spin'}
              style={{
                width: 36,
                height: 36,
                color: 'var(--color-linear-sage-bright)',
              }}
              aria-hidden
            />
          ) : (
            <Mic
              style={{
                width: 36,
                height: 36,
                color: isError
                  ? 'var(--color-linear-danger)'
                  : 'var(--color-linear-sage-bright)',
              }}
              aria-hidden
            />
          )}
        </div>
      </div>

      {/* Live waveform — 16 bars, AudioContext-driven amplitude */}
      <Waveform
        active={isListening}
        processing={isUploading}
        level={level}
        reducedMotion={reducedMotion}
      />

      {/* Phase-specific copy + controls */}
      {phase === 'idle' || isRequesting ? (
        <>
          <h2
            style={{
              margin: 0,
              fontFamily: 'var(--font-sans)',
              fontSize: 24,
              fontWeight: 500,
              lineHeight: 1.2,
              letterSpacing: '-0.012em',
              color: 'var(--color-linear-text)',
            }}
          >
            Dictate a quick summary
          </h2>
          <p
            style={{
              marginTop: 12,
              maxWidth: 460,
              fontFamily: 'var(--font-sans)',
              fontSize: 14,
              lineHeight: 1.55,
              letterSpacing: '-0.005em',
              color: 'var(--color-linear-text-2)',
            }}
          >
            Tap below and speak. Keep it natural — we&apos;ll turn your
            dictation into a structured SOAP note.
          </p>
          <div style={{ marginTop: 28 }}>
            <button
              type="button"
              onClick={startRecording}
              disabled={isRequesting}
              className="qm-lin-btn-primary"
              style={{
                height: 36,
                padding: '0 18px',
                fontSize: 13,
              }}
            >
              <Mic style={{ width: 14, height: 14 }} aria-hidden />
              {isRequesting ? 'Getting mic ready…' : 'Start dictating'}
            </button>
          </div>
          <p
            style={{
              marginTop: 24,
              fontFamily: 'var(--font-mono)',
              fontSize: 11,
              letterSpacing: '0.05em',
              color: 'var(--color-linear-text-3)',
              textTransform: 'uppercase',
            }}
          >
            Up to 10 minutes · WebM/Opus · Stays private
          </p>
        </>
      ) : isListening ? (
        <>
          <span
            className="qm-lin-pill qm-lin-pill--sage"
            style={{
              height: 22,
              padding: '0 9px',
              fontFamily: 'var(--font-sans)',
              fontSize: 10.5,
              letterSpacing: '0.07em',
              textTransform: 'uppercase',
              marginBottom: 12,
            }}
          >
            <span
              aria-hidden
              style={{
                width: 6,
                height: 6,
                borderRadius: '50%',
                background: 'var(--color-linear-sage)',
                boxShadow: '0 0 6px rgba(122,166,140,0.7)',
              }}
            />
            Recording · {mm}:{ss}
          </span>
          <p
            style={{
              margin: 0,
              fontFamily: 'var(--font-sans)',
              fontSize: 13.5,
              color: 'var(--color-linear-text-2)',
              letterSpacing: '-0.005em',
            }}
          >
            Listening. You can speak as you would in any other visit.
          </p>
          <div style={{ marginTop: 28 }}>
            <button
              type="button"
              onClick={stopRecording}
              className="qm-lin-btn-primary"
              style={{
                height: 36,
                padding: '0 18px',
                fontSize: 13,
              }}
            >
              <Square
                style={{ width: 12, height: 12, fill: 'currentColor' }}
                aria-hidden
              />
              Stop &amp; process
            </button>
          </div>
          <p
            style={{
              marginTop: 22,
              fontFamily: 'var(--font-mono)',
              fontSize: 11,
              letterSpacing: '0.05em',
              color: 'var(--color-linear-text-3)',
              textTransform: 'uppercase',
            }}
          >
            Auto-stops at 10:00
          </p>
        </>
      ) : isUploading ? (
        <>
          <h2
            style={{
              margin: 0,
              fontFamily: 'var(--font-sans)',
              fontSize: 22,
              fontWeight: 500,
              lineHeight: 1.2,
              letterSpacing: '-0.012em',
              color: 'var(--color-linear-text)',
            }}
          >
            Processing your dictation
          </h2>
          <p
            style={{
              marginTop: 12,
              display: 'inline-flex',
              alignItems: 'center',
              justifyContent: 'center',
              gap: 8,
              fontFamily: 'var(--font-sans)',
              fontSize: 13,
              color: 'var(--color-linear-text-2)',
            }}
          >
            <Loader2
              className={reducedMotion ? undefined : 'animate-spin'}
              style={{ width: 14, height: 14 }}
              aria-hidden
            />
            Uploading and queuing for SOAP generation…
          </p>
        </>
      ) : (
        <>
          <h2
            style={{
              margin: 0,
              fontFamily: 'var(--font-sans)',
              fontSize: 22,
              fontWeight: 500,
              lineHeight: 1.2,
              letterSpacing: '-0.012em',
              color: 'var(--color-linear-text)',
            }}
          >
            Something went wrong
          </h2>
          <p
            style={{
              marginTop: 12,
              maxWidth: 460,
              fontSize: 13,
              color: 'var(--color-linear-danger)',
            }}
          >
            {error ?? 'Unknown error.'}
          </p>
          <div style={{ marginTop: 28 }}>
            <button
              type="button"
              onClick={() => {
                setError(null);
                setPhase('idle');
              }}
              className="qm-lin-btn-primary"
              style={{
                height: 32,
                padding: '0 14px',
                fontSize: 12.5,
              }}
            >
              Try again
            </button>
          </div>
        </>
      )}
    </div>
  );
}

// ----------------------------------------------------------------------------
// Waveform — 16 sage bars whose live height is driven by the
// AudioContext analyser amplitude (0-1). Quiet moments collapse the
// meter and louder moments push it up; the per-bar phase comes from a
// deterministic sin-based seed so the meter reads as alive on first
// paint without a per-frame setState. Falls back to a flat row when
// reduced-motion is set or when not actively listening.
// ----------------------------------------------------------------------------

function Waveform({
  active,
  processing,
  level,
  reducedMotion,
}: {
  active: boolean;
  processing: boolean;
  level: number;
  reducedMotion: boolean;
}) {
  const BARS = 16;
  return (
    <div
      aria-hidden
      style={{
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        gap: 3,
        height: 32,
        marginBottom: 24,
        width: '100%',
        maxWidth: 220,
      }}
    >
      {Array.from({ length: BARS }).map((_, i) => {
        const seed = 0.5 + (Math.sin(i * 0.9) * 0.5 + 0.5) * 0.5;
        const baseHeight = 6;
        const peakHeight = active
          ? Math.max(6, Math.round(baseHeight + seed * (8 + level * 22)))
          : baseHeight;
        const delay = (i * 67) % 900;
        const dur = 700 + ((i * 53) % 500);
        return (
          <span
            key={i}
            className={
              active && !reducedMotion ? 'qm-lin-wave-bar' : undefined
            }
            style={{
              width: 3,
              height: peakHeight,
              borderRadius: 2,
              background: processing
                ? 'var(--color-linear-warning)'
                : 'var(--color-linear-sage)',
              opacity: processing ? 0.4 : 0.85,
              transition:
                'height 80ms linear, background 200ms ease-out, opacity 200ms ease-out',
              animationDelay:
                active && !reducedMotion ? `-${delay}ms` : undefined,
              animationDuration:
                active && !reducedMotion ? `${dur}ms` : undefined,
            }}
          />
        );
      })}
    </div>
  );
}
