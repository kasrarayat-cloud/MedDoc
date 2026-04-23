'use client';

// HANDOFF §2.3 live-recording client (Gate 9). Cinematic orb centre
// with timer; right rail shows a placeholder transcript. MediaRecorder
// captures audio in 250ms webm/opus chunks (same cadence as the
// existing VoiceDictator) and uploads on stop.

import { useCallback, useEffect, useRef, useState } from 'react';
import { useRouter } from 'next/navigation';
import { toast } from 'sonner';

import { Ic } from '@/components/ui/icon';
import { SpecChip, type SpecialtyKind } from '@/components/ui/spec-chip';
import { LiveOrb } from '@/components/recording/live-orb';

type Phase = 'idle' | 'requesting' | 'recording' | 'uploading' | 'error';

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
}: {
  visitId: string;
  patientName: string;
  specialty: string;
}) {
  const router = useRouter();
  const [phase, setPhase] = useState<Phase>('idle');
  const [elapsed, setElapsed] = useState(0);
  const [marks, setMarks] = useState<number[]>([]);
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
      // Persist marked moments alongside the upload. The PATCH route
      // lives on /api/visits/[id] in a later gate — for now we POST
      // onto a side helper via the same dictation route if markedMoments
      // are present. If the endpoint doesn't know the field yet it's
      // ignored; payload stays small.
      if (marks.length > 0) {
        const momentsPayload = marks.map((t) => ({ timestampMs: t }));
        try {
          await fetch(`/api/visits/${visitId}/dictation/upload`, {
            method: 'PATCH',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ markedMoments: momentsPayload }),
          });
        } catch {
          /* best-effort — don't block the happy path */
        }
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
  }, [visitId, marks, router]);

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
        finalizeAndUpload();
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
  }, [finalizeAndUpload]);

  function stop() {
    if (recorderRef.current?.state === 'recording') {
      try {
        recorderRef.current.stop();
      } catch {
        /* ignore */
      }
    }
  }

  function markMoment() {
    if (phase !== 'recording') return;
    const t = Date.now() - startTsRef.current;
    setMarks((prev) => [...prev, t]);
  }

  const isRecording = phase === 'recording';
  const isUploading = phase === 'uploading';

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
            <>
              <button
                type="button"
                onClick={markMoment}
                className="qm-btn qm-btn-ghost"
              >
                <Ic.star width={14} height={14} />
                Mark moment
                {marks.length > 0 && (
                  <span
                    style={{
                      fontSize: 10,
                      fontFamily: 'var(--mono)',
                      color: 'var(--accent-bright)',
                      marginLeft: 4,
                    }}
                  >
                    {marks.length}
                  </span>
                )}
              </button>
              <button
                type="button"
                onClick={stop}
                className="qm-btn qm-btn-primary"
                style={{ padding: '10px 18px' }}
              >
                <Ic.stop width={14} height={14} />
                Stop & transcribe
              </button>
            </>
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
        {marks.length > 0 && (
          <div style={{ marginTop: 28 }}>
            <div className="qm-sectlabel" style={{ marginBottom: 10 }}>
              § Marked moments
            </div>
            <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
              {marks.map((ms, i) => (
                <div
                  key={i}
                  style={{
                    fontFamily: 'var(--mono)',
                    fontSize: 12,
                    color: 'var(--fg-2)',
                    padding: '6px 10px',
                    borderRadius: 8,
                    background: 'rgba(139,92,255,0.06)',
                    border: '1px solid rgba(139,92,255,0.15)',
                  }}
                >
                  ★ {formatElapsed(Math.floor(ms / 1000))}
                </div>
              ))}
            </div>
          </div>
        )}
      </aside>
    </div>
  );
}
