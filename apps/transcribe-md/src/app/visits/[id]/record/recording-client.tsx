'use client';

// HANDOFF §2.3 live-recording client (Gate 9). Cinematic orb centre
// with timer; right rail shows a placeholder transcript. MediaRecorder
// captures audio in 250ms webm/opus chunks (same cadence as the
// existing VoiceDictator) and uploads on stop.
//
// Phase 2 (Clinician remodel) — Strategy A dual-theme via additive
// `theme` prop. Default `'legacy'` keeps the LiveOrb + dark cinematic
// scene byte-for-byte. `theme="clinician"` replaces the Three.js
// LiveOrb with the calm class-driven chrome from
// landing-and-recording.html (.qm-cl-halo + sage .qm-cl-mic-dot +
// .qm-cl-wave-bar + .qm-cl-pill-sage timer + .qm-cl-transcript-line).
//
// 🔴 PROTECTED: All MediaRecorder lifecycle code (start, stop, onstop,
// ondataavailable, finalizeAndUpload, finalizeRef trampoline,
// streamRef cleanup, max-seconds tick) is preserved byte-for-byte.

import { useCallback, useEffect, useRef, useState } from 'react';
import { useRouter } from 'next/navigation';
import { toast } from 'sonner';

import { cn } from '@/lib/cn';
import { Ic } from '@/components/ui/icon';
import { SpecChip, type SpecialtyKind } from '@/components/ui/spec-chip';
import { LiveOrb } from '@/components/recording/live-orb';

type Phase = 'idle' | 'requesting' | 'recording' | 'uploading' | 'error';
type RecordingClientTheme = 'legacy' | 'clinician';

const MIME = 'audio/webm;codecs=opus';
const CHUNK_MS = 250;
const MAX_SECONDS = 30 * 60;

const KNOWN: readonly SpecialtyKind[] = [
  'cardiology',
  'pain',
  'ortho',
  'primary',
  'pulmonology',
  'ophthalmology',
];
function toSpecKind(raw: string): SpecialtyKind {
  const lower = raw.toLowerCase() as SpecialtyKind;
  return KNOWN.includes(lower) ? lower : 'primary';
}

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
  theme = 'legacy',
}: {
  visitId: string;
  patientName: string;
  specialty: string;
  /** Phase 2 (Clinician remodel) — additive theme prop. */
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

  if (theme === 'clinician') {
    return (
      <ClinicianRecordingView
        phase={phase}
        elapsed={elapsed}
        error={error}
        patientName={patientName}
        specialty={specialty}
        onStart={start}
        onStop={stop}
      />
    );
  }

  return (
    <div
      style={{
        height: '100%',
        display: 'grid',
        gridTemplateColumns: '1fr 380px',
        minHeight: 0,
      }}
    >
      {/* Centre stage — orb + timer + controls */}
      <div
        style={{
          position: 'relative',
          display: 'flex',
          flexDirection: 'column',
          alignItems: 'center',
          justifyContent: 'center',
          padding: 40,
          gap: 32,
        }}
      >
        <div
          style={{
            display: 'flex',
            flexDirection: 'column',
            alignItems: 'center',
            gap: 14,
          }}
        >
          <SpecChip kind={toSpecKind(specialty)} size="md" />
          <h1
            className="qm-serif"
            style={{
              margin: 0,
              fontSize: 30,
              fontWeight: 400,
              letterSpacing: '-0.02em',
              color: 'var(--fg)',
              textAlign: 'center',
            }}
          >
            Recording — <em style={{ color: 'var(--accent-bright)' }}>{patientName}</em>
          </h1>
        </div>

        <LiveOrb paused={!isRecording} reducedMotion={reducedMotion} />

        <div
          style={{
            fontFamily: 'var(--mono)',
            fontSize: 28,
            color: 'var(--fg)',
            letterSpacing: '0.05em',
          }}
        >
          {formatElapsed(elapsed)}
        </div>

        {error && (
          <p
            role="alert"
            style={{
              margin: 0,
              fontSize: 13,
              color: 'var(--coral)',
            }}
          >
            {error}
          </p>
        )}

        <div style={{ display: 'flex', gap: 10 }}>
          {phase === 'idle' || phase === 'error' ? (
            <button
              type="button"
              onClick={start}
              className="qm-btn qm-btn-primary"
              style={{ padding: '12px 22px', fontSize: 14 }}
            >
              <span
                aria-hidden
                style={{
                  width: 8,
                  height: 8,
                  borderRadius: 999,
                  background: '#FB7185',
                  boxShadow: '0 0 8px #FB7185',
                }}
              />
              Start recording
            </button>
          ) : phase === 'requesting' ? (
            <button type="button" disabled className="qm-btn qm-btn-ghost">
              Requesting mic…
            </button>
          ) : isRecording ? (
            <button
              type="button"
              onClick={stop}
              className="qm-btn qm-btn-primary"
              style={{ padding: '10px 18px' }}
            >
              <Ic.stop width={14} height={14} />
              Stop & transcribe
            </button>
          ) : isUploading ? (
            <button type="button" disabled className="qm-btn qm-btn-ghost">
              <span className="qm-spin" style={{ display: 'inline-block' }}>
                <Ic.sparkle width={14} height={14} />
              </span>
              Uploading…
            </button>
          ) : null}
        </div>
      </div>

      {/* Right rail — transcript placeholder. Real live transcript
         streams in once scribe-ws is wired (future pass). */}
      <aside
        style={{
          borderLeft: '1px solid var(--line)',
          background: 'rgba(12,10,22,0.4)',
          overflow: 'auto',
          padding: 24,
        }}
      >
        <div className="qm-sectlabel" style={{ marginBottom: 14 }}>
          § Live transcript
        </div>
        {isRecording ? (
          <div
            style={{
              padding: '18px 16px',
              borderRadius: 12,
              border: '1px dashed var(--line)',
              color: 'var(--fg-3)',
              fontSize: 12.5,
              lineHeight: 1.55,
            }}
          >
            <div
              style={{
                display: 'inline-flex',
                alignItems: 'center',
                gap: 8,
                marginBottom: 8,
                color: 'var(--accent-bright)',
              }}
            >
              <span
                style={{
                  width: 6,
                  height: 6,
                  borderRadius: 999,
                  background: 'var(--accent-bright)',
                }}
                className="qm-pulse"
              />
              Listening…
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
              color: 'var(--fg-4)',
              fontSize: 12.5,
              fontStyle: 'italic',
            }}
          >
            Transcript will appear here once recording starts.
          </div>
        )}
      </aside>
    </div>
  );
}

// ----------------------------------------------------------------------------
// Clinician variant — calm halo + sage mic-dot + class-driven waveform.
// Mirrors the visit-recording widget in landing-and-recording.html. Per
// CL-5: no Three.js orbs in Clinician, no springs, no bounces. The
// initials avatar replaces SpecChip for the doctor's social-cue visual
// identity (per the mockup's "EL — Mrs. Lopez" pattern).
// ----------------------------------------------------------------------------

function ClinicianRecordingView({
  phase,
  elapsed,
  error,
  patientName,
  specialty,
  onStart,
  onStop,
}: {
  phase: Phase;
  elapsed: number;
  error: string | null;
  patientName: string;
  specialty: string;
  onStart: () => void;
  onStop: () => void;
}) {
  const isRecording = phase === 'recording';
  const isUploading = phase === 'uploading';
  const isError = phase === 'error';

  // Twelve waveform bars, hand-tuned peaks per the mockup so the meter
  // reads as alive rather than uniform.
  const peaks = [12, 18, 14, 20, 16, 22, 12, 18, 14, 10, 17, 13];
  const delays = [0, 0.1, 0.2, 0.3, 0.05, 0.15, 0.25, 0.4, 0.5, 0.35, 0.6, 0.55];

  return (
    <div
      style={{
        display: 'flex',
        justifyContent: 'center',
        padding: '32px 24px 56px',
        minHeight: '100%',
      }}
    >
      <div
        className="qm-cl-card"
        style={{
          width: '100%',
          maxWidth: 760,
          padding: 40,
          borderRadius: 20,
        }}
      >
        {/* Patient header row: avatar + name + status pill */}
        <div
          style={{
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between',
            marginBottom: 28,
            gap: 16,
            flexWrap: 'wrap',
          }}
        >
          <div
            style={{
              display: 'flex',
              alignItems: 'center',
              gap: 14,
              minWidth: 0,
            }}
          >
            <div
              className="qm-cl-avatar qm-cl-avatar-sage"
              aria-hidden
              style={{
                width: 48,
                height: 48,
                borderRadius: 14,
                fontSize: 18,
              }}
            >
              {patientName.charAt(0).toUpperCase()}
            </div>
            <div style={{ minWidth: 0 }}>
              <div
                className="qm-cl-serif"
                style={{
                  fontSize: 22,
                  fontWeight: 500,
                  color: 'var(--ink)',
                  lineHeight: 1.2,
                  letterSpacing: '-0.005em',
                }}
              >
                Recording with {patientName}
              </div>
              <div
                style={{
                  fontSize: 13,
                  color: 'var(--ink-3)',
                  marginTop: 4,
                  display: 'flex',
                  alignItems: 'center',
                  gap: 8,
                }}
              >
                <span style={{ textTransform: 'capitalize' }}>{specialty}</span>
              </div>
            </div>
          </div>

          {isRecording && (
            <span
              className="qm-cl-pill qm-cl-pill-sage"
              style={{ padding: '6px 14px', fontSize: 13 }}
            >
              <span className="qm-cl-pill-dot" />
              Recording · {formatElapsed(elapsed)}
            </span>
          )}
          {isUploading && (
            <span
              className="qm-cl-pill qm-cl-pill-teal"
              style={{ padding: '6px 14px', fontSize: 13 }}
            >
              <span className="qm-cl-pill-dot" />
              Uploading
            </span>
          )}
          {isError && (
            <span
              className="qm-cl-pill qm-cl-pill-coral"
              style={{ padding: '6px 14px', fontSize: 13 }}
            >
              <span className="qm-cl-pill-dot" />
              Error
            </span>
          )}
        </div>

        {/* Halo + mic centerpiece */}
        <div
          style={{
            display: 'flex',
            flexDirection: 'column',
            alignItems: 'center',
            justifyContent: 'center',
            padding: '32px 0 12px',
          }}
        >
          <div
            style={{
              position: 'relative',
              width: 160,
              height: 160,
            }}
          >
            {(isRecording || isUploading) && (
              <>
                <div className="qm-cl-halo" aria-hidden />
                <div className="qm-cl-halo qm-cl-halo-delayed" aria-hidden />
              </>
            )}
            <div
              style={{
                position: 'absolute',
                inset: 0,
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
              }}
            >
              <div
                className={cn(isRecording && 'qm-cl-mic-dot')}
                style={{
                  width: 78,
                  height: 78,
                  borderRadius: 999,
                  background: 'var(--cream-card)',
                  border: `1.5px solid ${
                    isError ? 'var(--coral)' : 'var(--sage)'
                  }`,
                  boxShadow: 'var(--shadow-card)',
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                }}
                aria-hidden
              >
                <svg
                  width="32"
                  height="32"
                  viewBox="0 0 32 32"
                  fill="none"
                  aria-hidden
                >
                  <rect
                    x="12"
                    y="6"
                    width="8"
                    height="14"
                    rx="4"
                    fill={isError ? 'var(--coral)' : 'var(--sage)'}
                  />
                  <path
                    d="M8 17 q0 8 8 8 q8 0 8 -8"
                    stroke={isError ? 'var(--coral)' : 'var(--sage)'}
                    strokeWidth="1.6"
                    strokeLinecap="round"
                    fill="none"
                  />
                  <line
                    x1="16"
                    y1="25"
                    x2="16"
                    y2="29"
                    stroke={isError ? 'var(--coral)' : 'var(--sage)'}
                    strokeWidth="1.6"
                    strokeLinecap="round"
                  />
                </svg>
              </div>
            </div>
          </div>

          {/* Subtle waveform — present but quiet */}
          {isRecording && (
            <div
              className="flex items-end gap-[3px]"
              style={{ height: 22, marginTop: 24 }}
              aria-hidden
            >
              {peaks.map((p, i) => (
                <span
                  key={i}
                  className="qm-cl-wave-bar"
                  style={
                    {
                      '--peak': `${p}px`,
                      animationDelay: `${delays[i]}s`,
                    } as React.CSSProperties
                  }
                />
              ))}
            </div>
          )}

          <div
            className="qm-cl-serif"
            style={{
              marginTop: 18,
              fontSize: 14,
              fontStyle: 'italic',
              color: 'var(--ink-3)',
              textAlign: 'center',
              maxWidth: 460,
            }}
          >
            {phase === 'idle'
              ? 'Press start when you’re ready. You can stop whenever the visit ends.'
              : phase === 'requesting'
                ? 'Asking your browser for the microphone…'
                : isRecording
                  ? 'Listening. You can speak as you would in any other visit.'
                  : isUploading
                    ? 'Uploading and queuing the draft…'
                    : 'Something went wrong. Please try again.'}
          </div>
        </div>

        {error && (
          <p
            role="alert"
            style={{
              margin: '12px 0 0',
              fontSize: 13,
              color: 'var(--coral-deep)',
              textAlign: 'center',
            }}
          >
            {error}
          </p>
        )}

        {/* Live transcript placeholder — quiet, italic */}
        <div style={{ marginTop: 28 }}>
          <div className="qm-cl-section-label" style={{ marginBottom: 12 }}>
            Live transcript
          </div>
          {isRecording ? (
            <div
              className="qm-cl-serif"
              style={{
                fontSize: 15,
                lineHeight: 1.7,
                color: 'var(--ink-3)',
                fontStyle: 'italic',
                padding: '14px 16px',
                borderRadius: 12,
                background: 'var(--cream-2)',
                border: '1px dashed var(--line-strong)',
              }}
            >
              Streaming transcription lands in a follow-up pass. Your audio
              is being captured in 250 ms chunks and will be transcribed the
              moment you stop.
            </div>
          ) : (
            <div
              className="qm-cl-serif"
              style={{
                fontSize: 14,
                fontStyle: 'italic',
                color: 'var(--ink-4)',
                padding: '14px 16px',
              }}
            >
              Transcript will appear here once recording starts.
            </div>
          )}
        </div>

        {/* Footer controls */}
        <div
          style={{
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between',
            paddingTop: 28,
            marginTop: 28,
            borderTop: '1px solid var(--line)',
            gap: 12,
            flexWrap: 'wrap',
          }}
        >
          {phase === 'idle' || phase === 'error' ? (
            <>
              <span style={{ flex: 1 }} />
              <button
                type="button"
                onClick={onStart}
                className="qm-cl-btn qm-cl-btn-primary"
              >
                <span
                  aria-hidden
                  style={{
                    width: 8,
                    height: 8,
                    borderRadius: 999,
                    background: 'var(--coral)',
                    boxShadow: '0 0 0 3px var(--coral-tint)',
                  }}
                />
                Start recording
              </button>
            </>
          ) : phase === 'requesting' ? (
            <>
              <span style={{ flex: 1 }} />
              <button
                type="button"
                disabled
                className="qm-cl-btn qm-cl-btn-ghost"
                style={{ opacity: 0.6 }}
              >
                Requesting mic…
              </button>
            </>
          ) : isRecording ? (
            <>
              <span style={{ flex: 1 }} />
              <button
                type="button"
                onClick={onStop}
                className="qm-cl-btn qm-cl-btn-primary"
              >
                <Ic.stop width={14} height={14} />
                End visit & draft note
              </button>
            </>
          ) : isUploading ? (
            <>
              <span style={{ flex: 1 }} />
              <button
                type="button"
                disabled
                className="qm-cl-btn qm-cl-btn-ghost"
                style={{ opacity: 0.6 }}
              >
                <span className="qm-spin" style={{ display: 'inline-block' }}>
                  <Ic.sparkle width={14} height={14} />
                </span>
                Uploading…
              </button>
            </>
          ) : null}
        </div>
      </div>
    </div>
  );
}
