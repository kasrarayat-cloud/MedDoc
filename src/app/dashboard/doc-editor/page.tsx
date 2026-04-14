'use client';

/* eslint-disable @typescript-eslint/no-explicit-any */
// Web Speech API type declarations
declare global {
  interface Window {
    SpeechRecognition: any;
    webkitSpeechRecognition: any;
  }
}

import React, { useState, useRef, useEffect, useCallback } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import {
  Upload,
  FileText,
  Bot,
  User,
  Send,
  Edit3,
  X,
  AlertCircle,
  Loader2,
  Sparkles,
  Mic,
  MicOff,
  Download,
  FileDown,
} from 'lucide-react';

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

interface Message {
  id: string;
  role: 'user' | 'assistant' | 'system';
  content: string;
  timestamp: Date;
}

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function makeId(): string {
  return Math.random().toString(36).substring(2) + Date.now().toString(36);
}

function formatTime(date: Date): string {
  return date.toLocaleTimeString('en-US', {
    hour: 'numeric',
    minute: '2-digit',
    hour12: true,
  });
}

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

export default function DocEditorPage() {
  // File state
  const [file, setFile] = useState<File | null>(null);
  const [documentContent, setDocumentContent] = useState('');
  const [isDragOver, setIsDragOver] = useState(false);
  const [uploadError, setUploadError] = useState('');

  // Chat state
  const [messages, setMessages] = useState<Message[]>([]);
  const [inputText, setInputText] = useState('');
  const [isProcessing, setIsProcessing] = useState(false);

  // Voice Assistant State - MediaRecorder + Whisper with first-speech buffer
  // idle: not recording
  // listening: recording, waiting for user's FIRST speech (no timer yet)
  // processing: user has started speaking, 2.5s silence detection active
  // submitting: audio uploaded to Whisper for transcription
  // editing: transcribed text sent to AI for document editing
  type VoiceState = 'idle' | 'listening' | 'processing' | 'submitting' | 'editing';
  const [voiceState, setVoiceState] = useState<VoiceState>('idle');
  const [voiceSupported, setVoiceSupported] = useState(false);
  const [liveTranscript, setLiveTranscript] = useState(''); // last transcribed text
  // volumeLevel: written but not currently rendered (UI viz pending). Keep
  // the setter so the analyser node still drives state for future use.
  const [, setVolumeLevel] = useState(0);

  const voiceStateRef = useRef<VoiceState>('idle');

  // MediaRecorder refs
  const mediaRecorderRef = useRef<MediaRecorder | null>(null);
  const mediaStreamRef = useRef<MediaStream | null>(null);
  const audioChunksRef = useRef<Blob[]>([]);
  const selectedMimeRef = useRef<string>('audio/webm');

  // Web Audio API refs (for VAD / silence detection)
  const audioContextRef = useRef<AudioContext | null>(null);
  const analyserRef = useRef<AnalyserNode | null>(null);
  const sourceNodeRef = useRef<MediaStreamAudioSourceNode | null>(null);
  const rafIdRef = useRef<number | null>(null);

  // Silence detection state
  const silenceTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const firstSpeechDetectedRef = useRef(false); // has user said anything yet?
  const lastSoundTimeRef = useRef(0); // timestamp of last detected sound
  const submittingRef = useRef(false); // prevent double-submit
  const autoStoppedRef = useRef(false); // was this stop auto-triggered by silence?

  // Keep refs in sync with state
  useEffect(() => { voiceStateRef.current = voiceState; }, [voiceState]);

  // VAD tuning constants
  const SILENCE_THRESHOLD = 15; // audio level below which we consider "silence" (0-255)
  const SPEECH_START_THRESHOLD = 25; // minimum level to consider "user is speaking"
  const SILENCE_DURATION_MS = 2500; // 2.5s silence AFTER first speech = auto-submit
  const MAX_WAIT_FOR_FIRST_SPEECH_MS = 15000; // stop after 15s if no speech at all

  // Save state
  const [isSaving, setIsSaving] = useState(false);

  // Refs
  const fileInputRef = useRef<HTMLInputElement>(null);
  const chatEndRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLInputElement>(null);

  // Check voice support on mount
  useEffect(() => {
    const hasMediaRecorder =
      typeof window !== 'undefined' &&
      typeof navigator !== 'undefined' &&
      !!navigator.mediaDevices &&
      !!window.MediaRecorder &&
      !!(window.AudioContext || (window as unknown as { webkitAudioContext?: typeof AudioContext }).webkitAudioContext);
    setVoiceSupported(hasMediaRecorder);
  }, []);

  // Global cleanup on unmount - release all resources
  useEffect(() => {
    return () => {
      // Clear timers
      if (silenceTimerRef.current) {
        clearTimeout(silenceTimerRef.current);
        silenceTimerRef.current = null;
      }
      // Cancel RAF loop
      if (rafIdRef.current !== null) {
        cancelAnimationFrame(rafIdRef.current);
        rafIdRef.current = null;
      }
      // Stop mic tracks
      if (mediaStreamRef.current) {
        mediaStreamRef.current.getTracks().forEach(t => t.stop());
        mediaStreamRef.current = null;
      }
      // Stop MediaRecorder
      if (mediaRecorderRef.current && mediaRecorderRef.current.state !== 'inactive') {
        try { mediaRecorderRef.current.stop(); } catch { /* */ }
      }
      // Disconnect source + close audio context
      if (sourceNodeRef.current) {
        try { sourceNodeRef.current.disconnect(); } catch { /* */ }
        sourceNodeRef.current = null;
      }
      if (audioContextRef.current && audioContextRef.current.state !== 'closed') {
        try { audioContextRef.current.close(); } catch { /* */ }
        audioContextRef.current = null;
      }
      analyserRef.current = null;
    };
  }, []);

  // Auto-scroll chat
  useEffect(() => {
    chatEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages, isProcessing]);

  // -----------------------------------------------------------------------
  // Voice Recognition
  // -----------------------------------------------------------------------

  // Voice - fully automatic: tap mic → speak → auto-send on silence
  // Uses refs to avoid stale closure issues
  const documentContentRef = useRef(documentContent);
  const messagesRef = useRef(messages);
  const isProcessingRef = useRef(isProcessing);
  useEffect(() => { documentContentRef.current = documentContent; }, [documentContent]);
  useEffect(() => { messagesRef.current = messages; }, [messages]);
  useEffect(() => { isProcessingRef.current = isProcessing; }, [isProcessing]);

  // ---------------------------------------------------------------------
  // AI Send - sends text to AI and updates document if UPDATED_DOC returned
  // ---------------------------------------------------------------------
  const sendToAI = useCallback(async (text: string): Promise<void> => {
    if (!text || !documentContentRef.current) return;

    // Add user message
    const userMsg: Message = { id: makeId(), role: 'user', content: text, timestamp: new Date() };
    setMessages(prev => [...prev, userMsg]);
    setInputText('');
    setIsProcessing(true);

    try {
      const history = messagesRef.current
        .filter(m => m.role !== 'system')
        .map(m => ({ role: m.role as 'user' | 'assistant', content: m.content }));

      const res = await fetch('/api/doc-editor', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          action: 'edit',
          documentContent: documentContentRef.current,
          message: text,
          conversationHistory: history,
        }),
      });

      const data = await res.json();
      if (!res.ok || data.error) {
        throw new Error(data.error || `Server error: ${res.status}`);
      }

      const aiText: string = data.aiResponse || '';
      const docMatch = aiText.match(/UPDATED_DOC\s*\n([\s\S]*?)```/);
      if (docMatch?.[1]) {
        const updated = docMatch[1].replace(/^---\s*$/gm, '').trim();
        if (updated.length > 20) setDocumentContent(updated);
      }
      const display = aiText.replace(/```[\s\S]*?```/g, '').trim() || 'Changes applied.';
      setMessages(prev => [...prev, { id: makeId(), role: 'assistant', content: display, timestamp: new Date() }]);
    } catch (err) {
      const msg = err instanceof Error ? err.message : 'Request failed';
      setMessages(prev => [...prev, { id: makeId(), role: 'assistant', content: `Error: ${msg}`, timestamp: new Date() }]);
    } finally {
      setIsProcessing(false);
    }
  }, []);



  // ---------------------------------------------------------------------
  // Voice Assistant - MediaRecorder + OpenAI Whisper + VAD
  // State machine: idle -> listening -> processing -> submitting -> editing -> idle
  // First-speech buffer: silence timer only starts AFTER user speaks
  // ---------------------------------------------------------------------

  /** Clear silence debounce timer */
  const clearSilenceTimer = useCallback(() => {
    if (silenceTimerRef.current) {
      clearTimeout(silenceTimerRef.current);
      silenceTimerRef.current = null;
    }
  }, []);

  /** Stop RAF loop (VAD volume analyzer) */
  const stopVoiceAnalysis = useCallback(() => {
    if (rafIdRef.current !== null) {
      cancelAnimationFrame(rafIdRef.current);
      rafIdRef.current = null;
    }
    clearSilenceTimer();
  }, [clearSilenceTimer]);

  /** Release all microphone + audio resources */
  const releaseAudioResources = useCallback(() => {
    stopVoiceAnalysis();
    if (mediaStreamRef.current) {
      mediaStreamRef.current.getTracks().forEach(t => {
        try { t.stop(); } catch { /* */ }
      });
      mediaStreamRef.current = null;
    }
    if (sourceNodeRef.current) {
      try { sourceNodeRef.current.disconnect(); } catch { /* */ }
      sourceNodeRef.current = null;
    }
    if (audioContextRef.current && audioContextRef.current.state !== 'closed') {
      try { audioContextRef.current.close(); } catch { /* */ }
      audioContextRef.current = null;
    }
    analyserRef.current = null;
    if (mediaRecorderRef.current) {
      mediaRecorderRef.current.ondataavailable = null;
      mediaRecorderRef.current.onstop = null;
      mediaRecorderRef.current.onerror = null;
      mediaRecorderRef.current = null;
    }
  }, [stopVoiceAnalysis]);

  /** Reset all voice state to idle */
  const resetVoiceState = useCallback(() => {
    releaseAudioResources();
    audioChunksRef.current = [];
    firstSpeechDetectedRef.current = false;
    lastSoundTimeRef.current = 0;
    submittingRef.current = false;
    autoStoppedRef.current = false;
    setVolumeLevel(0);
    setLiveTranscript('');
    voiceStateRef.current = 'idle';
    setVoiceState('idle');
  }, [releaseAudioResources]);

  // Forward refs so callbacks can reference each other
  const startListeningRef = useRef<(() => Promise<void>) | null>(null);
  const stopListeningRef = useRef<((autoTriggered?: boolean) => void) | null>(null);

  /**
   * Transcribe audio via Whisper API (server-side /api/transcribe)
   * then send transcript to AI for document editing.
   */
  const transcribeAndSend = useCallback(async (audioBlob: Blob) => {
    if (submittingRef.current) return;
    submittingRef.current = true;

    try {
      // Guard against empty/tiny audio
      if (audioBlob.size < 1000) {
        setMessages(prev => [
          ...prev,
          { id: makeId(), role: 'system', content: 'No audio detected. Try again.', timestamp: new Date() },
        ]);
        resetVoiceState();
        return;
      }

      // State: submitting (Whisper transcription)
      voiceStateRef.current = 'submitting';
      setVoiceState('submitting');

      // Upload to server-side /api/transcribe (Whisper)
      const formData = new FormData();
      formData.append('audio', audioBlob, `recording.${selectedMimeRef.current.includes('webm') ? 'webm' : 'mp4'}`);

      const res = await fetch('/api/transcribe', {
        method: 'POST',
        body: formData,
      });

      if (!res.ok) {
        const err = await res.json().catch(() => ({ error: 'Transcription failed' }));
        throw new Error(err.error || `Transcription failed: ${res.status}`);
      }

      const { text } = await res.json();

      if (!text || !text.trim() || text.trim().length < 2) {
        setMessages(prev => [
          ...prev,
          { id: makeId(), role: 'system', content: 'No speech detected. Try again.', timestamp: new Date() },
        ]);
        resetVoiceState();
        return;
      }

      const transcript = text.trim();
      setLiveTranscript(transcript);

      // State: editing (AI processes transcript)
      voiceStateRef.current = 'editing';
      setVoiceState('editing');

      // Send to AI for document editing
      await sendToAI(transcript);
    } catch (err) {
      const msg = err instanceof Error ? err.message : 'Voice processing failed';
      setMessages(prev => [
        ...prev,
        { id: makeId(), role: 'system', content: `Voice error: ${msg}`, timestamp: new Date() },
      ]);
    } finally {
      resetVoiceState();
    }
  }, [sendToAI, resetVoiceState]);

  /**
   * Start VAD RAF loop - analyzes audio levels for silence detection.
   * Silence timer ONLY starts after first speech is detected (first-speech buffer).
   */
  const startVoiceAnalysis = useCallback((onSilenceDetected: () => void) => {
    if (!analyserRef.current) return;

    const analyser = analyserRef.current;
    const bufferLength = analyser.frequencyBinCount;
    const dataArray = new Uint8Array(bufferLength);
    const recordStartTime = Date.now();

    const analyse = () => {
      if (!analyserRef.current) return;
      analyser.getByteFrequencyData(dataArray);

      // Calculate average volume (simple RMS approximation)
      let sum = 0;
      for (let i = 0; i < bufferLength; i++) {
        sum += dataArray[i];
      }
      const average = sum / bufferLength;
      setVolumeLevel(Math.min(100, (average / 128) * 100));

      const now = Date.now();
      const timeSinceStart = now - recordStartTime;

      if (average > SPEECH_START_THRESHOLD) {
        // SPEECH DETECTED
        lastSoundTimeRef.current = now;
        if (!firstSpeechDetectedRef.current) {
          // FIRST SPEECH! Transition listening -> processing
          firstSpeechDetectedRef.current = true;
          voiceStateRef.current = 'processing';
          setVoiceState('processing');
        }
        // Clear any pending silence timer (user is speaking again)
        if (silenceTimerRef.current) {
          clearTimeout(silenceTimerRef.current);
          silenceTimerRef.current = null;
        }
      } else if (average < SILENCE_THRESHOLD) {
        // SILENCE
        if (firstSpeechDetectedRef.current) {
          // User HAS spoken before - start/continue silence timer
          if (!silenceTimerRef.current) {
            silenceTimerRef.current = setTimeout(() => {
              // 2.5s of silence passed - auto-stop
              silenceTimerRef.current = null;
              autoStoppedRef.current = true;
              onSilenceDetected();
            }, SILENCE_DURATION_MS);
          }
        } else {
          // User hasn't spoken yet - wait patiently (no timer!)
          if (timeSinceStart > MAX_WAIT_FOR_FIRST_SPEECH_MS) {
            // Max wait exceeded - give up
            autoStoppedRef.current = true;
            onSilenceDetected();
            return;
          }
        }
      }

      // Continue loop
      rafIdRef.current = requestAnimationFrame(analyse);
    };

    rafIdRef.current = requestAnimationFrame(analyse);
  }, [SPEECH_START_THRESHOLD, SILENCE_THRESHOLD, SILENCE_DURATION_MS, MAX_WAIT_FOR_FIRST_SPEECH_MS]);

  /** Start MediaRecorder + VAD */
  const startListening = useCallback(async () => {
    if (voiceStateRef.current !== 'idle') return;
    if (!documentContentRef.current) return;

    try {
      // 1. Request microphone access
      const stream = await navigator.mediaDevices.getUserMedia({
        audio: {
          echoCancellation: true,
          noiseSuppression: true,
          autoGainControl: true,
        },
      });
      mediaStreamRef.current = stream;

      // 2. Set up Web Audio API for volume analysis
      const AudioCtx = window.AudioContext || (window as unknown as { webkitAudioContext: typeof AudioContext }).webkitAudioContext;
      const audioContext = new AudioCtx();
      audioContextRef.current = audioContext;

      const source = audioContext.createMediaStreamSource(stream);
      sourceNodeRef.current = source;

      const analyser = audioContext.createAnalyser();
      analyser.fftSize = 512;
      analyser.smoothingTimeConstant = 0.5;
      analyserRef.current = analyser;

      source.connect(analyser);

      // 3. Find supported MIME type
      const mimeTypes = [
        'audio/webm;codecs=opus',
        'audio/webm',
        'audio/mp4',
        'audio/ogg;codecs=opus',
      ];
      let selectedMime = '';
      for (const mime of mimeTypes) {
        if (MediaRecorder.isTypeSupported(mime)) {
          selectedMime = mime;
          break;
        }
      }
      selectedMimeRef.current = selectedMime || 'audio/webm';

      // 4. Create MediaRecorder
      const recorder = selectedMime
        ? new MediaRecorder(stream, { mimeType: selectedMime })
        : new MediaRecorder(stream);
      mediaRecorderRef.current = recorder;
      audioChunksRef.current = [];
      firstSpeechDetectedRef.current = false;
      lastSoundTimeRef.current = 0;
      autoStoppedRef.current = false;
      submittingRef.current = false;

      // 5. Set up event handlers
      recorder.ondataavailable = (event) => {
        if (event.data.size > 0) {
          audioChunksRef.current.push(event.data);
        }
      };

      recorder.onstop = async () => {
        // Stop VAD loop first
        stopVoiceAnalysis();

        // Release mic tracks immediately
        if (mediaStreamRef.current) {
          mediaStreamRef.current.getTracks().forEach(t => t.stop());
          mediaStreamRef.current = null;
        }
        if (sourceNodeRef.current) {
          try { sourceNodeRef.current.disconnect(); } catch { /* */ }
          sourceNodeRef.current = null;
        }
        if (audioContextRef.current && audioContextRef.current.state !== 'closed') {
          try { await audioContextRef.current.close(); } catch { /* */ }
          audioContextRef.current = null;
        }
        analyserRef.current = null;

        // Build audio blob
        const blob = new Blob(audioChunksRef.current, {
          type: selectedMimeRef.current,
        });
        audioChunksRef.current = [];
        mediaRecorderRef.current = null;
        setVolumeLevel(0);

        // Only transcribe if user actually spoke
        if (firstSpeechDetectedRef.current) {
          await transcribeAndSend(blob);
        } else {
          // No speech detected - silent reset
          setMessages(prev => [
            ...prev,
            { id: makeId(), role: 'system', content: 'No speech detected.', timestamp: new Date() },
          ]);
          resetVoiceState();
        }
      };

      recorder.onerror = () => {
        console.error('MediaRecorder error');
        setMessages(prev => [
          ...prev,
          { id: makeId(), role: 'system', content: 'Recording failed. Try again.', timestamp: new Date() },
        ]);
        resetVoiceState();
      };

      // 6. Start recording (collect chunks every 100ms)
      recorder.start(100);
      voiceStateRef.current = 'listening';
      setVoiceState('listening');

      // 7. Start VAD analysis loop
      startVoiceAnalysis(() => {
        // Silence detected callback - stop recording
        stopListeningRef.current?.(true);
      });
    } catch (err) {
      console.error('Failed to start recording:', err);
      resetVoiceState();

      const isPermissionError =
        err instanceof Error &&
        (err.name === 'NotAllowedError' || err.name === 'PermissionDeniedError');

      const msg = isPermissionError
        ? 'Microphone access denied. Please allow microphone in browser settings.'
        : 'Could not access microphone. Please check your device.';

      setMessages(prev => [
        ...prev,
        { id: makeId(), role: 'system', content: msg, timestamp: new Date() },
      ]);
    }
  }, [resetVoiceState, startVoiceAnalysis, stopVoiceAnalysis, transcribeAndSend]);

  /** Stop recording (triggers onstop → transcribeAndSend) */
  const stopListening = useCallback((autoTriggered = false) => {
    if (autoTriggered) autoStoppedRef.current = true;
    stopVoiceAnalysis();

    if (mediaRecorderRef.current && mediaRecorderRef.current.state !== 'inactive') {
      try {
        mediaRecorderRef.current.stop();
      } catch (err) {
        console.error('Failed to stop recorder:', err);
        resetVoiceState();
      }
    } else {
      resetVoiceState();
    }
  }, [stopVoiceAnalysis, resetVoiceState]);

  // Keep refs synced
  useEffect(() => { startListeningRef.current = startListening; }, [startListening]);
  useEffect(() => { stopListeningRef.current = stopListening; }, [stopListening]);

  /** Toggle: idle -> listening, or listening/processing -> stop */
  const toggleVoice = useCallback(() => {
    const state = voiceStateRef.current;
    if (state === 'idle') {
      startListening();
    } else if (state === 'listening' || state === 'processing') {
      stopListening(false);
    }
    // Ignore clicks during submitting/editing
  }, [startListening, stopListening]);

  /** Cancel voice entirely (Cancel button) */
  const cancelVoice = useCallback(() => {
    resetVoiceState();
  }, [resetVoiceState]);

  // -----------------------------------------------------------------------
  // File Upload
  // -----------------------------------------------------------------------

  const handleFile = useCallback(async (selectedFile: File) => {
    setUploadError('');

    if (!selectedFile.name.endsWith('.docx')) {
      setUploadError('Only .docx files are supported');
      return;
    }
    if (selectedFile.size > 10 * 1024 * 1024) {
      setUploadError('File size must be less than 10MB');
      return;
    }

    setFile(selectedFile);
    setIsProcessing(true);
    setMessages([]);

    // Upload and extract text
    try {
      const formData = new FormData();
      formData.append('file', selectedFile);
      formData.append('action', 'chat');
      formData.append('message', 'The doctor has uploaded a document. Just acknowledge that you received it and briefly describe what you see (procedure type, patient info if present). Keep it short - 2-3 sentences max.');

      const res = await fetch('/api/doc-editor', {
        method: 'POST',
        body: formData,
      });

      const data = await res.json();

      if (!res.ok) {
        throw new Error(data.error || 'Failed to process file');
      }

      setDocumentContent(data.documentContent);

      setMessages([
        {
          id: makeId(),
          role: 'system',
          content: `Document loaded: ${selectedFile.name}`,
          timestamp: new Date(),
        },
        {
          id: makeId(),
          role: 'assistant',
          content: data.aiResponse,
          timestamp: new Date(),
        },
      ]);

    } catch (err) {
      const errMsg = err instanceof Error ? err.message : 'Upload failed';
      setUploadError(errMsg);
      setFile(null);
    } finally {
      setIsProcessing(false);
    }
  }, []);

  const handleDrop = useCallback(
    (e: React.DragEvent) => {
      e.preventDefault();
      setIsDragOver(false);
      const droppedFile = e.dataTransfer.files[0];
      if (droppedFile) handleFile(droppedFile);
    },
    [handleFile]
  );

  const handleFileInput = useCallback(
    (e: React.ChangeEvent<HTMLInputElement>) => {
      const selectedFile = e.target.files?.[0];
      if (selectedFile) handleFile(selectedFile);
    },
    [handleFile]
  );

  const removeFile = () => {
    setFile(null);
    setDocumentContent('');
    setMessages([]);
    setUploadError('');
    cancelVoice();
    if (fileInputRef.current) fileInputRef.current.value = '';
  };

  // -----------------------------------------------------------------------
  // Send Message (Edit instruction)
  // -----------------------------------------------------------------------

  const sendMessage = useCallback(
    async (text?: string) => {
      const messageText = text || inputText.trim();
      if (!messageText || !documentContent || isProcessing) return;

      // Cancel active voice recording if user types manually
      if (voiceState === 'listening' || voiceState === 'processing') {
        cancelVoice();
      }

      await sendToAI(messageText);
    },
    [inputText, documentContent, isProcessing, voiceState, cancelVoice, sendToAI]
  );

  // -----------------------------------------------------------------------
  // Save as Word
  // -----------------------------------------------------------------------

  const saveDocument = useCallback(
    async (format: 'docx' | 'pdf') => {
      if (!documentContent) return;

      setIsSaving(true);

      try {
        const contentToSave = documentContent;

        const res = await fetch('/api/doc-editor/save', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            content: contentToSave,
            format,
            fileName: file?.name || 'document',
          }),
        });

        if (!res.ok) {
          let errMsg = 'Failed to save';
          try {
            const errData = await res.json();
            errMsg = errData.error || errMsg;
          } catch {
            errMsg = `Server error: ${res.status}`;
          }
          throw new Error(errMsg);
        }

        const blob = await res.blob();
        const url = window.URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.style.display = 'none';
        a.href = url;
        const baseName = (file?.name || 'document').replace(/\.docx$/i, '');
        a.download = `${baseName}_edited.docx`;
        document.body.appendChild(a);
        a.click();
        // Small delay before cleanup to ensure download starts
        setTimeout(() => {
          document.body.removeChild(a);
          window.URL.revokeObjectURL(url);
        }, 200);

        // Success message
        setMessages((prev) => [
          ...prev,
          {
            id: makeId(),
            role: 'system',
            content: `Document saved as ${format.toUpperCase()} successfully!`,
            timestamp: new Date(),
          },
        ]);
      } catch (err) {
        const errMsg = err instanceof Error ? err.message : 'Save failed';
        setMessages((prev) => [
          ...prev,
          {
            id: makeId(),
            role: 'system',
            content: `Save failed: ${errMsg}`,
            timestamp: new Date(),
          },
        ]);
      } finally {
        setIsSaving(false);
      }
    },
    [documentContent, file]
  );

  // -----------------------------------------------------------------------
  // Render
  // -----------------------------------------------------------------------

  return (
    <div className="h-screen flex flex-col p-4 lg:p-5 gap-3 overflow-x-hidden overflow-y-hidden">
      {/* Header - compact */}
      <motion.div
        initial={{ opacity: 0, y: -10 }}
        animate={{ opacity: 1, y: 0 }}
        className="rounded-2xl bg-gradient-to-r from-blue-600 via-violet-600 to-purple-600 p-4 text-white relative overflow-visible shrink-0"
      >
        <div className="flex items-center gap-3 relative z-20">
          <div className="p-2 rounded-xl bg-white/15 backdrop-blur-sm">
            <Sparkles className="w-5 h-5" />
          </div>
          <div className="flex-1">
            <h1 className="text-xl font-bold">AI Document Editor</h1>
            <p className="text-sm text-white/80">
              Upload your Word document, tell AI what to edit — type or use voice
            </p>
          </div>

        </div>
        <div className="absolute -top-10 -right-10 w-40 h-40 rounded-full bg-white/5" />
        <div className="absolute -bottom-8 -left-8 w-32 h-32 rounded-full bg-white/5" />
      </motion.div>

      {/* Main Content - Two Column - fills remaining height */}
      <div className="grid grid-cols-1 lg:grid-cols-5 gap-3 flex-1 min-h-0">
        {/* Left Panel - Document */}
        <motion.div
          initial={{ opacity: 0, x: -20 }}
          animate={{ opacity: 1, x: 0 }}
          transition={{ delay: 0.1 }}
          className="lg:col-span-2 rounded-2xl bg-white/5 dark:bg-slate-900/50 border border-white/10 overflow-hidden flex flex-col min-h-0"
        >
          {!file ? (
            /* Upload Zone */
            <div
              onClick={() => fileInputRef.current?.click()}
              onDragOver={(e) => {
                e.preventDefault();
                setIsDragOver(true);
              }}
              onDragLeave={() => setIsDragOver(false)}
              onDrop={handleDrop}
              className={`flex-1 flex flex-col items-center justify-center p-8 cursor-pointer transition-all duration-300 m-4 rounded-2xl border-2 border-dashed ${
                isDragOver
                  ? 'border-blue-400 bg-blue-500/10 scale-[1.02]'
                  : 'border-slate-600 hover:border-slate-400 hover:bg-white/5'
              }`}
            >
              <motion.div
                animate={isDragOver ? { scale: 1.1, y: -5 } : { scale: 1, y: 0 }}
                className="p-4 rounded-2xl bg-gradient-to-br from-blue-500/20 to-teal-500/20 mb-4"
              >
                <Upload className="w-8 h-8 text-blue-400" />
              </motion.div>
              <p className="text-white font-medium text-lg mb-1">
                Drop your .docx file here
              </p>
              <p className="text-slate-400 text-sm mb-3">or click to browse</p>
              <p className="text-slate-500 text-xs">.docx files only, max 10MB</p>

              <input
                ref={fileInputRef}
                type="file"
                accept=".docx"
                onChange={handleFileInput}
                className="hidden"
              />

              {uploadError && (
                <motion.div
                  initial={{ opacity: 0, y: 5 }}
                  animate={{ opacity: 1, y: 0 }}
                  className="flex items-center gap-2 mt-4 px-4 py-2 rounded-lg bg-red-500/10 border border-red-500/20"
                >
                  <AlertCircle className="w-4 h-4 text-red-400" />
                  <p className="text-sm text-red-400">{uploadError}</p>
                </motion.div>
              )}
            </div>
          ) : (
            /* Document Preview - Real Document Look */
            <div className="flex flex-col h-full bg-slate-800/30">
              {/* File header with Save */}
              <div className="flex items-center gap-2 px-3 py-2.5 border-b border-white/10 bg-slate-900/50">
                <div className="p-1.5 rounded-lg bg-blue-500/20">
                  <FileText className="w-3.5 h-3.5 text-blue-400" />
                </div>
                <div className="flex-1 min-w-0">
                  <p className="text-sm font-medium text-white truncate">{file.name}</p>
                </div>
                <motion.button
                  whileHover={{ scale: 1.03 }}
                  whileTap={{ scale: 0.97 }}
                  onClick={() => saveDocument('docx')}
                  disabled={isSaving}
                  className="flex items-center gap-1.5 px-3 py-1.5 bg-gradient-to-r from-emerald-500 to-teal-500 hover:from-emerald-400 hover:to-teal-400 text-white text-xs font-semibold rounded-lg shadow-lg shadow-emerald-500/20 disabled:opacity-50 transition-all cursor-pointer"
                >
                  {isSaving ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <Download className="w-3.5 h-3.5" />}
                  Save .docx
                </motion.button>
                <button
                  onClick={removeFile}
                  className="p-1.5 rounded-lg hover:bg-white/10 transition-colors text-slate-400 hover:text-red-400 cursor-pointer"
                >
                  <X className="w-4 h-4" />
                </button>
              </div>

              {/* Document - Clean Card Style */}
              <div className="flex-1 overflow-y-auto p-3">
                {isProcessing && !documentContent ? (
                  <div className="flex items-center justify-center py-12">
                    <Loader2 className="w-6 h-6 text-blue-400 animate-spin" />
                    <p className="ml-3 text-slate-400">Reading document...</p>
                  </div>
                ) : (
                  <div className="space-y-2">
                    {(() => {
                      const lines = documentContent.split('\n').filter((l) => l.trim());
                      const fields: { label: string; value: string }[] = [];
                      const bodyLines: string[] = [];
                      const diagLines: string[] = [];
                      let signatureLine = '';

                      // Long text fields that should go to the Description section
                      // (NOT BRIEF HISTORY — that stays in Clinical section, fully visible)
                      const longTextFields = ['DESCRIPTION', 'PROCEDURE'];
                      let descriptionText = '';

                      for (const line of lines) {
                        const trimmed = line.trim();
                        const fieldMatch = trimmed.match(/^([A-Z][A-Z\s/]+):[\t\s]*(.*)/);
                        if (fieldMatch) {
                          const label = fieldMatch[1].trim();
                          const value = fieldMatch[2]?.trim().replace(/<[^>]+>/g, '').trim() || '';
                          // Long text fields: collect value separately (exclude BRIEF HISTORY)
                          if (longTextFields.includes(label) && value.length > 80) {
                            descriptionText += (descriptionText ? '\n\n' : '') + value;
                          } else {
                            fields.push({ label, value });
                          }
                        } else if (/^M\d/.test(trimmed) || trimmed.startsWith('Diagnosis')) {
                          diagLines.push(trimmed);
                        } else if (trimmed.includes('Moussazadeh') || trimmed.includes('M.D.')) {
                          signatureLine = trimmed;
                        } else if (!/^[-\/0]+$/.test(trimmed.replace(/\s/g, '')) && trimmed !== '--/--/----' && trimmed !== '00/00/0000') {
                          // Regular body text (post-procedure notes etc.)
                          bodyLines.push(trimmed);
                        }
                      }

                      // Combine description + body lines
                      const allDescText = [descriptionText, ...bodyLines].filter(Boolean).join('\n\n');

                      // Group: patient info, procedure info, clinical
                      const patientFields = ['DATE', 'PATIENT', 'DOB', 'DOI', 'DOL'];
                      const procFields = ['SURGEON', 'ASSISTANT', 'PLACE OF SURGERY', 'TITLE OF PROCEDURE', 'ANESTHESIA'];
                      const clinicalFields = ['ESTIMATED BLOOD LOSS', 'COMPLICATIONS', 'BRIEF HISTORY'];

                      // Fields that should span the FULL width of the card (for long text)
                      const fullWidthFields = ['TITLE OF PROCEDURE', 'PLACE OF SURGERY', 'BRIEF HISTORY'];

                      const renderGroup = (title: string, fieldNames: string[], color: string) => {
                        const groupFields = fields.filter((f) => fieldNames.includes(f.label));
                        if (groupFields.length === 0) return null;
                        return (
                          <div className={`rounded-lg border ${color} p-3`}>
                            <p className="text-[10px] font-bold uppercase tracking-widest text-slate-500 mb-2">{title}</p>
                            <div className="grid grid-cols-2 gap-x-4 gap-y-2 items-start">
                              {groupFields.map((f, i) => {
                                const isWide = fullWidthFields.includes(f.label);
                                return (
                                  <div key={i} className={`${isWide ? 'col-span-2' : ''} min-h-[auto]`}>
                                    <span className="text-[10px] text-slate-500 uppercase block">
                                      {f.label.replace('TITLE OF PROCEDURE', 'PROCEDURE')}
                                    </span>
                                    {f.value ? (
                                      <p className="text-[13px] text-white font-medium leading-relaxed whitespace-normal break-words">
                                        {f.value}
                                      </p>
                                    ) : (
                                      <p className="text-[13px] text-slate-600 italic">—</p>
                                    )}
                                  </div>
                                );
                              })}
                            </div>
                          </div>
                        );
                      };

                      return (
                        <>
                          {renderGroup('Patient Info', patientFields, 'border-blue-500/20 bg-blue-500/5')}
                          {renderGroup('Procedure', procFields, 'border-violet-500/20 bg-violet-500/5')}
                          {renderGroup('Clinical', clinicalFields, 'border-emerald-500/20 bg-emerald-500/5')}

                          {/* Description - full text with scroll */}
                          {allDescText && (
                            <div className="rounded-lg border border-slate-700/50 bg-slate-800/30 p-3">
                              <p className="text-[10px] font-bold uppercase tracking-widest text-slate-500 mb-2">Procedure Description</p>
                              <div className="max-h-[250px] overflow-y-auto pr-1 custom-scrollbar">
                                {allDescText.split('\n\n').map((para, i) => (
                                  <p key={i} className="text-[12px] text-slate-300 leading-[1.8] mb-2 text-justify">{para}</p>
                                ))}
                              </div>
                            </div>
                          )}

                          {/* Diagnosis + Signature */}
                          {(diagLines.length > 0 || signatureLine) && (
                            <div className="rounded-lg border border-slate-700/50 bg-slate-800/30 p-3">
                              {signatureLine && (
                                <p className="text-[12px] text-cyan-400 font-semibold mb-2">{signatureLine}</p>
                              )}
                              {diagLines.length > 0 && (
                                <div>
                                  <p className="text-[10px] font-bold uppercase tracking-widest text-slate-500 mb-1">Diagnosis</p>
                                  {diagLines.map((d, i) => (
                                    <p key={i} className="text-[11px] text-slate-400 font-mono">{d}</p>
                                  ))}
                                </div>
                              )}
                            </div>
                          )}
                        </>
                      );
                    })()}
                  </div>
                )}
              </div>
            </div>
          )}
        </motion.div>

        {/* Right Panel - AI Chat */}
        <motion.div
          initial={{ opacity: 0, x: 20 }}
          animate={{ opacity: 1, x: 0 }}
          transition={{ delay: 0.2 }}
          className="lg:col-span-3 rounded-2xl bg-white/5 dark:bg-slate-900/50 border border-white/10 overflow-hidden flex flex-col min-h-0"
        >
          {/* Chat header */}
          <div className="flex items-center gap-3 px-5 py-3.5 border-b border-white/10">
            <div className="p-2 rounded-xl bg-gradient-to-br from-violet-500/20 to-purple-500/20">
              <Bot className="w-5 h-5 text-violet-400" />
            </div>
            <div className="flex-1">
              <h3 className="text-sm font-semibold text-white">AI Document Editor</h3>
              <div className="flex items-center gap-1.5">
                <div className="w-1.5 h-1.5 rounded-full bg-green-400 animate-pulse" />
                <p className="text-xs text-slate-400">Ready</p>
              </div>
            </div>
            <div className="flex items-center gap-2">
              <div className="flex items-center gap-1 px-2 py-1 rounded-lg bg-blue-500/10 border border-blue-500/20">
                <Edit3 className="w-3 h-3 text-blue-400" />
                <span className="text-[10px] text-blue-400 font-medium">AI Edit</span>
              </div>
            </div>
          </div>

          {/* Messages area */}
          <div className="flex-1 overflow-y-auto p-4 space-y-4">
            {messages.length === 0 && !isProcessing ? (
              /* Empty state */
              <div className="flex flex-col items-center justify-center h-full text-center py-12">
                <div className="p-4 rounded-2xl bg-slate-800/50 mb-4">
                  <FileDown className="w-8 h-8 text-slate-500" />
                </div>
                <p className="text-slate-400 font-medium mb-1">Upload a document to get started</p>
                <p className="text-slate-500 text-sm max-w-sm">
                  Upload your Word file — empty fields will be detected automatically
                </p>
              </div>
            ) : (
              /* Messages */
              messages.map((msg) => (
                <motion.div
                  key={msg.id}
                  initial={{ opacity: 0, y: 10 }}
                  animate={{ opacity: 1, y: 0 }}
                  className={`flex gap-3 ${msg.role === 'user' ? 'flex-row-reverse' : ''}`}
                >
                  {msg.role === 'system' ? (
                    /* System message */
                    <div className="w-full flex justify-center">
                      <div className="inline-flex items-center gap-2 px-3 py-1.5 rounded-full bg-slate-800/50 border border-slate-700/50">
                        <div className="w-1.5 h-1.5 rounded-full bg-blue-400" />
                        <p className="text-xs text-slate-400">{msg.content}</p>
                      </div>
                    </div>
                  ) : (
                    <>
                      {/* Avatar */}
                      <div
                        className={`shrink-0 w-8 h-8 rounded-full flex items-center justify-center ${
                          msg.role === 'user'
                            ? 'bg-gradient-to-br from-blue-500 to-teal-400'
                            : 'bg-gradient-to-br from-violet-500 to-purple-500'
                        }`}
                      >
                        {msg.role === 'user' ? (
                          <User className="w-4 h-4 text-white" />
                        ) : (
                          <Bot className="w-4 h-4 text-white" />
                        )}
                      </div>

                      {/* Message bubble */}
                      <div
                        className={`max-w-[80%] rounded-2xl px-4 py-3 ${
                          msg.role === 'user'
                            ? 'bg-gradient-to-r from-blue-600 to-blue-500 text-white'
                            : 'bg-slate-800/80 border border-slate-700/50 text-slate-200'
                        }`}
                      >
                        <div className="text-sm leading-relaxed whitespace-pre-wrap">
                          {msg.content}
                        </div>
                        <p
                          className={`text-[10px] mt-1.5 ${
                            msg.role === 'user' ? 'text-blue-200/60' : 'text-slate-500'
                          }`}
                        >
                          {formatTime(msg.timestamp)}
                        </p>
                      </div>
                    </>
                  )}
                </motion.div>
              ))
            )}

            {/* Typing indicator */}
            {isProcessing && messages.length > 0 && (
              <motion.div
                initial={{ opacity: 0 }}
                animate={{ opacity: 1 }}
                className="flex items-center gap-3"
              >
                <div className="w-8 h-8 rounded-full bg-gradient-to-br from-violet-500 to-purple-500 flex items-center justify-center">
                  <Bot className="w-4 h-4 text-white" />
                </div>
                <div className="bg-slate-800/80 border border-slate-700/50 rounded-2xl px-4 py-3">
                  <div className="flex items-center gap-1.5">
                    <div className="w-2 h-2 rounded-full bg-violet-400 animate-bounce" style={{ animationDelay: '0ms' }} />
                    <div className="w-2 h-2 rounded-full bg-violet-400 animate-bounce" style={{ animationDelay: '150ms' }} />
                    <div className="w-2 h-2 rounded-full bg-violet-400 animate-bounce" style={{ animationDelay: '300ms' }} />
                    <span className="ml-2 text-xs text-slate-400">AI is editing...</span>
                  </div>
                </div>
              </motion.div>
            )}

            <div ref={chatEndRef} />
          </div>

          {/* Voice state indicators */}
          <AnimatePresence>
            {voiceState === 'listening' && (
              <motion.div
                key="listening"
                initial={{ opacity: 0, height: 0 }}
                animate={{ opacity: 1, height: 'auto' }}
                exit={{ opacity: 0, height: 0 }}
                className="mx-4"
              >
                <div className="flex items-center gap-3 px-4 py-3 rounded-xl bg-red-500/10 border border-red-500/30 mb-2">
                  <div className="relative flex items-center justify-center shrink-0">
                    <div className="absolute w-7 h-7 rounded-full bg-red-500/30 animate-ping" />
                    <div className="absolute w-5 h-5 rounded-full bg-red-500/40" />
                    <Mic className="w-4 h-4 text-red-300 relative" />
                  </div>
                  <div className="flex-1 min-w-0">
                    <p className="text-sm text-red-300 font-bold">Listening...</p>
                    <p className="text-[11px] text-red-400/80">Take your time — start speaking whenever ready</p>
                  </div>
                  <button
                    onClick={cancelVoice}
                    className="text-[10px] text-slate-400 hover:text-white px-2 py-1 rounded-md hover:bg-white/10 shrink-0"
                  >
                    Cancel
                  </button>
                </div>
              </motion.div>
            )}

            {voiceState === 'processing' && (
              <motion.div
                key="processing"
                initial={{ opacity: 0, height: 0 }}
                animate={{ opacity: 1, height: 'auto' }}
                exit={{ opacity: 0, height: 0 }}
                className="mx-4"
              >
                <div className="flex items-center gap-3 px-4 py-3 rounded-xl bg-gradient-to-r from-emerald-500/15 to-teal-500/15 border border-emerald-400/40 mb-2 shadow-lg shadow-emerald-500/10">
                  <div className="relative flex items-center justify-center shrink-0">
                    <div className="absolute w-6 h-6 rounded-full bg-emerald-400/30 animate-pulse" />
                    <Mic className="w-4 h-4 text-emerald-300 relative" />
                  </div>
                  <div className="flex-1 min-w-0">
                    <p className="text-sm text-emerald-300 font-bold">Listening to your command...</p>
                    {liveTranscript ? (
                      <p className="text-[11px] text-emerald-200/80 italic truncate">&ldquo;{liveTranscript}&rdquo;</p>
                    ) : (
                      <p className="text-[11px] text-emerald-400/80">Keep speaking — pause 2.5s to auto-send</p>
                    )}
                  </div>
                  <button
                    onClick={cancelVoice}
                    className="text-[10px] text-slate-400 hover:text-white px-2 py-1 rounded-md hover:bg-white/10 shrink-0"
                  >
                    Cancel
                  </button>
                </div>
              </motion.div>
            )}

            {voiceState === 'submitting' && (
              <motion.div
                key="submitting"
                initial={{ opacity: 0, height: 0 }}
                animate={{ opacity: 1, height: 'auto' }}
                exit={{ opacity: 0, height: 0 }}
                className="mx-4"
              >
                <div className="flex items-center gap-3 px-4 py-3 rounded-xl bg-violet-500/10 border border-violet-500/20 mb-2">
                  <Loader2 className="w-4 h-4 text-violet-400 animate-spin" />
                  <div className="flex-1">
                    <p className="text-xs text-violet-400 font-semibold">Wait, processing...</p>
                    <p className="text-[11px] text-slate-400">Sending to AI</p>
                  </div>
                </div>
              </motion.div>
            )}

            {voiceState === 'editing' && (
              <motion.div
                key="editing"
                initial={{ opacity: 0, height: 0 }}
                animate={{ opacity: 1, height: 'auto' }}
                exit={{ opacity: 0, height: 0 }}
                className="mx-4"
              >
                <div className="flex items-center gap-3 px-4 py-3 rounded-xl bg-blue-500/10 border border-blue-500/20 mb-2">
                  <Edit3 className="w-4 h-4 text-blue-400 animate-pulse" />
                  <div className="flex-1">
                    <p className="text-xs text-blue-400 font-semibold">Editing document...</p>
                    <p className="text-[11px] text-slate-400">AI is updating your document</p>
                  </div>
                </div>
              </motion.div>
            )}
          </AnimatePresence>

          {/* Input area */}
          <div className="px-4 pb-4 pt-2">
            <div className="flex items-center gap-2 p-2 rounded-2xl bg-slate-800/50 border border-slate-700/50 focus-within:border-blue-500/50 transition-colors">
              {/* Mic button */}
              {voiceSupported && (
                <motion.button
                  whileHover={{ scale: voiceState === 'idle' || voiceState === 'listening' || voiceState === 'processing' ? 1.08 : 1 }}
                  whileTap={{ scale: voiceState === 'idle' || voiceState === 'listening' || voiceState === 'processing' ? 0.92 : 1 }}
                  onClick={toggleVoice}
                  disabled={!file || isProcessing || voiceState === 'submitting' || voiceState === 'editing'}
                  className={`p-2.5 rounded-xl relative transition-all cursor-pointer disabled:opacity-30 disabled:cursor-not-allowed ${
                    voiceState === 'listening'
                      ? 'bg-red-500/20 text-red-300 ring-2 ring-red-500/40'
                      : voiceState === 'processing'
                      ? 'bg-emerald-500/20 text-emerald-300 ring-2 ring-emerald-500/40'
                      : voiceState === 'submitting'
                      ? 'bg-violet-500/20 text-violet-400'
                      : voiceState === 'editing'
                      ? 'bg-blue-500/20 text-blue-400'
                      : 'text-slate-400 hover:text-white hover:bg-white/10'
                  }`}
                  title={
                    voiceState === 'idle' ? 'Click to start voice input' :
                    voiceState === 'listening' ? 'Listening... (click to cancel)' :
                    voiceState === 'processing' ? 'Capturing command (click to stop & send)' :
                    voiceState === 'submitting' ? 'Processing...' :
                    'Editing document...'
                  }
                >
                  {(voiceState === 'listening' || voiceState === 'processing') && (
                    <span className={`absolute inset-0 rounded-xl animate-ping ${
                      voiceState === 'listening' ? 'bg-red-500/20' : 'bg-emerald-500/20'
                    }`} />
                  )}
                  {voiceState === 'submitting' || voiceState === 'editing' ? (
                    <Loader2 className="w-5 h-5 animate-spin relative" />
                  ) : voiceState === 'listening' || voiceState === 'processing' ? (
                    <MicOff className="w-5 h-5 relative" />
                  ) : (
                    <Mic className="w-5 h-5 relative" />
                  )}
                </motion.button>
              )}

              {/* Text input */}
              <input
                ref={inputRef}
                type="text"
                value={inputText}
                onChange={(e) => setInputText(e.target.value)}
                onKeyDown={(e) => e.key === 'Enter' && !e.shiftKey && sendMessage()}
                placeholder={
                  !file
                    ? 'Upload a document first...'
                    : voiceState === 'listening'
                    ? 'Listening — start speaking anytime...'
                    : voiceState === 'processing'
                    ? 'Capturing command — pause 2.5s to send'
                    : voiceState === 'submitting'
                    ? 'Processing...'
                    : voiceState === 'editing'
                    ? 'Editing document...'
                    : 'Click mic or type your command...'
                }
                disabled={!file || isProcessing || voiceState !== 'idle'}
                className="flex-1 bg-transparent text-white placeholder-slate-500 text-sm px-2 py-2 outline-none disabled:opacity-50"
              />

              {/* Send button */}
              <motion.button
                whileHover={{ scale: 1.05 }}
                whileTap={{ scale: 0.95 }}
                onClick={() => sendMessage()}
                disabled={!file || !inputText.trim() || isProcessing || voiceState !== 'idle'}
                className="p-2.5 rounded-xl bg-gradient-to-r from-blue-500 to-teal-500 text-white disabled:opacity-30 disabled:cursor-not-allowed transition-all cursor-pointer"
              >
                {isProcessing ? (
                  <Loader2 className="w-5 h-5 animate-spin" />
                ) : (
                  <Send className="w-5 h-5" />
                )}
              </motion.button>
            </div>
            <p className="text-center text-[11px] text-slate-500 mt-2">
              {voiceSupported
                ? voiceState === 'idle'
                  ? 'Click the mic to start voice input, or type your command'
                  : voiceState === 'listening'
                  ? 'Ready — start speaking whenever you want'
                  : voiceState === 'processing'
                  ? 'Pause 2.5 seconds when done to auto-send'
                  : 'AI-powered document editing'
                : 'AI-powered document editing'}
            </p>
          </div>
        </motion.div>
      </div>

    </div>
  );
}
