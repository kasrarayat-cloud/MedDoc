'use client';

// ============================================================================
// useRealtimeSession — WebRTC connection to OpenAI Realtime API
// ----------------------------------------------------------------------------
// Replaces useVoiceRecorder + useAudioPlayback. The browser opens a
// peer connection directly to OpenAI; our server only mints the ephemeral
// token (see /api/realtime/session) and dispatches tool calls (see
// /api/assistant-tool). Audio + tool events flow over WebRTC.
//
// Connection topology:
//
//   Mic → AudioTrack ──▶ RTCPeerConnection ──▶ OpenAI
//                     ◀──────── audio playback (peer's <audio>)
//                     ◀──── DataChannel events (transcripts, function_call, etc.)
//
// Events of interest on the data channel:
//   input_audio_buffer.speech_started     → user started talking (state: listening)
//   input_audio_buffer.speech_stopped     → user stopped (state: thinking)
//   conversation.item.input_audio_transcription.completed
//                                         → final user transcript
//   response.audio.delta                  → AI audio chunks (browser plays via track)
//   response.audio_transcript.done        → final AI transcript text
//   response.function_call_arguments.done → model wants to call a tool
//   response.done                         → AI finished current response
//
// Function calls: when the model emits response.function_call_arguments.done
// we POST {patientId, toolName, args} to /api/assistant-tool, then send the
// returned `output` back via conversation.item.create + response.create.
// ============================================================================

import { useCallback, useEffect, useRef, useState } from 'react';

export type RealtimeStatus =
  | 'idle'
  | 'connecting'
  | 'listening'
  | 'thinking'
  | 'working' // a tool call is in flight (editing / scheduling / etc.)
  | 'speaking'
  | 'error';

export interface RealtimeToolAction {
  type: string;
  [key: string]: unknown;
}

export interface UseRealtimeSessionOptions {
  patientId: string;
  /** Notified when a tool call completes — UI uses this to render
   *  document previews, action chips, etc. */
  onToolAction?: (action: RealtimeToolAction) => void;
  /** Surfaced as the AI's last spoken reply text. */
  onAssistantTranscript?: (text: string) => void;
  /** Surfaced as the doctor's last utterance text. */
  onUserTranscript?: (text: string) => void;
}

export interface UseRealtimeSession {
  status: RealtimeStatus;
  error: string | null;
  /**
   * Name of the tool currently executing (e.g. "edit_clinical_note",
   * "schedule_appointment"). Null when no tool is in flight. UI uses this
   * to render a descriptive label under the "working" orb state.
   */
  currentTool: string | null;
  /** Open the connection. Resolves once the data channel is open. */
  start: () => Promise<void>;
  /** Close everything — peer connection, audio tracks, data channel. */
  stop: () => void;
  /** True if a session is active in any non-idle state. */
  isActive: boolean;
  /**
   * Inject a synthetic user message into the session. Used by side-channel
   * UIs (e.g., file picker after upload completes) to feed event results
   * back to the model so it can react and speak naturally.
   */
  sendUserMessage: (text: string) => boolean;
  /**
   * Update the model's system instructions mid-session. Use after a
   * side-channel write changes patient context (uploaded file, AI-edited
   * note, etc.) so the AI's view of CUSTOM_PROCEDURES / RECENT_NOTES /
   * BRIEF_HISTORY stays current without restarting the WebRTC session.
   */
  updateInstructions: (instructions: string) => boolean;
}

const OPENAI_REALTIME_BASE = 'https://api.openai.com/v1/realtime';

export function useRealtimeSession(options: UseRealtimeSessionOptions): UseRealtimeSession {
  const { patientId } = options;

  const [status, setStatus] = useState<RealtimeStatus>('idle');
  const [error, setError] = useState<string | null>(null);
  const [currentTool, setCurrentTool] = useState<string | null>(null);

  // Keep callbacks fresh without restarting the session every render.
  const onToolActionRef = useRef(options.onToolAction);
  const onAssistantTranscriptRef = useRef(options.onAssistantTranscript);
  const onUserTranscriptRef = useRef(options.onUserTranscript);
  useEffect(() => {
    onToolActionRef.current = options.onToolAction;
    onAssistantTranscriptRef.current = options.onAssistantTranscript;
    onUserTranscriptRef.current = options.onUserTranscript;
  }, [options.onToolAction, options.onAssistantTranscript, options.onUserTranscript]);

  const peerRef = useRef<RTCPeerConnection | null>(null);
  const dataChannelRef = useRef<RTCDataChannel | null>(null);
  const localStreamRef = useRef<MediaStream | null>(null);
  const remoteAudioRef = useRef<HTMLAudioElement | null>(null);
  // Wall-clock when the WebRTC connection finished setting up. Used on
  // session end to POST actual duration to /api/realtime/session/end so
  // the metrics dashboard can price Realtime minutes. 0 = no active session.
  const sessionStartMsRef = useRef<number>(0);
  // ID of the in-flight model response, or null if none. Drives the
  // response.create queue: if we'd fire a create while a response is
  // still generating, OpenAI rejects with "Conversation already has an
  // active response". We buffer the intent in `pendingCreate` and flush
  // on the next response.done event.
  const activeResponseIdRef = useRef<string | null>(null);
  const pendingCreateRef = useRef(false);
  // Watchdog — if we transition to "thinking" and no response.done /
  // audio.delta / error arrives within this window, force back to
  // listening. Covers cases where OpenAI drops the terminal event on
  // the data channel (seen in practice: "thinking" sticks until the
  // doctor makes a sound, which fires speech_started and unsticks it).
  const thinkingWatchdogRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const THINKING_WATCHDOG_MS = 15_000;

  const clearThinkingWatchdog = useCallback(() => {
    if (thinkingWatchdogRef.current) {
      clearTimeout(thinkingWatchdogRef.current);
      thinkingWatchdogRef.current = null;
    }
  }, []);

  const armThinkingWatchdog = useCallback(() => {
    clearThinkingWatchdog();
    thinkingWatchdogRef.current = setTimeout(() => {
      console.warn(
        '[realtime] thinking watchdog fired — forcing listening (no response.done arrived)'
      );
      activeResponseIdRef.current = null;
      setStatus('listening');
    }, THINKING_WATCHDOG_MS);
  }, [clearThinkingWatchdog]);

  // Gate every response.create behind the active-response tracker. If no
  // response is in flight, send immediately; otherwise buffer a single bit
  // of intent that response.done will flush. One pending slot is enough —
  // coalescing repeat creates during the same response is the desired behavior.
  const requestResponseCreate = useCallback(() => {
    const dc = dataChannelRef.current;
    if (!dc || dc.readyState !== 'open') return;
    if (activeResponseIdRef.current) {
      pendingCreateRef.current = true;
      return;
    }
    dc.send(JSON.stringify({ type: 'response.create' }));
  }, []);

  // Cleanup — runs on stop() and on unmount. Tear down everything so the
  // mic light goes off and no orphan connections linger.
  const cleanup = useCallback(() => {
    // Report duration to the server so the metrics dashboard can price the
    // session. Fire-and-forget; if the beacon fails (e.g., page unload
    // mid-network), metrics lose a few seconds, not the whole session.
    const startedAt = sessionStartMsRef.current;
    if (startedAt > 0) {
      const durationSeconds = Math.max(1, Math.round((Date.now() - startedAt) / 1000));
      sessionStartMsRef.current = 0;
      const payload = JSON.stringify({ durationSeconds });
      try {
        // sendBeacon is the reliable primitive for unload-time pings —
        // browsers queue it even as the tab is closing. Falls back to
        // fetch() if sendBeacon isn't available.
        if (typeof navigator !== 'undefined' && typeof navigator.sendBeacon === 'function') {
          const blob = new Blob([payload], { type: 'application/json' });
          navigator.sendBeacon('/api/realtime/session/end', blob);
        } else {
          void fetch('/api/realtime/session/end', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: payload,
            keepalive: true,
          }).catch(() => { /* best-effort */ });
        }
      } catch {
        // swallow — metrics will be slightly short, not broken
      }
    }

    activeResponseIdRef.current = null;
    pendingCreateRef.current = false;
    if (thinkingWatchdogRef.current) {
      clearTimeout(thinkingWatchdogRef.current);
      thinkingWatchdogRef.current = null;
    }

    dataChannelRef.current?.close();
    dataChannelRef.current = null;
    peerRef.current?.getSenders().forEach((s) => {
      try { s.track?.stop(); } catch { /* ignore */ }
    });
    peerRef.current?.close();
    peerRef.current = null;
    localStreamRef.current?.getTracks().forEach((t) => t.stop());
    localStreamRef.current = null;
    if (remoteAudioRef.current) {
      remoteAudioRef.current.pause();
      remoteAudioRef.current.srcObject = null;
      remoteAudioRef.current = null;
    }
  }, []);

  useEffect(() => {
    return () => {
      cleanup();
    };
  }, [cleanup]);

  // Tool call handler — POSTs to our server, ships result back to the model
  // via the data channel using the OpenAI Realtime event format.
  const handleToolCall = useCallback(
    async (callId: string, toolName: string, argsRaw: string) => {
      let parsedArgs: Record<string, unknown> = {};
      try {
        parsedArgs = JSON.parse(argsRaw) as Record<string, unknown>;
      } catch {
        // Malformed args from model — let the server handle the error path.
      }

      // Flip to working state so the orb shows the tool-specific label while
      // the POST is in flight. Cleared when the tool returns.
      setCurrentTool(toolName);
      setStatus('working');

      let toolOutput = '';
      try {
        const res = await fetch('/api/assistant-tool', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ patientId, toolName, args: parsedArgs }),
        });
        const data = (await res.json()) as { output?: string; action?: RealtimeToolAction };
        toolOutput = data.output ?? '';
        console.info('[realtime] tool result:', toolName, { output: toolOutput, action: data.action });
        if (data.action) {
          onToolActionRef.current?.(data.action);
        }
      } catch (err) {
        toolOutput =
          err instanceof Error ? `Tool failed: ${err.message}` : 'Tool failed.';
        console.error('[realtime] tool dispatch failed:', toolName, err);
      } finally {
        // Tool done — drop back to thinking while the model processes the
        // result. speech_started / audio.delta / response.done drive the
        // rest of the state machine from here.
        setCurrentTool(null);
        setStatus('thinking');
      }

      // Ship the tool result back to the model. The Realtime event format:
      //   1. conversation.item.create with the function_call_output
      //   2. response.create to ask the model to continue
      const dc = dataChannelRef.current;
      if (!dc || dc.readyState !== 'open') return;
      dc.send(
        JSON.stringify({
          type: 'conversation.item.create',
          item: {
            type: 'function_call_output',
            call_id: callId,
            output: toolOutput,
          },
        })
      );
      requestResponseCreate();
    },
    [patientId, requestResponseCreate]
  );

  // Main event handler for data channel messages from OpenAI. Do NOT
  // read React state inside this callback — the dc.onmessage binding is
  // set once at session start and captures whatever closure was current
  // then. Using refs or unconditional setters is safe; reading `status`
  // here reads a stale value and was the root cause of the orb getting
  // stuck on "thinking" until the doctor made a noise (which flipped
  // it via input_audio_buffer.speech_started).
  const handleEvent = useCallback(
    (raw: string) => {
      let event: { type: string; [key: string]: unknown };
      try {
        event = JSON.parse(raw) as typeof event;
      } catch {
        return;
      }
      // Coarse trace of every state-transition-worthy event so the user
      // can open DevTools and see exactly what happened if the session
      // feels stuck or unresponsive.
      switch (event.type) {
        case 'input_audio_buffer.speech_started':
          console.info('[realtime] speech_started (doctor talking)');
          clearThinkingWatchdog();
          setStatus('listening');
          break;
        case 'input_audio_buffer.speech_stopped':
          console.info('[realtime] speech_stopped — committing, awaiting model');
          setStatus('thinking');
          armThinkingWatchdog();
          break;
        case 'input_audio_buffer.committed':
          console.info('[realtime] audio_buffer.committed');
          break;
        case 'response.created': {
          const resp = (event as { response?: { id?: string } }).response;
          activeResponseIdRef.current = resp?.id ?? 'unknown';
          console.info('[realtime] response.created', activeResponseIdRef.current);
          // Re-arm so a response that starts but never emits audio/done
          // still frees the orb.
          armThinkingWatchdog();
          break;
        }
        case 'response.audio.delta':
          // Unconditional set — React bails on identity equality for
          // primitives, and reading `status` here closes over a stale
          // value from session-start.
          setStatus('speaking');
          clearThinkingWatchdog();
          break;
        case 'response.audio_transcript.done': {
          const transcript = (event as { transcript?: string }).transcript;
          console.info('[realtime] assistant transcript done:', transcript?.slice(0, 120));
          if (typeof transcript === 'string' && transcript.trim()) {
            onAssistantTranscriptRef.current?.(transcript);
          }
          break;
        }
        case 'conversation.item.input_audio_transcription.completed': {
          const transcript = (event as { transcript?: string }).transcript;
          console.info('[realtime] user transcript:', transcript?.slice(0, 120));
          if (typeof transcript === 'string' && transcript.trim()) {
            onUserTranscriptRef.current?.(transcript);
          }
          break;
        }
        case 'response.function_call_arguments.done': {
          const callId = (event as { call_id?: string }).call_id;
          const name = (event as { name?: string }).name;
          const args = (event as { arguments?: string }).arguments;
          console.info('[realtime] tool call:', name, args);
          if (callId && name) {
            // Tool calls can run long; the watchdog shouldn't fire while
            // the server is doing the work. handleToolCall sets 'working'
            // and transitions back to 'thinking' at the end, which will
            // re-arm via the speech_stopped path if needed.
            clearThinkingWatchdog();
            void handleToolCall(callId, name, args ?? '{}');
          }
          break;
        }
        case 'response.done':
        case 'response.cancelled':
        case 'response.failed':
        case 'output_audio_buffer.stopped': {
          // Any terminal event frees the orb. `response.done` is the
          // normal path; the others cover OpenAI-side drops / cancels.
          console.info('[realtime]', event.type);
          activeResponseIdRef.current = null;
          clearThinkingWatchdog();
          if (pendingCreateRef.current) {
            pendingCreateRef.current = false;
            const dc = dataChannelRef.current;
            if (dc && dc.readyState === 'open') {
              dc.send(JSON.stringify({ type: 'response.create' }));
            }
          }
          setStatus('listening');
          break;
        }
        case 'error': {
          const err = (event as { error?: { message?: string; code?: string } }).error;
          console.error('[realtime] error event:', err);
          if (err?.message) setError(err.message);
          // Don't leave the orb spinning on a backend error.
          clearThinkingWatchdog();
          setStatus('listening');
          break;
        }
      }
    },
    [handleToolCall, armThinkingWatchdog, clearThinkingWatchdog]
  );

  const start = useCallback(async () => {
    if (status !== 'idle' && status !== 'error') return;
    setError(null);
    setStatus('connecting');

    try {
      // Detect browser's IANA timezone so the server can frame the system
      // prompt in local time. Without this, the model generates scheduledAt
      // ISO strings in UTC and appointments end up off by the user's offset
      // (e.g., Pacific doctor says "10 AM" → model emits "10:00Z" → reads
      // back as 3 AM local).
      let timezone: string | undefined;
      try {
        timezone = Intl.DateTimeFormat().resolvedOptions().timeZone;
      } catch {
        // Older browsers / restricted environments — server falls back to UTC.
      }

      // 1. Mint an ephemeral session token from our server.
      const sessionResp = await fetch('/api/realtime/session', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ patientId, timezone }),
      });
      if (!sessionResp.ok) {
        const data = (await sessionResp.json().catch(() => ({}))) as { error?: string };
        throw new Error(data.error || `Session creation failed (${sessionResp.status})`);
      }
      const { clientSecret, model } = (await sessionResp.json()) as {
        clientSecret: string;
        model: string;
      };

      // 2. Open the peer connection. Set up audio output sink first so we
      // can receive the model's voice as soon as the track arrives.
      const pc = new RTCPeerConnection();
      peerRef.current = pc;

      const remoteAudio = document.createElement('audio');
      remoteAudio.autoplay = true;
      remoteAudioRef.current = remoteAudio;
      pc.ontrack = (e) => {
        remoteAudio.srcObject = e.streams[0];
      };

      // 3. Mic → outbound track. Browser default echoCancellation/noise
      // suppression keeps the mic from picking up the AI's own voice.
      const localStream = await navigator.mediaDevices.getUserMedia({
        audio: { echoCancellation: true, noiseSuppression: true, autoGainControl: true },
      });
      localStreamRef.current = localStream;
      for (const track of localStream.getAudioTracks()) {
        pc.addTrack(track, localStream);
      }

      // 4. Data channel for events (transcripts, tool calls, etc.).
      const dc = pc.createDataChannel('oai-events');
      dataChannelRef.current = dc;
      dc.onmessage = (e) => handleEvent(typeof e.data === 'string' ? e.data : '');
      dc.onopen = () => {
        // Clock starts now — first moment of billable Realtime time.
        sessionStartMsRef.current = Date.now();
        // Once open, OpenAI immediately starts streaming events. Default
        // status: listening. The server VAD will refine to thinking/speaking
        // based on actual audio.
        setStatus('listening');
      };
      dc.onclose = () => {
        if (status !== 'idle' && status !== 'error') setStatus('idle');
      };

      // 5. SDP exchange. Browser creates an offer, POSTs to OpenAI, which
      // returns the answer SDP. POST is to a model-specific endpoint.
      const offer = await pc.createOffer();
      await pc.setLocalDescription(offer);

      const sdpResp = await fetch(`${OPENAI_REALTIME_BASE}?model=${encodeURIComponent(model)}`, {
        method: 'POST',
        headers: {
          Authorization: `Bearer ${clientSecret}`,
          'Content-Type': 'application/sdp',
        },
        body: offer.sdp ?? '',
      });
      if (!sdpResp.ok) {
        throw new Error(`OpenAI SDP exchange failed (${sdpResp.status})`);
      }
      const answerSdp = await sdpResp.text();
      await pc.setRemoteDescription({ type: 'answer', sdp: answerSdp });
    } catch (err) {
      const message = err instanceof Error ? err.message : 'Failed to start session';
      setError(message);
      setStatus('error');
      cleanup();
    }
  }, [patientId, status, handleEvent, cleanup]);

  const stop = useCallback(() => {
    cleanup();
    setStatus('idle');
    setCurrentTool(null);
  }, [cleanup]);

  // Inject a user message into the conversation. Returns true if the message
  // was sent, false if the data channel isn't open. Used by side-channel UIs
  // (file picker, future ones) to feed action results back to the model.
  const sendUserMessage = useCallback((text: string): boolean => {
    const dc = dataChannelRef.current;
    if (!dc || dc.readyState !== 'open') return false;
    dc.send(
      JSON.stringify({
        type: 'conversation.item.create',
        item: {
          type: 'message',
          role: 'user',
          content: [{ type: 'input_text', text }],
        },
      })
    );
    requestResponseCreate();
    return true;
  }, [requestResponseCreate]);

  // Push a session.update event with refreshed system instructions. Returns
  // true if the channel is open and the message was sent. The Realtime API
  // applies the new instructions to the model's next response without
  // dropping the active conversation.
  const updateInstructions = useCallback((instructions: string): boolean => {
    const dc = dataChannelRef.current;
    if (!dc || dc.readyState !== 'open') return false;
    dc.send(
      JSON.stringify({
        type: 'session.update',
        session: { instructions },
      })
    );
    return true;
  }, []);

  return {
    status,
    error,
    start,
    stop,
    isActive: status !== 'idle' && status !== 'error',
    sendUserMessage,
    updateInstructions,
    currentTool,
  };
}
