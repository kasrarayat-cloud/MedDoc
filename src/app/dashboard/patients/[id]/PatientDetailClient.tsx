'use client';

import { useState, useTransition, useRef, useEffect } from 'react';
import Link from 'next/link';
import { useRouter } from 'next/navigation';
import { motion, AnimatePresence } from 'framer-motion';
import {
  ArrowLeft,
  Sparkles,
  FileText,
  Calendar,
  Stethoscope,
  Mail,
  Phone,
  Tag,
  Edit3,
  Activity,
  Clock,
  FileEdit,
  ChevronDown,
  Pencil,
  Save,
  X,
  Loader2,
  ChevronRight,
  ClipboardList,
  UploadCloud,
  AlertCircle,
  Archive,
  AudioLines,
  Paperclip,
  FileBadge,
  Trash2,
} from 'lucide-react';
import { formatLastVisit, formatRelativeDate } from '@/lib/mock-patients';
import type { PatientView } from '@/lib/data/patients';
import type { ClinicalNoteView } from '@/lib/data/clinical-notes';
import { PROCEDURE_TEMPLATES } from '@/lib/constants/procedure-templates';
import {
  archivePatientAction,
  createNoteFromTemplateAction,
  updateNoteManuallyAction,
  uploadCustomProcedureAction,
  generateFinalReportAction,
  deleteDocumentAction,
} from '@/app/dashboard/patients/actions';
import EditPatientModal from './EditPatientModal';
import DocumentGeneratorModal from './DocumentGeneratorModal';
import ScheduleVisitModal from './ScheduleVisitModal';
import GlobalAIAssistant from './GlobalAIAssistant';
import PatientFileUploadModal from './PatientFileUploadModal';

const statusStyles = {
  ACTIVE: 'bg-emerald-500/15 text-emerald-300 border-emerald-500/30',
  INACTIVE: 'bg-amber-500/15 text-amber-300 border-amber-500/30',
  ARCHIVED: 'bg-slate-600/20 text-slate-400 border-slate-600/30',
} as const;

const noteStatusStyles = {
  DRAFT: 'bg-slate-600/20 text-slate-300 border-slate-600/30',
  FINALIZED: 'bg-blue-500/15 text-blue-300 border-blue-500/30',
  SIGNED: 'bg-emerald-500/15 text-emerald-300 border-emerald-500/30',
} as const;

interface PatientDetailClientProps {
  patient: PatientView;
  notes: ClinicalNoteView[];
  customProcedures: ClinicalNoteView[];
  /** Attachments on the chart — metadata rows, no bytes yet. */
  patientFiles: ClinicalNoteView[];
  /** AI-synthesized reports. Saved as DRAFT; doctor signs off later. */
  finalReports: ClinicalNoteView[];
}

function formatBytes(n: number | undefined): string {
  if (!n || n <= 0) return '—';
  if (n < 1024) return `${n} B`;
  if (n < 1024 * 1024) return `${(n / 1024).toFixed(1)} KB`;
  return `${(n / 1024 / 1024).toFixed(1)} MB`;
}

export default function PatientDetailClient({
  patient,
  notes,
  customProcedures,
  patientFiles,
  finalReports,
}: PatientDetailClientProps) {
  const age = new Date().getFullYear() - patient.birthYear;
  const initials = `${patient.firstName[0]}${patient.lastName[0]}`;
  const router = useRouter();
  const [expandedNoteId, setExpandedNoteId] = useState<string | null>(null);
  const [editModalOpen, setEditModalOpen] = useState(false);
  const [docGenModalOpen, setDocGenModalOpen] = useState(false);
  const [scheduleModalOpen, setScheduleModalOpen] = useState(false);
  const [fileUploadModalOpen, setFileUploadModalOpen] = useState(false);
  // Client-side mirrors of the server-rendered lists. Let the modal and
  // the Generate button prepend new rows optimistically so the UI updates
  // without a full page reload. A router.refresh() on the action still
  // keeps these in sync across tabs eventually.
  const [files, setFiles] = useState<ClinicalNoteView[]>(patientFiles);
  const [reports, setReports] = useState<ClinicalNoteView[]>(finalReports);
  /** Which final report is expanded in the list — matches the pattern used
   *  for clinical notes above. */
  const [expandedReportId, setExpandedReportId] = useState<string | null>(null);
  /** `isPending` flag for the final-report generation call. Drives the
   *  loading spinner + disabled state on the "Generate via AI" button. */
  const [reportGenerating, setReportGenerating] = useState(false);
  const [reportError, setReportError] = useState<string | null>(null);

  const handleGenerateFinalReport = async () => {
    if (reportGenerating) return;
    setReportGenerating(true);
    setReportError(null);
    try {
      const result = await generateFinalReportAction(patient.id);
      if (!result.ok) {
        setReportError(result.error);
        return;
      }
      // Prepend — newest first matches the server-side ordering.
      setReports((prev) => [result.data, ...prev]);
      setExpandedReportId(result.data.id);
    } catch (err) {
      const message =
        err instanceof Error ? err.message : 'Failed to generate report';
      setReportError(message);
    } finally {
      setReportGenerating(false);
    }
  };

  const handleFileUploaded = (file: ClinicalNoteView) => {
    setFiles((prev) => [file, ...prev]);
  };

  /** id currently mid-delete. Drives per-row disabled + spinner, and
   *  prevents accidental double-clicks across any of the four lists. */
  const [deletingId, setDeletingId] = useState<string | null>(null);

  /** Shared delete handler. `onSuccess` is how each card tells us to
   *  update its local state (files/reports have state mirrors; notes
   *  and custom procedures come from props and rely on router.refresh). */
  const handleDeleteDocument = async (
    docId: string,
    opts: {
      kind: 'clinical note' | 'custom procedure' | 'final report' | 'attached file';
      onSuccess?: () => void;
    }
  ) => {
    if (deletingId) return;
    const confirmed = window.confirm(
      `Delete this ${opts.kind}? This action is logged to the audit trail and cannot be undone from the UI.`
    );
    if (!confirmed) return;
    setDeletingId(docId);
    try {
      const result = await deleteDocumentAction(docId, patient.id);
      if (!result.ok) {
        window.alert(`Delete failed: ${result.error}`);
        return;
      }
      if (opts.onSuccess) opts.onSuccess();
      // Pull fresh data for the lists that come from server props (notes,
      // customProcedures). Harmless for the state-backed lists — they've
      // already been updated optimistically.
      router.refresh();
    } catch (err) {
      const message = err instanceof Error ? err.message : 'Delete failed';
      window.alert(`Delete failed: ${message}`);
    } finally {
      setDeletingId(null);
    }
  };
  /** Centered Cmd+K-style assistant. Opened by the prominent header
   *  button or by the global Cmd/Ctrl+K shortcut. */
  const [aiOpen, setAiOpen] = useState(false);

  // Global Cmd+K (Ctrl+K on Windows/Linux) opens the assistant from
  // anywhere on the patient page — Spotlight-style muscle memory.
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === 'k') {
        e.preventDefault();
        setAiOpen((v) => !v);
      }
    };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, []);

  // Template dropdown
  const [templateMenuOpen, setTemplateMenuOpen] = useState(false);
  const [templatePending, startTemplateTransition] = useTransition();
  const templateMenuRef = useRef<HTMLDivElement>(null);

  // Manual note editing
  const [editingNoteId, setEditingNoteId] = useState<string | null>(null);
  const [editDraft, setEditDraft] = useState('');
  const [savePending, startSaveTransition] = useTransition();
  const [saveError, setSaveError] = useState<string | null>(null);

  // Close template menu on outside click
  useEffect(() => {
    if (!templateMenuOpen) return;
    const handler = (e: MouseEvent) => {
      if (templateMenuRef.current && !templateMenuRef.current.contains(e.target as Node)) {
        setTemplateMenuOpen(false);
      }
    };
    document.addEventListener('mousedown', handler);
    return () => document.removeEventListener('mousedown', handler);
  }, [templateMenuOpen]);

  const handleSelectTemplate = (templateId: string) => {
    setTemplateMenuOpen(false);
    startTemplateTransition(async () => {
      await createNoteFromTemplateAction(patient.id, templateId);
      router.refresh();
    });
  };

  const startManualEdit = (note: ClinicalNoteView) => {
    setEditingNoteId(note.id);
    setEditDraft(note.content);
    setSaveError(null);
  };

  const cancelManualEdit = () => {
    setEditingNoteId(null);
    setEditDraft('');
    setSaveError(null);
  };

  const handleSaveManualEdit = (noteId: string) => {
    setSaveError(null);
    startSaveTransition(async () => {
      const result = await updateNoteManuallyAction(noteId, patient.id, editDraft);
      if (result.ok) {
        setEditingNoteId(null);
        setEditDraft('');
        router.refresh();
      } else {
        setSaveError(result.error);
      }
    });
  };

  // Archive
  const [archivePending, startArchiveTransition] = useTransition();
  const [archiveError, setArchiveError] = useState<string | null>(null);

  const handleArchive = () => {
    const confirmed = window.confirm(
      `Archive ${patient.firstName} ${patient.lastName}? They will be hidden from active views but the record is retained for HIPAA retention.`
    );
    if (!confirmed) return;
    setArchiveError(null);
    startArchiveTransition(async () => {
      const result = await archivePatientAction(patient.id);
      if (result.ok) {
        router.push('/dashboard/patients');
      } else {
        setArchiveError(result.error || 'Failed to archive patient');
      }
    });
  };

  // File upload
  const fileInputRef = useRef<HTMLInputElement>(null);
  const [uploadPending, startUploadTransition] = useTransition();
  const [uploadError, setUploadError] = useState<string | null>(null);

  const handleFileUpload = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;
    setUploadError(null);

    startUploadTransition(async () => {
      const fd = new FormData();
      fd.append('file', file);
      const result = await uploadCustomProcedureAction(patient.id, fd);
      if (result.ok) {
        router.refresh();
      } else {
        setUploadError(result.error);
      }
      // Reset input so the same file can be re-selected
      if (fileInputRef.current) fileInputRef.current.value = '';
    });
  };

  return (
    <div className="relative min-h-screen overflow-hidden bg-[#0A192F]">
      {/* ====== AMBIENT GLOWS ====== */}
      <div className="absolute top-[5%] -left-[150px] w-[500px] h-[500px] rounded-full bg-blue-500 opacity-25 blur-[120px] pointer-events-none z-0" />
      <div className="absolute top-[15%] -right-[100px] w-[450px] h-[450px] rounded-full bg-teal-400 opacity-20 blur-[120px] pointer-events-none z-0" />
      <div className="absolute bottom-[10%] left-[20%] w-[600px] h-[600px] rounded-full bg-violet-600 opacity-15 blur-[140px] pointer-events-none z-0" />
      <div className="absolute bottom-[5%] right-[10%] w-[400px] h-[400px] rounded-full bg-cyan-400 opacity-15 blur-[100px] pointer-events-none z-0" />

      {/* ====== MAIN CONTENT ====== */}
      <div className="relative z-10 mx-auto max-w-7xl px-4 sm:px-6 lg:px-8 py-8">
        {/* Back button */}
        <motion.div initial={{ opacity: 0, x: -10 }} animate={{ opacity: 1, x: 0 }}>
          <Link
            href="/dashboard/patients"
            className="inline-flex items-center gap-2 text-sm text-slate-400 hover:text-white transition-colors mb-6 group"
          >
            <ArrowLeft className="w-4 h-4 group-hover:-translate-x-0.5 transition-transform" />
            Back to Patients
          </Link>
        </motion.div>

        {/* ====== HEADER CARD ====== */}
        <motion.div
          initial={{ opacity: 0, y: -10 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.05 }}
          className="rounded-2xl bg-white/5 backdrop-blur-md border border-white/10 p-6 mb-6 relative overflow-hidden"
        >
          {/* Gradient accent */}
          <div className="absolute top-0 left-0 right-0 h-px bg-gradient-to-r from-transparent via-blue-400/40 to-transparent" />

          <div className="flex flex-col lg:flex-row gap-6 items-start">
            {/* Avatar + name block */}
            <div className="flex items-center gap-4 flex-1 min-w-0">
              <div className="shrink-0 w-20 h-20 rounded-2xl flex items-center justify-center text-2xl font-bold bg-gradient-to-br from-blue-500/30 to-teal-500/30 border border-blue-500/40 text-white shadow-lg shadow-blue-500/20">
                {initials}
              </div>
              <div className="min-w-0">
                <div className="flex items-center gap-3 mb-1 flex-wrap">
                  <h1 className="text-2xl font-bold text-white truncate">
                    {patient.firstName} {patient.lastName}
                  </h1>
                  <span
                    className={`inline-flex items-center gap-1.5 px-2 py-0.5 rounded-full text-[10px] font-semibold uppercase tracking-wider border ${statusStyles[patient.status]}`}
                  >
                    <span className="w-1.5 h-1.5 rounded-full bg-current" />
                    {patient.status}
                  </span>
                  <button
                    onClick={() => setEditModalOpen(true)}
                    className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-lg text-[11px] font-medium text-slate-400 hover:text-white bg-white/5 border border-white/10 hover:bg-white/10 hover:border-white/20 transition-all cursor-pointer"
                  >
                    <Edit3 className="w-3 h-3" />
                    Edit Profile
                  </button>
                  {patient.status === 'ARCHIVED' ? (
                    <span
                      title="Restore UI not wired yet — promote status via Edit Profile or DB."
                      className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-lg text-[11px] font-medium text-slate-500 bg-slate-700/30 border border-slate-600/40 cursor-not-allowed"
                    >
                      <Archive className="w-3 h-3" />
                      Archived
                    </span>
                  ) : (
                    <button
                      onClick={handleArchive}
                      disabled={archivePending}
                      className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-lg text-[11px] font-medium text-amber-300 hover:text-amber-200 bg-amber-500/10 border border-amber-500/30 hover:bg-amber-500/20 hover:border-amber-500/50 transition-all cursor-pointer disabled:opacity-50 disabled:cursor-not-allowed"
                    >
                      {archivePending ? (
                        <Loader2 className="w-3 h-3 animate-spin" />
                      ) : (
                        <Archive className="w-3 h-3" />
                      )}
                      {archivePending ? 'Archiving…' : 'Archive Patient'}
                    </button>
                  )}
                </div>
                {archiveError && (
                  <div className="mt-2 inline-flex items-center gap-1.5 px-2.5 py-1 rounded-lg text-[11px] text-red-300 bg-red-500/10 border border-red-500/30">
                    <AlertCircle className="w-3 h-3" />
                    {archiveError}
                  </div>
                )}
                {/* Demographics row */}
                <div className="flex items-center gap-4 text-sm text-slate-400 flex-wrap">
                  <span className="flex items-center gap-1.5">
                    <Calendar className="w-3.5 h-3.5" />
                    Born {patient.birthYear} ({age} y.o.)
                  </span>
                  <span className="flex items-center gap-1.5">
                    <Stethoscope className="w-3.5 h-3.5" />
                    {patient.assignedDoctor}
                  </span>
                  {patient.email && (
                    <span className="flex items-center gap-1.5">
                      <Mail className="w-3.5 h-3.5" />
                      {patient.email}
                    </span>
                  )}
                  {patient.phoneLast4 && (
                    <span className="flex items-center gap-1.5">
                      <Phone className="w-3.5 h-3.5" />
                      ··· {patient.phoneLast4}
                    </span>
                  )}
                </div>
                {/* Tags */}
                {patient.tags.length > 0 && (
                  <div className="flex items-center gap-1.5 mt-3 flex-wrap">
                    <Tag className="w-3 h-3 text-slate-500" />
                    {patient.tags.map((tag) => (
                      <span
                        key={tag}
                        className="text-[10px] px-2 py-0.5 rounded-full bg-blue-500/10 border border-blue-500/20 text-blue-300"
                      >
                        {tag}
                      </span>
                    ))}
                  </div>
                )}
              </div>
            </div>

            {/* Right column: AI trigger + MRN badge.
                Minimal Linear/Raycast-style button — restrained for clinical
                context. Distinctive gradient icon tile on the left keeps it
                findable; rest of the button stays quiet. */}
            <div className="flex flex-col gap-2 shrink-0 min-w-[220px]">
              <button
                type="button"
                onClick={() => setAiOpen(true)}
                aria-label="Open AI Assistant"
                className="group inline-flex items-center gap-2.5 px-3 py-2.5 rounded-lg bg-slate-900/70 border border-slate-700/60 hover:border-violet-400/50 hover:bg-slate-900 transition-colors cursor-pointer"
              >
                <span className="flex h-6 w-6 shrink-0 items-center justify-center rounded-md bg-gradient-to-br from-violet-500 via-blue-500 to-teal-500 shadow-lg shadow-violet-500/40">
                  <AudioLines className="w-3.5 h-3.5 text-white" />
                </span>
                <span className="text-sm font-semibold text-slate-100 group-hover:text-white">
                  Ask AI
                </span>
                <kbd className="ml-auto px-1.5 py-0.5 rounded text-[10px] font-mono font-medium bg-slate-800 border border-slate-700 text-slate-400 group-hover:text-slate-200 transition-colors">
                  ⌘K
                </kbd>
              </button>
              <div className="flex items-center gap-2 px-3 py-2 rounded-lg bg-white/5 border border-white/10">
                <FileText className="w-4 h-4 text-slate-400" />
                <div>
                  <p className="text-[9px] uppercase tracking-wider text-slate-500 font-semibold">
                    MRN
                  </p>
                  <p className="text-xs font-mono text-slate-300">{patient.mrn}</p>
                </div>
              </div>
            </div>
          </div>
        </motion.div>

        {/* ====== TWO-COLUMN GRID ====== */}
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
          {/* === COLUMN 1: CLINICAL (2/3 width) === */}
          <motion.div
            initial={{ opacity: 0, y: 10 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.1 }}
            className="lg:col-span-2 space-y-6"
          >
            {/* Brief History card */}
            <div className="rounded-xl bg-white/5 backdrop-blur-md border border-white/10 p-5">
              <div className="flex items-center justify-between mb-4">
                <div className="flex items-center gap-2">
                  <div className="p-1.5 rounded-lg bg-orange-500/15 border border-orange-500/30">
                    <Activity className="w-4 h-4 text-orange-300" />
                  </div>
                  <h2 className="text-sm font-semibold text-white uppercase tracking-wider">
                    Brief History
                  </h2>
                </div>
                <button className="text-[11px] text-slate-400 hover:text-white flex items-center gap-1 transition-colors cursor-pointer">
                  <Edit3 className="w-3 h-3" />
                  Edit
                </button>
              </div>
              {patient.briefHistory.length > 0 ? (
                <ul className="space-y-2">
                  {patient.briefHistory.map((line, i) => (
                    <li key={i} className="flex items-start gap-2 text-sm text-slate-200">
                      <span className="text-orange-400 mt-1">•</span>
                      <span className="leading-relaxed">{line}</span>
                    </li>
                  ))}
                </ul>
              ) : (
                <p className="text-sm text-slate-500 italic">No clinical history recorded yet.</p>
              )}
            </div>

            {/* ====== CUSTOM PROCEDURES SECTION ====== */}
            <div className="rounded-xl bg-white/5 backdrop-blur-md border border-white/10 p-5">
              <div className="flex items-center justify-between mb-4">
                <div className="flex items-center gap-2">
                  <div className="p-1.5 rounded-lg bg-blue-500/15 border border-blue-500/30">
                    <UploadCloud className="w-4 h-4 text-blue-300" />
                  </div>
                  <h2 className="text-sm font-semibold text-white uppercase tracking-wider">
                    Custom Procedures
                  </h2>
                  <span className="text-[10px] px-1.5 py-0.5 rounded bg-white/5 text-slate-400 border border-white/10">
                    {customProcedures.length}
                  </span>
                </div>

                {/* Upload button */}
                <div className="flex items-center gap-2">
                  <input
                    ref={fileInputRef}
                    type="file"
                    accept=".pdf,.docx,application/pdf,application/vnd.openxmlformats-officedocument.wordprocessingml.document"
                    onChange={handleFileUpload}
                    className="hidden"
                  />
                  <button
                    type="button"
                    onClick={() => fileInputRef.current?.click()}
                    disabled={uploadPending}
                    className="inline-flex items-center gap-1.5 px-2.5 py-1.5 rounded-lg text-[11px] font-medium text-slate-300 bg-white/5 border border-white/10 hover:bg-white/10 hover:text-white transition-all cursor-pointer disabled:opacity-50"
                  >
                    {uploadPending ? (
                      <Loader2 className="w-3 h-3 animate-spin" />
                    ) : (
                      <UploadCloud className="w-3 h-3" />
                    )}
                    {uploadPending ? 'Extracting...' : 'Upload PDF / DOCX'}
                  </button>
                </div>
              </div>

              {/* Upload error banner */}
              {uploadError && (
                <div className="flex items-start gap-2 p-2.5 rounded-lg bg-red-500/10 border border-red-500/30 mb-4">
                  <AlertCircle className="w-3.5 h-3.5 text-red-400 shrink-0 mt-0.5" />
                  <p className="text-[11px] text-red-300 flex-1">{uploadError}</p>
                  <button type="button" onClick={() => setUploadError(null)} className="text-red-400 hover:text-red-300 cursor-pointer">
                    <X className="w-3 h-3" />
                  </button>
                </div>
              )}

              {customProcedures.length === 0 ? (
                <div className="py-8 text-center">
                  <div className="inline-flex items-center justify-center w-10 h-10 rounded-2xl bg-blue-500/10 border border-blue-500/20 mb-3">
                    <FileText className="w-5 h-5 text-blue-400/60" />
                  </div>
                  <p className="text-sm text-slate-400">No custom procedures</p>
                  <p className="text-xs text-slate-500 mt-1">
                    Upload a PDF or Word document to import a procedure.
                  </p>
                </div>
              ) : (
                <div className="space-y-2">
                  {customProcedures.map((proc) => {
                    const isExpanded = expandedNoteId === proc.id;
                    const preview = proc.content.split('\n').find((l) => l.trim())?.slice(0, 140) ?? '';
                    return (
                      <motion.div
                        key={proc.id}
                        layout
                        className="rounded-lg bg-slate-900/40 border border-white/5 hover:border-white/15 transition-all overflow-hidden"
                      >
                        <button
                          type="button"
                          onClick={() => setExpandedNoteId(isExpanded ? null : proc.id)}
                          className="w-full flex items-start gap-3 p-3 text-left cursor-pointer hover:bg-slate-900/60 transition-colors"
                        >
                          <div className="shrink-0 p-2 rounded-md bg-blue-500/10 border border-blue-500/20">
                            <FileText className="w-4 h-4 text-blue-300" />
                          </div>
                          <div className="flex-1 min-w-0">
                            <div className="flex items-center gap-2 mb-1 flex-wrap">
                              <p className="text-sm font-medium text-white truncate">
                                {proc.title}
                              </p>
                              <span className="text-[9px] px-1.5 py-0.5 rounded font-semibold uppercase tracking-wider border bg-blue-500/15 text-blue-300 border-blue-500/30">
                                Uploaded
                              </span>
                            </div>
                            {!isExpanded && (
                              <p className="text-xs text-slate-400 leading-relaxed line-clamp-2">
                                {preview}
                              </p>
                            )}
                            <div className="flex items-center gap-3 mt-1.5 text-[10px] text-slate-500">
                              <span className="flex items-center gap-1">
                                <Clock className="w-3 h-3" />
                                {formatRelativeDate(proc.createdAt)}
                              </span>
                            </div>
                          </div>
                          <ChevronDown
                            className={`w-4 h-4 text-slate-500 shrink-0 mt-1 transition-transform ${
                              isExpanded ? 'rotate-180' : ''
                            }`}
                          />
                        </button>

                        <AnimatePresence>
                          {isExpanded && (
                            <motion.div
                              initial={{ height: 0, opacity: 0 }}
                              animate={{ height: 'auto', opacity: 1 }}
                              exit={{ height: 0, opacity: 0 }}
                              transition={{ duration: 0.2 }}
                              className="overflow-hidden"
                            >
                              <div className="px-4 pb-4 pt-1 border-t border-white/5 mx-3">
                                {editingNoteId === proc.id ? (
                                  <div className="mt-3 space-y-3">
                                    <textarea
                                      value={editDraft}
                                      onChange={(e) => setEditDraft(e.target.value)}
                                      rows={16}
                                      disabled={savePending}
                                      className="w-full rounded-lg bg-slate-950/60 border border-blue-500/30 p-4 text-xs text-slate-200 leading-relaxed font-mono resize-y outline-none focus:border-blue-400/60 focus:ring-1 focus:ring-blue-400/20 transition-colors disabled:opacity-50"
                                    />
                                    {saveError && (
                                      <p className="text-[10px] text-red-400">{saveError}</p>
                                    )}
                                    <div className="flex items-center justify-end gap-2">
                                      <button
                                        type="button"
                                        onClick={cancelManualEdit}
                                        disabled={savePending}
                                        className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-medium text-slate-400 hover:text-white bg-white/5 border border-white/10 hover:bg-white/10 transition-all cursor-pointer disabled:opacity-50"
                                      >
                                        <X className="w-3 h-3" /> Cancel
                                      </button>
                                      <button
                                        type="button"
                                        onClick={() => handleSaveManualEdit(proc.id)}
                                        disabled={savePending}
                                        className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-semibold text-white bg-gradient-to-r from-blue-500 to-teal-500 shadow-md shadow-blue-500/25 hover:shadow-blue-500/40 transition-all cursor-pointer disabled:opacity-50"
                                      >
                                        {savePending ? (
                                          <><Loader2 className="w-3 h-3 animate-spin" /> Saving...</>
                                        ) : (
                                          <><Save className="w-3 h-3" /> Save Changes</>
                                        )}
                                      </button>
                                    </div>
                                  </div>
                                ) : (
                                  <>
                                    <pre className="mt-3 text-xs text-slate-200 leading-relaxed whitespace-pre-wrap font-sans bg-slate-950/60 rounded-lg p-4 border border-white/5">
                                      {proc.content}
                                    </pre>
                                    <div className="mt-2 flex items-center gap-2">
                                      <button
                                        type="button"
                                        onClick={() => startManualEdit(proc)}
                                        className="inline-flex items-center gap-1.5 px-2.5 py-1.5 rounded-lg text-[11px] font-medium text-slate-400 hover:text-white bg-white/5 border border-white/10 hover:bg-white/10 transition-all cursor-pointer"
                                      >
                                        <Pencil className="w-3 h-3" /> Edit Text
                                      </button>
                                      <button
                                        type="button"
                                        onClick={() =>
                                          handleDeleteDocument(proc.id, {
                                            kind: 'custom procedure',
                                          })
                                        }
                                        disabled={deletingId === proc.id}
                                        className="inline-flex items-center gap-1.5 px-2.5 py-1.5 rounded-lg text-[11px] font-medium text-red-300 hover:text-red-200 bg-red-500/10 border border-red-500/30 hover:bg-red-500/20 transition-all cursor-pointer disabled:opacity-50 disabled:cursor-not-allowed ml-auto"
                                      >
                                        {deletingId === proc.id ? (
                                          <Loader2 className="w-3 h-3 animate-spin" />
                                        ) : (
                                          <Trash2 className="w-3 h-3" />
                                        )}
                                        Delete
                                      </button>
                                    </div>
                                  </>
                                )}
                              </div>
                            </motion.div>
                          )}
                        </AnimatePresence>
                      </motion.div>
                    );
                  })}
                </div>
              )}
            </div>

            {/* Clinical Notes Feed (real, from DB) */}
            <div className="rounded-xl bg-white/5 backdrop-blur-md border border-white/10 p-5">
              <div className="flex items-center justify-between mb-4">
                <div className="flex items-center gap-2">
                  <div className="p-1.5 rounded-lg bg-violet-500/15 border border-violet-500/30">
                    <Sparkles className="w-4 h-4 text-violet-300" />
                  </div>
                  <h2 className="text-sm font-semibold text-white uppercase tracking-wider">
                    Clinical Notes
                  </h2>
                  <span className="text-[10px] px-1.5 py-0.5 rounded bg-white/5 text-slate-400 border border-white/10">
                    {notes.length}
                  </span>
                </div>

                <div className="flex items-center gap-2">
                  {/* Template Dropdown */}
                  <div className="relative" ref={templateMenuRef}>
                    <button
                      type="button"
                      onClick={() => setTemplateMenuOpen((v) => !v)}
                      disabled={templatePending}
                      className="inline-flex items-center gap-1.5 px-2.5 py-1.5 rounded-lg text-[11px] font-medium text-slate-300 bg-white/5 border border-white/10 hover:bg-white/10 hover:text-white transition-all cursor-pointer disabled:opacity-50"
                    >
                      {templatePending ? (
                        <Loader2 className="w-3 h-3 animate-spin" />
                      ) : (
                        <ClipboardList className="w-3 h-3" />
                      )}
                      {templatePending ? 'Creating...' : 'Load Template'}
                      <ChevronRight
                        className={`w-3 h-3 transition-transform ${templateMenuOpen ? 'rotate-90' : ''}`}
                      />
                    </button>

                    <AnimatePresence>
                      {templateMenuOpen && (
                        <motion.div
                          initial={{ opacity: 0, y: -4, scale: 0.95 }}
                          animate={{ opacity: 1, y: 0, scale: 1 }}
                          exit={{ opacity: 0, y: -4, scale: 0.95 }}
                          transition={{ duration: 0.15 }}
                          className="absolute right-0 top-full mt-1 z-50 w-72 rounded-xl bg-[#0d2137] border border-white/15 shadow-2xl shadow-black/50 overflow-hidden"
                        >
                          <div className="px-3 py-2 border-b border-white/10">
                            <p className="text-[10px] font-semibold text-slate-400 uppercase tracking-wider">
                              Select a template
                            </p>
                          </div>
                          <div className="py-1 max-h-64 overflow-y-auto">
                            {PROCEDURE_TEMPLATES.map((tpl) => (
                              <button
                                key={tpl.id}
                                type="button"
                                onClick={() => handleSelectTemplate(tpl.id)}
                                className="w-full flex items-start gap-3 px-3 py-2.5 text-left hover:bg-white/5 transition-colors cursor-pointer"
                              >
                                <div className="shrink-0 mt-0.5 p-1 rounded bg-violet-500/10 border border-violet-500/20">
                                  <FileText className="w-3 h-3 text-violet-300" />
                                </div>
                                <div className="min-w-0">
                                  <p className="text-xs font-medium text-white">
                                    {tpl.name}
                                  </p>
                                  <p className="text-[10px] text-slate-500 leading-snug mt-0.5">
                                    {tpl.description}
                                  </p>
                                </div>
                              </button>
                            ))}
                          </div>
                        </motion.div>
                      )}
                    </AnimatePresence>
                  </div>

                </div>
              </div>

              {notes.length === 0 ? (
                <div className="py-10 text-center">
                  <div className="inline-flex items-center justify-center w-12 h-12 rounded-2xl bg-violet-500/10 border border-violet-500/20 mb-3">
                    <FileText className="w-6 h-6 text-violet-400/60" />
                  </div>
                  <p className="text-sm text-slate-400">No notes yet</p>
                  <p className="text-xs text-slate-500 mt-1">
                    Use the dictation widget above to create your first AI-generated note.
                  </p>
                </div>
              ) : (
                <div className="space-y-2">
                  {notes.map((note) => {
                    const isExpanded = expandedNoteId === note.id;
                    const preview = note.content.split('\n').find((l) => l.trim())?.slice(0, 140) ?? '';
                    return (
                      <motion.div
                        key={note.id}
                        layout
                        className="rounded-lg bg-slate-900/40 border border-white/5 hover:border-white/15 transition-all overflow-hidden"
                      >
                        <button
                          type="button"
                          onClick={() => setExpandedNoteId(isExpanded ? null : note.id)}
                          className="w-full flex items-start gap-3 p-3 text-left cursor-pointer hover:bg-slate-900/60 transition-colors"
                        >
                          <div className="shrink-0 p-2 rounded-md bg-violet-500/10 border border-violet-500/20">
                            <FileText className="w-4 h-4 text-violet-300" />
                          </div>
                          <div className="flex-1 min-w-0">
                            <div className="flex items-center gap-2 mb-1 flex-wrap">
                              <p className="text-sm font-medium text-white truncate">
                                {note.title}
                              </p>
                              <span
                                className={`text-[9px] px-1.5 py-0.5 rounded font-semibold uppercase tracking-wider border ${noteStatusStyles[note.status]}`}
                              >
                                {note.status}
                              </span>
                            </div>
                            {!isExpanded && (
                              <p className="text-xs text-slate-400 leading-relaxed line-clamp-2">
                                {preview}
                              </p>
                            )}
                            <div className="flex items-center gap-3 mt-1.5 text-[10px] text-slate-500 flex-wrap">
                              <span className="flex items-center gap-1">
                                <Clock className="w-3 h-3" />
                                {formatRelativeDate(note.createdAt)}
                              </span>
                              {note.procedureType && (
                                <span className="flex items-center gap-1">
                                  <Stethoscope className="w-3 h-3" />
                                  {note.procedureType}
                                </span>
                              )}
                              {note.createdByName && (
                                <span className="flex items-center gap-1">
                                  <span className="text-slate-600">·</span>
                                  {note.createdByName}
                                </span>
                              )}
                            </div>
                          </div>
                          <ChevronDown
                            className={`w-4 h-4 text-slate-500 shrink-0 mt-1 transition-transform ${
                              isExpanded ? 'rotate-180' : ''
                            }`}
                          />
                        </button>

                        <AnimatePresence>
                          {isExpanded && (
                            <motion.div
                              initial={{ height: 0, opacity: 0 }}
                              animate={{ height: 'auto', opacity: 1 }}
                              exit={{ height: 0, opacity: 0 }}
                              transition={{ duration: 0.2 }}
                              className="overflow-hidden"
                            >
                              <div className="px-4 pb-4 pt-1 border-t border-white/5 mx-3">
                                {editingNoteId === note.id ? (
                                  /* ── Manual Edit Mode ── */
                                  <div className="mt-3 space-y-3">
                                    <textarea
                                      value={editDraft}
                                      onChange={(e) => setEditDraft(e.target.value)}
                                      rows={16}
                                      disabled={savePending}
                                      className="w-full rounded-lg bg-slate-950/60 border border-violet-500/30 p-4 text-xs text-slate-200 leading-relaxed font-mono resize-y outline-none focus:border-violet-400/60 focus:ring-1 focus:ring-violet-400/20 transition-colors disabled:opacity-50"
                                    />
                                    {saveError && (
                                      <p className="text-[10px] text-red-400">{saveError}</p>
                                    )}
                                    <div className="flex items-center justify-end gap-2">
                                      <button
                                        type="button"
                                        onClick={cancelManualEdit}
                                        disabled={savePending}
                                        className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-medium text-slate-400 hover:text-white bg-white/5 border border-white/10 hover:bg-white/10 transition-all cursor-pointer disabled:opacity-50"
                                      >
                                        <X className="w-3 h-3" />
                                        Cancel
                                      </button>
                                      <button
                                        type="button"
                                        onClick={() => handleSaveManualEdit(note.id)}
                                        disabled={savePending}
                                        className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-semibold text-white bg-gradient-to-r from-blue-500 to-teal-500 shadow-md shadow-blue-500/25 hover:shadow-blue-500/40 transition-all cursor-pointer disabled:opacity-50"
                                      >
                                        {savePending ? (
                                          <><Loader2 className="w-3 h-3 animate-spin" /> Saving...</>
                                        ) : (
                                          <><Save className="w-3 h-3" /> Save Changes</>
                                        )}
                                      </button>
                                    </div>
                                  </div>
                                ) : (
                                  /* ── View Mode ── */
                                  <>
                                    <pre className="mt-3 text-xs text-slate-200 leading-relaxed whitespace-pre-wrap font-sans bg-slate-950/60 rounded-lg p-4 border border-white/5">
                                      {note.content}
                                    </pre>
                                    {/* Action buttons row */}
                                    <div className="mt-2 flex items-center gap-2">
                                      <button
                                        type="button"
                                        onClick={() => startManualEdit(note)}
                                        className="inline-flex items-center gap-1.5 px-2.5 py-1.5 rounded-lg text-[11px] font-medium text-slate-400 hover:text-white bg-white/5 border border-white/10 hover:bg-white/10 transition-all cursor-pointer"
                                      >
                                        <Pencil className="w-3 h-3" />
                                        Edit Text
                                      </button>
                                      <button
                                        type="button"
                                        onClick={() =>
                                          handleDeleteDocument(note.id, {
                                            kind: 'clinical note',
                                          })
                                        }
                                        disabled={deletingId === note.id}
                                        className="inline-flex items-center gap-1.5 px-2.5 py-1.5 rounded-lg text-[11px] font-medium text-red-300 hover:text-red-200 bg-red-500/10 border border-red-500/30 hover:bg-red-500/20 transition-all cursor-pointer disabled:opacity-50 disabled:cursor-not-allowed ml-auto"
                                      >
                                        {deletingId === note.id ? (
                                          <Loader2 className="w-3 h-3 animate-spin" />
                                        ) : (
                                          <Trash2 className="w-3 h-3" />
                                        )}
                                        Delete
                                      </button>
                                    </div>
                                  </>
                                )}
                              </div>
                            </motion.div>
                          )}
                        </AnimatePresence>
                      </motion.div>
                    );
                  })}
                </div>
              )}
            </div>

            {/* ====== FINAL REPORTS SECTION ====== */}
            {/* Big deal for the doctors — sits directly under Clinical Notes
                so the eye lands on it after scanning the visit timeline.
                Generate button calls gpt-4o to synthesize brief history +
                notes + procedures into a structured report; Upload routes
                through the same file-attachment modal as Quick Actions. */}
            <div className="rounded-xl bg-white/5 backdrop-blur-md border border-white/10 p-5">
              <div className="flex items-center justify-between mb-4">
                <div className="flex items-center gap-2">
                  <div className="p-1.5 rounded-lg bg-rose-500/15 border border-rose-500/30">
                    <FileBadge className="w-4 h-4 text-rose-300" />
                  </div>
                  <h2 className="text-sm font-semibold text-white uppercase tracking-wider">
                    Final Reports
                  </h2>
                  <span className="text-[10px] px-1.5 py-0.5 rounded bg-white/5 text-slate-400 border border-white/10">
                    {reports.length}
                  </span>
                </div>

                <div className="flex items-center gap-2">
                  <button
                    type="button"
                    onClick={() => setFileUploadModalOpen(true)}
                    className="inline-flex items-center gap-1.5 px-2.5 py-1.5 rounded-lg text-[11px] font-medium text-slate-300 bg-white/5 border border-white/10 hover:bg-white/10 hover:text-white transition-all cursor-pointer"
                    title="Upload a report or reference file"
                  >
                    <UploadCloud className="w-3 h-3" />
                    Upload
                  </button>
                  <button
                    type="button"
                    onClick={handleGenerateFinalReport}
                    disabled={reportGenerating}
                    className="inline-flex items-center gap-1.5 px-2.5 py-1.5 rounded-lg text-[11px] font-semibold text-white bg-gradient-to-r from-rose-500 to-pink-500 shadow-md shadow-rose-500/25 hover:shadow-rose-500/40 hover:scale-[1.02] disabled:opacity-60 disabled:hover:scale-100 transition-all cursor-pointer disabled:cursor-not-allowed"
                  >
                    {reportGenerating ? (
                      <>
                        <Loader2 className="w-3 h-3 animate-spin" />
                        Generating…
                      </>
                    ) : (
                      <>
                        <Sparkles className="w-3 h-3" />
                        Generate via AI
                      </>
                    )}
                  </button>
                </div>
              </div>

              {reportError && (
                <div className="flex items-start gap-2 p-2.5 rounded-lg bg-red-500/10 border border-red-500/30 mb-4">
                  <AlertCircle className="w-3.5 h-3.5 text-red-400 shrink-0 mt-0.5" />
                  <p className="text-[11px] text-red-300 flex-1">{reportError}</p>
                  <button
                    type="button"
                    onClick={() => setReportError(null)}
                    className="text-red-400 hover:text-red-300 cursor-pointer"
                  >
                    <X className="w-3 h-3" />
                  </button>
                </div>
              )}

              {reports.length === 0 ? (
                <div className="py-10 text-center">
                  <div className="inline-flex items-center justify-center w-12 h-12 rounded-2xl bg-rose-500/10 border border-rose-500/20 mb-3">
                    <FileBadge className="w-6 h-6 text-rose-400/60" />
                  </div>
                  <p className="text-sm text-slate-400">No final reports yet.</p>
                  <p className="text-xs text-slate-500 mt-1">
                    Use &ldquo;Generate via AI&rdquo; to synthesize a
                    comprehensive case summary from this patient&apos;s history.
                  </p>
                </div>
              ) : (
                <div className="space-y-2">
                  {reports.map((report) => {
                    const isExpanded = expandedReportId === report.id;
                    const preview =
                      report.content.split('\n').find((l) => l.trim())?.slice(0, 140) ?? '';
                    return (
                      <motion.div
                        key={report.id}
                        layout
                        className="rounded-lg bg-slate-900/40 border border-white/5 hover:border-white/15 transition-all overflow-hidden"
                      >
                        <button
                          type="button"
                          onClick={() =>
                            setExpandedReportId(isExpanded ? null : report.id)
                          }
                          className="w-full flex items-start gap-3 p-3 text-left cursor-pointer hover:bg-slate-900/60 transition-colors"
                        >
                          <div className="shrink-0 p-2 rounded-md bg-rose-500/10 border border-rose-500/20">
                            <FileBadge className="w-4 h-4 text-rose-300" />
                          </div>
                          <div className="flex-1 min-w-0">
                            <div className="flex items-center gap-2 mb-1 flex-wrap">
                              <p className="text-sm font-medium text-white truncate">
                                {report.title}
                              </p>
                              <span
                                className={`text-[9px] px-1.5 py-0.5 rounded font-semibold uppercase tracking-wider border ${noteStatusStyles[report.status]}`}
                              >
                                {report.status}
                              </span>
                            </div>
                            {!isExpanded && (
                              <p className="text-xs text-slate-400 leading-relaxed line-clamp-2">
                                {preview}
                              </p>
                            )}
                            <div className="flex items-center gap-3 mt-1.5 text-[10px] text-slate-500 flex-wrap">
                              <span className="flex items-center gap-1">
                                <Clock className="w-3 h-3" />
                                {formatRelativeDate(report.createdAt)}
                              </span>
                              {report.createdByName && (
                                <span className="flex items-center gap-1">
                                  <span className="text-slate-600">·</span>
                                  {report.createdByName}
                                </span>
                              )}
                            </div>
                          </div>
                          <ChevronDown
                            className={`w-4 h-4 text-slate-500 shrink-0 mt-1 transition-transform ${
                              isExpanded ? 'rotate-180' : ''
                            }`}
                          />
                        </button>

                        <AnimatePresence>
                          {isExpanded && (
                            <motion.div
                              initial={{ height: 0, opacity: 0 }}
                              animate={{ height: 'auto', opacity: 1 }}
                              exit={{ height: 0, opacity: 0 }}
                              transition={{ duration: 0.2 }}
                              className="overflow-hidden"
                            >
                              <div className="px-4 pb-4 pt-1 border-t border-white/5 mx-3">
                                <pre className="mt-3 text-xs text-slate-200 leading-relaxed whitespace-pre-wrap font-sans bg-slate-950/60 rounded-lg p-4 border border-white/5">
                                  {report.content}
                                </pre>
                                <div className="mt-2 flex items-center gap-2 justify-end">
                                  <button
                                    type="button"
                                    onClick={() =>
                                      handleDeleteDocument(report.id, {
                                        kind: 'final report',
                                        onSuccess: () =>
                                          setReports((prev) =>
                                            prev.filter((r) => r.id !== report.id)
                                          ),
                                      })
                                    }
                                    disabled={deletingId === report.id}
                                    className="inline-flex items-center gap-1.5 px-2.5 py-1.5 rounded-lg text-[11px] font-medium text-red-300 hover:text-red-200 bg-red-500/10 border border-red-500/30 hover:bg-red-500/20 transition-all cursor-pointer disabled:opacity-50 disabled:cursor-not-allowed"
                                  >
                                    {deletingId === report.id ? (
                                      <Loader2 className="w-3 h-3 animate-spin" />
                                    ) : (
                                      <Trash2 className="w-3 h-3" />
                                    )}
                                    Delete
                                  </button>
                                </div>
                              </div>
                            </motion.div>
                          )}
                        </AnimatePresence>
                      </motion.div>
                    );
                  })}
                </div>
              )}
            </div>

            {/* ====== ATTACHED DOCUMENTS SECTION ====== */}
            {/* Shows file metadata the doctor has uploaded to this chart.
                Entries here are pointers — clicking doesn't download yet;
                that lands when real file storage is wired. */}
            <div className="rounded-xl bg-white/5 backdrop-blur-md border border-white/10 p-5">
              <div className="flex items-center justify-between mb-4">
                <div className="flex items-center gap-2">
                  <div className="p-1.5 rounded-lg bg-amber-500/15 border border-amber-500/30">
                    <Paperclip className="w-4 h-4 text-amber-300" />
                  </div>
                  <h2 className="text-sm font-semibold text-white uppercase tracking-wider">
                    Attached Documents
                  </h2>
                  <span className="text-[10px] px-1.5 py-0.5 rounded bg-white/5 text-slate-400 border border-white/10">
                    {files.length}
                  </span>
                </div>

                <button
                  type="button"
                  onClick={() => setFileUploadModalOpen(true)}
                  className="inline-flex items-center gap-1.5 px-2.5 py-1.5 rounded-lg text-[11px] font-medium text-slate-300 bg-white/5 border border-white/10 hover:bg-white/10 hover:text-white transition-all cursor-pointer"
                >
                  <UploadCloud className="w-3 h-3" />
                  Attach
                </button>
              </div>

              {files.length === 0 ? (
                <div className="py-8 text-center">
                  <div className="inline-flex items-center justify-center w-10 h-10 rounded-2xl bg-amber-500/10 border border-amber-500/20 mb-3">
                    <Paperclip className="w-5 h-5 text-amber-400/60" />
                  </div>
                  <p className="text-sm text-slate-400">No attachments yet</p>
                  <p className="text-xs text-slate-500 mt-1">
                    Attach imaging, lab results, or reference PDFs.
                  </p>
                </div>
              ) : (
                <ul className="space-y-2">
                  {files.map((file) => (
                    <li
                      key={file.id}
                      className="flex items-center gap-3 p-3 rounded-lg bg-slate-900/40 border border-white/5 hover:border-white/15 transition-colors"
                    >
                      <div className="shrink-0 p-2 rounded-md bg-amber-500/10 border border-amber-500/20">
                        <FileText className="w-4 h-4 text-amber-300" />
                      </div>
                      <div className="min-w-0 flex-1">
                        <p className="text-sm font-medium text-white truncate">
                          {file.fileName ?? file.title}
                        </p>
                        <div className="flex items-center gap-3 mt-0.5 text-[10px] text-slate-500 flex-wrap">
                          <span>{formatBytes(file.sizeBytes)}</span>
                          {file.mimeType && (
                            <>
                              <span className="text-slate-600">·</span>
                              <span className="font-mono">{file.mimeType}</span>
                            </>
                          )}
                          <span className="text-slate-600">·</span>
                          <span className="flex items-center gap-1">
                            <Clock className="w-3 h-3" />
                            {formatRelativeDate(file.createdAt)}
                          </span>
                          {file.createdByName && (
                            <>
                              <span className="text-slate-600">·</span>
                              <span>{file.createdByName}</span>
                            </>
                          )}
                        </div>
                      </div>
                      <button
                        type="button"
                        onClick={() =>
                          handleDeleteDocument(file.id, {
                            kind: 'attached file',
                            onSuccess: () =>
                              setFiles((prev) => prev.filter((f) => f.id !== file.id)),
                          })
                        }
                        disabled={deletingId === file.id}
                        className="shrink-0 inline-flex items-center gap-1 px-2 py-1 rounded text-[11px] font-medium text-red-300 hover:text-red-200 bg-red-500/10 border border-red-500/30 hover:bg-red-500/20 transition-all cursor-pointer disabled:opacity-50 disabled:cursor-not-allowed"
                        aria-label="Delete attached file"
                      >
                        {deletingId === file.id ? (
                          <Loader2 className="w-3 h-3 animate-spin" />
                        ) : (
                          <Trash2 className="w-3 h-3" />
                        )}
                      </button>
                    </li>
                  ))}
                </ul>
              )}
            </div>
          </motion.div>

          {/* === COLUMN 2: FILES & ACTIONS (1/3 width) === */}
          <motion.div
            initial={{ opacity: 0, y: 10 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.15 }}
            className="space-y-6"
          >
            {/* Quick Actions */}
            <div className="rounded-xl bg-gradient-to-br from-blue-500/10 to-teal-500/10 backdrop-blur-md border border-blue-500/20 p-5">
              <h2 className="text-sm font-semibold text-white uppercase tracking-wider mb-3">
                Quick Actions
              </h2>
              <div className="space-y-2">
                <button
                  onClick={() => setDocGenModalOpen(true)}
                  className="w-full flex items-center gap-3 px-3 py-2.5 rounded-lg bg-gradient-to-r from-blue-500 to-teal-500 text-white text-sm font-semibold shadow-lg shadow-blue-500/25 hover:shadow-blue-500/40 hover:scale-[1.02] transition-all group cursor-pointer"
                >
                  <Sparkles className="w-4 h-4" />
                  Generate Document
                  <span className="ml-auto opacity-60 group-hover:translate-x-0.5 transition-transform">
                    →
                  </span>
                </button>
                <button
                  onClick={() => setEditModalOpen(true)}
                  className="w-full flex items-center gap-3 px-3 py-2.5 rounded-lg bg-white/5 border border-white/10 text-slate-200 text-sm hover:bg-white/10 hover:border-white/20 transition-all cursor-pointer"
                >
                  <FileEdit className="w-4 h-4 text-blue-300" />
                  Edit Patient Record
                </button>
                <button
                  onClick={() => setScheduleModalOpen(true)}
                  className="w-full flex items-center gap-3 px-3 py-2.5 rounded-lg bg-white/5 border border-white/10 text-slate-200 text-sm hover:bg-white/10 hover:border-white/20 transition-all cursor-pointer"
                >
                  <Calendar className="w-4 h-4 text-emerald-300" />
                  Schedule Visit
                </button>
                <button
                  onClick={() => setFileUploadModalOpen(true)}
                  className="w-full flex items-center gap-3 px-3 py-2.5 rounded-lg bg-white/5 border border-white/10 text-slate-200 text-sm hover:bg-white/10 hover:border-white/20 transition-all cursor-pointer"
                >
                  <Paperclip className="w-4 h-4 text-amber-300" />
                  Attach File
                </button>
              </div>
            </div>

            {/* Last visit / created info */}
            <div className="rounded-xl bg-white/5 backdrop-blur-md border border-white/10 p-5">
              <h2 className="text-sm font-semibold text-white uppercase tracking-wider mb-3">
                Visit Info
              </h2>
              <div className="space-y-3 text-sm">
                <div>
                  <p className="text-[10px] uppercase tracking-wider text-slate-500 font-semibold mb-0.5">
                    Last Visit
                  </p>
                  <p className="text-white">{formatLastVisit(patient.lastVisit)}</p>
                  <p className="text-xs text-slate-400">{formatRelativeDate(patient.lastVisit)}</p>
                </div>
                <div className="border-t border-white/5 pt-3">
                  <p className="text-[10px] uppercase tracking-wider text-slate-500 font-semibold mb-0.5">
                    Patient Since
                  </p>
                  <p className="text-white">{formatLastVisit(patient.createdAt)}</p>
                </div>
              </div>
            </div>
          </motion.div>
        </div>
      </div>

      {/* Edit Patient Modal */}
      <EditPatientModal
        open={editModalOpen}
        onClose={() => setEditModalOpen(false)}
        patient={patient}
      />

      {/* Document Generator Modal */}
      <DocumentGeneratorModal
        open={docGenModalOpen}
        onClose={() => setDocGenModalOpen(false)}
        patientId={patient.id}
        patientName={`${patient.firstName} ${patient.lastName}`}
      />

      {/* Schedule Visit Modal */}
      <ScheduleVisitModal
        open={scheduleModalOpen}
        onClose={() => setScheduleModalOpen(false)}
        patientId={patient.id}
        patientName={`${patient.firstName} ${patient.lastName}`}
      />

      {/* Attach File Modal. onUploaded prepends the returned row to the
          Attached Documents list so the doctor sees it immediately. */}
      <PatientFileUploadModal
        open={fileUploadModalOpen}
        onClose={() => setFileUploadModalOpen(false)}
        patientId={patient.id}
        patientName={`${patient.firstName} ${patient.lastName}`}
        onUploaded={handleFileUploaded}
      />

      {/* Centered Spotlight-style AI assistant — opened by header button
          or global Cmd/Ctrl+K. Full patient context as props. */}
      <GlobalAIAssistant
        open={aiOpen}
        onClose={() => setAiOpen(false)}
        patientId={patient.id}
        patientName={`${patient.firstName} ${patient.lastName}`}
        patientStatus={patient.status}
        noteCount={notes.length}
        procedureCount={customProcedures.length}
      />
    </div>
  );
}
