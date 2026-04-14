'use client';

// ============================================================================
// Edit Patient Modal — Glassmorphism
// ----------------------------------------------------------------------------
// Pre-populated form that calls `updatePatientAction`.
// - Name, MRN, Birth Year, Phone, Email, Tags, Status
// - DrChrono ID is read-only (source of truth — can't change here)
// - Status dropdown: ACTIVE / INACTIVE / ARCHIVED
// - Loading + error + success states
// - ESC to close, backdrop click to close
// ============================================================================

import { useState, useEffect, useTransition } from 'react';
import { useRouter } from 'next/navigation';
import { motion, AnimatePresence } from 'framer-motion';
import { X, Loader2, AlertCircle, CheckCircle2, UserCog } from 'lucide-react';

import { updatePatientAction } from '@/app/dashboard/patients/actions';
import type { PatientView } from '@/lib/data/patients';

interface EditPatientModalProps {
  open: boolean;
  onClose: () => void;
  patient: PatientView;
}

interface FormState {
  firstName: string;
  lastName: string;
  mrn: string;
  birthYear: string;
  email: string;
  phoneLast4: string;
  tags: string;
  status: 'ACTIVE' | 'INACTIVE' | 'ARCHIVED';
}

function patientToForm(p: PatientView): FormState {
  return {
    firstName: p.firstName,
    lastName: p.lastName,
    mrn: p.mrn ?? '',
    birthYear: p.birthYear ? String(p.birthYear) : '',
    email: p.email ?? '',
    phoneLast4: p.phoneLast4 ?? '',
    tags: p.tags.join(', '),
    status: p.status,
  };
}

// Outer wrapper: AnimatePresence owns open/close. Inner content holds form
// state so each open mounts fresh — no reset useEffect needed.
export default function EditPatientModal({
  open,
  onClose,
  patient,
}: EditPatientModalProps) {
  return (
    <AnimatePresence>
      {open && <EditPatientModalContent onClose={onClose} patient={patient} />}
    </AnimatePresence>
  );
}

function EditPatientModalContent({
  onClose,
  patient,
}: {
  onClose: () => void;
  patient: EditPatientModalProps['patient'];
}) {
  const router = useRouter();
  const [isPending, startTransition] = useTransition();
  const [form, setForm] = useState<FormState>(() => patientToForm(patient));
  const [error, setError] = useState<string | null>(null);
  const [fieldErrors, setFieldErrors] = useState<Record<string, string[]>>({});
  const [success, setSuccess] = useState(false);

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

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    setFieldErrors({});

    const payload = {
      firstName: form.firstName.trim(),
      lastName: form.lastName.trim(),
      mrn: form.mrn.trim() || null,
      birthYear: form.birthYear ? parseInt(form.birthYear, 10) : null,
      email: form.email.trim() || null,
      phoneLast4: form.phoneLast4.trim() || null,
      tags: form.tags
        .split(',')
        .map((t) => t.trim())
        .filter(Boolean),
      status: form.status,
    };

    startTransition(async () => {
      const result = await updatePatientAction(patient.id, payload);

      if (!result.ok) {
        setError(result.error);
        if (result.fieldErrors) {
          setFieldErrors(result.fieldErrors);
        }
        return;
      }

      setSuccess(true);
      router.refresh();
      setTimeout(() => onClose(), 1000);
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
            aria-labelledby="edit-patient-title"
            className="fixed inset-0 z-[101] flex items-center justify-center p-4 pointer-events-none"
          >
            <div className="pointer-events-auto w-full max-w-lg rounded-2xl bg-[#0A192F] border border-white/10 shadow-2xl shadow-black/50 overflow-hidden">
              {/* Header */}
              <div className="relative px-6 py-4 border-b border-white/10 bg-gradient-to-r from-blue-500/10 to-teal-500/10">
                <div className="flex items-center gap-3">
                  <div className="p-2 rounded-lg bg-blue-500/20 border border-blue-500/30">
                    <UserCog className="w-5 h-5 text-blue-300" />
                  </div>
                  <div>
                    <h2
                      id="edit-patient-title"
                      className="text-lg font-bold text-white"
                    >
                      Edit Patient
                    </h2>
                    <p className="text-xs text-slate-400">
                      {patient.firstName} {patient.lastName} ·{' '}
                      <span className="font-mono">{patient.drChronoId}</span>
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

              {/* Form */}
              <form
                onSubmit={handleSubmit}
                className="px-6 py-5 space-y-4 max-h-[70vh] overflow-y-auto"
              >
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
                      Patient updated successfully!
                    </p>
                  </div>
                )}

                {/* Name row */}
                <div className="grid grid-cols-2 gap-3">
                  <Field label="First Name *" error={fieldErrors.firstName?.[0]}>
                    <input
                      type="text"
                      value={form.firstName}
                      onChange={(e) => update('firstName', e.target.value)}
                      required
                      disabled={isPending}
                      className="input-styled"
                    />
                  </Field>
                  <Field label="Last Name *" error={fieldErrors.lastName?.[0]}>
                    <input
                      type="text"
                      value={form.lastName}
                      onChange={(e) => update('lastName', e.target.value)}
                      required
                      disabled={isPending}
                      className="input-styled"
                    />
                  </Field>
                </div>

                {/* DrChrono ID (read-only) + MRN */}
                <div className="grid grid-cols-2 gap-3">
                  <Field
                    label="DrChrono ID"
                    hint="Read-only — source of truth"
                  >
                    <input
                      type="text"
                      value={patient.drChronoId}
                      readOnly
                      className="input-styled font-mono opacity-50 cursor-not-allowed"
                    />
                  </Field>
                  <Field label="MRN" error={fieldErrors.mrn?.[0]}>
                    <input
                      type="text"
                      value={form.mrn}
                      onChange={(e) => update('mrn', e.target.value)}
                      disabled={isPending}
                      className="input-styled font-mono"
                    />
                  </Field>
                </div>

                {/* Birth year + phone */}
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
                      min="1900"
                      max={new Date().getFullYear()}
                      className="input-styled"
                    />
                  </Field>
                  <Field
                    label="Phone (last 4)"
                    error={fieldErrors.phoneLast4?.[0]}
                    hint="Only last 4 digits"
                  >
                    <input
                      type="text"
                      value={form.phoneLast4}
                      onChange={(e) =>
                        update(
                          'phoneLast4',
                          e.target.value.replace(/\D/g, '').slice(0, 4)
                        )
                      }
                      disabled={isPending}
                      maxLength={4}
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
                    className="input-styled"
                  />
                </Field>

                {/* Tags */}
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

                {/* Status */}
                <Field
                  label="Patient Status"
                  hint="Changes take effect immediately after save"
                >
                  <select
                    value={form.status}
                    onChange={(e) =>
                      update(
                        'status',
                        e.target.value as FormState['status']
                      )
                    }
                    disabled={isPending}
                    className="input-styled appearance-none cursor-pointer"
                  >
                    <option value="ACTIVE">Active</option>
                    <option value="INACTIVE">Inactive</option>
                    <option value="ARCHIVED">Archived</option>
                  </select>
                </Field>

                {/* HIPAA notice */}
                <div className="text-[10px] text-slate-500 italic border-t border-white/5 pt-3">
                  <strong className="text-slate-400">HIPAA notice:</strong>{' '}
                  This update will be logged with your user ID, IP address,
                  changed field names, and timestamp in the immutable audit
                  trail.
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
                        Saving...
                      </>
                    ) : success ? (
                      <>
                        <CheckCircle2 className="w-4 h-4" />
                        Saved!
                      </>
                    ) : (
                      <>
                        <UserCog className="w-4 h-4" />
                        Save Changes
                      </>
                    )}
                  </button>
                </div>
              </form>
            </div>
          </motion.div>

          {/* Shared input styles — same as AddPatientModal */}
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
// Field wrapper — same as AddPatientModal for visual consistency
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
