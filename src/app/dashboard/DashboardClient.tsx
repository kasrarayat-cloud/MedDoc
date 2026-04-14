'use client';

// ============================================================================
// Dashboard Client — Analytics & Overview
// ============================================================================

import Link from 'next/link';
import { motion } from 'framer-motion';
import {
  Users,
  FileText,
  Calendar,
  CalendarDays,
  Activity,
  ArrowRight,
  Shield,
  Sparkles,
  UserPlus,
  Eye,
  Pencil,
} from 'lucide-react';

import type { CalendarAppointment } from '@/lib/data/appointments';

interface DashboardClientProps {
  doctorName: string;
  totalPatients: number;
  totalNotes: number;
  todayAppointmentCount: number;
  totalAppointments: number;
  upcomingAppointments: CalendarAppointment[];
  recentActivity: {
    action: string;
    targetType: string;
    targetId: string;
    timestamp: string;
    success: boolean;
  }[];
}

const fadeUp = {
  hidden: { opacity: 0, y: 15 },
  visible: { opacity: 1, y: 0 },
};

const stagger = {
  hidden: { opacity: 0 },
  visible: {
    opacity: 1,
    transition: { staggerChildren: 0.08, delayChildren: 0.05 },
  },
};

// Map audit actions to human-readable labels + icons
const ACTION_LABELS: Record<string, { label: string; icon: typeof Eye; color: string }> = {
  VIEWED_PATIENT_FILE: { label: 'Viewed patient record', icon: Eye, color: 'text-blue-400' },
  VIEWED_PATIENT_LIST: { label: 'Viewed patient list', icon: Users, color: 'text-blue-400' },
  CREATED_PATIENT: { label: 'Added new patient', icon: UserPlus, color: 'text-emerald-400' },
  UPDATED_PATIENT: { label: 'Updated patient record', icon: Pencil, color: 'text-amber-400' },
  CREATED_CLINICAL_NOTE: { label: 'Generated clinical note', icon: Sparkles, color: 'text-violet-400' },
  EDITED_NOTE: { label: 'Edited clinical note', icon: Pencil, color: 'text-amber-400' },
  GENERATED_DRAFT_DOCUMENT: { label: 'Generated document draft', icon: FileText, color: 'text-teal-400' },
  SCHEDULED_VISIT: { label: 'Scheduled visit', icon: Calendar, color: 'text-emerald-400' },
  LOGIN_SUCCESS: { label: 'Logged in', icon: Shield, color: 'text-blue-400' },
  LOGIN_FAILED: { label: 'Failed login attempt', icon: Shield, color: 'text-red-400' },
};

const VISIT_TYPE_LABELS: Record<string, { label: string; color: string }> = {
  CONSULTATION: { label: 'Consultation', color: 'text-blue-300 bg-blue-500/15 border-blue-500/30' },
  FOLLOW_UP: { label: 'Follow-up', color: 'text-emerald-300 bg-emerald-500/15 border-emerald-500/30' },
  PROCEDURE: { label: 'Procedure', color: 'text-violet-300 bg-violet-500/15 border-violet-500/30' },
};

function formatTime(iso: string): string {
  return new Date(iso).toLocaleTimeString('en-US', { hour: 'numeric', minute: '2-digit' });
}

function formatRelative(iso: string): string {
  const diff = Date.now() - new Date(iso).getTime();
  const mins = Math.floor(diff / 60000);
  if (mins < 1) return 'Just now';
  if (mins < 60) return `${mins}m ago`;
  const hours = Math.floor(mins / 60);
  if (hours < 24) return `${hours}h ago`;
  return `${Math.floor(hours / 24)}d ago`;
}

function isToday(iso: string): boolean {
  const d = new Date(iso);
  const t = new Date();
  return d.getFullYear() === t.getFullYear() && d.getMonth() === t.getMonth() && d.getDate() === t.getDate();
}

export default function DashboardClient({
  doctorName,
  totalPatients,
  totalNotes,
  todayAppointmentCount,
  totalAppointments,
  upcomingAppointments,
  recentActivity,
}: DashboardClientProps) {
  const firstName = doctorName.split(' ').pop() ?? doctorName;
  const greeting =
    new Date().getHours() < 12 ? 'Good morning' : new Date().getHours() < 18 ? 'Good afternoon' : 'Good evening';

  const stats = [
    {
      label: 'Active Patients',
      value: totalPatients,
      sub: 'In your CRM',
      icon: Users,
      gradient: 'from-blue-500 to-cyan-500',
      glow: 'bg-blue-500/20',
      href: '/dashboard/patients',
    },
    {
      label: 'Clinical Notes',
      value: totalNotes,
      sub: 'AI-generated notes',
      icon: FileText,
      gradient: 'from-violet-500 to-purple-500',
      glow: 'bg-violet-500/20',
      href: '/dashboard/patients',
    },
    {
      label: 'Today\'s Visits',
      value: todayAppointmentCount,
      sub: `${totalAppointments} total scheduled`,
      icon: CalendarDays,
      gradient: 'from-emerald-500 to-teal-500',
      glow: 'bg-emerald-500/20',
      href: '/dashboard/schedule',
    },
    {
      label: 'Audit Events',
      value: recentActivity.length,
      sub: 'Recent actions logged',
      icon: Shield,
      gradient: 'from-amber-500 to-orange-500',
      glow: 'bg-amber-500/20',
      href: '/dashboard/settings',
    },
  ];

  return (
    <div className="relative min-h-screen overflow-hidden bg-[#0A192F]">
      {/* Ambient glows */}
      <div className="absolute top-[5%] -left-[150px] w-[500px] h-[500px] rounded-full bg-blue-500 opacity-20 blur-[120px] pointer-events-none z-0" />
      <div className="absolute top-[30%] -right-[100px] w-[450px] h-[450px] rounded-full bg-violet-500 opacity-15 blur-[120px] pointer-events-none z-0" />
      <div className="absolute bottom-[10%] left-[30%] w-[500px] h-[500px] rounded-full bg-teal-400 opacity-10 blur-[140px] pointer-events-none z-0" />

      <div className="relative z-10 mx-auto max-w-7xl px-4 sm:px-6 lg:px-8 py-8">
        {/* Header */}
        <motion.div
          initial={{ opacity: 0, y: -10 }}
          animate={{ opacity: 1, y: 0 }}
          className="mb-8"
        >
          <h1 className="text-3xl font-bold text-white">
            {greeting}, {firstName}
          </h1>
          <p className="text-sm text-slate-400 mt-1">
            {new Date().toLocaleDateString('en-US', {
              weekday: 'long',
              month: 'long',
              day: 'numeric',
              year: 'numeric',
            })}
          </p>
        </motion.div>

        {/* Stat Cards */}
        <motion.div
          variants={stagger}
          initial="hidden"
          animate="visible"
          className="grid grid-cols-1 sm:grid-cols-2 xl:grid-cols-4 gap-4 mb-8"
        >
          {stats.map((stat) => {
            const Icon = stat.icon;
            return (
              <motion.div key={stat.label} variants={fadeUp}>
                <Link
                  href={stat.href}
                  className="block rounded-2xl bg-white/5 backdrop-blur-md border border-white/10 p-5 hover:bg-white/8 hover:border-white/20 transition-all group relative overflow-hidden"
                >
                  {/* Top accent line */}
                  <div className={`absolute top-0 left-0 right-0 h-px bg-gradient-to-r ${stat.gradient} opacity-60`} />

                  <div className="flex items-start justify-between">
                    <div>
                      <p className="text-xs font-semibold text-slate-400 uppercase tracking-wider">
                        {stat.label}
                      </p>
                      <p className={`text-3xl font-bold mt-2 bg-gradient-to-r ${stat.gradient} bg-clip-text text-transparent`}>
                        {stat.value}
                      </p>
                      <p className="text-[11px] text-slate-500 mt-1">{stat.sub}</p>
                    </div>
                    <div className={`p-2.5 rounded-xl ${stat.glow} border border-white/5`}>
                      <Icon className="w-5 h-5 text-white/80" />
                    </div>
                  </div>

                  <ArrowRight className="absolute bottom-4 right-4 w-4 h-4 text-slate-600 group-hover:text-white/40 group-hover:translate-x-0.5 transition-all" />
                </Link>
              </motion.div>
            );
          })}
        </motion.div>

        {/* Two-column layout */}
        <div className="grid grid-cols-1 lg:grid-cols-5 gap-6">
          {/* Left: Today's Schedule (3/5) */}
          <motion.div
            initial={{ opacity: 0, y: 10 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.15 }}
            className="lg:col-span-3"
          >
            <div className="rounded-2xl bg-white/5 backdrop-blur-md border border-white/10 overflow-hidden">
              <div className="flex items-center justify-between px-5 py-4 border-b border-white/5">
                <div className="flex items-center gap-2">
                  <div className="p-1.5 rounded-lg bg-emerald-500/15 border border-emerald-500/30">
                    <CalendarDays className="w-4 h-4 text-emerald-300" />
                  </div>
                  <h2 className="text-sm font-semibold text-white uppercase tracking-wider">
                    Upcoming Visits
                  </h2>
                </div>
                <Link
                  href="/dashboard/schedule"
                  className="text-[11px] text-slate-400 hover:text-white flex items-center gap-1 transition-colors"
                >
                  View calendar <ArrowRight className="w-3 h-3" />
                </Link>
              </div>

              {upcomingAppointments.length === 0 ? (
                <div className="py-16 text-center">
                  <div className="inline-flex items-center justify-center w-12 h-12 rounded-2xl bg-emerald-500/10 border border-emerald-500/20 mb-3">
                    <CalendarDays className="w-6 h-6 text-emerald-400/60" />
                  </div>
                  <p className="text-sm text-slate-400">No upcoming visits</p>
                  <p className="text-xs text-slate-500 mt-1">
                    Schedule visits from patient detail pages.
                  </p>
                </div>
              ) : (
                <div className="divide-y divide-white/5">
                  {upcomingAppointments.map((apt) => {
                    const typeInfo = VISIT_TYPE_LABELS[apt.type] ?? VISIT_TYPE_LABELS.CONSULTATION;
                    const today = isToday(apt.scheduledAt);

                    return (
                      <Link
                        key={apt.id}
                        href={`/dashboard/patients/${apt.patientId}`}
                        className="flex items-center gap-4 px-5 py-3.5 hover:bg-white/5 transition-colors group"
                      >
                        {/* Time */}
                        <div className="w-16 shrink-0 text-right">
                          <p className={`text-sm font-mono font-semibold ${today ? 'text-emerald-300' : 'text-slate-300'}`}>
                            {formatTime(apt.scheduledAt)}
                          </p>
                          <p className="text-[9px] uppercase tracking-wider text-slate-500">
                            {today ? 'Today' : 'Tomorrow'}
                          </p>
                        </div>

                        {/* Divider dot */}
                        <div className={`w-2 h-2 rounded-full shrink-0 ${today ? 'bg-emerald-400' : 'bg-blue-400'}`} />

                        {/* Info */}
                        <div className="flex-1 min-w-0">
                          <p className="text-sm font-medium text-white truncate group-hover:underline decoration-white/20 underline-offset-2">
                            {apt.patientFirstName} {apt.patientLastName}
                          </p>
                          <div className="flex items-center gap-2 mt-0.5">
                            <span className={`text-[9px] px-1.5 py-0.5 rounded-full font-semibold uppercase tracking-wider border ${typeInfo.color}`}>
                              {typeInfo.label}
                            </span>
                            {apt.notes && (
                              <span className="text-[10px] text-slate-500 truncate">
                                {apt.notes}
                              </span>
                            )}
                          </div>
                        </div>

                        <ArrowRight className="w-3.5 h-3.5 text-slate-600 group-hover:text-white/40 shrink-0" />
                      </Link>
                    );
                  })}
                </div>
              )}
            </div>
          </motion.div>

          {/* Right: Recent Activity (2/5) */}
          <motion.div
            initial={{ opacity: 0, y: 10 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.2 }}
            className="lg:col-span-2"
          >
            <div className="rounded-2xl bg-white/5 backdrop-blur-md border border-white/10 overflow-hidden">
              <div className="flex items-center justify-between px-5 py-4 border-b border-white/5">
                <div className="flex items-center gap-2">
                  <div className="p-1.5 rounded-lg bg-amber-500/15 border border-amber-500/30">
                    <Activity className="w-4 h-4 text-amber-300" />
                  </div>
                  <h2 className="text-sm font-semibold text-white uppercase tracking-wider">
                    Recent Activity
                  </h2>
                </div>
                <span className="text-[9px] px-1.5 py-0.5 rounded bg-amber-500/10 border border-amber-500/20 text-amber-300 font-semibold uppercase">
                  HIPAA Log
                </span>
              </div>

              {recentActivity.length === 0 ? (
                <div className="py-16 text-center">
                  <div className="inline-flex items-center justify-center w-12 h-12 rounded-2xl bg-amber-500/10 border border-amber-500/20 mb-3">
                    <Activity className="w-6 h-6 text-amber-400/60" />
                  </div>
                  <p className="text-sm text-slate-400">No activity yet</p>
                  <p className="text-xs text-slate-500 mt-1">
                    Actions will appear here as you use the CRM.
                  </p>
                </div>
              ) : (
                <div className="divide-y divide-white/5">
                  {recentActivity.map((entry, i) => {
                    const info = ACTION_LABELS[entry.action] ?? {
                      label: entry.action.replace(/_/g, ' ').toLowerCase(),
                      icon: Activity,
                      color: 'text-slate-400',
                    };
                    const Icon = info.icon;

                    return (
                      <div
                        key={i}
                        className="flex items-center gap-3 px-5 py-3 hover:bg-white/5 transition-colors"
                      >
                        <div className={`shrink-0 p-1.5 rounded-lg bg-white/5 ${info.color}`}>
                          <Icon className="w-3.5 h-3.5" />
                        </div>
                        <div className="flex-1 min-w-0">
                          <p className="text-xs font-medium text-slate-300 truncate">
                            {info.label}
                          </p>
                          {entry.targetType && (
                            <p className="text-[10px] text-slate-500 truncate">
                              {entry.targetType}
                              {entry.targetId ? `: ${entry.targetId.slice(0, 12)}...` : ''}
                            </p>
                          )}
                        </div>
                        <div className="shrink-0 text-right">
                          <p className="text-[10px] text-slate-500">
                            {entry.timestamp ? formatRelative(entry.timestamp) : ''}
                          </p>
                          {!entry.success && (
                            <span className="text-[9px] text-red-400 font-semibold">FAILED</span>
                          )}
                        </div>
                      </div>
                    );
                  })}
                </div>
              )}
            </div>
          </motion.div>
        </div>

        {/* Quick Links */}
        <motion.div
          initial={{ opacity: 0, y: 10 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.25 }}
          className="mt-6 grid grid-cols-1 sm:grid-cols-3 gap-4"
        >
          <Link
            href="/dashboard/patients"
            className="flex items-center gap-4 px-5 py-4 rounded-xl bg-gradient-to-r from-blue-500/10 to-cyan-500/5 border border-blue-500/20 hover:border-blue-400/40 transition-all group"
          >
            <div className="p-2.5 rounded-lg bg-blue-500/20">
              <Users className="w-5 h-5 text-blue-300" />
            </div>
            <div>
              <p className="text-sm font-semibold text-white">Patient CRM</p>
              <p className="text-[11px] text-slate-400">Manage records & notes</p>
            </div>
            <ArrowRight className="w-4 h-4 text-slate-600 ml-auto group-hover:text-blue-300 group-hover:translate-x-0.5 transition-all" />
          </Link>

          <Link
            href="/dashboard/schedule"
            className="flex items-center gap-4 px-5 py-4 rounded-xl bg-gradient-to-r from-emerald-500/10 to-teal-500/5 border border-emerald-500/20 hover:border-emerald-400/40 transition-all group"
          >
            <div className="p-2.5 rounded-lg bg-emerald-500/20">
              <CalendarDays className="w-5 h-5 text-emerald-300" />
            </div>
            <div>
              <p className="text-sm font-semibold text-white">Schedule</p>
              <p className="text-[11px] text-slate-400">Calendar & appointments</p>
            </div>
            <ArrowRight className="w-4 h-4 text-slate-600 ml-auto group-hover:text-emerald-300 group-hover:translate-x-0.5 transition-all" />
          </Link>

          <Link
            href="/dashboard/doc-editor"
            className="flex items-center gap-4 px-5 py-4 rounded-xl bg-gradient-to-r from-violet-500/10 to-purple-500/5 border border-violet-500/20 hover:border-violet-400/40 transition-all group"
          >
            <div className="p-2.5 rounded-lg bg-violet-500/20">
              <Sparkles className="w-5 h-5 text-violet-300" />
            </div>
            <div>
              <p className="text-sm font-semibold text-white">AI Doc Editor</p>
              <p className="text-[11px] text-slate-400">Upload & edit with AI</p>
            </div>
            <ArrowRight className="w-4 h-4 text-slate-600 ml-auto group-hover:text-violet-300 group-hover:translate-x-0.5 transition-all" />
          </Link>
        </motion.div>
      </div>
    </div>
  );
}
