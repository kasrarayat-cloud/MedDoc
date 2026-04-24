'use client';

import { useState, useMemo, useTransition, useEffect, useRef } from 'react';
import Link from 'next/link';
import { useRouter } from 'next/navigation';
import { motion, AnimatePresence } from 'framer-motion';
import {
  Users,
  Search,
  Plus,
  ChevronRight,
  Calendar,
  Filter,
  Activity,
  Sparkles,
  MoreVertical,
  Archive,
  Loader2,
  ShieldCheck,
  ShieldAlert,
  Shield,
} from 'lucide-react';
import { formatLastVisit, formatRelativeDate, type PatientStatus } from '@/lib/mock-patients';
import type { PatientView } from '@/lib/data/patients';
import AddPatientModal from './AddPatientModal';
import { archivePatientAction } from './actions';

const statusStyles: Record<PatientStatus, string> = {
  ACTIVE:
    'bg-emerald-500/15 text-emerald-300 border border-emerald-500/30',
  INACTIVE:
    'bg-amber-500/15 text-amber-300 border border-amber-500/30',
  ARCHIVED:
    'bg-slate-600/20 text-slate-400 border border-slate-600/30',
};

const statusDot: Record<PatientStatus, string> = {
  ACTIVE: 'bg-emerald-400',
  INACTIVE: 'bg-amber-400',
  ARCHIVED: 'bg-slate-500',
};

interface PatientsListClientProps {
  initialPatients: PatientView[];
}

export default function PatientsListClient({ initialPatients }: PatientsListClientProps) {
  const router = useRouter();
  const [query, setQuery] = useState('');
  const [statusFilter, setStatusFilter] = useState<'ALL' | PatientStatus>('ALL');
  // Insurance verification filter. Tri-state `insuranceVerified` on the
  // patient row (true/false/null) maps to our three discriminating labels:
  //   VERIFIED = true, UNVERIFIED = false, PENDING = null/undefined.
  const [insuranceFilter, setInsuranceFilter] = useState<
    'ALL' | 'VERIFIED' | 'UNVERIFIED' | 'PENDING'
  >('ALL');
  const [showAddModal, setShowAddModal] = useState(false);
  const [openKebabId, setOpenKebabId] = useState<string | null>(null);
  const [archivingId, setArchivingId] = useState<string | null>(null);
  const [isArchivePending, startArchiveTransition] = useTransition();
  const [toast, setToast] = useState<{ message: string; type: 'success' | 'error' } | null>(null);
  const kebabRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!openKebabId) return;
    const handler = (e: MouseEvent) => {
      if (kebabRef.current && !kebabRef.current.contains(e.target as Node)) {
        setOpenKebabId(null);
      }
    };
    document.addEventListener('mousedown', handler);
    return () => document.removeEventListener('mousedown', handler);
  }, [openKebabId]);

  useEffect(() => {
    if (!toast) return;
    const t = setTimeout(() => setToast(null), 3000);
    return () => clearTimeout(t);
  }, [toast]);

  const handleArchive = (patient: PatientView) => {
    setOpenKebabId(null);
    const confirmed = window.confirm(
      `Archive ${patient.firstName} ${patient.lastName}? They will be hidden from active views but the record is retained for HIPAA retention.`
    );
    if (!confirmed) return;
    setArchivingId(patient.id);
    startArchiveTransition(async () => {
      const result = await archivePatientAction(patient.id);
      setArchivingId(null);
      if (result.ok) {
        setToast({ message: 'Patient archived', type: 'success' });
        router.refresh();
      } else {
        setToast({ message: result.error || 'Failed to archive patient', type: 'error' });
      }
    });
  };

  const filtered = useMemo(() => {
    let result = initialPatients;
    if (query.trim()) {
      const q = query.toLowerCase();
      result = result.filter(
        (p) =>
          p.firstName.toLowerCase().includes(q) ||
          p.lastName.toLowerCase().includes(q) ||
          p.mrn.toLowerCase().includes(q) ||
          // drChronoId + chartId + cellPhone became optional — null-guard
          // before calling .toLowerCase()/.includes().
          (p.drChronoId?.toLowerCase().includes(q) ?? false) ||
          (p.chartId?.toLowerCase().includes(q) ?? false) ||
          (p.cellPhone?.toLowerCase().includes(q) ?? false) ||
          p.tags.some((t) => t.toLowerCase().includes(q))
      );
    }
    if (statusFilter !== 'ALL') {
      result = result.filter((p) => p.status === statusFilter);
    }
    if (insuranceFilter !== 'ALL') {
      result = result.filter((p) => {
        if (insuranceFilter === 'VERIFIED') return p.insuranceVerified === true;
        if (insuranceFilter === 'UNVERIFIED') return p.insuranceVerified === false;
        // PENDING = null/undefined (never been checked).
        return p.insuranceVerified === undefined || p.insuranceVerified === null;
      });
    }
    return result;
  }, [query, statusFilter, insuranceFilter, initialPatients]);

  const totalActive = initialPatients.filter((p) => p.status === 'ACTIVE').length;

  // Count patients seen within the last 7 days. The "now" reference is
  // captured once on mount via useState's lazy initializer — re-renders
  // reuse the same window so React's purity rule is satisfied. If
  // initialPatients changes during the session (router.refresh), we
  // recompute against the same window, which is correct behavior for
  // a stats card that doesn't auto-tick.
  const [weekCount] = useState(() => {
    const sevenDaysAgo = Date.now() - 7 * 24 * 60 * 60 * 1000;
    return initialPatients.filter(
      (p) => new Date(p.lastVisit).getTime() >= sevenDaysAgo
    ).length;
  });

  return (
    <div className="relative min-h-screen overflow-hidden bg-[#0A192F]">
      {/* ====== TOAST ====== */}
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

      {/* ====== AMBIENT GLOWS ====== */}
      <div className="absolute top-[5%] -left-[150px] w-[500px] h-[500px] rounded-full bg-blue-500 opacity-30 blur-[120px] pointer-events-none z-0" />
      <div className="absolute top-[10%] -right-[100px] w-[450px] h-[450px] rounded-full bg-teal-400 opacity-20 blur-[120px] pointer-events-none z-0" />
      <div className="absolute bottom-[5%] left-[20%] w-[600px] h-[600px] rounded-full bg-violet-600 opacity-15 blur-[140px] pointer-events-none z-0" />

      {/* ====== MAIN CONTENT ====== */}
      <div className="relative z-10 mx-auto max-w-7xl px-4 sm:px-6 lg:px-8 py-8">
        {/* Header */}
        <motion.div
          initial={{ opacity: 0, y: -10 }}
          animate={{ opacity: 1, y: 0 }}
          className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4 mb-8"
        >
          <div>
            <div className="flex items-center gap-3 mb-1">
              <div className="p-2 rounded-xl bg-gradient-to-br from-blue-500/20 to-teal-500/20 border border-blue-500/30">
                <Users className="w-5 h-5 text-blue-300" />
              </div>
              <h1 className="text-2xl font-bold text-white">Patients</h1>
            </div>
            <p className="text-sm text-slate-400 ml-12">
              {totalActive} active &middot; {initialPatients.length} total in your CRM
            </p>
          </div>

          <button
            onClick={() => setShowAddModal(true)}
            className="inline-flex items-center gap-2 px-4 py-2 rounded-xl bg-gradient-to-r from-blue-500 to-teal-500 text-white text-sm font-semibold shadow-lg shadow-blue-500/25 hover:shadow-blue-500/40 hover:scale-[1.02] transition-all cursor-pointer"
          >
            <Plus className="w-4 h-4" />
            Add Patient
          </button>
        </motion.div>

        {/* Stats row */}
        <motion.div
          initial={{ opacity: 0, y: 10 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.05 }}
          className="grid grid-cols-3 gap-3 mb-6"
        >
          <div className="rounded-xl bg-white/5 backdrop-blur-md border border-white/10 p-4">
            <div className="flex items-center gap-2 text-emerald-300/80 text-[11px] uppercase tracking-wider font-semibold">
              <Activity className="w-3 h-3" />
              Active
            </div>
            <p className="text-2xl font-bold text-white mt-1">{totalActive}</p>
          </div>
          <div className="rounded-xl bg-white/5 backdrop-blur-md border border-white/10 p-4">
            <div className="flex items-center gap-2 text-amber-300/80 text-[11px] uppercase tracking-wider font-semibold">
              <Calendar className="w-3 h-3" />
              This Week
            </div>
            <p className="text-2xl font-bold text-white mt-1">{weekCount}</p>
          </div>
          <div className="rounded-xl bg-white/5 backdrop-blur-md border border-white/10 p-4">
            <div className="flex items-center gap-2 text-blue-300/80 text-[11px] uppercase tracking-wider font-semibold">
              <Sparkles className="w-3 h-3" />
              Notes (30d)
            </div>
            <p className="text-2xl font-bold text-white mt-1">
              {initialPatients.reduce((sum, p) => sum + p.recentNotes.length, 0)}
            </p>
          </div>
        </motion.div>

        {/* Search + filters bar */}
        <motion.div
          initial={{ opacity: 0, y: 10 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.1 }}
          className="rounded-xl bg-white/5 backdrop-blur-md border border-white/10 p-3 mb-4 flex flex-col sm:flex-row gap-3"
        >
          <div className="flex-1 flex items-center gap-2 px-3 py-2 rounded-lg bg-slate-900/50 border border-white/5 focus-within:border-blue-500/50 transition-colors">
            <Search className="w-4 h-4 text-slate-400 shrink-0" />
            <input
              type="text"
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              placeholder="Search patients by name, MRN, Chart ID, phone, or tag..."
              className="flex-1 bg-transparent text-white placeholder-slate-500 text-sm outline-none"
            />
          </div>
          <div className="flex items-center gap-1 p-1 rounded-lg bg-slate-900/50 border border-white/5">
            {(['ALL', 'ACTIVE', 'INACTIVE', 'ARCHIVED'] as const).map((s) => (
              <button
                key={s}
                onClick={() => setStatusFilter(s)}
                className={`px-3 py-1.5 rounded-md text-xs font-medium transition-all cursor-pointer ${
                  statusFilter === s
                    ? 'bg-white/10 text-white'
                    : 'text-slate-400 hover:text-white'
                }`}
              >
                {s === 'ALL' ? 'All' : s.charAt(0) + s.slice(1).toLowerCase()}
              </button>
            ))}
          </div>
          {/* Insurance filter chips. Tri-state + All so doctors can
              quickly sort patients needing verification vs. already
              cleared vs. not yet checked. */}
          <div className="flex items-center gap-1 p-1 rounded-lg bg-slate-900/50 border border-white/5">
            {(
              [
                { key: 'ALL', label: 'All ins.', icon: Shield },
                { key: 'VERIFIED', label: 'Verified', icon: ShieldCheck },
                { key: 'UNVERIFIED', label: 'Unverified', icon: ShieldAlert },
                { key: 'PENDING', label: 'Pending', icon: Shield },
              ] as const
            ).map(({ key, label, icon: Icon }) => (
              <button
                key={key}
                onClick={() => setInsuranceFilter(key)}
                title={`Insurance: ${label}`}
                className={`inline-flex items-center gap-1.5 px-2.5 py-1.5 rounded-md text-xs font-medium transition-all cursor-pointer ${
                  insuranceFilter === key
                    ? key === 'VERIFIED'
                      ? 'bg-emerald-500/20 text-emerald-300'
                      : key === 'UNVERIFIED'
                        ? 'bg-red-500/20 text-red-300'
                        : key === 'PENDING'
                          ? 'bg-slate-500/20 text-slate-200'
                          : 'bg-white/10 text-white'
                    : 'text-slate-400 hover:text-white'
                }`}
              >
                <Icon className="w-3 h-3" />
                {label}
              </button>
            ))}
          </div>
          <button className="px-3 py-2 rounded-lg border border-white/10 hover:border-white/20 text-slate-300 hover:text-white text-xs font-medium flex items-center gap-1.5 transition-colors cursor-pointer">
            <Filter className="w-3.5 h-3.5" />
            More
          </button>
        </motion.div>

        {/* Patient Table */}
        <motion.div
          initial={{ opacity: 0, y: 10 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.15 }}
          className="rounded-xl bg-white/5 backdrop-blur-md border border-white/10 overflow-hidden"
        >
          {/* Table Header */}
          <div className="grid grid-cols-12 gap-4 px-5 py-3 border-b border-white/10 bg-white/[0.02]">
            <div className="col-span-3 text-[11px] font-semibold uppercase tracking-wider text-slate-500">
              Patient
            </div>
            <div className="col-span-2 text-[11px] font-semibold uppercase tracking-wider text-slate-500">
              Chart ID
            </div>
            <div className="col-span-2 text-[11px] font-semibold uppercase tracking-wider text-slate-500">
              Cell Phone
            </div>
            <div className="col-span-1 text-[11px] font-semibold uppercase tracking-wider text-slate-500">
              Born
            </div>
            <div className="col-span-2 text-[11px] font-semibold uppercase tracking-wider text-slate-500">
              Last Visit
            </div>
            <div className="col-span-1 text-[11px] font-semibold uppercase tracking-wider text-slate-500">
              Status
            </div>
            <div className="col-span-1" />
          </div>

          {/* Table Body */}
          <div className="divide-y divide-white/5">
            {filtered.length === 0 ? (
              <div className="px-5 py-16 text-center">
                <Users className="w-10 h-10 text-slate-600 mx-auto mb-3" />
                <p className="text-sm text-slate-400">No patients match your search</p>
                <p className="text-xs text-slate-500 mt-1">
                  Try a different name or clear filters
                </p>
              </div>
            ) : (
              filtered.map((patient, idx) => (
                <motion.div
                  key={patient.id}
                  initial={{ opacity: 0, x: -10 }}
                  animate={{ opacity: 1, x: 0 }}
                  transition={{ delay: 0.02 * idx }}
                >
                  <Link
                    href={`/dashboard/patients/${patient.id}`}
                    className="grid grid-cols-12 gap-4 px-5 py-4 items-center group hover:bg-white/[0.04] transition-colors cursor-pointer"
                  >
                    {/* Name + avatar */}
                    <div className="col-span-3 flex items-center gap-3 min-w-0">
                      <div
                        className={`shrink-0 w-10 h-10 rounded-full flex items-center justify-center text-sm font-bold border ${
                          patient.status === 'ACTIVE'
                            ? 'bg-gradient-to-br from-blue-500/30 to-teal-500/30 border-blue-500/40 text-white'
                            : 'bg-slate-700/50 border-white/10 text-slate-400'
                        }`}
                      >
                        {patient.firstName[0]}
                        {patient.lastName[0]}
                      </div>
                      <div className="min-w-0">
                        <p className="text-sm font-semibold text-white truncate">
                          {patient.firstName} {patient.lastName}
                        </p>
                        <div className="flex items-center gap-2 mt-0.5 flex-wrap">
                          <span className="text-[10px] text-slate-500 font-mono">
                            {patient.mrn || '—'}
                          </span>
                          {/* Insurance verification badge — three states:
                              verified (green), unverified (red), pending
                              (slate). Tooltip carries the label for a11y. */}
                          {patient.insuranceVerified === true ? (
                            <span
                              title="Insurance verified"
                              className="inline-flex items-center gap-0.5 text-[10px] px-1.5 py-0.5 rounded bg-emerald-500/10 text-emerald-300 border border-emerald-500/20"
                            >
                              <ShieldCheck className="w-3 h-3" />
                              Insurance
                            </span>
                          ) : patient.insuranceVerified === false ? (
                            <span
                              title="Insurance NOT verified"
                              className="inline-flex items-center gap-0.5 text-[10px] px-1.5 py-0.5 rounded bg-red-500/10 text-red-300 border border-red-500/20"
                            >
                              <ShieldAlert className="w-3 h-3" />
                              Unverified
                            </span>
                          ) : (
                            <span
                              title="Insurance verification pending"
                              className="inline-flex items-center gap-0.5 text-[10px] px-1.5 py-0.5 rounded bg-slate-500/10 text-slate-400 border border-slate-500/20"
                            >
                              <Shield className="w-3 h-3" />
                              Pending
                            </span>
                          )}
                          {patient.tags[0] && (
                            <span className="text-[10px] px-1.5 py-0.5 rounded bg-white/5 text-slate-400 border border-white/5">
                              {patient.tags[0]}
                            </span>
                          )}
                        </div>
                      </div>
                    </div>

                    {/* Chart ID */}
                    <div className="col-span-2 min-w-0">
                      <p className="text-sm font-mono text-slate-300 truncate">
                        {patient.chartId || '—'}
                      </p>
                    </div>

                    {/* Cell phone */}
                    <div className="col-span-2 min-w-0">
                      <p className="text-sm font-mono text-slate-300 truncate">
                        {patient.cellPhone || (patient.phoneLast4 ? `•••-${patient.phoneLast4}` : '—')}
                      </p>
                    </div>

                    {/* Birth year (de-identified) — "—" when not recorded */}
                    <div className="col-span-1">
                      <p className="text-sm text-slate-300">
                        {patient.birthYear ?? '—'}
                      </p>
                    </div>

                    {/* Last visit */}
                    <div className="col-span-2">
                      <p className="text-sm text-slate-300">
                        {formatLastVisit(patient.lastVisit)}
                      </p>
                      <p className="text-[10px] text-slate-500">
                        {formatRelativeDate(patient.lastVisit)}
                      </p>
                    </div>

                    {/* Status */}
                    <div className="col-span-1">
                      <span
                        className={`inline-flex items-center gap-1.5 px-2 py-0.5 rounded-full text-[10px] font-semibold uppercase tracking-wider ${statusStyles[patient.status]}`}
                      >
                        <span className={`w-1.5 h-1.5 rounded-full ${statusDot[patient.status]}`} />
                        {patient.status}
                      </span>
                    </div>

                    {/* Kebab menu + chevron */}
                    <div className="col-span-1 flex justify-end items-center gap-1 relative">
                      <button
                        type="button"
                        aria-label="Patient actions"
                        onClick={(e) => {
                          e.preventDefault();
                          e.stopPropagation();
                          setOpenKebabId(openKebabId === patient.id ? null : patient.id);
                        }}
                        disabled={archivingId === patient.id}
                        className="p-1.5 rounded-md text-slate-500 hover:text-white hover:bg-white/10 transition-colors cursor-pointer disabled:opacity-50"
                      >
                        {archivingId === patient.id && isArchivePending ? (
                          <Loader2 className="w-4 h-4 animate-spin" />
                        ) : (
                          <MoreVertical className="w-4 h-4" />
                        )}
                      </button>
                      <ChevronRight className="w-4 h-4 text-slate-500 group-hover:text-blue-400 group-hover:translate-x-0.5 transition-all" />

                      {openKebabId === patient.id && (
                        <div
                          ref={kebabRef}
                          onClick={(e) => {
                            e.preventDefault();
                            e.stopPropagation();
                          }}
                          className="absolute top-full right-0 mt-1 z-20 min-w-[180px] rounded-lg bg-slate-900/95 backdrop-blur-md border border-white/10 shadow-xl shadow-black/40 overflow-hidden"
                        >
                          <button
                            type="button"
                            onClick={(e) => {
                              e.preventDefault();
                              e.stopPropagation();
                              handleArchive(patient);
                            }}
                            disabled={patient.status === 'ARCHIVED'}
                            className="w-full flex items-center gap-2 px-3 py-2 text-xs text-amber-300 hover:bg-amber-500/10 transition-colors cursor-pointer disabled:opacity-40 disabled:cursor-not-allowed"
                          >
                            <Archive className="w-3.5 h-3.5" />
                            {patient.status === 'ARCHIVED' ? 'Already archived' : 'Archive patient'}
                          </button>
                        </div>
                      )}
                    </div>
                  </Link>
                </motion.div>
              ))
            )}
          </div>
        </motion.div>

        {/* Footer count */}
        <p className="text-xs text-slate-500 mt-4 text-center">
          Showing {filtered.length} of {initialPatients.length} patients
        </p>
      </div>

      {/* Add Patient Modal */}
      <AddPatientModal
        open={showAddModal}
        onClose={() => setShowAddModal(false)}
      />
    </div>
  );
}
