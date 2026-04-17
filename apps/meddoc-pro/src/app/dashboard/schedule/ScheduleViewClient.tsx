'use client';

// ============================================================================
// Schedule View — Time-Block Calendar + Flow Mode Kanban
// ============================================================================

import { useState, useMemo, useTransition, useCallback, useEffect } from 'react';
import Link from 'next/link';
import { useRouter, useSearchParams } from 'next/navigation';
import { motion, AnimatePresence } from 'framer-motion';
import {
  ChevronLeft,
  ChevronRight,
  Calendar,
  Clock,
  User,
  Stethoscope,
  ClipboardCheck,
  Activity,
  CalendarDays,
  Sparkles,
  Loader2,
  Plus,
  LayoutGrid,
  LayoutList,
  ChevronDown,
  Trash2,
} from 'lucide-react';

import type { CalendarAppointment } from '@/lib/data/appointments';
import {
  deleteAppointmentAction,
  generateAIPrepNoteAction,
  updateAppointmentStatusAction,
} from './actions';
import QuickAddModal, { type PatientOption } from './QuickAddModal';

interface ScheduleViewClientProps {
  appointments: CalendarAppointment[];
  patients: PatientOption[];
}

// Visible time range in the Timeline view. Clinicians can run early/late, so
// we span 7 AM – 8 PM by default. Anything outside this window renders in the
// "Outside hours" bucket above the grid — we refuse to silently hide rows.
const HOUR_START = 7;
const HOUR_END = 20; // inclusive — last row shown is 8 PM
const HOURS = Array.from({ length: HOUR_END - HOUR_START + 1 }, (_, i) => i + HOUR_START);

type AptStatus = CalendarAppointment['status'];

// ── Visit type styles ──
const VISIT_ICON: Record<CalendarAppointment['type'], { icon: typeof Stethoscope; label: string }> = {
  CONSULTATION: { icon: ClipboardCheck, label: 'Consultation' },
  FOLLOW_UP: { icon: Activity, label: 'Follow-up' },
  PROCEDURE: { icon: Stethoscope, label: 'Procedure' },
};

// ── Status-driven card styles ──
const STATUS_CARD: Record<AptStatus, { bg: string; border: string; accent: string; dot: string; label: string }> = {
  SCHEDULED: {
    bg: 'from-blue-500/12 to-blue-600/5',
    border: 'border-blue-500/30',
    accent: 'border-l-blue-400',
    dot: 'bg-blue-400',
    label: 'Scheduled',
  },
  WAITING: {
    bg: 'from-amber-500/15 to-amber-600/5',
    border: 'border-amber-500/40',
    accent: 'border-l-amber-400',
    dot: 'bg-amber-400',
    label: 'Waiting',
  },
  IN_ROOM: {
    bg: 'from-emerald-500/15 to-emerald-600/5',
    border: 'border-emerald-500/40',
    accent: 'border-l-emerald-400',
    dot: 'bg-emerald-400',
    label: 'In Room',
  },
  COMPLETED: {
    bg: 'from-slate-500/10 to-slate-600/5',
    border: 'border-slate-500/25',
    accent: 'border-l-slate-500',
    dot: 'bg-slate-400',
    label: 'Completed',
  },
  CANCELLED: {
    bg: 'from-red-500/10 to-red-600/5',
    border: 'border-red-500/25',
    accent: 'border-l-red-500',
    dot: 'bg-red-400',
    label: 'Cancelled',
  },
};

const STATUS_ORDER: AptStatus[] = ['SCHEDULED', 'WAITING', 'IN_ROOM', 'COMPLETED', 'CANCELLED'];

// ── Kanban column config ──
const KANBAN_COLS: { status: AptStatus; label: string; color: string; headerBg: string }[] = [
  { status: 'SCHEDULED', label: 'Scheduled', color: 'text-blue-300', headerBg: 'bg-blue-500/10 border-blue-500/30' },
  { status: 'WAITING', label: 'Waiting', color: 'text-amber-300', headerBg: 'bg-amber-500/10 border-amber-500/30' },
  { status: 'IN_ROOM', label: 'In Room', color: 'text-emerald-300', headerBg: 'bg-emerald-500/10 border-emerald-500/30' },
  { status: 'COMPLETED', label: 'Completed', color: 'text-slate-400', headerBg: 'bg-slate-500/10 border-slate-500/30' },
];

function formatHour(h: number): string { return h === 0 || h === 12 ? '12' : String(h > 12 ? h - 12 : h); }
function ampm(h: number): string { return h >= 12 ? 'PM' : 'AM'; }
function isSameDay(d1: Date, d2: Date): boolean {
  return d1.getFullYear() === d2.getFullYear() && d1.getMonth() === d2.getMonth() && d1.getDate() === d2.getDate();
}
function formatDateHeader(d: Date): string {
  const t = new Date(); const tm = new Date(); tm.setDate(t.getDate() + 1);
  const y = new Date(); y.setDate(t.getDate() - 1);
  let p = '';
  if (isSameDay(d, t)) p = 'Today — ';
  else if (isSameDay(d, tm)) p = 'Tomorrow — ';
  else if (isSameDay(d, y)) p = 'Yesterday — ';
  return `${p}${d.toLocaleDateString('en-US', { weekday: 'long', month: 'long', day: 'numeric', year: 'numeric' })}`;
}

// ════════════════════════════════════════════════════════════════════════════
// Main Component
// ════════════════════════════════════════════════════════════════════════════

export default function ScheduleViewClient({ appointments, patients }: ScheduleViewClientProps) {
  const router = useRouter();
  const searchParams = useSearchParams();
  const debugMode = searchParams?.get('debug') === '1';
  const [selectedDate, setSelectedDate] = useState(() => new Date());
  const [quickAddOpen, setQuickAddOpen] = useState(false);
  const [flowMode, setFlowMode] = useState(false);

  // AI Prep
  const [generatingPrepId, setGeneratingPrepId] = useState<string | null>(null);
  const [prepPending, startPrepTransition] = useTransition();

  // Status updates
  const [statusDropdownId, setStatusDropdownId] = useState<string | null>(null);
  const [, startStatusTransition] = useTransition();

  // Delete
  const [deletingId, setDeletingId] = useState<string | null>(null);
  const [, startDeleteTransition] = useTransition();
  const [toast, setToast] = useState<{ message: string; type: 'success' | 'error' } | null>(null);

  const handleGeneratePrep = useCallback((id: string, pid: string) => {
    setGeneratingPrepId(id);
    startPrepTransition(async () => {
      await generateAIPrepNoteAction(id, pid);
      setGeneratingPrepId(null);
      router.refresh();
    });
  }, [router]);

  const handleStatusChange = useCallback((id: string, newStatus: AptStatus) => {
    setStatusDropdownId(null);
    startStatusTransition(async () => {
      await updateAppointmentStatusAction(id, newStatus);
      router.refresh();
    });
  }, [router]);

  const handleDelete = useCallback((apt: CalendarAppointment) => {
    const confirmed = window.confirm(
      `Delete this appointment for ${apt.patientFirstName} ${apt.patientLastName}?\n\nThe entry will be removed from the calendar. For HIPAA, the record is kept in the audit log and can be recovered by an administrator.`
    );
    if (!confirmed) return;
    setDeletingId(apt.id);
    startDeleteTransition(async () => {
      const result = await deleteAppointmentAction(apt.id);
      setDeletingId(null);
      if (result.ok) {
        setToast({ message: 'Appointment deleted', type: 'success' });
        router.refresh();
      } else {
        setToast({ message: result.error || 'Failed to delete appointment', type: 'error' });
      }
    });
  }, [router]);

  // Auto-dismiss toast after 3s
  useEffect(() => {
    if (!toast) return;
    const t = setTimeout(() => setToast(null), 3000);
    return () => clearTimeout(t);
  }, [toast]);

  const dayApts = useMemo(
    () => appointments.filter((a) => isSameDay(new Date(a.scheduledAt), selectedDate)),
    [appointments, selectedDate]
  );

  const weekDays = useMemo(() => {
    const s = new Date(selectedDate); s.setDate(s.getDate() - s.getDay());
    return Array.from({ length: 7 }, (_, i) => {
      const d = new Date(s); d.setDate(d.getDate() + i);
      return { date: d, count: appointments.filter((a) => isSameDay(new Date(a.scheduledAt), d)).length, isSelected: isSameDay(d, selectedDate), isToday: isSameDay(d, new Date()) };
    });
  }, [appointments, selectedDate]);

  // Bucket appointments by local hour. Anything outside the visible window
  // goes into `outsideHoursApts` so it still renders — never disappear a row
  // just because the clock says 6am or 9pm.
  const { slotMap, outsideHoursApts } = useMemo(() => {
    const m = new Map<number, CalendarAppointment[]>();
    const outside: CalendarAppointment[] = [];
    for (const a of dayApts) {
      const h = new Date(a.scheduledAt).getHours();
      if (h < HOUR_START || h > HOUR_END) {
        outside.push(a);
      } else {
        m.set(h, [...(m.get(h) ?? []), a]);
      }
    }
    // Sort each hour's cards by minute so 10:00 sits above 10:45.
    for (const [h, list] of m) {
      m.set(h, [...list].sort((x, y) => new Date(x.scheduledAt).getMinutes() - new Date(y.scheduledAt).getMinutes()));
    }
    outside.sort((x, y) => new Date(x.scheduledAt).getTime() - new Date(y.scheduledAt).getTime());
    return { slotMap: m, outsideHoursApts: outside };
  }, [dayApts]);

  const prevDay = () => { const d = new Date(selectedDate); d.setDate(d.getDate() - 1); setSelectedDate(d); };
  const nextDay = () => { const d = new Date(selectedDate); d.setDate(d.getDate() + 1); setSelectedDate(d); };

  // ── Shared card renderer ──
  const renderCard = (apt: CalendarAppointment, compact = false) => {
    const sc = STATUS_CARD[apt.status];
    const vi = VISIT_ICON[apt.type];
    const Icon = vi.icon;
    const timeStr = new Date(apt.scheduledAt).toLocaleTimeString('en-US', { hour: 'numeric', minute: '2-digit' });
    const isGenPrep = prepPending && generatingPrepId === apt.id;
    const isDropOpen = statusDropdownId === apt.id;
    const isDeleting = deletingId === apt.id;

    return (
      <div key={apt.id} className={`rounded-xl bg-gradient-to-r ${sc.bg} border ${sc.border} border-l-[3px] ${sc.accent} p-3 transition-all`}>
        <div className="flex items-start gap-3">
          <Link href={`/dashboard/patients/${apt.patientId}`} className="shrink-0 p-1.5 rounded-lg bg-white/5 hover:bg-white/10 transition-colors">
            <Icon className="w-4 h-4 text-white" />
          </Link>
          <div className="flex-1 min-w-0">
            <div className="flex items-center gap-2 mb-0.5">
              <Link href={`/dashboard/patients/${apt.patientId}`} className="text-sm font-semibold text-white truncate hover:underline decoration-white/30 underline-offset-2">
                {apt.patientFirstName} {apt.patientLastName}
              </Link>
            </div>
            <div className="flex items-center gap-3 text-[11px] text-slate-400">
              <span className="flex items-center gap-1"><Clock className="w-3 h-3" />{timeStr}</span>
              {!compact && <span className="flex items-center gap-1"><User className="w-3 h-3" />{vi.label}</span>}
            </div>
            {apt.notes && !compact && <p className="text-[10px] text-slate-500 mt-1 truncate">{apt.notes}</p>}
          </div>

          {/* Delete button — soft-delete via status=CANCELLED. Record is
              retained in the DB + audit log; just hidden from the calendar. */}
          <button
            type="button"
            onClick={() => handleDelete(apt)}
            disabled={isDeleting}
            aria-label="Delete appointment"
            title="Delete appointment"
            className="shrink-0 p-1.5 rounded-md text-slate-400 hover:text-red-300 hover:bg-red-500/10 transition-colors cursor-pointer disabled:opacity-50 disabled:cursor-not-allowed"
          >
            {isDeleting ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <Trash2 className="w-3.5 h-3.5" />}
          </button>

          {/* Status dropdown */}
          <div className="relative shrink-0">
            <button
              type="button"
              onClick={() => setStatusDropdownId(isDropOpen ? null : apt.id)}
              className={`inline-flex items-center gap-1 px-2 py-1 rounded-md text-[10px] font-semibold border transition-all cursor-pointer ${
                apt.status === 'WAITING' ? 'bg-amber-500/15 text-amber-300 border-amber-500/30' :
                apt.status === 'IN_ROOM' ? 'bg-emerald-500/15 text-emerald-300 border-emerald-500/30' :
                apt.status === 'COMPLETED' ? 'bg-slate-500/15 text-slate-400 border-slate-500/30' :
                apt.status === 'CANCELLED' ? 'bg-red-500/15 text-red-300 border-red-500/30' :
                'bg-blue-500/15 text-blue-300 border-blue-500/30'
              }`}
            >
              <span className={`w-1.5 h-1.5 rounded-full ${sc.dot}`} />
              {sc.label}
              <ChevronDown className={`w-3 h-3 transition-transform ${isDropOpen ? 'rotate-180' : ''}`} />
            </button>

            <AnimatePresence>
              {isDropOpen && (
                <motion.div
                  initial={{ opacity: 0, y: 4, scale: 0.95 }}
                  animate={{ opacity: 1, y: 0, scale: 1 }}
                  exit={{ opacity: 0, y: 4, scale: 0.95 }}
                  transition={{ duration: 0.12 }}
                  className="absolute right-0 bottom-full mb-1 z-[60] w-36 rounded-lg bg-[#0d2137] border border-white/15 shadow-2xl shadow-black/50"
                >
                  {STATUS_ORDER.map((s) => {
                    const sConf = STATUS_CARD[s];
                    return (
                      <button
                        key={s}
                        type="button"
                        onClick={() => handleStatusChange(apt.id, s)}
                        className={`w-full flex items-center gap-2 px-3 py-2 text-left text-[11px] hover:bg-white/5 transition-colors cursor-pointer ${
                          apt.status === s ? 'bg-white/5 font-semibold' : ''
                        }`}
                      >
                        <span className={`w-2 h-2 rounded-full ${sConf.dot}`} />
                        <span className="text-slate-300">{sConf.label}</span>
                      </button>
                    );
                  })}
                </motion.div>
              )}
            </AnimatePresence>
          </div>
        </div>

        {/* AI Prep */}
        {!compact && (
          apt.aiPrepNote ? (
            <div className="mt-2.5 ml-9 rounded-lg bg-violet-500/10 border-l-2 border-violet-400/60 px-3 py-2">
              <div className="flex items-center gap-1.5 mb-1">
                <Sparkles className="w-3 h-3 text-violet-400" />
                <span className="text-[9px] font-semibold text-violet-300 uppercase tracking-wider">AI Prep</span>
              </div>
              <p className="text-[11px] text-slate-300 leading-relaxed whitespace-pre-line">{apt.aiPrepNote}</p>
            </div>
          ) : (
            <div className="mt-2 ml-9">
              <button
                type="button"
                onClick={() => handleGeneratePrep(apt.id, apt.patientId)}
                disabled={isGenPrep}
                className="inline-flex items-center gap-1.5 px-2 py-1 rounded-md text-[10px] font-medium text-violet-300 bg-violet-500/10 border border-violet-500/20 hover:bg-violet-500/20 hover:border-violet-400/40 transition-all cursor-pointer disabled:opacity-50"
              >
                {isGenPrep ? <><Loader2 className="w-3 h-3 animate-spin" />Generating...</> : <><Sparkles className="w-3 h-3" />AI Prep</>}
              </button>
            </div>
          )
        )}
      </div>
    );
  };

  return (
    <div className="relative min-h-screen overflow-hidden bg-[#0A192F]">
      {/* Toast (success/error for delete + future actions) */}
      <AnimatePresence>
        {toast && (
          <motion.div
            initial={{ opacity: 0, y: -20, x: '-50%' }}
            animate={{ opacity: 1, y: 0, x: '-50%' }}
            exit={{ opacity: 0, y: -20, x: '-50%' }}
            className={`fixed top-6 left-1/2 z-[200] px-4 py-2.5 rounded-lg border text-xs shadow-2xl ${
              toast.type === 'success'
                ? 'bg-emerald-500/15 border-emerald-500/30 text-emerald-300'
                : 'bg-red-500/15 border-red-500/30 text-red-300'
            }`}
          >
            {toast.message}
          </motion.div>
        )}
      </AnimatePresence>

      <div className="absolute top-[5%] -left-[150px] w-[500px] h-[500px] rounded-full bg-blue-500 opacity-20 blur-[120px] pointer-events-none z-0" />
      <div className="absolute bottom-[10%] -right-[100px] w-[450px] h-[450px] rounded-full bg-teal-400 opacity-15 blur-[120px] pointer-events-none z-0" />

      <div className="relative z-10 mx-auto max-w-6xl px-4 sm:px-6 lg:px-8 py-8">
        {/* ── Header ── */}
        <motion.div initial={{ opacity: 0, y: -10 }} animate={{ opacity: 1, y: 0 }} className="flex items-center justify-between mb-6">
          <div className="flex items-center gap-3">
            <div className="p-2 rounded-xl bg-gradient-to-br from-blue-500/20 to-teal-500/20 border border-blue-500/30">
              <CalendarDays className="w-6 h-6 text-blue-300" />
            </div>
            <div>
              <h1 className="text-2xl font-bold text-white">Schedule</h1>
              <p className="text-sm text-slate-400">
                {dayApts.length} appointment{dayApts.length !== 1 ? 's' : ''}{' '}
                {isSameDay(selectedDate, new Date())
                  ? 'today'
                  : `on ${selectedDate.toLocaleDateString('en-US', { month: 'short', day: 'numeric' })}`}
              </p>
            </div>
          </div>
          <div className="flex items-center gap-2">
            {/* Flow Mode toggle */}
            <button
              onClick={() => setFlowMode((v) => !v)}
              className={`inline-flex items-center gap-1.5 px-3 py-2 rounded-xl text-xs font-semibold border transition-all cursor-pointer ${
                flowMode ? 'bg-violet-500/15 border-violet-500/30 text-violet-300' : 'bg-white/5 border-white/10 text-slate-400 hover:text-white'
              }`}
            >
              {flowMode ? <LayoutGrid className="w-3.5 h-3.5" /> : <LayoutList className="w-3.5 h-3.5" />}
              {flowMode ? 'Flow Mode' : 'Timeline'}
            </button>
            <button
              onClick={() => setQuickAddOpen(true)}
              className="inline-flex items-center gap-2 px-4 py-2.5 rounded-xl bg-gradient-to-r from-emerald-500 to-teal-500 text-white text-sm font-semibold shadow-lg shadow-emerald-500/25 hover:shadow-emerald-500/40 hover:scale-[1.02] transition-all cursor-pointer"
            >
              <Plus className="w-4 h-4" /> New Appointment
            </button>
          </div>
        </motion.div>

        {/* ── Diagnostic panel (only when ?debug=1) ── */}
        {debugMode && (
          <div className="mb-4 p-4 rounded-xl bg-fuchsia-500/10 border border-fuchsia-500/40 font-mono text-[11px] text-fuchsia-100 space-y-1">
            <div className="font-bold text-fuchsia-300">SCHEDULE DEBUG</div>
            <div>Browser TZ offset (min west of UTC): {new Date().getTimezoneOffset()}</div>
            <div>Browser now: {new Date().toString()}</div>
            <div>selectedDate: {selectedDate.toString()}</div>
            <div>appointments prop length: {appointments.length}</div>
            <div>dayApts.length (matches selectedDate): {dayApts.length}</div>
            <div>slotMap entries (in-range hours): {JSON.stringify(Array.from(slotMap.entries()).map(([h, v]) => [h, v.length]))}</div>
            <div>outsideHoursApts.length: {outsideHoursApts.length}</div>
            <div>flowMode: {String(flowMode)}</div>
            <div className="pt-2 border-t border-fuchsia-500/30 mt-2">All appointments prop (first 10):</div>
            {appointments.slice(0, 10).map((a) => {
              const d = new Date(a.scheduledAt);
              return (
                <div key={a.id}>
                  • {a.id.slice(0, 8)} | ISO={a.scheduledAt} | localH={d.getHours()}:{String(d.getMinutes()).padStart(2,'0')} | isSameDaySel={String(isSameDay(d, selectedDate))} | {a.patientFirstName} {a.patientLastName} | {a.status}
                </div>
              );
            })}
          </div>
        )}

        {/* ── Date Nav ── */}
        <motion.div initial={{ opacity: 0, y: -5 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.05 }} className="rounded-2xl bg-white/5 backdrop-blur-md border border-white/10 p-4 mb-6">
          <div className="flex items-center justify-between mb-4">
            <button onClick={prevDay} className="p-2 rounded-lg bg-white/5 border border-white/10 text-slate-400 hover:text-white hover:bg-white/10 transition-all cursor-pointer"><ChevronLeft className="w-4 h-4" /></button>
            <h2 className="text-lg font-bold text-white">{formatDateHeader(selectedDate)}</h2>
            <button onClick={nextDay} className="p-2 rounded-lg bg-white/5 border border-white/10 text-slate-400 hover:text-white hover:bg-white/10 transition-all cursor-pointer"><ChevronRight className="w-4 h-4" /></button>
          </div>
          <div className="flex items-center justify-between gap-1">
            {weekDays.map((day) => (
              <button key={day.date.toISOString()} onClick={() => setSelectedDate(new Date(day.date))} className={`flex-1 flex flex-col items-center gap-1 py-2 rounded-lg transition-all cursor-pointer ${day.isSelected ? 'bg-gradient-to-b from-blue-500/20 to-teal-500/10 border border-blue-500/30' : 'hover:bg-white/5 border border-transparent'}`}>
                <span className={`text-[10px] uppercase tracking-wider font-semibold ${day.isSelected ? 'text-blue-300' : 'text-slate-500'}`}>{day.date.toLocaleDateString('en-US', { weekday: 'short' })}</span>
                <span className={`text-sm font-bold ${day.isSelected ? 'text-white' : day.isToday ? 'text-blue-400' : 'text-slate-300'}`}>{day.date.getDate()}</span>
                {day.count > 0 && <div className="flex gap-0.5">{Array.from({ length: Math.min(day.count, 3) }, (_, i) => <div key={i} className={`w-1 h-1 rounded-full ${day.isSelected ? 'bg-blue-400' : 'bg-slate-500'}`} />)}</div>}
              </button>
            ))}
          </div>
          {!isSameDay(selectedDate, new Date()) && (
            <button onClick={() => setSelectedDate(new Date())} className="mt-3 mx-auto flex items-center gap-1.5 px-3 py-1 rounded-lg text-[11px] font-medium text-blue-300 bg-blue-500/10 border border-blue-500/20 hover:bg-blue-500/15 transition-all cursor-pointer"><Calendar className="w-3 h-3" />Go to Today</button>
          )}
        </motion.div>

        {/* ══ VIEW SWITCH ══ */}
        <motion.div initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.1 }}>
          {flowMode ? (
            /* ── KANBAN / FLOW MODE ── */
            <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
              {KANBAN_COLS.map((col) => {
                const colApts = dayApts.filter((a) => a.status === col.status);
                return (
                  <div key={col.status} className="rounded-2xl bg-white/5 backdrop-blur-md border border-white/10 flex flex-col">
                    {/* Column header */}
                    <div className={`px-4 py-3 border-b border-white/5 ${col.headerBg} border rounded-t-2xl`}>
                      <div className="flex items-center justify-between">
                        <span className={`text-xs font-bold uppercase tracking-wider ${col.color}`}>{col.label}</span>
                        <span className="text-[10px] px-1.5 py-0.5 rounded bg-white/10 text-slate-400">{colApts.length}</span>
                      </div>
                    </div>
                    {/* Cards */}
                    <div className="flex-1 p-3 space-y-2 min-h-[200px]">
                      {colApts.length === 0 ? (
                        <div className="py-8 text-center">
                          <p className="text-[10px] text-slate-600">No patients</p>
                        </div>
                      ) : (
                        colApts.map((apt) => renderCard(apt, true))
                      )}
                    </div>
                  </div>
                );
              })}
            </div>
          ) : (
            /* ── TIMELINE MODE ── */
            <div className="rounded-2xl bg-white/5 backdrop-blur-md border border-white/10 overflow-hidden">
              {/* Outside-hours bucket: appointments whose local hour falls
                  outside the visible HOUR_START..HOUR_END range. We surface
                  them rather than silently dropping them — covers early/late
                  visits and also shields against server/client TZ drift. */}
              {outsideHoursApts.length > 0 && (
                <div className="px-4 py-3 bg-amber-500/5 border-b border-amber-500/20">
                  <div className="flex items-center gap-2 mb-2">
                    <Clock className="w-3.5 h-3.5 text-amber-300" />
                    <span className="text-[10px] font-semibold text-amber-300 uppercase tracking-wider">
                      Outside visible hours ({formatHour(HOUR_START)} {ampm(HOUR_START)} – {formatHour(HOUR_END)} {ampm(HOUR_END)})
                    </span>
                  </div>
                  <div className="space-y-2">
                    {outsideHoursApts.map((apt) => renderCard(apt))}
                  </div>
                </div>
              )}

              {/* Hourly grid — scrollable so the full 7 AM – 8 PM range is
                  always reachable without blowing out page height. */}
              <div className="divide-y divide-white/5 max-h-[70vh] overflow-y-auto">
                {HOURS.map((hour) => {
                  const apts = slotMap.get(hour) ?? [];
                  const now = new Date();
                  const isNow = isSameDay(selectedDate, now) && now.getHours() === hour;
                  return (
                    <div key={hour} className={`flex min-h-[72px] relative ${isNow ? 'bg-blue-500/5' : ''}`}>
                      {isNow && (
                        <div className="absolute left-20 right-0 h-px bg-blue-400/60 z-10" style={{ top: `${((now.getMinutes() / 60) * 100).toFixed(1)}%` }}>
                          <div className="absolute -left-1 -top-1 w-2 h-2 rounded-full bg-blue-400" />
                        </div>
                      )}
                      <div className="w-20 shrink-0 py-3 px-4 text-right border-r border-white/5">
                        <span className={`text-xs font-mono ${isNow ? 'text-blue-300 font-bold' : 'text-slate-500'}`}>{formatHour(hour)} {ampm(hour)}</span>
                        {isNow && <div className="mt-0.5 text-[9px] text-blue-400 font-semibold uppercase">Now</div>}
                      </div>
                      <div className="flex-1 py-2 px-3 space-y-2 min-w-0">
                        {apts.length === 0 ? (
                          <div className="h-full" />
                        ) : (
                          apts.map((apt, i) => {
                            // Stagger cards vertically by minute so 10:00 sits
                            // above 10:30. Only apply to the first card to
                            // avoid overlap on dense hours — subsequent cards
                            // stack with normal space-y spacing.
                            const marginTop =
                              i === 0
                                ? `${(new Date(apt.scheduledAt).getMinutes() / 60) * 32}px`
                                : undefined;
                            return (
                              <div key={apt.id} style={marginTop ? { marginTop } : undefined}>
                                {renderCard(apt)}
                              </div>
                            );
                          })
                        )}
                      </div>
                    </div>
                  );
                })}
              </div>
            </div>
          )}
        </motion.div>
      </div>

      <QuickAddModal open={quickAddOpen} onClose={() => setQuickAddOpen(false)} patients={patients} defaultDate={selectedDate.toISOString().split('T')[0]} />
    </div>
  );
}
