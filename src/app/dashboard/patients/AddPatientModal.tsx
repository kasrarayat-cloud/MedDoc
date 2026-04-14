'use client';

import { useState, useEffect, useTransition } from 'react';
import { useRouter } from 'next/navigation';
import { motion, AnimatePresence } from 'framer-motion';
import { X, Loader2, AlertCircle, CheckCircle2, UserPlus } from 'lucide-react';
import { createPatientAction, getNextChartIdAction } from './actions';

interface AddPatientModalProps {
  open: boolean;
  onClose: () => void;
}

interface FormState {
  firstName: string;
  lastName: string;
  mrn: string;
  chartId: string;
  birthYear: string;
  email: string;
  phoneLast4: string;
  cellPhone: string;
  homePhone: string;
  insuranceVerified: boolean;
  tags: string;
}

const initialState: FormState = {
  firstName: '',
  lastName: '',
  mrn: '',
  chartId: '',
  birthYear: '',
  email: '',
  phoneLast4: '',
  cellPhone: '',
  homePhone: '',
  insuranceVerified: false,
  tags: '',
};

// Outer wrapper: AnimatePresence owns the open/close toggle. Form state
// lives in the inner Content component so each open mounts a fresh tree
// (state initialized via useState defaults — no reset effect needed,
// satisfies React 19's set-state-in-effect rule).
export default function AddPatientModal({ open, onClose }: AddPatientModalProps) {
  return (
    <AnimatePresence>
      {open && <AddPatientModalContent onClose={onClose} />}
    </AnimatePresence>
  );
}

function AddPatientModalContent({ onClose }: { onClose: () => void }) {
  const router = useRouter();
  const [isPending, startTransition] = useTransition();
  const [form, setForm] = useState<FormState>(initialState);
  const [error, setError] = useState<string | null>(null);
  const [fieldErrors, setFieldErrors] = useState<Record<string, string[]>>({});
  const [success, setSuccess] = useState(false);
  /** The next auto-generated chart ID for this practice, shown as a
   *  placeholder hint. Empty while loading or on error — we degrade to
   *  the static sample placeholder. If the user leaves the field blank
   *  at submit, the server regenerates (source of truth) so this value
   *  is advisory only. */
  const [suggestedChartId, setSuggestedChartId] = useState('');

  // Fetch the next chart ID for the placeholder on mount. Non-blocking —
  // if it fails the modal still works; server will auto-generate.
  useEffect(() => {
    let cancelled = false;
    getNextChartIdAction()
      .then((r) => {
        if (!cancelled && r.ok) setSuggestedChartId(r.data.chartId);
      })
      .catch(() => { /* swallow; not critical */ });
    return () => { cancelled = true; };
  }, []);

  // Close on ESC
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape') onClose();
    };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, [onClose]);

  const update = <K extends keyof FormState>(key: K, value: FormState[K]) => {
    setForm((prev) => ({ ...prev, [key]: value }));
    if (fieldErrors[key]) {
      const next = { ...fieldErrors };
      delete next[key];
      setFieldErrors(next);
    }
  };

  // Cell phone changes also auto-derive `phoneLast4` from the last 4 digits
  // (stripping spaces/dashes/parens). Fully clearing the cell phone leaves
  // the existing phoneLast4 alone — supports the "no cell, manual last-4
  // entry" case the field was originally designed for.
  const handleCellPhoneChange = (value: string) => {
    const digits = value.replace(/\D/g, '');
    const derivedLast4 = digits.slice(-4);
    setForm((prev) => ({
      ...prev,
      cellPhone: value,
      phoneLast4: derivedLast4 || prev.phoneLast4,
    }));
    if (fieldErrors.cellPhone || fieldErrors.phoneLast4) {
      setFieldErrors((prev) => {
        const next = { ...prev };
        delete next.cellPhone;
        delete next.phoneLast4;
        return next;
      });
    }
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    setFieldErrors({});

    // Build payload — convert empty strings to null so the server sees a
    // clean shape. `insuranceVerified` stays as the boolean checkbox state;
    // we send false explicitly (it's meaningful: "unverified on file")
    // rather than dropping it when unchecked.
    const payload = {
      firstName: form.firstName.trim(),
      lastName: form.lastName.trim(),
      mrn: form.mrn.trim() || null,
      chartId: form.chartId.trim() || null,
      birthYear: form.birthYear ? parseInt(form.birthYear, 10) : null,
      email: form.email.trim() || null,
      phoneLast4: form.phoneLast4.trim() || null,
      cellPhone: form.cellPhone.trim() || null,
      homePhone: form.homePhone.trim() || null,
      insuranceVerified: form.insuranceVerified,
      tags: form.tags
        .split(',')
        .map((t) => t.trim())
        .filter(Boolean),
    };

    startTransition(async () => {
      const result = await createPatientAction(payload);

      if (!result.ok) {
        setError(result.error);
        if (result.fieldErrors) {
          setFieldErrors(result.fieldErrors);
        }
        return;
      }

      // Success
      setSuccess(true);
      router.refresh();

      // Close after a brief success animation
      setTimeout(() => {
        onClose();
      }, 1000);
    });
  };

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

      {/* Modal panel */}
          <motion.div
            initial={{ opacity: 0, scale: 0.95, y: 20 }}
            animate={{ opacity: 1, scale: 1, y: 0 }}
            exit={{ opacity: 0, scale: 0.95, y: 20 }}
            transition={{ type: 'spring', stiffness: 300, damping: 30 }}
            role="dialog"
            aria-modal="true"
            aria-labelledby="add-patient-title"
            className="fixed inset-0 z-[101] flex items-center justify-center p-4 pointer-events-none"
          >
            <div className="pointer-events-auto w-full max-w-2xl rounded-2xl bg-[#0A192F] border border-white/10 shadow-2xl shadow-black/50 overflow-hidden">
              {/* Header */}
              <div className="relative px-6 py-4 border-b border-white/10 bg-gradient-to-r from-blue-500/10 to-teal-500/10">
                <div className="flex items-center gap-3">
                  <div className="p-2 rounded-lg bg-blue-500/20 border border-blue-500/30">
                    <UserPlus className="w-5 h-5 text-blue-300" />
                  </div>
                  <div>
                    <h2 id="add-patient-title" className="text-lg font-bold text-white">
                      Add New Patient
                    </h2>
                    <p className="text-xs text-slate-400">
                      Create a new patient record in the CRM
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

              {/* Body / Form */}
              <form onSubmit={handleSubmit} className="px-6 py-5 space-y-4 max-h-[70vh] overflow-y-auto">
                {/* Error banner */}
                {error && !success && (
                  <div className="flex items-start gap-2 p-3 rounded-lg bg-red-500/10 border border-red-500/30">
                    <AlertCircle className="w-4 h-4 text-red-400 shrink-0 mt-0.5" />
                    <p className="text-xs text-red-300">{error}</p>
                  </div>
                )}

                {/* Success banner */}
                {success && (
                  <div className="flex items-start gap-2 p-3 rounded-lg bg-emerald-500/10 border border-emerald-500/30">
                    <CheckCircle2 className="w-4 h-4 text-emerald-400 shrink-0 mt-0.5" />
                    <p className="text-xs text-emerald-300">
                      Patient created successfully!
                    </p>
                  </div>
                )}

                {/* Name row */}
                <div className="grid grid-cols-2 gap-3">
                  <Field
                    label="First Name *"
                    error={fieldErrors.firstName?.[0]}
                  >
                    <input
                      type="text"
                      value={form.firstName}
                      onChange={(e) => update('firstName', e.target.value)}
                      required
                      disabled={isPending}
                      placeholder="Sarah"
                      className="input-styled"
                    />
                  </Field>
                  <Field
                    label="Last Name *"
                    error={fieldErrors.lastName?.[0]}
                  >
                    <input
                      type="text"
                      value={form.lastName}
                      onChange={(e) => update('lastName', e.target.value)}
                      required
                      disabled={isPending}
                      placeholder="Mitchell"
                      className="input-styled"
                    />
                  </Field>
                </div>

                {/* IDs row — Chart ID + MRN, evenly spanned. */}
                <div className="grid grid-cols-2 gap-3">
                  <Field
                    label="Chart ID"
                    error={fieldErrors.chartId?.[0]}
                    hint={suggestedChartId ? `Leave blank to auto-assign ${suggestedChartId}` : 'Leave blank to auto-assign'}
                  >
                    <input
                      type="text"
                      value={form.chartId}
                      onChange={(e) => update('chartId', e.target.value)}
                      disabled={isPending}
                      placeholder={suggestedChartId || 'C-1001'}
                      className="input-styled font-mono"
                    />
                  </Field>
                  <Field label="MRN" error={fieldErrors.mrn?.[0]} hint="For filings">
                    <input
                      type="text"
                      value={form.mrn}
                      onChange={(e) => update('mrn', e.target.value)}
                      disabled={isPending}
                      placeholder="MRN-440182"
                      className="input-styled font-mono"
                    />
                  </Field>
                </div>

                {/* Birth year + phone (last 4) row */}
                <div className="grid grid-cols-2 gap-3">
                  <Field
                    label="Birth Year"
                    error={fieldErrors.birthYear?.[0]}
                    hint="Year only (HIPAA Safe Harbor)"
                  >
                    <input
                      type="number"
                      value={form.birthYear}
                      onChange={(e) => update('birthYear', e.target.value)}
                      disabled={isPending}
                      placeholder="1978"
                      min="1900"
                      max={new Date().getFullYear()}
                      className="input-styled"
                    />
                  </Field>
                  <Field
                    label="Phone (last 4)"
                    error={fieldErrors.phoneLast4?.[0]}
                    hint="Minimal-PHI fallback"
                  >
                    <input
                      type="text"
                      value={form.phoneLast4}
                      onChange={(e) =>
                        update('phoneLast4', e.target.value.replace(/\D/g, '').slice(0, 4))
                      }
                      disabled={isPending}
                      placeholder="4421"
                      maxLength={4}
                      className="input-styled font-mono"
                    />
                  </Field>
                </div>

                {/* Cell + home phone — two columns */}
                <div className="grid grid-cols-2 gap-3">
                  <Field
                    label="Cell Phone"
                    error={fieldErrors.cellPhone?.[0]}
                    hint="Auto-fills last-4 below"
                  >
                    <input
                      type="tel"
                      value={form.cellPhone}
                      onChange={(e) => handleCellPhoneChange(e.target.value)}
                      disabled={isPending}
                      placeholder="(555) 123-4421"
                      maxLength={32}
                      className="input-styled font-mono"
                    />
                  </Field>
                  <Field label="Home Phone" error={fieldErrors.homePhone?.[0]}>
                    <input
                      type="tel"
                      value={form.homePhone}
                      onChange={(e) => update('homePhone', e.target.value)}
                      disabled={isPending}
                      placeholder="(555) 123-0000"
                      maxLength={32}
                      className="input-styled font-mono"
                    />
                  </Field>
                </div>

                {/* Email */}
                <Field label="Email" error={fieldErrors.email?.[0]}>
                  <input
                    type="email"
                    value={form.email}
                    onChange={(e) => update('email', e.target.value)}
                    disabled={isPending}
                    placeholder="patient@example.com"
                    className="input-styled"
                  />
                </Field>

                {/* Insurance + Tags — single compact row.
                    Ghost label spacer above the checkbox matches the Tags
                    Field's top label height so the checkbox box sits on
                    the same horizontal line as the Tags input. */}
                <div className="grid grid-cols-[auto_1fr] gap-3 items-start">
                  <div className="flex flex-col">
                    <span
                      aria-hidden="true"
                      className="block text-[11px] font-semibold uppercase tracking-wider mb-1 invisible select-none"
                    >
                      .
                    </span>
                    <label className="flex items-center gap-2 p-2.5 rounded-lg bg-white/5 border border-white/10 cursor-pointer hover:bg-white/10 transition-colors">
                      <input
                        type="checkbox"
                        checked={form.insuranceVerified}
                        onChange={(e) => update('insuranceVerified', e.target.checked)}
                        disabled={isPending}
                        className="w-4 h-4 accent-emerald-500 cursor-pointer"
                      />
                      <span className="text-[11px] font-semibold text-slate-300 whitespace-nowrap">
                        Insurance verified
                      </span>
                    </label>
                  </div>
                  <Field label="Tags" hint="Comma-separated">
                    <input
                      type="text"
                      value={form.tags}
                      onChange={(e) => update('tags', e.target.value)}
                      disabled={isPending}
                      placeholder="post-op, chronic-pain"
                      className="input-styled"
                    />
                  </Field>
                </div>

                {/* HIPAA notice */}
                <div className="text-[10px] text-slate-500 italic border-t border-white/5 pt-3">
                  <strong className="text-slate-400">HIPAA notice:</strong> This action will be
                  logged with your user ID, IP address, and timestamp in the audit trail.
                </div>

                {/* Footer buttons */}
                <div className="flex items-center justify-end gap-2 pt-2">
                  <button
                    type="button"
                    onClick={onClose}
                    disabled={isPending}
                    className="px-4 py-2 rounded-lg text-sm font-medium text-slate-300 hover:text-white hover:bg-white/5 transition-colors disabled:opacity-50"
                  >
                    Cancel
                  </button>
                  <button
                    type="submit"
                    disabled={isPending || success}
                    className="inline-flex items-center gap-2 px-4 py-2 rounded-lg bg-gradient-to-r from-blue-500 to-teal-500 text-white text-sm font-semibold shadow-lg shadow-blue-500/25 hover:shadow-blue-500/40 disabled:opacity-50 disabled:cursor-not-allowed transition-all"
                  >
                    {isPending ? (
                      <>
                        <Loader2 className="w-4 h-4 animate-spin" />
                        Creating...
                      </>
                    ) : success ? (
                      <>
                        <CheckCircle2 className="w-4 h-4" />
                        Created!
                      </>
                    ) : (
                      <>
                        <UserPlus className="w-4 h-4" />
                        Create Patient
                      </>
                    )}
                  </button>
                </div>
              </form>
            </div>
          </motion.div>

          {/* Inline styles helper for input fields (consistency) */}
          <style jsx>{`
            :global(.input-styled) {
              width: 100%;
              padding: 0.5rem 0.75rem;
              border-radius: 0.5rem;
              background-color: rgba(15, 23, 42, 0.6);
              border: 1px solid rgba(255, 255, 255, 0.08);
              color: white;
              font-size: 0.875rem;
              outline: none;
              transition: border-color 0.2s;
            }
            :global(.input-styled::placeholder) {
              color: rgb(100, 116, 139);
            }
            :global(.input-styled:focus) {
              border-color: rgba(59, 130, 246, 0.5);
            }
            :global(.input-styled:disabled) {
              opacity: 0.5;
              cursor: not-allowed;
            }
          `}</style>
    </>
  );
}

// ----------------------------------------------------------------------------
// Field wrapper — label + hint + optional error
// ----------------------------------------------------------------------------
function Field({
  label,
  hint,
  error,
  children,
}: {
  label: string;
  hint?: string;
  error?: string;
  children: React.ReactNode;
}) {
  return (
    <div>
      <label className="block text-[11px] font-semibold text-slate-300 uppercase tracking-wider mb-1">
        {label}
      </label>
      {children}
      {error ? (
        <p className="text-[10px] text-red-400 mt-1">{error}</p>
      ) : hint ? (
        <p className="text-[10px] text-slate-500 mt-1">{hint}</p>
      ) : null}
    </div>
  );
}
