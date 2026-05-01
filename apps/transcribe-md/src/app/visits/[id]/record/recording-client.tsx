'use client';

// Phase 5 — Linear V1 Faithful live-recording client.
// Reference: docs/design-directions-v8-linear/recording.html
//
// Two-column layout (440px ‖ 1fr): centered mic + sage halo + 40-bar
// waveform + status row + actions on the left, live transcript on the
// right. Dark canvas throughout, sage accent, JetBrains Mono uppercase
// for status copy. The legacy LiveOrb dual-theme branch from Phase 2
// is dropped — Linear V1 is single-theme.
//
// 🔴 PROTECTED: All MediaRecorder lifecycle code (start, stop, onstop,
// ondataavailable, finalizeAndUpload, finalizeRef trampoline,
// streamRef cleanup, max-seconds tick) is preserved byte-for-byte.

import { useCallback, useEffect, useRef, useState } from 'react';
import { useRouter } from 'next/navigation';
import { toast } from 'sonner';

import { Ic } from '@/components/ui/icon';

type Phase = 'idle' | 'requesting' | 'recording' | 'uploading' | 'error';
type RecordingClientTheme = 'legacy' | 'clinician';

const MIME = 'audio/webm;codecs=opus';
const CHUNK_MS = 250;
const MAX_SECONDS = 30 * 60;

function pad2(n: number): string {
  return n < 10 ? `0${n}` : String(n);
}
function formatElapsed(sec: number): string {
  const m = Math.floor(sec / 60);
  const s = sec % 60;
  return `${pad2(m)}:${pad2(s)}`;
}

export function RecordingClient({
  visitId,
  patientName,
  specialty,
}: {
  visitId: string;
  patientName: string;
  specialty: string;
  /** @deprecated kept for back-compat; Linear V1 is single-theme. */
  theme?: RecordingClientTheme;
}) {
  const router = useRouter();
  const [phase, setPhase] = useState<Phase>('idle');
  const [elapsed, setElapsed] = useState(0);
  const [error, setError] = useState<string | null>(null);
  const [reducedMotion, setReducedMotion] = useState<boolean>(() => {
    if (typeof window === 'undefined') return false;
    return window.matchMedia('(prefers-reduced-motion: reduce)').matches;
  });

  const recorderRef = useRef<MediaRecorder | null>(null);
  const streamRef = useRef<MediaStream | null>(null);
  const chunksRef = useRef<Blob[]>([]);
  const tickRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const startTsRef = useRef<number>(0);
  const finalizingRef = useRef(false);
  // Audit H1 — preventive guard. The MediaRecorder's onstop handler is
  // registered once (inside `start`) and lives until the recording
  // ends. If anything in `finalizeAndUpload` ever starts closing over
  // a state value, onstop would fire with stale state (same class of
  // bug as the reverted mark-moments PATCH). Route the latest
  // finalizeAndUpload through this ref so future additions don't
  // re-introduce the pattern — onstop reads finalizeRef.current().
  const finalizeRef = useRef<() => Promise<void>>(async () => {});

  // Reduced-motion subscription (§8.9). Initial value is read by the
  // lazy useState initializer above; this effect only subscribes to
  // runtime flips (e.g. the user toggling the OS setting).
  useEffect(() => {
    if (typeof window === 'undefined') return;
    const mq = window.matchMedia('(prefers-reduced-motion: reduce)');
    const handler = () => setReducedMotion(mq.matches);
    mq.addEventListener('change', handler);
    return () => mq.removeEventListener('change', handler);
  }, []);

  // Cleanup on unmount.
  useEffect(() => {
    return () => {
      if (tickRef.current) clearInterval(tickRef.current);
      if (recorderRef.current?.state === 'recording') {
        try {
          recorderRef.current.stop();
        } catch {
          /* ignore */
        }
      }
      streamRef.current?.getTracks().forEach((t) => t.stop());
    };
  }, []);

  const finalizeAndUpload = useCallback(async () => {
    if (finalizingRef.current) return;
    finalizingRef.current = true;
    setPhase('uploading');
    // NOTE: if you add a dependency on component state to this
    // function, ensure the MediaRecorder.onstop handler below still
    // reads the LATEST version via finalizeRef.current() — see the
    // H1 preventive note where finalizeRef is declared.
    const blob = new Blob(chunksRef.current, { type: MIME });
    chunksRef.current = [];
    try {
      const res = await fetch(`/api/visits/${visitId}/dictation/upload`, {
        method: 'POST',
        headers: { 'Content-Type': MIME },
        body: blob,
      });
      if (!res.ok) {
        const body = await res.json().catch(() => ({}));
        throw new Error(body.error ?? `Upload failed (${res.status})`);
      }
      toast.success('Recording uploaded', {
        description: 'Drafting your note now.',
      });
      router.push(`/visits/${visitId}`);
      router.refresh();
    } catch (err) {
      finalizingRef.current = false;
      const msg = err instanceof Error ? err.message : 'Upload failed';
      setError(msg);
      setPhase('error');
      toast.error('Upload failed', { description: msg });
    }
  }, [visitId, router]);

  // Keep finalizeRef pointed at the current closure. `recorder.onstop`
  // reads from the ref rather than capturing `finalizeAndUpload`
  // directly, so swapping in a newer version — e.g. after a deps
  // change — doesn't leave a stale handler attached to an in-flight
  // MediaRecorder.
  finalizeRef.current = finalizeAndUpload;

  const start = useCallback(async () => {
    setError(null);
    setPhase('requesting');
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      streamRef.current = stream;
      const recorder = new MediaRecorder(stream, { mimeType: MIME });
      recorder.ondataavailable = (e) => {
        if (e.data && e.data.size > 0) chunksRef.current.push(e.data);
      };
      recorder.onstop = () => {
        streamRef.current?.getTracks().forEach((t) => t.stop());
        streamRef.current = null;
        if (tickRef.current) clearInterval(tickRef.current);
        tickRef.current = null;
        // Route through the ref so we always invoke the latest
        // finalizeAndUpload — preventive fix for audit H1.
        finalizeRef.current();
      };
      recorderRef.current = recorder;
      recorder.start(CHUNK_MS);
      startTsRef.current = Date.now();
      setElapsed(0);
      setPhase('recording');
      tickRef.current = setInterval(() => {
        const sec = Math.floor((Date.now() - startTsRef.current) / 1000);
        setElapsed(sec);
        if (sec >= MAX_SECONDS) stop();
      }, 250);
    } catch (err) {
      const msg =
        err instanceof Error ? err.message : 'Microphone access denied';
      setError(msg);
      setPhase('error');
      toast.error('Could not start recording', { description: msg });
    }
    // `finalizeAndUpload` is invoked via finalizeRef.current inside
    // recorder.onstop — no direct dependency needed, and including it
    // would re-render `start` unnecessarily.
  }, []);

  function stop() {
    if (recorderRef.current?.state === 'recording') {
      try {
        recorderRef.current.stop();
      } catch {
        /* ignore */
      }
    }
  }

  const isRecording = phase === 'recording';
  const isUploading = phase === 'uploading';
  const isError = phase === 'error';
  const isRequesting = phase === 'requesting';

  // Phase-aware status sentence rendered in JetBrains Mono uppercase.
  const statusLabel: string = isRecording
    ? 'RECORDING'
    : isUploading
      ? 'UPLOADING'
      : isRequesting
        ? 'REQUESTING PERMISSION'
        : isError
          ? 'ERROR'
          : 'READY';

  return (
    <div
      style={{
        display: 'grid',
        gridTemplateColumns: '440px 1fr',
        height: 'calc(100vh - 48px)',
        minHeight: 0,
        position: 'relative',
        background: 'var(--color-linear-bg)',
      }}
    >
      {/* Linear-style sage spotlight behind the left column. */}
      <div
        aria-hidden
        style={{
          position: 'absolute',
          top: -120,
          left: 60,
          width: 560,
          height: 560,
          background:
            'radial-gradient(closest-side, var(--color-linear-sage-glow), transparent 72%)',
          filter: 'blur(8px)',
          pointerEvents: 'none',
          zIndex: 0,
        }}
      />

      {/* LEFT — mic + halo + waveform + status + actions */}
      <aside
        style={{
          background: 'var(--color-linear-surface-1)',
          borderRight: '1px solid var(--color-linear-hairline)',
          padding: '28px 28px 22px',
          display: 'flex',
          flexDirection: 'column',
          position: 'relative',
          zIndex: 1,
        }}
      >
        {/* Patient meta */}
        <div style={{ marginBottom: 24 }}>
          <h1
            style={{
              margin: '0 0 4px',
              fontFamily: 'var(--font-sans)',
              fontSize: 18,
              fontWeight: 600,
              letterSpacing: '-0.015em',
              lineHeight: 1.25,
              color: 'var(--color-linear-text)',
            }}
          >
            {patientName}
          </h1>
          <div
            style={{
              fontFamily: 'var(--font-mono)',
              fontSize: 11.5,
              color: 'var(--color-linear-text-3)',
              fontVariantNumeric: 'tabular-nums',
              letterSpacing: 0,
              textTransform: 'capitalize',
            }}
          >
            {specialty}
          </div>
        </div>

        {/* Halo + mic centerpiece */}
        <div
          style={{
            display: 'grid',
            placeItems: 'center',
            margin: '18px auto 26px',
            width: 200,
            height: 200,
            position: 'relative',
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
          {/* Pulsing sage glow halo (active during recording / uploading) */}
          {(isRecording || isUploading) && !reducedMotion && (
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
          {/* Mic dot (sage-bright) */}
          <span
            aria-hidden
            className={isRecording && !reducedMotion ? 'qm-lin-mic-dot' : undefined}
            style={{
              position: 'relative',
              width: 16,
              height: 16,
              borderRadius: '50%',
              background: isError
                ? 'var(--color-linear-danger)'
                : 'var(--color-linear-sage-bright)',
              boxShadow: isError
                ? '0 0 18px rgba(212,87,74,0.65), 0 0 0 4px rgba(212,87,74,0.10)'
                : '0 0 18px rgba(155,196,168,0.65), 0 0 0 4px rgba(155,196,168,0.10)',
            }}
          />
        </div>

        {/* 40-bar waveform */}
        <Waveform
          active={isRecording}
          processing={isUploading}
          reducedMotion={reducedMotion}
        />

        {/* Status row — sage pill + mono elapsed */}
        <div
          style={{
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between',
            padding: '10px 0 6px',
            borderTop: '1px solid var(--color-linear-hairline)',
            borderBottom: '1px solid var(--color-linear-hairline)',
            marginBottom: 18,
          }}
        >
          <span
            className={
              isUploading || isRequesting
                ? 'qm-lin-pill qm-lin-pill--processing'
                : isError
                  ? 'qm-lin-pill qm-lin-pill--review'
                  : 'qm-lin-pill qm-lin-pill--sage'
            }
            style={{
              padding: '0 9px',
              height: 22,
              fontFamily: 'var(--font-sans)',
              fontSize: 10.5,
              letterSpacing: '0.07em',
              textTransform: 'uppercase',
            }}
          >
            {/* Use the inline dot for the sage variant since pill--sage
                doesn't include one; pill--processing has its own
                ::before dot. */}
            {!isUploading && !isRequesting && (
              <span
                aria-hidden
                style={{
                  width: 6,
                  height: 6,
                  borderRadius: '50%',
                  background: isError
                    ? 'var(--color-linear-danger)'
                    : 'var(--color-linear-sage)',
                  boxShadow: isError
                    ? '0 0 6px rgba(212,87,74,0.7)'
                    : '0 0 6px rgba(122,166,140,0.7)',
                }}
              />
            )}
            {statusLabel}
          </span>
          <span
            style={{
              fontFamily: 'var(--font-mono)',
              fontSize: 14,
              color: 'var(--color-linear-text)',
              fontVariantNumeric: 'tabular-nums',
              letterSpacing: 0,
              fontWeight: 500,
            }}
          >
            {formatElapsed(elapsed)}
          </span>
        </div>

        {error && (
          <p
            role="alert"
            style={{
              margin: '0 0 14px',
              fontSize: 12.5,
              color: 'var(--color-linear-danger)',
              lineHeight: 1.5,
            }}
          >
            {error}
          </p>
        )}

        {/* Actions */}
        <div
          style={{
            display: 'flex',
            alignItems: 'center',
            gap: 8,
            marginTop: 'auto',
            paddingTop: 18,
          }}
        >
          {phase === 'idle' || isError ? (
            <button
              type="button"
              onClick={start}
              className="qm-lin-btn-primary"
              style={{ height: 38, padding: '0 14px', flex: 2, fontSize: 12.5 }}
            >
              <span
                aria-hidden
                style={{
                  width: 8,
                  height: 8,
                  borderRadius: '50%',
                  background: '#0d1611',
                }}
              />
              Start recording
            </button>
          ) : isRequesting ? (
            <button
              type="button"
              disabled
              className="qm-lin-btn"
              style={{ height: 38, padding: '0 14px', flex: 1, fontSize: 12.5 }}
            >
              Requesting mic…
            </button>
          ) : isRecording ? (
            <button
              type="button"
              onClick={stop}
              className="qm-lin-btn-primary"
              style={{ height: 38, padding: '0 14px', flex: 2, fontSize: 12.5 }}
            >
              <Ic.stop width={12} height={12} aria-hidden />
              Stop &amp; process
            </button>
          ) : isUploading ? (
            <button
              type="button"
              disabled
              className="qm-lin-btn"
              style={{ height: 38, padding: '0 14px', flex: 1, fontSize: 12.5 }}
            >
              <span
                className={reducedMotion ? undefined : 'animate-spin'}
                style={{ display: 'inline-flex' }}
              >
                <Ic.sparkle width={12} height={12} aria-hidden />
              </span>
              Uploading…
            </button>
          ) : null}
        </div>
      </aside>

      {/* RIGHT — live transcript */}
      <section
        style={{
          display: 'flex',
          flexDirection: 'column',
          minWidth: 0,
          height: '100%',
          position: 'relative',
          zIndex: 1,
        }}
      >
        <div
          style={{
            display: 'flex',
            alignItems: 'center',
            gap: 10,
            padding: '14px 24px',
            borderBottom: '1px solid var(--color-linear-hairline)',
            fontFamily: 'var(--font-mono)',
            fontSize: 10,
            letterSpacing: '0.10em',
            textTransform: 'uppercase',
            color: 'var(--color-linear-text-3)',
            background: 'rgba(13,14,16,0.4)',
          }}
        >
          <span
            aria-hidden
            className={isRecording && !reducedMotion ? 'qm-lin-mic-dot' : undefined}
            style={{
              width: 6,
              height: 6,
              borderRadius: '50%',
              background: 'var(--color-linear-sage-bright)',
              boxShadow: '0 0 6px rgba(155,196,168,0.7)',
            }}
          />
          <span>Live transcript</span>
        </div>
        <div
          style={{
            flex: 1,
            overflow: 'auto',
            padding: '24px',
          }}
        >
          {isRecording ? (
            <div
              className="qm-lin-fade-in"
              style={{
                padding: '16px 18px',
                background: 'var(--color-linear-surface-1)',
                border: '1px solid var(--color-linear-border)',
                borderRadius: 8,
                color: 'var(--color-linear-text-3)',
                fontFamily: 'var(--font-sans)',
                fontSize: 13,
                lineHeight: 1.6,
                letterSpacing: '-0.005em',
              }}
            >
              <div
                style={{
                  display: 'inline-flex',
                  alignItems: 'center',
                  gap: 8,
                  marginBottom: 8,
                  color: 'var(--color-linear-sage-bright)',
                  fontFamily: 'var(--font-mono)',
                  fontSize: 10,
                  letterSpacing: '0.10em',
                  textTransform: 'uppercase',
                }}
              >
                <span
                  aria-hidden
                  className={!reducedMotion ? 'qm-lin-mic-dot' : undefined}
                  style={{
                    width: 6,
                    height: 6,
                    borderRadius: '50%',
                    background: 'var(--color-linear-sage-bright)',
                    boxShadow: '0 0 6px rgba(155,196,168,0.7)',
                  }}
                />
                Listening
              </div>
              <p style={{ margin: 0 }}>
                Streaming transcription lands in a follow-up pass. Your audio
                is being captured in 250 ms chunks and will be transcribed
                the moment you stop.
              </p>
            </div>
          ) : (
            <div
              style={{
                color: 'var(--color-linear-text-3)',
                fontFamily: 'var(--font-sans)',
                fontSize: 12.5,
                fontStyle: 'italic',
                letterSpacing: '-0.005em',
              }}
            >
              Transcript will appear here once recording starts.
            </div>
          )}
        </div>
      </section>
    </div>
  );
}

// ----------------------------------------------------------------------------
// Waveform — 40 sage bars whose height jitters in a clamped random walk
// (driven by the 80ms-tick CSS bar-pulse animation, with a modest
// per-bar phase via animationDelay). The mockup pre-randomizes the
// initial heights so the meter reads as alive on first paint. We
// recreate that shape with a deterministic sin-based seed.
// ----------------------------------------------------------------------------

function Waveform({
  active,
  processing,
  reducedMotion,
}: {
  active: boolean;
  processing: boolean;
  reducedMotion: boolean;
}) {
  const BARS = 40;
  return (
    <div
      aria-hidden
      style={{
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        gap: 3,
        height: 40,
        margin: '0 auto 22px',
        width: '100%',
        maxWidth: 340,
      }}
    >
      {Array.from({ length: BARS }).map((_, i) => {
        const seedHeight = 6 + Math.round(Math.abs(Math.sin(i * 1.7)) * 22);
        const delay = (i * 47) % 1100;
        const dur = 800 + ((i * 31) % 600);
        return (
          <span
            key={i}
            className={active && !reducedMotion ? 'qm-lin-wave-bar' : undefined}
            style={{
              width: 4,
              height: seedHeight,
              borderRadius: 2,
              background: processing
                ? 'var(--color-linear-warning)'
                : 'var(--color-linear-sage)',
              opacity: processing ? 0.4 : 0.85,
              transition:
                'height 80ms linear, background 200ms ease-out, opacity 200ms ease-out',
              animationDelay: active && !reducedMotion ? `-${delay}ms` : undefined,
              animationDuration: active && !reducedMotion ? `${dur}ms` : undefined,
            }}
          />
        );
      })}
    </div>
  );
}
