'use client';

// ============================================================================
// GlobalAIAssistant — Realtime voice assistant (Phase 2)
// ----------------------------------------------------------------------------
// Connects to OpenAI Realtime API via WebRTC. Single neural model handles
// STT + dialogue + TTS in one streaming session: ~500ms first-byte latency,
// native barge-in, true conversational feel. Tool calls (create_clinical_note,
// edit_clinical_note, schedule_appointment, summarize_chart, generate_document)
// are dispatched server-side via /api/assistant-tool with full HIPAA auth.
//
// Visual: docked bottom-right, ~380px wide, no backdrop. Patient chart stays
// fully visible behind it.
//
// Lifecycle:
//   tap orb (idle) → connecting → listening (server VAD active)
//   doctor speaks  → listening → thinking → speaking
//   AI replies     → speaking → listening (loops naturally)
//   tap orb        → idle (close session)
//
// Manual controls:
//   - Tap orb during any state to toggle the session
//   - X / ESC / click outside (none — no backdrop) closes
// ============================================================================

import { useCallback, useEffect, useRef, useState } from 'react';
import { useRouter } from 'next/navigation';
import { motion, AnimatePresence } from 'framer-motion';
import {
  Sparkles,
  Mic,
  X,
  Loader2,
  AlertCircle,
  FileText,
  Copy,
  Check,
  UploadCloud,
  AudioLines,
  Wand2,
} from 'lucide-react';

import {
  useRealtimeSession,
  type RealtimeStatus,
  type RealtimeToolAction,
} from '@/lib/hooks/useRealtimeSession';
import { uploadCustomProcedureAction } from '@/app/dashboard/patients/actions';

interface GlobalAIAssistantProps {
  open: boolean;
  onClose: () => void;
  patientId: string;
  patientName: string;
  patientStatus: 'ACTIVE' | 'INACTIVE' | 'ARCHIVED';
  noteCount: number;
  procedureCount: number;
}

export default function GlobalAIAssistant({ open, onClose, ...props }: GlobalAIAssistantProps) {
  return (
    <AnimatePresence>
      {open && <GlobalAIAssistantPanel onClose={onClose} {...props} />}
    </AnimatePresence>
  );
}

function GlobalAIAssistantPanel({
  onClose,
  patientId,
  patientName,
  patientStatus,
  noteCount,
  procedureCount,
}: Omit<GlobalAIAssistantProps, 'open'>) {
  const router = useRouter();

  const [lastUserUtterance, setLastUserUtterance] = useState('');
  const [lastAssistantReply, setLastAssistantReply] = useState('');
  const [lastAction, setLastAction] = useState<RealtimeToolAction | null>(null);
  /** Set when the AI calls request_file_upload. The panel shows a file
   *  picker; on file pick we upload + tell the model what happened. */
  const [awaitingFileUpload, setAwaitingFileUpload] = useState<{ reason: string } | null>(null);
  const [uploading, setUploading] = useState(false);
  const fileInputRef = useRef<HTMLInputElement>(null);
  /** True when the session has been in 'thinking' >5s without responding.
   *  Triggers a small hint so the doctor knows she's not silently stuck. */
  const [thinkingTooLong, setThinkingTooLong] = useState(false);

  // Helper — refreshes the AI's system instructions so newly-created /
  // edited content shows up in her CUSTOM_PROCEDURES / RECENT_NOTES /
  // BRIEF_HISTORY context. Otherwise she'll insist a just-uploaded file
  // doesn't exist because her snapshot is stale from session start.
  const refreshAssistantContext = useCallback(async () => {
    try {
      // Browser timezone so the refreshed prompt re-frames dates in local
      // time. Same logic as the initial session create.
      let timezone: string | undefined;
      try {
        timezone = Intl.DateTimeFormat().resolvedOptions().timeZone;
      } catch {
        // ignore; server falls back to UTC
      }
      const res = await fetch('/api/realtime/refresh-context', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ patientId, timezone }),
      });
      if (!res.ok) return;
      const data = (await res.json()) as { instructions?: string };
      if (data.instructions) {
        const sent = sessionApiRef.current?.updateInstructions(data.instructions);
        console.info('[assistant] context refreshed, session.update sent:', sent);
      }
    } catch (err) {
      console.warn('[assistant] context refresh failed:', err);
    }
  }, [patientId]);

  // Forward ref so refreshAssistantContext (defined above) can reach the
  // session methods (defined just below). Avoids a temporal dependency
  // cycle in the hook order.
  const sessionApiRef = useRef<ReturnType<typeof useRealtimeSession> | null>(null);

  const session = useRealtimeSession({
    patientId,
    onUserTranscript: (text) => {
      setLastUserUtterance(text);
    },
    onAssistantTranscript: (text) => {
      setLastAssistantReply(text);
    },
    onToolAction: (action) => {
      setLastAction(action);
      // File upload tools surface as awaiting_file_upload. Show the visible
      // picker button — auto-clicking the hidden input is unreliable
      // because browsers reject input.click() outside a real user-gesture
      // chain. Best-effort attempt below; the prominent button in the
      // panel is the reliable path.
      if (action.type === 'awaiting_file_upload') {
        const reason = String(action.reason ?? 'a file');
        console.info('[assistant] request_file_upload received:', reason);
        setAwaitingFileUpload({ reason });
        try {
          fileInputRef.current?.click();
        } catch {
          // ignore; visible button is the fallback
        }
        return;
      }
      // After any write, refresh the page (so the new content appears in
      // the chart below) AND refresh the AI's context (so she knows about
      // it on the next turn).
      const t = action.type;
      // Every write-action needs to trigger a chart + AI-context
      // refresh, otherwise the model's next turn sees stale lists and
      // mis-routes follow-up commands (e.g. "edit the final report" →
      // edit_custom_procedure because FINAL_REPORTS was empty in the
      // cached prompt).
      if (
        t === 'created_note' ||
        t === 'edited_note' ||
        t === 'scheduled_appointment' ||
        t === 'updated_patient' ||
        t === 'final_report_generated'
      ) {
        router.refresh();
        void refreshAssistantContext();
      }
    },
  });

  // Chart writes outside the AI (modal uploads, manual edits, deletes
  // etc.) dispatch a `meddoc:chart-updated` CustomEvent. We re-pull the
  // session prompt on that signal so the AI's FINAL_REPORTS /
  // ATTACHED_FILES / RECENT_NOTES context stays accurate within an open
  // session.
  useEffect(() => {
    const handler = () => {
      void refreshAssistantContext();
    };
    window.addEventListener('meddoc:chart-updated', handler);
    return () => window.removeEventListener('meddoc:chart-updated', handler);
  }, [refreshAssistantContext]);

  // Keep the ref in sync so refreshAssistantContext can reach updateInstructions.
  useEffect(() => {
    sessionApiRef.current = session;
  }, [session]);

  // Stuck-state detector: if the session sits in 'thinking' for >5s, show
  // a hint so the doctor knows she's not silently failing. Clears as soon
  // as status transitions out of thinking.
  useEffect(() => {
    if (session.status !== 'thinking') {
      setThinkingTooLong(false);
      return;
    }
    const t = setTimeout(() => setThinkingTooLong(true), 5000);
    return () => clearTimeout(t);
  }, [session.status]);

  // File-picker handler. Runs the existing audited upload, then feeds the
  // result back into the conversation so the model can speak the result.
  const handleFileSelected = useCallback(
    async (e: React.ChangeEvent<HTMLInputElement>) => {
      const file = e.target.files?.[0];
      // Reset the input so the same file can be re-selected later.
      e.target.value = '';
      if (!file) {
        // Cancelled — let the model know so it can move on.
        session.sendUserMessage('I cancelled the file picker — no file was attached.');
        setAwaitingFileUpload(null);
        return;
      }
      setUploading(true);
      try {
        const fd = new FormData();
        fd.append('file', file);
        const result = await uploadCustomProcedureAction(patientId, fd);
        if (result.ok) {
          // Refresh the AI's context FIRST so the next turn (which she'll
          // start as soon as she hears our synthetic message) sees the new
          // procedure in CUSTOM_PROCEDURES. Then the synthetic message
          // tells her what happened so she can confirm aloud.
          await refreshAssistantContext();
          session.sendUserMessage(
            `I just uploaded "${file.name}" as a custom procedure. It's now in CUSTOM_PROCEDURES context. Confirm it's attached.`
          );
          router.refresh();
        } else {
          session.sendUserMessage(`The upload failed: ${result.error}`);
        }
      } catch (err) {
        const message = err instanceof Error ? err.message : 'Upload failed';
        session.sendUserMessage(`The upload failed: ${message}`);
      } finally {
        setUploading(false);
        setAwaitingFileUpload(null);
      }
    },
    [patientId, router, session, refreshAssistantContext]
  );

  // ESC closes the panel.
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape') onClose();
    };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, [onClose]);

  // Hard cleanup on unmount — never leave the WebRTC session alive.
  useEffect(() => {
    return () => {
      session.stop();
    };
    // session methods are stable; we intentionally only run on unmount.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const handleOrbClick = useCallback(async () => {
    if (session.isActive) {
      session.stop();
      return;
    }
    await session.start();
  }, [session]);

  const handleClose = useCallback(() => {
    session.stop();
    onClose();
  }, [session, onClose]);

  return (
    <motion.div
      initial={{ opacity: 0, y: 16, scale: 0.97 }}
      animate={{ opacity: 1, y: 0, scale: 1 }}
      exit={{ opacity: 0, y: 16, scale: 0.97 }}
      transition={{ type: 'spring', stiffness: 360, damping: 30 }}
      role="dialog"
      aria-label="AI Assistant"
      // Softer shadow, more restrained border, rounder corners. The panel
      // should feel like a first-class app surface, not a game overlay.
      className="fixed bottom-6 right-6 z-[100] w-[min(400px,calc(100vw-2rem))] rounded-3xl bg-[#0b1424] border border-slate-700/50 shadow-[0_16px_40px_-10px_rgba(0,0,0,0.7)] backdrop-blur-xl flex flex-col overflow-hidden pointer-events-auto"
      style={{ maxHeight: 'min(580px, calc(100vh - 3rem))' }}
    >
      {/* ── Header ── Minimal: gradient icon tile on the left, status dot,
          close button on the right. No "Realtime" badge — status dot does it. */}
      <div className="flex items-center gap-3 px-4 py-3 border-b border-slate-700/50 shrink-0">
        <div className="relative flex h-8 w-8 shrink-0 items-center justify-center rounded-lg bg-gradient-to-br from-violet-500 via-blue-500 to-teal-500 shadow-lg shadow-violet-500/30">
          <AudioLines className="w-4 h-4 text-white" />
          {/* Live status pip — emerald when session is active, slate idle. */}
          <span
            className={`absolute -bottom-0.5 -right-0.5 flex h-2.5 w-2.5 rounded-full ring-2 ring-[#0b1424] ${
              session.isActive ? 'bg-emerald-400' : 'bg-slate-500'
            }`}
          />
        </div>
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-1.5">
            <p className="text-sm font-semibold text-white truncate leading-tight">
              Voice Assistant
            </p>
            {patientStatus !== 'ACTIVE' && (
              <span
                className={`px-1.5 py-0.5 rounded text-[9px] font-semibold uppercase tracking-wider ${
                  patientStatus === 'ARCHIVED'
                    ? 'bg-slate-700 text-slate-300'
                    : 'bg-amber-500/20 text-amber-200'
                }`}
              >
                {patientStatus.toLowerCase()}
              </span>
            )}
          </div>
          <p className="text-[11px] text-slate-400 truncate mt-0.5">
            {patientName} · {noteCount} notes · {procedureCount} procedures
          </p>
        </div>
        <button
          type="button"
          onClick={handleClose}
          aria-label="Close AI Assistant"
          className="p-1.5 rounded-md text-slate-500 hover:text-white hover:bg-slate-800 transition-colors cursor-pointer"
        >
          <X className="w-4 h-4" />
        </button>
      </div>

      {/* ── Body ── */}
      <VoicePanelBody
        status={session.status}
        currentTool={session.currentTool}
        lastUserUtterance={lastUserUtterance}
        lastAssistantReply={lastAssistantReply}
        lastAction={lastAction}
        sessionError={session.error}
        onOrbClick={handleOrbClick}
        awaitingFileUpload={awaitingFileUpload}
        uploading={uploading}
        onPickFileClick={() => fileInputRef.current?.click()}
        thinkingTooLong={thinkingTooLong}
      />

      {/* Hidden file input — the AI tool call triggers .click() on this so
          the OS file picker pops up. Browser security requires the picker
          to be opened from within a user-gesture chain; the tool call is
          part of the WebRTC event loop the user initiated by tapping the
          orb, which in modern browsers counts. If a future browser blocks
          this, the doctor can also click the visible "Pick file" button
          which is unambiguously inside a user gesture. */}
      <input
        ref={fileInputRef}
        type="file"
        accept=".pdf,.docx,application/pdf,application/vnd.openxmlformats-officedocument.wordprocessingml.document"
        className="hidden"
        onChange={handleFileSelected}
      />

      <div className="px-4 py-2.5 border-t border-slate-700/50 shrink-0">
        <p className="text-[10px] text-slate-500 text-center tracking-wide">
          Tap orb to start · ESC to close · Interrupt anytime
        </p>
      </div>
    </motion.div>
  );
}

// ---------------------------------------------------------------------------
// VoicePanelBody — orb + state-driven status.
// ---------------------------------------------------------------------------
function VoicePanelBody({
  status,
  currentTool,
  lastUserUtterance,
  lastAssistantReply,
  lastAction,
  sessionError,
  onOrbClick,
  awaitingFileUpload,
  uploading,
  onPickFileClick,
  thinkingTooLong,
}: {
  status: RealtimeStatus;
  currentTool: string | null;
  lastUserUtterance: string;
  lastAssistantReply: string;
  lastAction: RealtimeToolAction | null;
  sessionError: string | null;
  onOrbClick: () => void;
  awaitingFileUpload: { reason: string } | null;
  uploading: boolean;
  onPickFileClick: () => void;
  thinkingTooLong: boolean;
}) {
  const orbStyles: Record<RealtimeStatus, { from: string; to: string; ring: string; pulse: boolean; label: string; sub: string }> = {
    idle: {
      from: 'from-slate-700',
      to: 'to-slate-800',
      ring: 'ring-white/10',
      pulse: false,
      label: 'Tap to start',
      sub: 'Speak naturally — schedule, dictate, edit, summarize.',
    },
    connecting: {
      from: 'from-violet-500',
      to: 'to-blue-500',
      ring: 'ring-violet-400/40',
      pulse: true,
      label: 'Connecting…',
      sub: 'Setting up the voice channel.',
    },
    listening: {
      from: 'from-emerald-500',
      to: 'to-teal-500',
      ring: 'ring-emerald-400/50',
      pulse: true,
      label: 'Listening',
      sub: 'Speak naturally. I\'ll respond.',
    },
    thinking: {
      from: 'from-violet-500',
      to: 'to-blue-500',
      ring: 'ring-violet-400/50',
      pulse: true,
      label: 'Thinking…',
      sub: '',
    },
    working: {
      from: 'from-amber-500',
      to: 'to-orange-500',
      ring: 'ring-amber-400/50',
      pulse: true,
      label: labelForTool(currentTool),
      sub: 'Writing changes to the chart…',
    },
    speaking: {
      from: 'from-blue-500',
      to: 'to-cyan-500',
      ring: 'ring-blue-400/50',
      pulse: true,
      label: 'Speaking',
      sub: 'Interrupt anytime by talking over me.',
    },
    error: {
      from: 'from-red-500',
      to: 'to-rose-600',
      ring: 'ring-red-400/40',
      pulse: false,
      label: 'Error',
      sub: 'Tap orb to retry.',
    },
  };
  const s = orbStyles[status];

  const generatedDoc =
    lastAction?.type === 'generated_document'
      ? (lastAction as { documentTitle?: string; content?: string })
      : null;

  return (
    <div className="flex-1 flex flex-col items-center justify-start px-4 py-4 space-y-3 min-h-[360px] overflow-y-auto">
      {/* Doctor's last utterance — surfaces as soon as the model emits the
          input transcript, well before it starts speaking the reply. */}
      <div className="w-full min-h-[18px] text-[11px] text-slate-500 italic text-center">
        {lastUserUtterance && `"${lastUserUtterance}"`}
      </div>

      {/* File upload prompt — high prominence so it's impossible to miss.
          The auto-click that fires when the AI calls the tool is unreliable
          across browsers (input.click() outside a user gesture is silently
          rejected), so this big button is the real path. Pulsing ring
          draws the eye when newly visible. */}
      {(awaitingFileUpload || uploading) && (
        <motion.div
          initial={{ opacity: 0, scale: 0.94 }}
          animate={{ opacity: 1, scale: 1 }}
          className="w-full px-4 py-4 rounded-xl bg-gradient-to-br from-blue-500/15 to-cyan-500/15 border-2 border-blue-400/50 flex flex-col items-center gap-3 text-center shadow-lg shadow-blue-500/20"
        >
          {uploading ? (
            <>
              <Loader2 className="w-7 h-7 text-blue-300 animate-spin" />
              <p className="text-sm font-bold text-blue-100">Uploading…</p>
              <p className="text-[11px] text-slate-300">
                Extracting text and attaching to Custom Procedures.
              </p>
            </>
          ) : (
            <>
              <UploadCloud className="w-7 h-7 text-blue-300" />
              <p className="text-sm font-bold text-blue-100">
                Pick a file to attach
              </p>
              <p className="text-[11px] text-slate-300">
                {awaitingFileUpload?.reason}
              </p>
              <button
                type="button"
                onClick={onPickFileClick}
                aria-label="Open file picker"
                className="relative mt-1 inline-flex items-center gap-2 px-4 py-2.5 rounded-lg bg-gradient-to-r from-blue-500 to-cyan-500 hover:from-blue-400 hover:to-cyan-400 text-white text-sm font-bold shadow-lg shadow-blue-500/40 hover:shadow-blue-500/60 hover:scale-[1.03] transition-all cursor-pointer"
              >
                <span className="absolute inset-0 rounded-lg bg-blue-400/50 animate-ping opacity-40" />
                <UploadCloud className="w-4 h-4 relative" />
                <span className="relative">Choose PDF / DOCX</span>
              </button>
              <p className="text-[10px] text-slate-500 italic">
                Browser may have already opened it — check for the OS dialog.
              </p>
            </>
          )}
        </motion.div>
      )}

      {/* Orb — smooth radial-glow sphere with framer-motion breathing
          animation. No chunky ring; the outer glow (box-shadow) gives
          depth without visual noise. */}
      <button
        type="button"
        onClick={onOrbClick}
        aria-label={`Voice ${status}`}
        className="group relative flex items-center justify-center cursor-pointer my-3 outline-none"
      >
        <motion.span
          animate={s.pulse ? { scale: [1, 1.04, 1] } : { scale: 1 }}
          transition={s.pulse ? { repeat: Infinity, duration: 2.2, ease: 'easeInOut' } : { duration: 0.3 }}
          className={`relative flex h-28 w-28 items-center justify-center rounded-full bg-gradient-to-br ${s.from} ${s.to} transition-transform group-hover:scale-[1.03]`}
          style={{
            // Soft outer glow + subtle inner highlight via layered shadows.
            boxShadow: s.pulse
              ? '0 0 48px rgba(139,92,246,0.25), 0 0 24px rgba(59,130,246,0.2), inset 0 1px 2px rgba(255,255,255,0.15)'
              : '0 8px 24px rgba(0,0,0,0.4), inset 0 1px 2px rgba(255,255,255,0.1)',
          }}
        >
          {status === 'connecting' || status === 'thinking' ? (
            <Loader2 className="w-9 h-9 text-white animate-spin" />
          ) : status === 'working' ? (
            // Wand icon reads as "acting / editing / making changes" —
            // distinct from the spinner (which reads as passive waiting).
            <Wand2 className="w-9 h-9 text-white" />
          ) : (
            <Mic className="w-9 h-9 text-white" />
          )}
        </motion.span>
      </button>

      <div className="text-center space-y-0.5">
        <p className="text-sm font-bold text-white">{s.label}</p>
        {s.sub && <p className="text-[10px] text-slate-400">{s.sub}</p>}
      </div>

      {/* Stuck-state hint — if she's been thinking >5s something's off.
          Usually: didn't hear the utterance, or the model is delayed.
          Tell the doctor how to recover instead of silent hang. */}
      {thinkingTooLong && status === 'thinking' && (
        <div className="w-full inline-flex items-center gap-1.5 px-2 py-1.5 rounded-lg bg-amber-500/10 border border-amber-500/30 text-[10px] text-amber-200 justify-center text-center">
          <AlertCircle className="w-3 h-3 shrink-0" />
          <span>Still thinking… tap the orb to cancel and try again.</span>
        </div>
      )}

      {/* AI's last reply — visible fallback if you missed the audio. */}
      {lastAssistantReply && !sessionError && (
        <div className="w-full text-[11px] text-slate-300 text-center px-2 leading-relaxed">
          {lastAssistantReply}
        </div>
      )}

      {/* Generated document preview. */}
      {generatedDoc && generatedDoc.content && (
        <DocumentPreview
          title={generatedDoc.documentTitle ?? 'Document'}
          content={generatedDoc.content}
        />
      )}

      {sessionError && (
        <div className="w-full inline-flex items-center gap-1.5 px-2 py-1.5 rounded-lg bg-red-500/10 border border-red-500/30 text-[10px] text-red-300 justify-center">
          <AlertCircle className="w-3 h-3 shrink-0" />
          <span className="text-left">{sessionError}</span>
        </div>
      )}

      {status === 'idle' && !lastUserUtterance && !lastAssistantReply && (
        <div className="flex items-center gap-1.5 text-[10px] text-slate-600">
          <Sparkles className="w-3 h-3 text-violet-400/60" />
          Voice-only · Realtime · auto-conversational
        </div>
      )}
    </div>
  );
}

// ---------------------------------------------------------------------------
// DocumentPreview — collapsible scrollable preview with Copy button.
// ---------------------------------------------------------------------------
// Human-readable label for each tool name. Falls back to a generic
// "Working…" when we don't have a specific mapping — safer than showing
// the raw snake_case tool name to the doctor.
function labelForTool(toolName: string | null): string {
  switch (toolName) {
    case 'create_clinical_note':
      return 'Saving note…';
    case 'read_clinical_note':
      return 'Reading note…';
    case 'edit_clinical_note':
      return 'Editing note…';
    case 'delete_clinical_note':
      return 'Deleting note…';
    case 'read_custom_procedure':
      return 'Reading procedure…';
    case 'edit_custom_procedure':
      return 'Editing procedure…';
    case 'delete_custom_procedure':
      return 'Deleting procedure…';
    case 'schedule_appointment':
      return 'Scheduling…';
    case 'cancel_appointment':
      return 'Cancelling appointment…';
    case 'summarize_chart':
      return 'Summarizing…';
    case 'generate_document':
      return 'Drafting document…';
    case 'update_patient':
      return 'Updating patient…';
    case 'archive_patient':
      return 'Archiving patient…';
    case 'request_file_upload':
      return 'Opening upload…';
    default:
      return 'Working…';
  }
}

function DocumentPreview({ title, content }: { title: string; content: string }) {
  const [copied, setCopied] = useState(false);
  const [expanded, setExpanded] = useState(true);

  const handleCopy = async () => {
    try {
      await navigator.clipboard.writeText(content);
      setCopied(true);
      setTimeout(() => setCopied(false), 1500);
    } catch {
      // Clipboard API unavailable — manual select fallback.
    }
  };

  return (
    <div className="w-full rounded-lg border border-amber-500/20 bg-amber-500/[0.04] overflow-hidden">
      <button
        type="button"
        onClick={() => setExpanded((v) => !v)}
        className="w-full flex items-center gap-2 px-3 py-2 text-left hover:bg-amber-500/[0.08] transition-colors cursor-pointer"
      >
        <FileText className="w-3.5 h-3.5 text-amber-300 shrink-0" />
        <span className="text-[11px] font-semibold text-amber-200 flex-1 truncate">{title}</span>
        <span className="text-[9px] text-amber-300/70 uppercase tracking-wider">
          {expanded ? 'Hide' : 'Show'}
        </span>
      </button>
      {expanded && (
        <div className="border-t border-amber-500/20">
          <div className="max-h-48 overflow-y-auto px-3 py-2 text-[11px] text-slate-200 font-mono leading-relaxed whitespace-pre-wrap break-words bg-slate-950/40">
            {content}
          </div>
          <div className="flex items-center justify-end gap-2 px-2 py-1.5 border-t border-amber-500/20 bg-amber-500/[0.04]">
            <button
              type="button"
              onClick={handleCopy}
              className="inline-flex items-center gap-1 px-2 py-1 rounded text-[10px] font-semibold text-amber-200 hover:bg-amber-500/15 transition-colors cursor-pointer"
            >
              {copied ? <><Check className="w-3 h-3" /> Copied</> : <><Copy className="w-3 h-3" /> Copy text</>}
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
