'use client';

// ============================================================================
// Edit Patient Modal — Glassmorphism
// ----------------------------------------------------------------------------
// Pre-populated form that calls `updatePatientAction`. Mirrors
// AddPatientModal field-for-field so anything captured at intake can be
// corrected later.
// ============================================================================

import { useState, useEffect, useTransition, useCallback } from 'react';
import { useRouter } from 'next/navigation';
import { motion, AnimatePresence } from 'framer-motion';
import { X, Loader2, AlertCircle, CheckCircle2, UserCog } from 'lucide-react';

import {
  updatePatientAction,
  listPracticeDoctorsAction,
  type DoctorOption,
} from '@/app/dashboard/patients/actions';
import type { PatientView } from '@/lib/data/patients';
import {
  patientViewToProfile,
  profileToPayload,
  type PatientProfileFormState,
  type PatientSex,
} from '@/app/dashboard/patients/patient-form-shared';
import InsuranceStatusToggle from '@/app/dashboard/patients/InsuranceStatusToggle';

interface EditPatientModalProps {
  open: boolean;
  onClose: () => void;
  patient: PatientView;
}

interface FormState extends PatientProfileFormState {
  // Edit-specific extensions on top of the shared profile shape. Any
  // field listed here lives ONLY in the Edit flow — if you need it on
  // Add too, put it in PatientProfileFormState instead.
  briefHistory: string;
  status: 'ACTIVE' | 'INACTIVE' | 'ARCHIVED';
}

function patientToForm(p: PatientView): FormState {
  return {
    ...patientViewToProfile(p),
    briefHistory: p.briefHistory.join('\n'),
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
  const [assignedDoctorId, setAssignedDoctorId] = useState<string>(
    // Preselect the current assignment so the dropdown reflects reality
    // on open. Untouched submits leave it as-is; if the user actively
    // changes it we flip assignedDoctorChanged and include it in the
    // payload.
    patient.assignedDoctorId ?? ''
  );
  const [assignedDoctorChanged, setAssignedDoctorChanged] = useState(false);
  const [doctors, setDoctors] = useState<DoctorOption[]>([]);
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

  // Load doctors for the assigned-provider dropdown. Same non-blocking
  // contract as AddPatientModal — failure degrades to empty list.
  useEffect(() => {
    let cancelled = false;
    listPracticeDoctorsAction()
      .then((r) => {
        if (!cancelled && r.ok) setDoctors(r.data);
      })
      .catch((err) => {
        console.warn('[EditPatientModal] listPracticeDoctors failed:', err);
      });
    return () => {
      cancelled = true;
    };
  }, []);

  const update = useCallback(
    <K extends keyof FormState>(key: K, value: FormState[K]) => {
      setForm((prev) => ({ ...prev, [key]: value }));
      setFieldErrors((prev) => {
        if (!prev[key]) return prev;
        const next = { ...prev };
        delete next[key];
        return next;
      });
    },
    []
  );

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    setFieldErrors({});

    // Profile fields use the shared converter so Edit + Add stay in sync.
    // Edit-only fields (briefHistory, status) are spread on after.
    const payload: Record<string, unknown> = {
      ...profileToPayload(form),
      briefHistory: form.briefHistory
        .split('\n')
        .map((s) => s.trim())
        .filter(Boolean),
      status: form.status,
    };
    // Only include assignedDoctorId if the user actually touched the
    // dropdown — otherwise the server would see an empty string and
    // clear the existing assignment.
    if (assignedDoctorChanged) {
      payload.assignedDoctorId = assignedDoctorId || null;
    }

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
        <div className="pointer-events-auto w-full max-w-2xl rounded-2xl bg-[#0A192F] border border-white/10 shadow-2xl shadow-black/50 overflow-hidden">
          {/* Header */}
          <div className="relative px-6 py-4 border-b border-white/10 bg-gradient-to-r from-blue-500/10 to-teal-500/10">
            <div className="flex items-center gap-3">
              <div className="p-2 rounded-lg bg-blue-500/20 border border-blue-500/30">
                <UserCog className="w-5 h-5 text-blue-300" />
              </div>
              <div className="min-w-0">
                <h2 id="edit-patient-title" className="text-lg font-bold text-white">
                  Edit Patient
                </h2>
                <p className="text-xs text-slate-400 truncate">
                  {patient.firstName} {patient.lastName}
                  {patient.chartId ? (
                    <>
                      {' · '}
                      <span className="font-mono">{patient.chartId}</span>
                    </>
                  ) : null}
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

            {/* Chart ID + MRN. Chart ID is practice-unique; the server
                rejects duplicates within the practice. Changing or
                clearing it is allowed — rarely needed, but some intake
                flows produce a temporary ID that gets renumbered later. */}
            <div className="grid grid-cols-2 gap-3">
              <Field
                label="Chart ID"
                error={fieldErrors.chartId?.[0]}
                hint="Unique per practice"
              >
                <input
                  type="text"
                  value={form.chartId}
                  onChange={(e) => update('chartId', e.target.value)}
                  disabled={isPending}
                  placeholder="C-1001"
                  className="input-styled font-mono"
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

            {/* Birth year + phoneLast4 */}
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
                hint="Minimal-PHI fallback"
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

            {/* Cell + home phone */}
            <div className="grid grid-cols-2 gap-3">
              <Field label="Cell Phone" error={fieldErrors.cellPhone?.[0]}>
                <input
                  type="tel"
                  value={form.cellPhone}
                  onChange={(e) => update('cellPhone', e.target.value)}
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

            {/* Sex + Assigned Provider */}
            <div className="grid grid-cols-2 gap-3">
              <Field label="Sex" hint="Clinical context only">
                <select
                  value={form.sex}
                  onChange={(e) => update('sex', e.target.value as PatientSex)}
                  disabled={isPending}
                  className="input-styled"
                >
                  <option value="UNKNOWN">Not specified</option>
                  <option value="FEMALE">Female</option>
                  <option value="MALE">Male</option>
                  <option value="OTHER">Other</option>
                </select>
              </Field>
              <Field
                label="Assigned Provider"
                error={fieldErrors.assignedDoctorId?.[0]}
                hint={
                  doctors.length === 0
                    ? 'No doctors available'
                    : assignedDoctorChanged
                      ? 'Will be saved'
                      : 'Leave unchanged to keep current assignment'
                }
              >
                <select
                  value={assignedDoctorId}
                  onChange={(e) => {
                    setAssignedDoctorId(e.target.value);
                    setAssignedDoctorChanged(true);
                  }}
                  disabled={isPending || doctors.length === 0}
                  className="input-styled"
                >
                  <option value="">
                    {assignedDoctorChanged ? 'Unassigned' : '— Keep current —'}
                  </option>
                  {doctors.map((d) => (
                    <option key={d.id} value={d.id}>
                      {d.name || d.email}
                    </option>
                  ))}
                </select>
              </Field>
            </div>

            {/* Address */}
            <Field label="Address Line 1" error={fieldErrors.addressLine1?.[0]}>
              <input
                type="text"
                value={form.addressLine1}
                onChange={(e) => update('addressLine1', e.target.value)}
                disabled={isPending}
                placeholder="123 Main St"
                className="input-styled"
              />
            </Field>
            <Field
              label="Address Line 2"
              error={fieldErrors.addressLine2?.[0]}
              hint="Apt / suite (optional)"
            >
              <input
                type="text"
                value={form.addressLine2}
                onChange={(e) => update('addressLine2', e.target.value)}
                disabled={isPending}
                placeholder="Apt 4B"
                className="input-styled"
              />
            </Field>
            <div className="grid grid-cols-[1fr_80px_110px] gap-3">
              <Field label="City" error={fieldErrors.city?.[0]}>
                <input
                  type="text"
                  value={form.city}
                  onChange={(e) => update('city', e.target.value)}
                  disabled={isPending}
                  placeholder="San Francisco"
                  className="input-styled"
                />
              </Field>
              <Field label="State" error={fieldErrors.state?.[0]}>
                <input
                  type="text"
                  value={form.state}
                  onChange={(e) =>
                    update(
                      'state',
                      e.target.value
                        .replace(/[^A-Za-z]/g, '')
                        .slice(0, 2)
                        .toUpperCase()
                    )
                  }
                  disabled={isPending}
                  placeholder="CA"
                  maxLength={2}
                  className="input-styled font-mono uppercase"
                />
              </Field>
              <Field label="Postal Code" error={fieldErrors.postalCode?.[0]}>
                <input
                  type="text"
                  value={form.postalCode}
                  onChange={(e) => update('postalCode', e.target.value)}
                  disabled={isPending}
                  placeholder="94103"
                  maxLength={10}
                  className="input-styled font-mono"
                />
              </Field>
            </div>

            {/* Pharmacy */}
            <div className="grid grid-cols-[1fr_180px] gap-3">
              <Field
                label="Preferred Pharmacy"
                error={fieldErrors.pharmacyName?.[0]}
                hint="For e-prescribing"
              >
                <input
                  type="text"
                  value={form.pharmacyName}
                  onChange={(e) => update('pharmacyName', e.target.value)}
                  disabled={isPending}
                  placeholder="CVS on Market St"
                  className="input-styled"
                />
              </Field>
              <Field label="Pharmacy Phone" error={fieldErrors.pharmacyPhone?.[0]}>
                <input
                  type="tel"
                  value={form.pharmacyPhone}
                  onChange={(e) => update('pharmacyPhone', e.target.value)}
                  disabled={isPending}
                  placeholder="(555) 123-0000"
                  maxLength={32}
                  className="input-styled font-mono"
                />
              </Field>
            </div>

            {/* Brief history — one entry per line. Edits replace the full
                array, so removing a line removes the entry. */}
            <Field
              label="Brief History"
              hint="One line per entry. Edits replace the full list."
            >
              <textarea
                value={form.briefHistory}
                onChange={(e) => update('briefHistory', e.target.value)}
                disabled={isPending}
                placeholder={'Started LESI series 2025\nFailed PT 2024'}
                rows={4}
                className="input-styled resize-y min-h-[90px]"
              />
            </Field>

            {/* Insurance + Tags */}
            <div className="grid grid-cols-[auto_1fr] gap-3 items-start">
              <InsuranceStatusToggle
                value={form.insuranceVerified}
                onChange={(v) => update('insuranceVerified', v)}
                disabled={isPending}
              />
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

            {/* Status */}
            <Field
              label="Patient Status"
              hint="Changes take effect immediately after save"
            >
              <select
                value={form.status}
                onChange={(e) =>
                  update('status', e.target.value as FormState['status'])
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
              <strong className="text-slate-400">HIPAA notice:</strong> This
              update will be logged with your user ID, IP address, changed
              field names, and timestamp in the immutable audit trail.
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
// Field wrapper — same shape as AddPatientModal's. Children live INSIDE the
// label so clicking the label focuses the control and getByLabel works.
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
    <label className="block">
      <span className="block text-[11px] font-semibold text-slate-300 uppercase tracking-wider mb-1">
        {label.replace(/\s*\*\s*$/, '')}
      </span>
      {children}
      {error ? (
        <p className="text-[10px] text-red-400 mt-1">{error}</p>
      ) : hint ? (
        <p className="text-[10px] text-slate-500 mt-1">{hint}</p>
      ) : null}
    </label>
  );
}
