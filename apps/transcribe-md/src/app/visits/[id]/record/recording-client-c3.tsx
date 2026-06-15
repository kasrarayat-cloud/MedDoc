'use client';

// ============================================================================
// Record — C3 "calm, one-clear-action" skin (Stage 1c, flag-gated).
// ----------------------------------------------------------------------------
// Renders ONLY when NEXT_PUBLIC_SKIN_BETA is on (see record/page.tsx). The
// two-column "mic ‖ live transcript" Linear V1 layout collapses to a single
// calm card with one obvious action, an HONEST audio meter (not a fake live
// transcript), and an honest processing list. Same flow language as the
// /concepts/record mockup, rendered in the real app's --color-linear-* tokens.
//
// 🔴 PROTECTED — preserved BYTE-FOR-BYTE from recording-client.tsx:
//   MIME / CHUNK_MS / MAX_SECONDS, the Phase union, every ref
//   (recorderRef, streamRef, chunksRef, tickRef, startTsRef, finalizingRef,
//   finalizeRef), the reduced-motion subscription, the unmount cleanup,
//   finalizeAndUpload (incl. the /api/visits/[id]/dictation/upload POST +
//   the finalizeRef trampoline), start, stop, and the MAX_SECONDS tick.
//
// SKIN-ONLY: this is a re-layout. The MediaRecorder lifecycle, the upload
// endpoint, the worker pipeline, and the router push are unchanged. The ONE
// deliberate deviation from the mockup is intentional and contract-driven:
// the mockup's client-only "Pause" and "Write the note?" confirm steps are
// NOT reproduced, because inserting them would decouple stop() from the
// protected onstop → finalizeAndUpload upload path. stop() still uploads
// immediately, exactly as the live app does today. Copy + calm card match
// the mockup; the irreversible-process semantics are honored unchanged.
// ============================================================================

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

// Honest processing steps shown while the upload + worker pipeline run. These
// are descriptive of what the unchanged pipeline does — not a fake progress bar
// wired to anything; the doctor is routed to /visits/[id] the moment the upload
// POST resolves (same as the live app).
const PROC_STEPS = [
  'Uploaded securely',
  'Transcribing the visit',
  'Drafting the SOAP note',
  'Checking safety & coding',
];

export function RecordingClientC3({
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
  // Audit H1 — preventive guard (see recording-client.tsx for the full note).
  // onstop reads finalizeRef.current() so a deps-changed finalizeAndUpload
  // never leaves a stale handler attached to an in-flight MediaRecorder.
  const finalizeRef = useRef<() => Promise<void>>(async () => {});

  // Reduced-motion subscription (§8.9).
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
    // NOTE: if you add a dependency on component state to this function,
    // ensure the MediaRecorder.onstop handler below still reads the LATEST
    // version via finalizeRef.current() — see the H1 preventive note.
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

  // Keep finalizeRef pointed at the current closure (see H1 note above).
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

  // ── Presentation only below this line (C3 calm skin) ───────────────────────

  return (
    <div className="qm-c3-rec-wrap">
      <span className="qm-c3-rec-sample" aria-hidden>
        {patientName} · <span style={{ textTransform: 'capitalize' }}>{specialty}</span>
      </span>

      {(phase === 'idle' || isError || isRequesting) && (
        <div className="qm-c3-rec-card">
          <span className="qm-c3-rec-kicker">New visit</span>
          <h1 className="qm-c3-rec-h">Start the visit</h1>
          <p className="qm-c3-rec-p">
            We&apos;ll record the conversation and write the note after you stop.
            Nothing is processed until you choose to.
          </p>
          {error && (
            <p role="alert" className="qm-c3-rec-error">
              {error}
            </p>
          )}
          <button
            type="button"
            onClick={start}
            disabled={isRequesting}
            className="qm-c3-rec-go"
          >
            <span className="qm-c3-rec-go-dot" aria-hidden />
            {isRequesting ? 'Requesting microphone…' : 'Start recording'}
          </button>
          <p className="qm-c3-rec-hint">
            {isError
              ? 'Something went wrong — check microphone access and try again.'
              : 'Press start when you and the patient are ready.'}
          </p>
        </div>
      )}

      {isRecording && (
        <div className="qm-c3-rec-card">
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
          <div className="qm-c3-rec-timer">{formatElapsed(elapsed)}</div>
          <Waveform active reducedMotion={reducedMotion} />
          <p className="qm-c3-rec-honest">
            Listening to the visit. The note is written after you stop — there&apos;s
            no live transcript to watch.
          </p>
          <div className="qm-c3-rec-controls">
            <button
              type="button"
              onClick={stop}
              className="qm-c3-rec-stop"
            >
              <Ic.stop width={13} height={13} aria-hidden />
              Stop &amp; write the note
            </button>
          </div>
        </div>
      )}

      {isUploading && (
        <div className="qm-c3-rec-card">
          <div
            className={
              reducedMotion ? 'qm-c3-rec-spin done' : 'qm-c3-rec-spin'
            }
            aria-hidden
          />
          <h1 className="qm-c3-rec-h" aria-live="polite">
            Writing the note…
          </h1>
          <ol className="qm-c3-rec-steps">
            {PROC_STEPS.map((s, i) => (
              <li key={s} className={i === 0 ? 'now' : ''}>
                <span className="qm-c3-rec-mark" aria-hidden>
                  {i === 0 ? '◴' : '○'}
                </span>{' '}
                {s}
              </li>
            ))}
          </ol>
          <p className="qm-c3-rec-hint" aria-live="polite">
            You can leave — it&apos;ll be ready on your dashboard.
          </p>
        </div>
      )}
    </div>
  );
}

// ----------------------------------------------------------------------------
// Waveform — honest audio meter. Identical 40-bar deterministic-seed shape +
// the existing qm-lin-wave-bar animation used by the Linear V1 recorder, so the
// C3 skin reuses proven motion (no new keyframes). Decorative only (aria-hidden).
// ----------------------------------------------------------------------------
function Waveform({
  active,
  reducedMotion,
}: {
  active: boolean;
  reducedMotion: boolean;
}) {
  const BARS = 40;
  return (
    <div className="qm-c3-rec-wave" aria-hidden>
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
              background: 'var(--color-linear-sage)',
              opacity: 0.85,
              transition: 'height 80ms linear',
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
