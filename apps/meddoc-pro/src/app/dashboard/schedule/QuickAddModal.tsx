'use client';

// ============================================================================
// Quick Add Appointment Modal — with Patient Search/Select
// ============================================================================

import { useState, useEffect, useTransition, useMemo } from 'react';
import { useRouter } from 'next/navigation';
import { motion, AnimatePresence } from 'framer-motion';
import {
  X,
  Loader2,
  AlertCircle,
  CheckCircle2,
  CalendarPlus,
  Search,
  User,
} from 'lucide-react';

import { quickAddAppointmentAction } from './actions';
import { localDateTimeToISO } from '@/lib/datetime';

export interface PatientOption {
  id: string;
  firstName: string;
  lastName: string;
  mrn: string;
}

interface QuickAddModalProps {
  open: boolean;
  onClose: () => void;
  patients: PatientOption[];
  /** Pre-fill date from the currently selected calendar day */
  defaultDate?: string;
}

// Outer wrapper: AnimatePresence owns open/close. Inner content holds
// state so each open mounts fresh — no reset useEffect needed.
export default function QuickAddModal({
  open,
  onClose,
  patients,
  defaultDate,
}: QuickAddModalProps) {
  return (
    <AnimatePresence>
      {open && (
        <QuickAddModalContent
          onClose={onClose}
          patients={patients}
          defaultDate={defaultDate}
        />
      )}
    </AnimatePresence>
  );
}

function QuickAddModalContent({
  onClose,
  patients,
  defaultDate,
}: {
  onClose: () => void;
  patients: PatientOption[];
  defaultDate?: string;
}) {
  const router = useRouter();
  const [isPending, startTransition] = useTransition();
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState(false);

  // Form state — initialized fresh on each mount (each modal-open).
  const [patientQuery, setPatientQuery] = useState('');
  const [selectedPatientId, setSelectedPatientId] = useState('');
  const [dropdownOpen, setDropdownOpen] = useState(false);
  const [date, setDate] = useState(defaultDate ?? new Date().toISOString().split('T')[0]);
  const [time, setTime] = useState('09:00');
  const [visitType, setVisitType] = useState<'CONSULTATION' | 'FOLLOW_UP' | 'PROCEDURE'>('FOLLOW_UP');
  const [notes, setNotes] = useState('');

  // ESC to close
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => { if (e.key === 'Escape') onClose(); };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, [onClose]);

  // Filtered patient list
  const filteredPatients = useMemo(() => {
    if (!patientQuery.trim()) return patients.slice(0, 8);
    const q = patientQuery.toLowerCase();
    return patients
      .filter(
        (p) =>
          p.firstName.toLowerCase().includes(q) ||
          p.lastName.toLowerCase().includes(q) ||
          p.mrn.toLowerCase().includes(q)
      )
      .slice(0, 8);
  }, [patients, patientQuery]);

  const selectedPatient = patients.find((p) => p.id === selectedPatientId);

  const handleSelectPatient = (p: PatientOption) => {
    setSelectedPatientId(p.id);
    setPatientQuery(`${p.firstName} ${p.lastName}`);
    setDropdownOpen(false);
  };

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);

    if (!selectedPatientId) {
      setError('Please select a patient.');
      return;
    }

    let scheduledAt: string;
    try {
      scheduledAt = localDateTimeToISO(date, time);
    } catch {
      setError('Please provide a valid date and time.');
      return;
    }

    const fd = new FormData();
    fd.append('patientId', selectedPatientId);
    fd.append('scheduledAt', scheduledAt);
    fd.append('visitType', visitType);
    if (notes.trim()) fd.append('notes', notes.trim());

    startTransition(async () => {
      const result = await quickAddAppointmentAction(fd);
      if (!result.ok) {
        setError(result.error);
        return;
      }
      setSuccess(true);
      router.refresh();
      setTimeout(() => onClose(), 1000);
    });
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
            className="fixed inset-0 z-[101] flex items-center justify-center p-4 pointer-events-none"
          >
            <div className="pointer-events-auto w-full max-w-md rounded-2xl bg-[#0A192F] border border-white/10 shadow-2xl shadow-black/50 overflow-hidden">
              {/* Header */}
              <div className="relative px-6 py-4 border-b border-white/10 bg-gradient-to-r from-emerald-500/10 to-teal-500/10">
                <div className="flex items-center gap-3">
                  <div className="p-2 rounded-lg bg-emerald-500/20 border border-emerald-500/30">
                    <CalendarPlus className="w-5 h-5 text-emerald-300" />
                  </div>
                  <div>
                    <h2 className="text-lg font-bold text-white">New Appointment</h2>
                    <p className="text-xs text-slate-400">Quick schedule from calendar</p>
                  </div>
                </div>
                <button
                  onClick={onClose}
                  className="absolute top-3 right-3 p-2 rounded-lg text-slate-400 hover:text-white hover:bg-white/5 transition-colors"
                >
                  <X className="w-4 h-4" />
                </button>
              </div>

              {/* Form */}
              <form onSubmit={handleSubmit} className="px-6 py-5 space-y-4 max-h-[70vh] overflow-y-auto">
                {error && !success && (
                  <div className="flex items-start gap-2 p-3 rounded-lg bg-red-500/10 border border-red-500/30">
                    <AlertCircle className="w-4 h-4 text-red-400 shrink-0 mt-0.5" />
                    <p className="text-xs text-red-300">{error}</p>
                  </div>
                )}
                {success && (
                  <div className="flex items-start gap-2 p-3 rounded-lg bg-emerald-500/10 border border-emerald-500/30">
                    <CheckCircle2 className="w-4 h-4 text-emerald-400 shrink-0 mt-0.5" />
                    <p className="text-xs text-emerald-300">Appointment scheduled!</p>
                  </div>
                )}

                {/* Patient Search */}
                <div>
                  <label className="block text-[11px] font-semibold text-slate-300 uppercase tracking-wider mb-1">
                    Patient *
                  </label>
                  <div className="relative">
                    <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-slate-500" />
                    <input
                      type="text"
                      value={patientQuery}
                      onChange={(e) => {
                        setPatientQuery(e.target.value);
                        setDropdownOpen(true);
                        if (selectedPatientId) setSelectedPatientId('');
                      }}
                      onFocus={() => setDropdownOpen(true)}
                      placeholder="Search by name or MRN..."
                      disabled={isPending}
                      className="w-full pl-10 pr-4 py-2.5 rounded-xl bg-slate-900/60 border border-white/10 text-sm text-white placeholder-slate-500 outline-none focus:border-emerald-400/50 transition-colors"
                    />
                    {selectedPatient && (
                      <div className="absolute right-3 top-1/2 -translate-y-1/2">
                        <CheckCircle2 className="w-4 h-4 text-emerald-400" />
                      </div>
                    )}

                    {/* Dropdown */}
                    <AnimatePresence>
                      {dropdownOpen && !selectedPatientId && (
                        <motion.div
                          initial={{ opacity: 0, y: -4 }}
                          animate={{ opacity: 1, y: 0 }}
                          exit={{ opacity: 0, y: -4 }}
                          className="absolute left-0 right-0 top-full mt-1 z-50 rounded-xl bg-[#0d2137] border border-white/15 shadow-2xl shadow-black/50 max-h-48 overflow-y-auto"
                        >
                          {filteredPatients.length === 0 ? (
                            <div className="px-4 py-3 text-xs text-slate-500">No patients found.</div>
                          ) : (
                            filteredPatients.map((p) => (
                              <button
                                key={p.id}
                                type="button"
                                onClick={() => handleSelectPatient(p)}
                                className="w-full flex items-center gap-3 px-4 py-2.5 hover:bg-white/5 transition-colors text-left cursor-pointer"
                              >
                                <div className="w-7 h-7 rounded-full bg-gradient-to-br from-blue-500/30 to-teal-500/30 border border-blue-500/20 flex items-center justify-center shrink-0">
                                  <User className="w-3 h-3 text-white/80" />
                                </div>
                                <div>
                                  <p className="text-xs font-medium text-white">
                                    {p.firstName} {p.lastName}
                                  </p>
                                  <p className="text-[10px] text-slate-500 font-mono">{p.mrn}</p>
                                </div>
                              </button>
                            ))
                          )}
                        </motion.div>
                      )}
                    </AnimatePresence>
                  </div>
                </div>

                {/* Date + Time */}
                <div className="grid grid-cols-2 gap-3">
                  <div>
                    <label className="block text-[11px] font-semibold text-slate-300 uppercase tracking-wider mb-1">
                      Date *
                    </label>
                    <input
                      type="date"
                      value={date}
                      onChange={(e) => setDate(e.target.value)}
                      required
                      disabled={isPending}
                      className="input-styled"
                    />
                  </div>
                  <div>
                    <label className="block text-[11px] font-semibold text-slate-300 uppercase tracking-wider mb-1">
                      Time *
                    </label>
                    <input
                      type="time"
                      value={time}
                      onChange={(e) => setTime(e.target.value)}
                      required
                      disabled={isPending}
                      className="input-styled"
                    />
                  </div>
                </div>

                {/* Visit Type */}
                <div>
                  <label className="block text-[11px] font-semibold text-slate-300 uppercase tracking-wider mb-1">
                    Visit Type *
                  </label>
                  <select
                    value={visitType}
                    onChange={(e) => setVisitType(e.target.value as typeof visitType)}
                    disabled={isPending}
                    className="input-styled appearance-none cursor-pointer"
                  >
                    <option value="CONSULTATION">Consultation</option>
                    <option value="FOLLOW_UP">Follow-up</option>
                    <option value="PROCEDURE">Procedure</option>
                  </select>
                </div>

                {/* Notes */}
                <div>
                  <label className="block text-[11px] font-semibold text-slate-300 uppercase tracking-wider mb-1">
                    Notes
                  </label>
                  <input
                    type="text"
                    value={notes}
                    onChange={(e) => setNotes(e.target.value)}
                    disabled={isPending}
                    placeholder="e.g. 3rd LESI follow-up"
                    className="input-styled"
                  />
                </div>

                {/* Footer */}
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
                    className="inline-flex items-center gap-2 px-4 py-2 rounded-lg bg-gradient-to-r from-emerald-500 to-teal-500 text-white text-sm font-semibold shadow-lg shadow-emerald-500/25 hover:shadow-emerald-500/40 disabled:opacity-50 disabled:cursor-not-allowed transition-all"
                  >
                    {isPending ? (
                      <><Loader2 className="w-4 h-4 animate-spin" /> Scheduling...</>
                    ) : success ? (
                      <><CheckCircle2 className="w-4 h-4" /> Scheduled!</>
                    ) : (
                      <><CalendarPlus className="w-4 h-4" /> Schedule</>
                    )}
                  </button>
                </div>
              </form>
            </div>
          </motion.div>

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
            :global(.input-styled::placeholder) { color: rgb(100, 116, 139); }
            :global(.input-styled:focus) { border-color: rgba(59, 130, 246, 0.5); }
            :global(.input-styled:disabled) { opacity: 0.5; cursor: not-allowed; }
          `}</style>
    </>
  );
}
