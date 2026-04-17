'use client';

// ============================================================================
// useAudioPlayback — TTS playback with mid-stream interrupt
// ----------------------------------------------------------------------------
// Caller passes text → hook fetches /api/tts → plays the returned MP3 via
// HTMLAudioElement. `stop()` interrupts playback at any time (used by the
// barge-in path: if VAD detects the doctor speaking while the AI is talking,
// we cut the AI off and start recording).
//
// Status:
//   idle    — no playback in flight
//   loading — TTS request in progress
//   playing — audio element is actually outputting sound
//   error   — fetch or decode failed (see `error` field)
//
// onEnded fires when audio finishes naturally (not interrupted) — the voice
// state machine uses this to flip back to listening for the next utterance.
// ============================================================================

import { useCallback, useEffect, useRef, useState } from 'react';

export type PlaybackStatus = 'idle' | 'loading' | 'playing' | 'error';

export interface UseAudioPlaybackOptions {
  /** Fired when audio finishes playing without being interrupted. */
  onEnded?: () => void;
}

export interface UseAudioPlayback {
  status: PlaybackStatus;
  error: string | null;
  /** Speak the given text. Cancels any in-flight playback first. */
  play: (text: string) => Promise<void>;
  /** Interrupt current playback. No-op if idle. Does NOT fire onEnded. */
  stop: () => void;
}

export function useAudioPlayback(options: UseAudioPlaybackOptions = {}): UseAudioPlayback {
  const [status, setStatus] = useState<PlaybackStatus>('idle');
  const [error, setError] = useState<string | null>(null);

  const audioRef = useRef<HTMLAudioElement | null>(null);
  const objectUrlRef = useRef<string | null>(null);
  const onEndedRef = useRef(options.onEnded);
  // Aborts an in-flight fetch when stop() is called before audio starts.
  const fetchAbortRef = useRef<AbortController | null>(null);
  // Distinguish natural end (fires onEnded) from interrupt (doesn't).
  const wasInterruptedRef = useRef(false);

  useEffect(() => {
    onEndedRef.current = options.onEnded;
  }, [options.onEnded]);

  const cleanup = useCallback(() => {
    if (audioRef.current) {
      audioRef.current.pause();
      audioRef.current.src = '';
      audioRef.current = null;
    }
    if (objectUrlRef.current) {
      URL.revokeObjectURL(objectUrlRef.current);
      objectUrlRef.current = null;
    }
    fetchAbortRef.current?.abort();
    fetchAbortRef.current = null;
  }, []);

  // Cleanup on unmount — never leak a playing audio element or object URL.
  useEffect(() => {
    return () => {
      cleanup();
    };
  }, [cleanup]);

  const stop = useCallback(() => {
    wasInterruptedRef.current = true;
    cleanup();
    setStatus('idle');
  }, [cleanup]);

  const play = useCallback(
    async (text: string) => {
      // Always cancel any prior playback first — guarantees a single audio
      // element at a time, no overlapping TTS streams.
      cleanup();
      wasInterruptedRef.current = false;
      setError(null);
      setStatus('loading');

      const controller = new AbortController();
      fetchAbortRef.current = controller;

      try {
        const res = await fetch('/api/tts', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ text }),
          signal: controller.signal,
        });
        if (!res.ok) {
          const data = (await res.json().catch(() => ({}))) as { error?: string };
          throw new Error(data.error || `TTS HTTP ${res.status}`);
        }
        const blob = await res.blob();
        const url = URL.createObjectURL(blob);
        objectUrlRef.current = url;

        const audio = new Audio(url);
        audioRef.current = audio;
        audio.onplay = () => setStatus('playing');
        audio.onended = () => {
          // Only fire onEnded for natural completion. Interrupt path sets
          // wasInterruptedRef and runs cleanup() directly via stop().
          if (!wasInterruptedRef.current) {
            cleanup();
            setStatus('idle');
            onEndedRef.current?.();
          }
        };
        audio.onerror = () => {
          setError('Audio playback failed.');
          setStatus('error');
          cleanup();
        };
        await audio.play();
      } catch (err) {
        // Abort surfaces as an Error with name='AbortError'. Treat that as
        // a clean stop, not a failure — the caller intentionally cancelled.
        if (err instanceof Error && err.name === 'AbortError') {
          setStatus('idle');
          return;
        }
        const message = err instanceof Error ? err.message : 'Playback failed';
        setError(message);
        setStatus('error');
        cleanup();
      }
    },
    [cleanup]
  );

  return { status, error, play, stop };
}
