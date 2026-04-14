'use client';

// ============================================================================
// Document Generator Modal — 3-step flow
// ----------------------------------------------------------------------------
// Step 1: Select document type (Referral Letter, Patient Instructions, etc.)
// Step 2: Loading / generating via GPT-4o-mini
// Step 3: Review & edit generated text, copy or download
// ============================================================================

import { useState, useEffect, useCallback, useRef, useTransition } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import {
  X,
  Loader2,
  FileText,
  Copy,
  Download,
  Check,
  AlertCircle,
  ArrowLeft,
  Send,
  ClipboardCheck,
  ScrollText,
  ShieldCheck,
  Sparkles,
} from 'lucide-react';

import {
  generateDocumentAction,
  type DocumentType,
  type GeneratedDocument,
} from '@/app/dashboard/patients/actions';

interface DocumentGeneratorModalProps {
  open: boolean;
  onClose: () => void;
  patientId: string;
  patientName: string;
}

type Step = 'select' | 'generating' | 'review';

const DOC_TYPES: {
  type: DocumentType;
  label: string;
  description: string;
  icon: typeof FileText;
  color: string;
}[] = [
  {
    type: 'REFERRAL_LETTER',
    label: 'Referral Letter',
    description: 'Formal letter to a specialist with clinical summary',
    icon: Send,
    color: 'from-blue-500/20 to-blue-600/10 border-blue-500/30 hover:border-blue-400/50',
  },
  {
    type: 'PATIENT_HANDOUT',
    label: 'Patient Instructions',
    description: 'Plain-language post-visit instructions for the patient',
    icon: ClipboardCheck,
    color: 'from-emerald-500/20 to-emerald-600/10 border-emerald-500/30 hover:border-emerald-400/50',
  },
  {
    type: 'DISABILITY_FORM',
    label: 'Disability Statement',
    description: 'Functional limitations statement for disability claims',
    icon: ScrollText,
    color: 'from-amber-500/20 to-amber-600/10 border-amber-500/30 hover:border-amber-400/50',
  },
  {
    type: 'PRIOR_AUTH',
    label: 'Prior Authorization',
    description: 'Medical necessity letter for insurance approval',
    icon: ShieldCheck,
    color: 'from-violet-500/20 to-violet-600/10 border-violet-500/30 hover:border-violet-400/50',
  },
];

// Outer wrapper: AnimatePresence owns open/close. Inner content holds
// state so each open mounts fresh — no reset useEffect needed.
export default function DocumentGeneratorModal({
  open,
  onClose,
  patientId,
  patientName,
}: DocumentGeneratorModalProps) {
  return (
    <AnimatePresence>
      {open && (
        <DocumentGeneratorModalContent
          onClose={onClose}
          patientId={patientId}
          patientName={patientName}
        />
      )}
    </AnimatePresence>
  );
}

function DocumentGeneratorModalContent({
  onClose,
  patientId,
  patientName,
}: {
  onClose: () => void;
  patientId: string;
  patientName: string;
}) {
  const [step, setStep] = useState<Step>('select');
  const [isPending, startTransition] = useTransition();
  const [error, setError] = useState<string | null>(null);
  const [result, setResult] = useState<GeneratedDocument | null>(null);
  const [editedContent, setEditedContent] = useState('');
  const [copied, setCopied] = useState(false);
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  // ESC to close
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape') onClose();
    };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, [onClose]);

  const handleSelectType = useCallback(
    (docType: DocumentType) => {
      setError(null);
      setStep('generating');

      startTransition(async () => {
        const res = await generateDocumentAction(patientId, docType);

        if (!res.ok) {
          setError(res.error);
          setStep('select');
          return;
        }

        setResult(res.data);
        setEditedContent(res.data.content);
        setStep('review');
      });
    },
    [patientId]
  );

  const handleCopy = useCallback(async () => {
    try {
      await navigator.clipboard.writeText(editedContent);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    } catch {
      // Fallback
      textareaRef.current?.select();
      document.execCommand('copy');
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    }
  }, [editedContent]);

  const handleDownload = useCallback(() => {
    const blob = new Blob([editedContent], { type: 'text/plain;charset=utf-8' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    const safeName = patientName.replace(/[^a-zA-Z0-9]/g, '_');
    const typeLabel = result?.title?.replace(/\s+/g, '_') ?? 'Document';
    a.href = url;
    a.download = `${typeLabel}_${safeName}_${new Date().toISOString().split('T')[0]}.txt`;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
  }, [editedContent, patientName, result]);

  return (
    <>
      {/* Backdrop */}
      <motion.div
        initial={{ opacity: 0 }}
        animate={{ opacity: 1 }}
        exit={{ opacity: 0 }}
        onClick={onClose}
        className="fixed inset-0 z-[100] bg-black/70 backdrop-blur-sm"
      />

      {/* Modal */}
          <motion.div
            initial={{ opacity: 0, scale: 0.95, y: 20 }}
            animate={{ opacity: 1, scale: 1, y: 0 }}
            exit={{ opacity: 0, scale: 0.95, y: 20 }}
            transition={{ type: 'spring', stiffness: 300, damping: 30 }}
            role="dialog"
            aria-modal="true"
            aria-labelledby="docgen-title"
            className="fixed inset-0 z-[101] flex items-center justify-center p-4 pointer-events-none"
          >
            <div
              className={`pointer-events-auto w-full rounded-2xl bg-[#0A192F] border border-white/10 shadow-2xl shadow-black/50 overflow-hidden transition-all duration-300 ${
                step === 'review' ? 'max-w-2xl' : 'max-w-lg'
              }`}
            >
              {/* Header */}
              <div className="relative px-6 py-4 border-b border-white/10 bg-gradient-to-r from-violet-500/10 to-blue-500/10">
                <div className="flex items-center gap-3">
                  <div className="p-2 rounded-lg bg-violet-500/20 border border-violet-500/30">
                    <Sparkles className="w-5 h-5 text-violet-300" />
                  </div>
                  <div>
                    <h2 id="docgen-title" className="text-lg font-bold text-white">
                      {step === 'review' && result
                        ? result.title
                        : 'Generate Document'}
                    </h2>
                    <p className="text-xs text-slate-400">
                      {step === 'select' && `AI-powered document drafting for ${patientName}`}
                      {step === 'generating' && 'Analyzing clinical notes...'}
                      {step === 'review' &&
                        `Based on ${result?.sourceNoteCount ?? 0} clinical note${
                          (result?.sourceNoteCount ?? 0) !== 1 ? 's' : ''
                        }`}
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
              <div className="px-6 py-5 max-h-[75vh] overflow-y-auto">
                <AnimatePresence mode="wait">
                  {/* ── STEP 1: Select Document Type ── */}
                  {step === 'select' && (
                    <motion.div
                      key="select"
                      initial={{ opacity: 0, y: 10 }}
                      animate={{ opacity: 1, y: 0 }}
                      exit={{ opacity: 0, y: -10 }}
                      className="space-y-3"
                    >
                      {error && (
                        <div className="flex items-start gap-2 p-3 rounded-lg bg-red-500/10 border border-red-500/30 mb-4">
                          <AlertCircle className="w-4 h-4 text-red-400 shrink-0 mt-0.5" />
                          <p className="text-xs text-red-300">{error}</p>
                        </div>
                      )}

                      <p className="text-xs text-slate-400 mb-4">
                        Select a document type. AI will draft it from this patient&apos;s recent clinical notes.
                      </p>

                      {DOC_TYPES.map((doc) => {
                        const Icon = doc.icon;
                        return (
                          <button
                            key={doc.type}
                            type="button"
                            onClick={() => handleSelectType(doc.type)}
                            disabled={isPending}
                            className={`w-full flex items-center gap-4 p-4 rounded-xl bg-gradient-to-r ${doc.color} border backdrop-blur-sm transition-all hover:scale-[1.01] disabled:opacity-50 disabled:cursor-not-allowed cursor-pointer text-left`}
                          >
                            <div className="shrink-0 p-2.5 rounded-lg bg-white/5">
                              <Icon className="w-5 h-5 text-white" />
                            </div>
                            <div>
                              <p className="text-sm font-semibold text-white">
                                {doc.label}
                              </p>
                              <p className="text-xs text-slate-400 mt-0.5">
                                {doc.description}
                              </p>
                            </div>
                          </button>
                        );
                      })}
                    </motion.div>
                  )}

                  {/* ── STEP 2: Generating ── */}
                  {step === 'generating' && (
                    <motion.div
                      key="generating"
                      initial={{ opacity: 0, y: 10 }}
                      animate={{ opacity: 1, y: 0 }}
                      exit={{ opacity: 0, y: -10 }}
                      className="py-16 flex flex-col items-center gap-4 text-center"
                    >
                      <div className="relative">
                        <div className="absolute inset-0 rounded-full bg-violet-500/30 blur-xl animate-pulse" />
                        <div className="relative p-4 rounded-full bg-gradient-to-br from-violet-500 to-blue-500 shadow-lg shadow-violet-500/40">
                          <Loader2 className="w-8 h-8 text-white animate-spin" />
                        </div>
                      </div>
                      <div>
                        <p className="text-sm font-semibold text-white">
                          Generating document...
                        </p>
                        <p className="text-xs text-slate-400 mt-1">
                          Analyzing clinical notes with GPT-4o-mini
                        </p>
                      </div>
                    </motion.div>
                  )}

                  {/* ── STEP 3: Review & Edit ── */}
                  {step === 'review' && result && (
                    <motion.div
                      key="review"
                      initial={{ opacity: 0, y: 10 }}
                      animate={{ opacity: 1, y: 0 }}
                      exit={{ opacity: 0, y: -10 }}
                      className="space-y-4"
                    >
                      {/* Action bar */}
                      <div className="flex items-center gap-2 flex-wrap">
                        <button
                          type="button"
                          onClick={() => {
                            setStep('select');
                            setResult(null);
                            setError(null);
                          }}
                          className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-medium text-slate-400 hover:text-white bg-white/5 border border-white/10 hover:bg-white/10 transition-all cursor-pointer"
                        >
                          <ArrowLeft className="w-3 h-3" />
                          Back
                        </button>
                        <div className="flex-1" />
                        <button
                          type="button"
                          onClick={handleCopy}
                          className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-medium text-white bg-white/10 border border-white/10 hover:bg-white/15 transition-all cursor-pointer"
                        >
                          {copied ? (
                            <>
                              <Check className="w-3 h-3 text-emerald-400" />
                              Copied!
                            </>
                          ) : (
                            <>
                              <Copy className="w-3 h-3" />
                              Copy
                            </>
                          )}
                        </button>
                        <button
                          type="button"
                          onClick={handleDownload}
                          className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-semibold text-white bg-gradient-to-r from-blue-500 to-teal-500 shadow-md shadow-blue-500/25 hover:shadow-blue-500/40 transition-all cursor-pointer"
                        >
                          <Download className="w-3 h-3" />
                          Download .txt
                        </button>
                      </div>

                      {/* Editable textarea */}
                      <textarea
                        ref={textareaRef}
                        value={editedContent}
                        onChange={(e) => setEditedContent(e.target.value)}
                        rows={20}
                        spellCheck
                        className="w-full rounded-xl bg-slate-950/60 border border-white/10 p-4 text-sm text-slate-200 leading-relaxed font-mono resize-y outline-none focus:border-blue-400/50 focus:ring-1 focus:ring-blue-400/20 transition-colors"
                      />

                      <p className="text-[10px] text-slate-500 italic">
                        Review and edit as needed. Nothing is saved until you copy or download. All
                        generation events are HIPAA-logged.
                      </p>
                    </motion.div>
                  )}
                </AnimatePresence>
              </div>
            </div>
      </motion.div>
    </>
  );
}
