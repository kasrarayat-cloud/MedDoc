'use client';

import { useCallback, useEffect, useRef, useState } from 'react';
import { useRouter } from 'next/navigation';
import { presignLiveUploadAction } from './actions';

type Phase = 'idle' | 'starting' | 'recording' | 'ending' | 'error';

interface FinalSegment {
  id: string;
  speaker: string;
  text: string;
}

interface InterimSegment {
  speaker: string;
  text: string;
}

interface Props {
  visitId: string;
}

// Chunk interval in ms — matches spec §9 ("250ms chunks"). MediaRecorder
// fires ondataavailable on this cadence.
const CHUNK_MS = 250;
const MIME = 'audio/webm;codecs=opus';

function speakerLabel(raw: string): { label: string; color: string } {
  // Cleanup runs server-side after finalize; the live UI uses Deepgram's
  // neutral labels. Colour them by parity so the clinician can tell them
  // apart — M7 can map to CLINICIAN/PATIENT live once we have confidence
  // in the diarization.
  if (raw === 'UNKNOWN') return { label: 'Speaker ?', color: 'text-slate-400' };
  const m = /^speaker_(\d+)$/.exec(raw);
  if (m) {
    const n = Number(m[1]);
    return {
      label: `Speaker ${n + 1}`,
      color: n % 2 === 0 ? 'text-sky-300' : 'text-emerald-300',
    };
  }
  return { label: raw, color: 'text-slate-300' };
}

export default function RecordClient({ visitId }: Props) {
  const router = useRouter();
  const [phase, setPhase] = useState<Phase>('idle');
  const [finals, setFinals] = useState<FinalSegment[]>([]);
  const [interim, setInterim] = useState<InterimSegment | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [wsLost, setWsLost] = useState(false);

  const wsRef = useRef<WebSocket | null>(null);
  const recorderRef = useRef<MediaRecorder | null>(null);
  const streamRef = useRef<MediaStream | null>(null);
  const audioChunksRef = useRef<Blob[]>([]);
  const startTimeRef = useRef<number>(0);
  // "user ended" marker so the onclose handler can distinguish expected
  // close from a connection drop and only show the "Connection lost"
  // banner in the latter case.
  const endingRef = useRef(false);

  const cleanup = useCallback(() => {
    try {
      recorderRef.current?.stop();
    } catch {
      /* already stopped */
    }
    streamRef.current?.getTracks().forEach((t) => t.stop());
    if (wsRef.current && wsRef.current.readyState === WebSocket.OPEN) {
      try {
        wsRef.current.close();
      } catch {
        /* already closing */
      }
    }
    recorderRef.current = null;
    streamRef.current = null;
    wsRef.current = null;
  }, []);

  useEffect(() => {
    return () => cleanup();
  }, [cleanup]);

  async function start() {
    setError(null);
    setWsLost(false);
    setFinals([]);
    setInterim(null);
    audioChunksRef.current = [];
    endingRef.current = false;
    setPhase('starting');

    try {
      if (!navigator.mediaDevices?.getUserMedia) {
        throw new Error('This browser does not support audio recording.');
      }
      if (typeof MediaRecorder === 'undefined' || !MediaRecorder.isTypeSupported(MIME)) {
        throw new Error(`This browser does not support ${MIME}.`);
      }

      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      streamRef.current = stream;

      // WebSocket URL — same origin as the scribe app (scribe.<domain>).
      // Caddy routes /api/ws/* to the scribe-ws sidecar.
      const wsUrl =
        `${window.location.protocol.replace('http', 'ws')}//${window.location.host}` +
        `/api/ws/visit/${visitId}`;

      const ws = new WebSocket(wsUrl);
      ws.binaryType = 'arraybuffer';
      wsRef.current = ws;

      await new Promise<void>((resolve, reject) => {
        ws.onopen = () => resolve();
        ws.onerror = () =>
          reject(new Error('WebSocket connection failed — check scribe-ws.'));
      });

      ws.onmessage = (event) => {
        if (typeof event.data !== 'string') return;
        try {
          const msg = JSON.parse(event.data) as {
            type?: string;
            speaker?: string;
            text?: string;
            code?: string;
          };
          if (msg.type === 'interim' && msg.speaker && msg.text) {
            setInterim({ speaker: msg.speaker, text: msg.text });
          } else if (msg.type === 'final' && msg.speaker && msg.text) {
            setFinals((prev) => [
              ...prev,
              {
                id: `${Date.now()}-${Math.random().toString(36).slice(2, 8)}`,
                speaker: msg.speaker!,
                text: msg.text!,
              },
            ]);
            setInterim(null);
          } else if (msg.type === 'error') {
            setError(`Deepgram error: ${msg.code ?? 'unknown'}`);
          }
          // 'ready' and 'closed' are informational — no UI change needed.
        } catch {
          /* malformed message — ignore */
        }
      };

      ws.onclose = () => {
        if (!endingRef.current) setWsLost(true);
      };

      const recorder = new MediaRecorder(stream, { mimeType: MIME });
      recorderRef.current = recorder;
      recorder.ondataavailable = (e) => {
        if (e.data && e.data.size > 0) {
          if (ws.readyState === WebSocket.OPEN) {
            // Blob is accepted by WebSocket.send; Caddy + scribe-ws handle
            // the binary frame and forward to Deepgram as an ArrayBuffer.
            ws.send(e.data);
          }
          audioChunksRef.current.push(e.data);
        }
      };
      recorder.onerror = (e) => {
        setError(`Recorder error: ${(e as unknown as { error?: { message?: string } }).error?.message ?? 'unknown'}`);
        setPhase('error');
        cleanup();
      };

      startTimeRef.current = Date.now();
      recorder.start(CHUNK_MS);
      setPhase('recording');
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
      setPhase('error');
      cleanup();
    }
  }

  async function end() {
    if (phase !== 'recording') return;
    setPhase('ending');
    endingRef.current = true;

    // Flush the last MediaRecorder chunk before we disconnect.
    const recorder = recorderRef.current;
    if (recorder && recorder.state !== 'inactive') {
      await new Promise<void>((resolve) => {
        recorder.onstop = () => resolve();
        try {
          recorder.stop();
        } catch {
          resolve();
        }
      });
    }

    // Tell the server to drain Deepgram + close — it will LPUSH any
    // trailing finals to Redis before shutting down the WS.
    const ws = wsRef.current;
    if (ws && ws.readyState === WebSocket.OPEN) {
      try {
        ws.send(JSON.stringify({ type: 'end' }));
      } catch {
        /* ignored — server will time it out */
      }
    }

    const durationSec = Math.round((Date.now() - startTimeRef.current) / 1000);
    const audioBlob = new Blob(audioChunksRef.current, { type: 'audio/webm' });

    try {
      const { uploadUrl, sourceFileName } = await presignLiveUploadAction({ visitId });

      // Direct PUT to MinIO — spec §10 "do NOT proxy audio through the app".
      const putRes = await fetch(uploadUrl, {
        method: 'PUT',
        headers: { 'Content-Type': 'audio/webm' },
        body: audioBlob,
      });
      if (!putRes.ok) throw new Error(`Upload failed: ${putRes.status}`);

      // Flush Redis → ScribeTranscript + enqueue finalize_visit.
      const completeRes = await fetch(`/api/uploads/${visitId}/live-complete`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ durationSec, sourceFileName }),
      });
      if (!completeRes.ok) {
        const body = (await completeRes.json().catch(() => ({}))) as { error?: string };
        throw new Error(body.error || `Finalize failed: ${completeRes.status}`);
      }

      streamRef.current?.getTracks().forEach((t) => t.stop());
      router.replace(`/visits/${visitId}`);
      router.refresh();
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
      setPhase('error');
      cleanup();
    }
  }

  return (
    <div className="space-y-5">
      {wsLost && phase === 'recording' && (
        <div className="border border-amber-600/40 rounded-xl p-4 bg-amber-500/10 text-sm text-amber-200">
          Connection lost. End the visit to save what was captured so far; live
          reconnect lands in a later milestone.
        </div>
      )}

      {error && (
        <div className="border border-rose-600/40 rounded-xl p-4 bg-rose-500/10 text-sm text-rose-200">
          {error}
        </div>
      )}

      <div className="border border-slate-800 rounded-xl p-5 bg-slate-900/40 min-h-[320px] max-h-[520px] overflow-y-auto space-y-2">
        {finals.length === 0 && !interim && phase !== 'recording' && (
          <div className="text-sm text-slate-500">
            Click Start to begin. The transcript will appear live here.
          </div>
        )}
        {finals.length === 0 && !interim && phase === 'recording' && (
          <div className="text-sm text-slate-500 italic">Listening…</div>
        )}
        {finals.map((seg) => {
          const { label, color } = speakerLabel(seg.speaker);
          return (
            <div key={seg.id} className="text-sm leading-relaxed">
              <span className={`font-medium ${color}`}>{label}:</span>{' '}
              <span className="text-slate-200">{seg.text}</span>
            </div>
          );
        })}
        {interim && (
          <div className="text-sm leading-relaxed italic">
            <span className={`font-medium ${speakerLabel(interim.speaker).color}`}>
              {speakerLabel(interim.speaker).label}:
            </span>{' '}
            <span className="text-slate-400">{interim.text}</span>
          </div>
        )}
      </div>

      <div className="flex items-center gap-3">
        {phase === 'recording' ? (
          <button
            type="button"
            onClick={end}
            className="flex-1 py-2.5 rounded-lg bg-rose-600 hover:bg-rose-500 text-sm font-semibold"
          >
            End visit
          </button>
        ) : (
          <button
            type="button"
            onClick={start}
            disabled={phase === 'starting' || phase === 'ending'}
            className="flex-1 py-2.5 rounded-lg bg-blue-600 hover:bg-blue-500 disabled:bg-slate-700 disabled:cursor-not-allowed text-sm font-semibold"
          >
            {phase === 'idle' || phase === 'error'
              ? 'Start recording'
              : phase === 'starting'
                ? 'Starting…'
                : phase === 'ending'
                  ? 'Finalizing…'
                  : 'Start recording'}
          </button>
        )}
        {phase === 'recording' && (
          <div className="flex items-center gap-2 text-xs text-slate-400">
            <span className="inline-block w-2 h-2 rounded-full bg-rose-500 animate-pulse" />
            recording
          </div>
        )}
      </div>
    </div>
  );
}
