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
import { useVoiceRecorder } from '@/lib/hooks/useVoiceRecorder';
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

  // Voice Assistant State — shared useVoiceRecorder hook (same one Add
  // Patient uses). The hook owns the MediaRecorder + VAD + auto-stop.
  // `voiceState` is a thin overlay for the two post-recording phases
  // (submitting to Whisper, sending transcript to the doc-editor chat).
  type VoiceState = 'submitting' | 'editing' | null;
  const [voiceState, setVoiceState] = useState<VoiceState>(null);
  const [liveTranscript, setLiveTranscript] = useState('');

  // Save state
  const [isSaving, setIsSaving] = useState(false);

  // Refs
  const fileInputRef = useRef<HTMLInputElement>(null);
  const chatEndRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLInputElement>(null);

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

      // Extract the UPDATED_DOC block. Multiple patterns because the
      // model drifts: sometimes the fence is lowercase, sometimes it's
      // truncated mid-doc and the closing ``` is missing, sometimes
      // there's leading/trailing whitespace. Try strict → loose → open.
      const extractUpdatedDoc = (text: string): string | null => {
        // Strict: ```UPDATED_DOC\n<content>\n```
        const strict = text.match(
          /```\s*UPDATED_DOC\s*\r?\n([\s\S]*?)\r?\n```/i
        );
        if (strict?.[1]) return strict[1];
        // Truncated: no closing fence. Take everything after the opener.
        const truncated = text.match(/```\s*UPDATED_DOC\s*\r?\n([\s\S]*)$/i);
        if (truncated?.[1]) {
          // If there's a stray closing fence partway through (rare), cut
          // there; otherwise keep the whole tail.
          const tail = truncated[1];
          const strayClose = tail.lastIndexOf('```');
          return strayClose > 50 ? tail.slice(0, strayClose) : tail;
        }
        // Bare marker without fence (model emitted "UPDATED_DOC:" etc.).
        const bare = text.match(/UPDATED_DOC[:\s-]*\r?\n([\s\S]*)$/i);
        if (bare?.[1]) return bare[1];
        return null;
      };

      const rawUpdated = extractUpdatedDoc(aiText);
      let docWasUpdated = false;
      if (rawUpdated) {
        const updated = rawUpdated
          .replace(/^---\s*$/gm, '') // strip our own --- separators if echoed back
          .replace(/^```\s*$/gm, '') // strip any stray fences
          .trim();
        if (updated.length > 20) {
          setDocumentContent(updated);
          docWasUpdated = true;
        }
      }

      // Strip all fenced code blocks from the display text so the
      // user doesn't see the raw UPDATED_DOC dump in chat.
      let display = aiText.replace(/```[\s\S]*?```/g, '').trim();
      // Also strip a truncated trailing block (no close fence).
      display = display.replace(/```[\s\S]*$/g, '').trim();

      if (!docWasUpdated) {
        // The model replied but didn't include a valid UPDATED_DOC
        // block — the document was NOT changed. Tell the doctor
        // explicitly instead of silently showing "Changes applied."
        // while the file still shows the old version.
        const warning =
          (display || 'The AI replied without an updated document.') +
          '\n\n⚠️ No changes applied — the AI didn\'t return the edited document. Try rephrasing the request (e.g., "change X to Y in the document").';
        setMessages((prev) => [
          ...prev,
          { id: makeId(), role: 'system', content: warning, timestamp: new Date() },
        ]);
      } else {
        setMessages((prev) => [
          ...prev,
          {
            id: makeId(),
            role: 'assistant',
            content: display || 'Changes applied.',
            timestamp: new Date(),
          },
        ]);
      }
    } catch (err) {
      const msg = err instanceof Error ? err.message : 'Request failed';
      setMessages(prev => [...prev, { id: makeId(), role: 'assistant', content: `Error: ${msg}`, timestamp: new Date() }]);
    } finally {
      setIsProcessing(false);
    }
  }, []);

  // -----------------------------------------------------------------------
  // Voice → Whisper → AI edit
  // Same recording behavior as Add Patient (useVoiceRecorder), with the
  // doc-editor-specific post-transcribe flow (POST the text to the AI
  // chat that rewrites the document).
  // -----------------------------------------------------------------------

  const handleAudioBlob = useCallback(
    async (blob: Blob | null) => {
      if (!blob || blob.size < 1000) {
        setMessages((prev) => [
          ...prev,
          { id: makeId(), role: 'system', content: 'No audio detected. Try again.', timestamp: new Date() },
        ]);
        setVoiceState(null);
        return;
      }
      setVoiceState('submitting');
      try {
        const formData = new FormData();
        formData.append('audio', blob, 'recording.webm');
        const res = await fetch('/api/transcribe', {
          method: 'POST',
          body: formData,
        });
        if (!res.ok) {
          const err = await res.json().catch(() => ({ error: 'Transcription failed' }));
          throw new Error(err.error || `Transcription failed: ${res.status}`);
        }
        const { text } = (await res.json()) as { text?: string };
        if (!text || text.trim().length < 2) {
          setMessages((prev) => [
            ...prev,
            { id: makeId(), role: 'system', content: 'No speech detected. Try again.', timestamp: new Date() },
          ]);
          setVoiceState(null);
          return;
        }
        const transcript = text.trim();
        setLiveTranscript(transcript);
        setVoiceState('editing');
        await sendToAI(transcript);
      } catch (err) {
        const msg = err instanceof Error ? err.message : 'Voice processing failed';
        setMessages((prev) => [
          ...prev,
          { id: makeId(), role: 'system', content: `Voice error: ${msg}`, timestamp: new Date() },
        ]);
      } finally {
        setVoiceState(null);
      }
    },
    [sendToAI]
  );

  const voice = useVoiceRecorder({
    // Same tuning as Add Patient: room to think between phrases + a
    // generous hard cap for long dictated edits.
    silenceTimeoutMs: 4000,
    maxDurationMs: 120_000,
    onAutoStop: handleAudioBlob,
  });

  const toggleVoice = useCallback(async () => {
    if (voiceState === 'submitting' || voiceState === 'editing') return;
    if (voice.isRecording) {
      const blob = await voice.stop();
      void handleAudioBlob(blob);
    } else {
      void voice.start();
    }
  }, [voice, voiceState, handleAudioBlob]);

  const cancelVoice = useCallback(() => {
    if (voice.isRecording) void voice.stop();
    setVoiceState(null);
  }, [voice]);

  // Support flag — the hook uses MediaRecorder under the hood, same
  // checks as before. Kept as a ref-free derived constant for the UI.
  const voiceSupported =
    typeof window !== 'undefined' &&
    typeof navigator !== 'undefined' &&
    !!navigator.mediaDevices &&
    typeof window.MediaRecorder !== 'undefined';

  // Collapsed UI state — maps the hook's recorder status + our own
  // post-recording overlay back into the 5-bucket view the JSX was
  // built around. Keeps the render block untouched while the plumbing
  // below matches Add Patient exactly.
  const uiVoiceState: 'idle' | 'listening' | 'processing' | 'submitting' | 'editing' =
    voiceState === 'submitting'
      ? 'submitting'
      : voiceState === 'editing'
        ? 'editing'
        : voice.status === 'recording'
          ? 'processing'
          : voice.status === 'listening' || voice.status === 'starting'
            ? 'listening'
            : 'idle';

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
      if (voice.isRecording) {
        cancelVoice();
      }

      await sendToAI(messageText);
    },
    [inputText, documentContent, isProcessing, voice, cancelVoice, sendToAI]
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
            {uiVoiceState === 'listening' && (
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

            {uiVoiceState === 'processing' && (
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

            {uiVoiceState === 'submitting' && (
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

            {uiVoiceState === 'editing' && (
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
                  whileHover={{ scale: uiVoiceState === 'idle' || uiVoiceState === 'listening' || uiVoiceState === 'processing' ? 1.08 : 1 }}
                  whileTap={{ scale: uiVoiceState === 'idle' || uiVoiceState === 'listening' || uiVoiceState === 'processing' ? 0.92 : 1 }}
                  onClick={toggleVoice}
                  disabled={!file || isProcessing || uiVoiceState === 'submitting' || uiVoiceState === 'editing'}
                  className={`p-2.5 rounded-xl relative transition-all cursor-pointer disabled:opacity-30 disabled:cursor-not-allowed ${
                    uiVoiceState === 'listening'
                      ? 'bg-red-500/20 text-red-300 ring-2 ring-red-500/40'
                      : uiVoiceState === 'processing'
                      ? 'bg-emerald-500/20 text-emerald-300 ring-2 ring-emerald-500/40'
                      : uiVoiceState === 'submitting'
                      ? 'bg-violet-500/20 text-violet-400'
                      : uiVoiceState === 'editing'
                      ? 'bg-blue-500/20 text-blue-400'
                      : 'text-slate-400 hover:text-white hover:bg-white/10'
                  }`}
                  title={
                    uiVoiceState === 'idle' ? 'Click to start voice input' :
                    uiVoiceState === 'listening' ? 'Listening... (click to cancel)' :
                    uiVoiceState === 'processing' ? 'Capturing command (click to stop & send)' :
                    uiVoiceState === 'submitting' ? 'Processing...' :
                    'Editing document...'
                  }
                >
                  {(uiVoiceState === 'listening' || uiVoiceState === 'processing') && (
                    <span className={`absolute inset-0 rounded-xl animate-ping ${
                      uiVoiceState === 'listening' ? 'bg-red-500/20' : 'bg-emerald-500/20'
                    }`} />
                  )}
                  {uiVoiceState === 'submitting' || uiVoiceState === 'editing' ? (
                    <Loader2 className="w-5 h-5 animate-spin relative" />
                  ) : uiVoiceState === 'listening' || uiVoiceState === 'processing' ? (
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
                    : uiVoiceState === 'listening'
                    ? 'Listening — start speaking anytime...'
                    : uiVoiceState === 'processing'
                    ? 'Capturing command — pause 2.5s to send'
                    : uiVoiceState === 'submitting'
                    ? 'Processing...'
                    : uiVoiceState === 'editing'
                    ? 'Editing document...'
                    : 'Click mic or type your command...'
                }
                disabled={!file || isProcessing || uiVoiceState !== 'idle'}
                className="flex-1 bg-transparent text-white placeholder-slate-500 text-sm px-2 py-2 outline-none disabled:opacity-50"
              />

              {/* Send button */}
              <motion.button
                whileHover={{ scale: 1.05 }}
                whileTap={{ scale: 0.95 }}
                onClick={() => sendMessage()}
                disabled={!file || !inputText.trim() || isProcessing || uiVoiceState !== 'idle'}
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
                ? uiVoiceState === 'idle'
                  ? 'Click the mic to start voice input, or type your command'
                  : uiVoiceState === 'listening'
                  ? 'Ready — start speaking whenever you want'
                  : uiVoiceState === 'processing'
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
