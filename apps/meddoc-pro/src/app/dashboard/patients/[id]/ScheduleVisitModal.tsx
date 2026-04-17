'use client';

// ============================================================================
// Schedule Visit Modal — Glassmorphism
// ----------------------------------------------------------------------------
// Date + Time + Visit Type + optional Notes → scheduleVisitAction
// ============================================================================

import { useState, useEffect, useTransition } from 'react';
import { useRouter } from 'next/navigation';
import { motion, AnimatePresence } from 'framer-motion';
import { X, Loader2, AlertCircle, CheckCircle2, CalendarPlus } from 'lucide-react';

import { scheduleVisitAction } from '@/app/dashboard/patients/actions';
import { localDateTimeToISO } from '@/lib/datetime';

interface ScheduleVisitModalProps {
  open: boolean;
  onClose: () => void;
  patientId: string;
  patientName: string;
}

export default function ScheduleVisitModal({
  open,
  onClose,
  patientId,
  patientName,
}: ScheduleVisitModalProps) {
  const router = useRouter();
  const [isPending, startTransition] = useTransition();
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState(false);

  // Default date = tomorrow, time = 9:00 AM
  const tomorrow = new Date();
  tomorrow.setDate(tomorrow.getDate() + 1);
  const defaultDate = tomorrow.toISOString().split('T')[0];

  const [date, setDate] = useState(defaultDate);
  const [time, setTime] = useState('09:00');
  const [visitType, setVisitType] = useState<'CONSULTATION' | 'FOLLOW_UP' | 'PROCEDURE'>('FOLLOW_UP');
  const [notes, setNotes] = useState('');

  useEffect(() => {
    if (open) {
      setDate(defaultDate);
      setTime('09:00');
      setVisitType('FOLLOW_UP');
      setNotes('');
      setError(null);
      setSuccess(false);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [open]);

  useEffect(() => {
    if (!open) return;
    const onKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape') onClose();
    };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, [open, onClose]);

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);

    if (!date || !time) {
      setError('Date and time are required.');
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
    fd.append('scheduledAt', scheduledAt);
    fd.append('visitType', visitType);
    if (notes.trim()) fd.append('notes', notes.trim());

    startTransition(async () => {
      const result = await scheduleVisitAction(patientId, fd);
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
    <AnimatePresence>
      {open && (
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
            aria-labelledby="schedule-visit-title"
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
                    <h2 id="schedule-visit-title" className="text-lg font-bold text-white">
                      Schedule Visit
                    </h2>
                    <p className="text-xs text-slate-400">
                      {patientName}
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
              <form onSubmit={handleSubmit} className="px-6 py-5 space-y-4">
                {error && !success && (
                  <div className="flex items-start gap-2 p-3 rounded-lg bg-red-500/10 border border-red-500/30">
                    <AlertCircle className="w-4 h-4 text-red-400 shrink-0 mt-0.5" />
                    <p className="text-xs text-red-300">{error}</p>
                  </div>
                )}

                {success && (
                  <div className="flex items-start gap-2 p-3 rounded-lg bg-emerald-500/10 border border-emerald-500/30">
                    <CheckCircle2 className="w-4 h-4 text-emerald-400 shrink-0 mt-0.5" />
                    <p className="text-xs text-emerald-300">Visit scheduled successfully!</p>
                  </div>
                )}

                {/* Date + Time row */}
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
                      min={new Date().toISOString().split('T')[0]}
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
                  <p className="text-[10px] text-slate-500 mt-1">Optional — brief visit context</p>
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
                      <><CalendarPlus className="w-4 h-4" /> Schedule Visit</>
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
      )}
    </AnimatePresence>
  );
}
