'use client';

// ============================================================================
// useVoiceRecorder — tap-to-start mic capture with silence-based auto-stop
// ----------------------------------------------------------------------------
// Lifecycle:
//   start()  — requests mic permission, opens MediaRecorder + AudioContext
//              analyser, begins capture and starts the VAD sampler
//   stop()   — manual early stop. Returns Blob, releases mic + analyser.
//
// Voice Activity Detection:
//   We sample the analyser's RMS volume at ~10Hz. The recording auto-stops
//   when the user has clearly started speaking AND has been silent for
//   `silenceTimeoutMs` consecutive ms. This avoids the "doctor releases the
//   button mid-sentence" failure mode of push-to-talk.
//
//   `onAutoStop` fires exactly once when VAD triggers — receives the same
//   Blob that a manual stop() would have returned. Manual stop() never
//   triggers onAutoStop (the caller already has the blob in hand).
//
// State machine:
//   idle → starting → listening (waiting for first sound)
//                  → recording (active speech)
//                  → stopping → idle (with blob via stop() OR onAutoStop)
//                  → error
// ============================================================================

import { useCallback, useEffect, useRef, useState } from 'react';

export type RecorderStatus =
  | 'idle'
  | 'starting'
  | 'listening' // mic open, no speech detected yet
  | 'recording' // VAD detected speech — silence countdown active
  | 'stopping'
  | 'error';

export interface UseVoiceRecorderOptions {
  /** ms of continuous silence after first speech before auto-stop. Default 2500. */
  silenceTimeoutMs?: number;
  /** Hard cap on recording length — safety net so a stuck session doesn't run forever. Default 60_000. */
  maxDurationMs?: number;
  /** Called when VAD auto-stops the recording. Receives the same Blob that stop() would. */
  onAutoStop?: (blob: Blob | null) => void;
}

export interface UseVoiceRecorder {
  status: RecorderStatus;
  error: string | null;
  /** Start capturing. Resolves when mic + analyser are running. */
  start: () => Promise<void>;
  /** Manual stop. Returns the captured audio blob (or null). Skips onAutoStop. */
  stop: () => Promise<Blob | null>;
  /** True for both 'listening' and 'recording' states. */
  isRecording: boolean;
}

// VAD tuning. Threshold is normalized RMS (0..1) of the time-domain signal.
// 0.015 is roughly "quiet office speech at 30cm from mic" — picks up normal
// dictation without triggering on HVAC / typing.
const VAD_VOLUME_THRESHOLD = 0.015;
const VAD_SAMPLE_INTERVAL_MS = 100;
const DEFAULT_SILENCE_TIMEOUT_MS = 2500;
const DEFAULT_MAX_DURATION_MS = 60_000;

export function useVoiceRecorder(options: UseVoiceRecorderOptions = {}): UseVoiceRecorder {
  const silenceTimeoutMs = options.silenceTimeoutMs ?? DEFAULT_SILENCE_TIMEOUT_MS;
  const maxDurationMs = options.maxDurationMs ?? DEFAULT_MAX_DURATION_MS;
  const onAutoStopRef = useRef(options.onAutoStop);
  // Keep callback ref current without making it a dep of start/stop callbacks.
  useEffect(() => {
    onAutoStopRef.current = options.onAutoStop;
  }, [options.onAutoStop]);

  const [status, setStatus] = useState<RecorderStatus>('idle');
  const [error, setError] = useState<string | null>(null);

  const recorderRef = useRef<MediaRecorder | null>(null);
  const streamRef = useRef<MediaStream | null>(null);
  const audioCtxRef = useRef<AudioContext | null>(null);
  const analyserRef = useRef<AnalyserNode | null>(null);
  const sourceRef = useRef<MediaStreamAudioSourceNode | null>(null);
  const chunksRef = useRef<Blob[]>([]);
  const stopResolverRef = useRef<((blob: Blob | null) => void) | null>(null);
  const vadIntervalRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const maxDurationTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  // Track whether the current stop() was triggered by VAD vs manual call.
  const autoStopFlagRef = useRef(false);
  // VAD bookkeeping
  const hasSpokenRef = useRef(false);
  const lastVoiceMsRef = useRef(0);

  // Release every external resource — mic, audio graph, timers. Called on
  // both clean stop and error paths.
  const releaseResources = useCallback(() => {
    if (vadIntervalRef.current) {
      clearInterval(vadIntervalRef.current);
      vadIntervalRef.current = null;
    }
    if (maxDurationTimerRef.current) {
      clearTimeout(maxDurationTimerRef.current);
      maxDurationTimerRef.current = null;
    }
    sourceRef.current?.disconnect();
    sourceRef.current = null;
    analyserRef.current?.disconnect();
    analyserRef.current = null;
    if (audioCtxRef.current && audioCtxRef.current.state !== 'closed') {
      audioCtxRef.current.close().catch(() => { /* ignore */ });
    }
    audioCtxRef.current = null;
    streamRef.current?.getTracks().forEach((t) => t.stop());
    streamRef.current = null;
    recorderRef.current = null;
    chunksRef.current = [];
    hasSpokenRef.current = false;
    lastVoiceMsRef.current = 0;
  }, []);

  // Cleanup on unmount — never leave the mic open.
  useEffect(() => {
    return () => {
      releaseResources();
    };
  }, [releaseResources]);

  // Internal: trigger MediaRecorder.stop(). The recorder.onstop handler
  // assembles the blob and resolves either the manual stop() promise or
  // the onAutoStop callback, depending on autoStopFlagRef.
  const triggerStop = useCallback((isAuto: boolean) => {
    autoStopFlagRef.current = isAuto;
    const recorder = recorderRef.current;
    if (!recorder || recorder.state === 'inactive') return;
    setStatus('stopping');
    try {
      recorder.stop();
    } catch (err) {
      const message = err instanceof Error ? err.message : 'Failed to stop recording.';
      setError(message);
      setStatus('error');
      releaseResources();
    }
  }, [releaseResources]);

  const start = useCallback(async () => {
    if (status === 'recording' || status === 'starting' || status === 'listening') return;
    setError(null);
    setStatus('starting');

    if (typeof window === 'undefined' || !navigator.mediaDevices?.getUserMedia) {
      setError('Microphone capture not supported in this browser.');
      setStatus('error');
      return;
    }

    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      streamRef.current = stream;

      const recorder = new MediaRecorder(stream);
      recorderRef.current = recorder;
      chunksRef.current = [];

      recorder.ondataavailable = (e) => {
        if (e.data && e.data.size > 0) chunksRef.current.push(e.data);
      };
      recorder.onstop = () => {
        const blob = chunksRef.current.length
          ? new Blob(chunksRef.current, { type: chunksRef.current[0].type || 'audio/webm' })
          : null;
        const wasAuto = autoStopFlagRef.current;
        autoStopFlagRef.current = false;
        const autoCallback = onAutoStopRef.current;
        const manualResolver = stopResolverRef.current;
        stopResolverRef.current = null;
        releaseResources();
        setStatus('idle');
        if (wasAuto) {
          autoCallback?.(blob);
        } else {
          manualResolver?.(blob);
        }
      };
      recorder.onerror = (event: Event) => {
        const err = (event as unknown as { error?: { message?: string } }).error;
        setError(err?.message ?? 'Recorder error');
        setStatus('error');
        releaseResources();
      };

      // ── VAD setup ──
      // AudioContext + AnalyserNode for volume sampling. Keeps the audio
      // graph entirely separate from MediaRecorder so they can be stopped
      // independently.
      // eslint-disable-next-line @typescript-eslint/no-explicit-any
      const AudioCtx: typeof AudioContext = window.AudioContext ?? (window as any).webkitAudioContext;
      const audioCtx = new AudioCtx();
      const source = audioCtx.createMediaStreamSource(stream);
      const analyser = audioCtx.createAnalyser();
      analyser.fftSize = 512;
      source.connect(analyser);
      audioCtxRef.current = audioCtx;
      sourceRef.current = source;
      analyserRef.current = analyser;

      const buf = new Float32Array(analyser.fftSize);
      hasSpokenRef.current = false;
      lastVoiceMsRef.current = 0;
      const sampleStartMs = Date.now();

      vadIntervalRef.current = setInterval(() => {
        const a = analyserRef.current;
        if (!a) return;
        a.getFloatTimeDomainData(buf);
        let sumSq = 0;
        for (let i = 0; i < buf.length; i++) sumSq += buf[i] * buf[i];
        const rms = Math.sqrt(sumSq / buf.length);

        const now = Date.now();
        if (rms > VAD_VOLUME_THRESHOLD) {
          if (!hasSpokenRef.current) {
            hasSpokenRef.current = true;
            setStatus('recording');
          }
          lastVoiceMsRef.current = now;
        } else if (
          hasSpokenRef.current &&
          now - lastVoiceMsRef.current > silenceTimeoutMs
        ) {
          // Auto-stop: silence detected after a real utterance.
          triggerStop(true);
        }
      }, VAD_SAMPLE_INTERVAL_MS);

      // Hard cap — never let a session run forever (e.g., user walks away
      // with the mic open). Triggers an auto-stop just like silence.
      maxDurationTimerRef.current = setTimeout(() => {
        if (recorderRef.current && recorderRef.current.state !== 'inactive') {
          triggerStop(true);
        }
      }, maxDurationMs);

      recorder.start();
      // Initial state is `listening` until the first volume spike flips
      // it to `recording`. Lets the UI distinguish "waiting for you" from
      // "actively capturing speech".
      setStatus('listening');

      // Suppress an unused-var warning for the timing baseline; keeping
      // the variable in case we want to add a no-speech-at-all timeout later.
      void sampleStartMs;
    } catch (err) {
      const message =
        err instanceof Error
          ? err.name === 'NotAllowedError'
            ? 'Microphone access was denied. Allow it in browser settings.'
            : err.message
          : 'Failed to start recording.';
      setError(message);
      setStatus('error');
      releaseResources();
    }
  }, [status, silenceTimeoutMs, maxDurationMs, releaseResources, triggerStop]);

  const stop = useCallback(async () => {
    const recorder = recorderRef.current;
    if (!recorder || recorder.state === 'inactive') {
      setStatus('idle');
      return null;
    }
    return new Promise<Blob | null>((resolve) => {
      stopResolverRef.current = resolve;
      triggerStop(false);
      // If triggerStop hit an error path, releaseResources already ran and
      // status is 'error' — but the promise will hang. Guard:
      if (recorderRef.current === null) {
        stopResolverRef.current = null;
        resolve(null);
      }
    });
  }, [triggerStop]);

  return {
    status,
    error,
    start,
    stop,
    isRecording: status === 'listening' || status === 'recording',
  };
}
