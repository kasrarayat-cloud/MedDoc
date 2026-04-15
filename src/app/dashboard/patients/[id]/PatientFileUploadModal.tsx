'use client';

// ============================================================================
// PatientFileUploadModal — visual shell only (no backend yet)
// ----------------------------------------------------------------------------
// Drag-and-drop zone for PDFs, DOCXs, and images. Kept intentionally
// dumb: file state + local preview + a disabled "Upload" button. When
// the backend wire-up lands, swap the placeholder handler for a real
// POST — everything else is already in place.
//
// Matches EditPatientModal / ScheduleVisitModal chrome so the three
// feel cohesive when opened from Quick Actions.
// ============================================================================

import { useCallback, useEffect, useRef, useState } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import {
  X,
  UploadCloud,
  FileText,
  Image as ImageIcon,
  FileArchive,
  CheckCircle2,
  AlertCircle,
  Paperclip,
  Loader2,
} from 'lucide-react';
import { uploadPatientFileAction } from '@/app/dashboard/patients/actions';
import type { ClinicalNoteView } from '@/lib/data/clinical-notes';

interface PatientFileUploadModalProps {
  open: boolean;
  onClose: () => void;
  patientId: string;
  patientName: string;
  /** Which chart card the upload should land under. The Final Reports
   *  card passes 'FINAL_REPORT' so uploaded PDFs surface alongside the
   *  AI-generated reports instead of in Attached Documents. */
  uploadAs?: 'PATIENT_FILE' | 'FINAL_REPORT';
  /** Called with the server-persisted row after a successful upload so the
   *  parent can optimistically prepend it to its list. */
  onUploaded?: (file: ClinicalNoteView) => void;
}

// 25 MB — same cap Whisper uses elsewhere so the limit feels consistent
// across the app even though this modal doesn't call Whisper.
const MAX_SIZE_BYTES = 25 * 1024 * 1024;

const ACCEPTED_EXTENSIONS = ['.pdf', '.docx', '.png', '.jpg', '.jpeg', '.webp'];
const ACCEPT_ATTR = [
  'application/pdf',
  'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
  'image/png',
  'image/jpeg',
  'image/webp',
].join(',');

function extensionOf(name: string): string {
  const i = name.lastIndexOf('.');
  return i >= 0 ? name.slice(i).toLowerCase() : '';
}

function isAccepted(file: File): boolean {
  return ACCEPTED_EXTENSIONS.includes(extensionOf(file.name));
}

function humanBytes(n: number): string {
  if (n < 1024) return `${n} B`;
  if (n < 1024 * 1024) return `${(n / 1024).toFixed(1)} KB`;
  return `${(n / 1024 / 1024).toFixed(1)} MB`;
}

function iconForFile(file: File) {
  const ext = extensionOf(file.name);
  if (ext === '.pdf') return <FileText className="w-5 h-5 text-red-300" />;
  if (ext === '.docx') return <FileText className="w-5 h-5 text-blue-300" />;
  if (['.png', '.jpg', '.jpeg', '.webp'].includes(ext)) {
    return <ImageIcon className="w-5 h-5 text-emerald-300" />;
  }
  return <FileArchive className="w-5 h-5 text-slate-300" />;
}

export default function PatientFileUploadModal({
  open,
  onClose,
  patientId,
  patientName,
  uploadAs,
  onUploaded,
}: PatientFileUploadModalProps) {
  return (
    <AnimatePresence>
      {open && (
        <ModalContent
          onClose={onClose}
          patientId={patientId}
          patientName={patientName}
          uploadAs={uploadAs}
          onUploaded={onUploaded}
        />
      )}
    </AnimatePresence>
  );
}

function ModalContent({
  onClose,
  patientId,
  patientName,
  uploadAs,
  onUploaded,
}: {
  onClose: () => void;
  patientId: string;
  patientName: string;
  uploadAs?: 'PATIENT_FILE' | 'FINAL_REPORT';
  onUploaded?: (file: ClinicalNoteView) => void;
}) {
  const [file, setFile] = useState<File | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [isDragging, setIsDragging] = useState(false);
  const [isUploading, setIsUploading] = useState(false);
  const [success, setSuccess] = useState(false);
  const inputRef = useRef<HTMLInputElement | null>(null);

  // Track nested drag events so leaving an inner child doesn't flip the
  // highlight off. enter/leave fire on every child transition — the
  // depth counter only flips state at the true boundary.
  const dragDepthRef = useRef(0);

  // Close on ESC.
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape') onClose();
    };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, [onClose]);

  const acceptFile = useCallback((candidate: File | null | undefined) => {
    if (!candidate) return;
    if (!isAccepted(candidate)) {
      setError(`Unsupported file type "${extensionOf(candidate.name)}". Allowed: ${ACCEPTED_EXTENSIONS.join(', ')}.`);
      setFile(null);
      return;
    }
    if (candidate.size > MAX_SIZE_BYTES) {
      setError(`File is too large (${humanBytes(candidate.size)}). Limit is 25 MB.`);
      setFile(null);
      return;
    }
    setError(null);
    setFile(candidate);
  }, []);

  const handleDragEnter = (e: React.DragEvent<HTMLDivElement>) => {
    e.preventDefault();
    e.stopPropagation();
    dragDepthRef.current += 1;
    setIsDragging(true);
  };

  const handleDragLeave = (e: React.DragEvent<HTMLDivElement>) => {
    e.preventDefault();
    e.stopPropagation();
    dragDepthRef.current = Math.max(0, dragDepthRef.current - 1);
    if (dragDepthRef.current === 0) setIsDragging(false);
  };

  const handleDragOver = (e: React.DragEvent<HTMLDivElement>) => {
    e.preventDefault();
    e.stopPropagation();
  };

  const handleDrop = (e: React.DragEvent<HTMLDivElement>) => {
    e.preventDefault();
    e.stopPropagation();
    dragDepthRef.current = 0;
    setIsDragging(false);
    const dropped = e.dataTransfer.files?.[0];
    acceptFile(dropped ?? null);
  };

  const handleBrowse = () => {
    inputRef.current?.click();
  };

  const handleInputChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    acceptFile(e.target.files?.[0] ?? null);
    // Reset so the same file can be re-selected after removal.
    if (inputRef.current) inputRef.current.value = '';
  };

  const handleRemove = () => {
    setFile(null);
    setError(null);
  };

  const handleUpload = async () => {
    if (!file || isUploading) return;
    setIsUploading(true);
    setError(null);
    try {
      // Send the real file bytes via FormData so the server can extract
      // text from PDF/DOCX. Image types persist as metadata only for now
      // (OCR / real storage is a separate build).
      const formData = new FormData();
      formData.append('file', file);
      if (uploadAs) formData.append('category', uploadAs);
      const result = await uploadPatientFileAction(patientId, formData);
      if (!result.ok) {
        setError(result.error);
        return;
      }
      setSuccess(true);
      onUploaded?.(result.data);
      setTimeout(() => {
        onClose();
      }, 800);
    } catch (err) {
      const message = err instanceof Error ? err.message : 'Upload failed';
      setError(message);
    } finally {
      setIsUploading(false);
    }
  };

  return (
    <>
      <motion.div
        initial={{ opacity: 0 }}
        animate={{ opacity: 1 }}
        exit={{ opacity: 0 }}
        onClick={onClose}
        className="fixed inset-0 z-[100] bg-black/70 backdrop-blur-sm"
      />

      <motion.div
        initial={{ opacity: 0, scale: 0.95, y: 20 }}
        animate={{ opacity: 1, scale: 1, y: 0 }}
        exit={{ opacity: 0, scale: 0.95, y: 20 }}
        transition={{ type: 'spring', stiffness: 300, damping: 30 }}
        role="dialog"
        aria-modal="true"
        aria-labelledby="patient-file-upload-title"
        className="fixed inset-0 z-[101] flex items-center justify-center p-4 pointer-events-none"
      >
        <div className="pointer-events-auto w-full max-w-lg rounded-2xl bg-[#0A192F] border border-white/10 shadow-2xl shadow-black/50 overflow-hidden">
          {/* Header */}
          <div className="relative px-6 py-4 border-b border-white/10 bg-gradient-to-r from-blue-500/10 to-teal-500/10">
            <div className="flex items-center gap-3">
              <div className="p-2 rounded-lg bg-blue-500/20 border border-blue-500/30">
                <Paperclip className="w-5 h-5 text-blue-300" />
              </div>
              <div className="min-w-0">
                <h2
                  id="patient-file-upload-title"
                  className="text-lg font-bold text-white"
                >
                  {uploadAs === 'FINAL_REPORT' ? 'Upload Final Report' : 'Upload Document'}
                </h2>
                <p className="text-xs text-slate-400 truncate">
                  {uploadAs === 'FINAL_REPORT'
                    ? `Attach a final report to ${patientName}'s chart`
                    : `Attach a file to ${patientName}'s chart`}
                </p>
              </div>
            </div>
            <button
              onClick={onClose}
              className="absolute top-3 right-3 p-2 rounded-lg text-slate-400 hover:text-white hover:bg-white/5 transition-colors"
              aria-label="Close"
            >
              <X className="w-4 h-4" />
            </button>
          </div>

          {/* Body */}
          <div className="px-6 py-5 space-y-4">
            {error && (
              <div className="flex items-start gap-2 p-3 rounded-lg bg-red-500/10 border border-red-500/30">
                <AlertCircle className="w-4 h-4 text-red-400 shrink-0 mt-0.5" />
                <p className="text-xs text-red-300">{error}</p>
              </div>
            )}

            {success && (
              <div className="flex items-start gap-2 p-3 rounded-lg bg-emerald-500/10 border border-emerald-500/30">
                <CheckCircle2 className="w-4 h-4 text-emerald-400 shrink-0 mt-0.5" />
                <p className="text-xs text-emerald-300">
                  File attached to {patientName}&apos;s chart.
                </p>
              </div>
            )}

            {/* Drop zone. Reacts to drag state with border + bg tint. */}
            <div
              onDragEnter={handleDragEnter}
              onDragLeave={handleDragLeave}
              onDragOver={handleDragOver}
              onDrop={handleDrop}
              onClick={handleBrowse}
              role="button"
              tabIndex={0}
              onKeyDown={(e) => {
                if (e.key === 'Enter' || e.key === ' ') {
                  e.preventDefault();
                  handleBrowse();
                }
              }}
              className={`relative flex flex-col items-center justify-center gap-3 py-10 px-6 rounded-xl border-2 border-dashed transition-all cursor-pointer ${
                isDragging
                  ? 'border-blue-400/80 bg-blue-500/10'
                  : 'border-white/10 bg-white/[0.03] hover:border-white/20 hover:bg-white/5'
              }`}
            >
              <div
                className={`p-3 rounded-full transition-colors ${
                  isDragging
                    ? 'bg-blue-500/20 border border-blue-500/40'
                    : 'bg-white/5 border border-white/10'
                }`}
              >
                <UploadCloud
                  className={`w-6 h-6 ${
                    isDragging ? 'text-blue-200' : 'text-slate-300'
                  }`}
                />
              </div>
              <div className="text-center">
                <p className="text-sm font-medium text-white">
                  {isDragging
                    ? 'Release to attach'
                    : 'Drag and drop a file here'}
                </p>
                <p className="text-xs text-slate-400 mt-1">
                  or <span className="text-blue-300 underline">browse</span> from
                  your computer
                </p>
                <p className="text-[10px] text-slate-500 mt-2">
                  PDF, DOCX, PNG, JPG, WEBP · up to 25 MB
                </p>
              </div>
              <input
                ref={inputRef}
                type="file"
                accept={ACCEPT_ATTR}
                onChange={handleInputChange}
                className="hidden"
              />
            </div>

            {/* Selected file preview. Minimal row with icon + name + size. */}
            {file && (
              <motion.div
                initial={{ opacity: 0, y: 4 }}
                animate={{ opacity: 1, y: 0 }}
                className="flex items-center gap-3 p-3 rounded-lg bg-slate-900/40 border border-white/10"
              >
                <div className="shrink-0 p-2 rounded-md bg-white/5 border border-white/10">
                  {iconForFile(file)}
                </div>
                <div className="min-w-0 flex-1">
                  <p className="text-sm font-medium text-white truncate">
                    {file.name}
                  </p>
                  <p className="text-[11px] text-slate-400">
                    {humanBytes(file.size)} · ready to upload
                  </p>
                </div>
                <button
                  type="button"
                  onClick={handleRemove}
                  className="p-1.5 rounded text-slate-400 hover:text-white hover:bg-white/10 transition-colors"
                  aria-label="Remove file"
                >
                  <X className="w-3.5 h-3.5" />
                </button>
              </motion.div>
            )}

            <p className="text-[10px] text-slate-500 italic border-t border-white/5 pt-3">
              <strong className="text-slate-400">HIPAA notice:</strong> Uploads are
              logged with your user ID, IP address, and timestamp in the audit
              trail once wired.
            </p>

            {/* Footer */}
            <div className="flex items-center justify-end gap-2">
              <button
                type="button"
                onClick={onClose}
                className="px-4 py-2 rounded-lg text-sm font-medium text-slate-300 hover:text-white hover:bg-white/5 transition-colors"
              >
                Cancel
              </button>
              <button
                type="button"
                onClick={handleUpload}
                disabled={!file || !!error || isUploading || success}
                className="inline-flex items-center gap-2 px-4 py-2 rounded-lg bg-gradient-to-r from-blue-500 to-teal-500 text-white text-sm font-semibold shadow-lg shadow-blue-500/25 hover:shadow-blue-500/40 disabled:opacity-50 disabled:cursor-not-allowed transition-all"
              >
                {isUploading ? (
                  <>
                    <Loader2 className="w-4 h-4 animate-spin" />
                    Uploading…
                  </>
                ) : success ? (
                  <>
                    <CheckCircle2 className="w-4 h-4" />
                    Attached
                  </>
                ) : (
                  <>
                    <CheckCircle2 className="w-4 h-4" />
                    Upload
                  </>
                )}
              </button>
            </div>
          </div>
        </div>
      </motion.div>
    </>
  );
}
