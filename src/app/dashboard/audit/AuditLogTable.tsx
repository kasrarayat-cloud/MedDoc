'use client';

// ============================================================================
// Audit Log Table — Glassmorphism Data Table with Search & Filters
// ============================================================================

import { useState, useMemo } from 'react';
import { motion } from 'framer-motion';
import {
  Shield,
  Search,
  CheckCircle2,
  XCircle,
  Eye,
  UserPlus,
  Pencil,
  Calendar,
  FileText,
  Activity,
  Sparkles,
  Trash2,
  LogIn,
  LogOut,
  Users,
  Download,
} from 'lucide-react';

import type { AuditLogView } from '@/lib/audit';

interface AuditLogTableProps {
  logs: AuditLogView[];
}

// Action → badge color + human label + icon
const ACTION_CONFIG: Record<
  string,
  { label: string; color: string; icon: typeof Eye }
> = {
  // View actions — blue
  VIEWED_PATIENT_LIST: { label: 'Viewed Patient List', color: 'bg-blue-500/15 text-blue-300 border-blue-500/30', icon: Users },
  VIEWED_PATIENT_FILE: { label: 'Viewed Patient File', color: 'bg-blue-500/15 text-blue-300 border-blue-500/30', icon: Eye },
  VIEWED_DOCUMENT: { label: 'Viewed Document', color: 'bg-blue-500/15 text-blue-300 border-blue-500/30', icon: Eye },

  // Create actions — green
  CREATED_PATIENT: { label: 'Created Patient', color: 'bg-emerald-500/15 text-emerald-300 border-emerald-500/30', icon: UserPlus },
  CREATED_CLINICAL_NOTE: { label: 'Created Clinical Note', color: 'bg-emerald-500/15 text-emerald-300 border-emerald-500/30', icon: Sparkles },
  CREATED_DOCUMENT: { label: 'Created Document', color: 'bg-emerald-500/15 text-emerald-300 border-emerald-500/30', icon: FileText },
  GENERATED_DRAFT_DOCUMENT: { label: 'Generated Draft', color: 'bg-emerald-500/15 text-emerald-300 border-emerald-500/30', icon: Sparkles },

  // Edit actions — amber
  UPDATED_PATIENT: { label: 'Updated Patient', color: 'bg-amber-500/15 text-amber-300 border-amber-500/30', icon: Pencil },
  EDITED_NOTE: { label: 'Edited Note', color: 'bg-amber-500/15 text-amber-300 border-amber-500/30', icon: Pencil },

  // Schedule — teal
  SCHEDULED_VISIT: { label: 'Scheduled Visit', color: 'bg-teal-500/15 text-teal-300 border-teal-500/30', icon: Calendar },

  // Delete / archive — red-ish
  ARCHIVED_PATIENT: { label: 'Archived Patient', color: 'bg-orange-500/15 text-orange-300 border-orange-500/30', icon: Trash2 },
  DELETED_DOCUMENT: { label: 'Deleted Document', color: 'bg-red-500/15 text-red-300 border-red-500/30', icon: Trash2 },

  // Auth — slate/violet
  LOGIN_SUCCESS: { label: 'Login Success', color: 'bg-violet-500/15 text-violet-300 border-violet-500/30', icon: LogIn },
  LOGIN_FAILED: { label: 'Login Failed', color: 'bg-red-500/15 text-red-300 border-red-500/30', icon: LogIn },
  LOGOUT: { label: 'Logout', color: 'bg-slate-500/15 text-slate-300 border-slate-500/30', icon: LogOut },

  // User admin
  USER_UPDATED: { label: 'User Updated', color: 'bg-amber-500/15 text-amber-300 border-amber-500/30', icon: Pencil },
  USER_DELETED: { label: 'User Deleted', color: 'bg-red-500/15 text-red-300 border-red-500/30', icon: Trash2 },
  PASSWORD_RESET_BY_ADMIN: { label: 'Password Reset (Admin)', color: 'bg-orange-500/15 text-orange-300 border-orange-500/30', icon: Shield },

  // Misc
  DOWNLOADED_DOCUMENT: { label: 'Downloaded Document', color: 'bg-blue-500/15 text-blue-300 border-blue-500/30', icon: Download },
  UPLOADED_TO_DROPBOX: { label: 'Uploaded to Dropbox', color: 'bg-blue-500/15 text-blue-300 border-blue-500/30', icon: Download },
  EXPORTED_AUDIT_LOG: { label: 'Exported Audit Log', color: 'bg-slate-500/15 text-slate-300 border-slate-500/30', icon: Shield },
};

function getActionConfig(action: string) {
  return (
    ACTION_CONFIG[action] ?? {
      label: action.replace(/_/g, ' '),
      color: 'bg-slate-500/15 text-slate-300 border-slate-500/30',
      icon: Activity,
    }
  );
}

function formatTimestamp(iso: string): string {
  const d = new Date(iso);
  return d.toLocaleDateString('en-US', {
    month: 'short',
    day: 'numeric',
    year: 'numeric',
  }) +
    ' - ' +
    d.toLocaleTimeString('en-US', {
      hour: '2-digit',
      minute: '2-digit',
      second: '2-digit',
    });
}

function truncateId(id: string | null): string {
  if (!id) return '-';
  return id.length > 16 ? id.slice(0, 14) + '...' : id;
}

export default function AuditLogTable({ logs }: AuditLogTableProps) {
  const [searchQuery, setSearchQuery] = useState('');
  const [statusFilter, setStatusFilter] = useState<'all' | 'success' | 'failure'>('all');

  const filtered = useMemo(() => {
    let result = logs;

    // Status filter
    if (statusFilter === 'success') result = result.filter((l) => l.success);
    if (statusFilter === 'failure') result = result.filter((l) => !l.success);

    // Text search
    if (searchQuery.trim()) {
      const q = searchQuery.toLowerCase();
      result = result.filter(
        (l) =>
          l.action.toLowerCase().includes(q) ||
          (l.userEmail ?? '').toLowerCase().includes(q) ||
          (l.userId ?? '').toLowerCase().includes(q) ||
          (l.targetType ?? '').toLowerCase().includes(q) ||
          (l.targetId ?? '').toLowerCase().includes(q) ||
          getActionConfig(l.action).label.toLowerCase().includes(q)
      );
    }

    return result;
  }, [logs, searchQuery, statusFilter]);

  const successCount = logs.filter((l) => l.success).length;
  const failureCount = logs.filter((l) => !l.success).length;

  return (
    <div className="relative min-h-screen overflow-hidden bg-[#0A192F]">
      {/* Ambient glows */}
      <div className="absolute top-[5%] -left-[150px] w-[500px] h-[500px] rounded-full bg-blue-500 opacity-20 blur-[120px] pointer-events-none z-0" />
      <div className="absolute bottom-[10%] -right-[100px] w-[400px] h-[400px] rounded-full bg-violet-500 opacity-15 blur-[120px] pointer-events-none z-0" />

      <div className="relative z-10 mx-auto max-w-7xl px-4 sm:px-6 lg:px-8 py-8">
        {/* Header */}
        <motion.div
          initial={{ opacity: 0, y: -10 }}
          animate={{ opacity: 1, y: 0 }}
          className="mb-6"
        >
          <div className="flex items-center gap-3 mb-1">
            <div className="p-2 rounded-xl bg-gradient-to-br from-amber-500/20 to-orange-500/20 border border-amber-500/30">
              <Shield className="w-6 h-6 text-amber-300" />
            </div>
            <div>
              <h1 className="text-2xl font-bold text-white">Audit Logs</h1>
              <p className="text-sm text-slate-400">
                HIPAA §164.312(b) compliance trail — {logs.length} total events
              </p>
            </div>
          </div>
        </motion.div>

        {/* Summary + Search Bar */}
        <motion.div
          initial={{ opacity: 0, y: -5 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.05 }}
          className="rounded-2xl bg-white/5 backdrop-blur-md border border-white/10 p-4 mb-6"
        >
          <div className="flex flex-col sm:flex-row items-start sm:items-center gap-4">
            {/* Search */}
            <div className="relative flex-1 w-full">
              <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-slate-500" />
              <input
                type="text"
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                placeholder="Search by action, user, or target..."
                className="w-full pl-10 pr-4 py-2.5 rounded-xl bg-white/5 border border-white/10 text-sm text-white placeholder-slate-500 outline-none focus:border-blue-400/50 focus:ring-1 focus:ring-blue-400/20 transition-colors"
              />
            </div>

            {/* Status filter pills */}
            <div className="flex items-center gap-2 shrink-0">
              <button
                onClick={() => setStatusFilter('all')}
                className={`px-3 py-1.5 rounded-lg text-[11px] font-semibold uppercase tracking-wider border transition-all cursor-pointer ${
                  statusFilter === 'all'
                    ? 'bg-white/10 border-white/20 text-white'
                    : 'bg-transparent border-white/5 text-slate-500 hover:text-slate-300'
                }`}
              >
                All ({logs.length})
              </button>
              <button
                onClick={() => setStatusFilter('success')}
                className={`px-3 py-1.5 rounded-lg text-[11px] font-semibold uppercase tracking-wider border transition-all cursor-pointer ${
                  statusFilter === 'success'
                    ? 'bg-emerald-500/15 border-emerald-500/30 text-emerald-300'
                    : 'bg-transparent border-white/5 text-slate-500 hover:text-slate-300'
                }`}
              >
                Success ({successCount})
              </button>
              <button
                onClick={() => setStatusFilter('failure')}
                className={`px-3 py-1.5 rounded-lg text-[11px] font-semibold uppercase tracking-wider border transition-all cursor-pointer ${
                  statusFilter === 'failure'
                    ? 'bg-red-500/15 border-red-500/30 text-red-300'
                    : 'bg-transparent border-white/5 text-slate-500 hover:text-slate-300'
                }`}
              >
                Failed ({failureCount})
              </button>
            </div>
          </div>
        </motion.div>

        {/* Table */}
        <motion.div
          initial={{ opacity: 0, y: 10 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.1 }}
          className="rounded-2xl bg-white/5 backdrop-blur-md border border-white/10 overflow-hidden"
        >
          {/* Table header */}
          <div className="hidden md:grid grid-cols-12 gap-3 px-5 py-3 border-b border-white/10 text-[10px] font-semibold text-slate-500 uppercase tracking-wider">
            <div className="col-span-3">Timestamp</div>
            <div className="col-span-2">User</div>
            <div className="col-span-3">Action</div>
            <div className="col-span-3">Target</div>
            <div className="col-span-1 text-center">Status</div>
          </div>

          {filtered.length === 0 ? (
            <div className="py-20 text-center">
              <Shield className="w-10 h-10 text-slate-600 mx-auto mb-3" />
              <p className="text-sm text-slate-400">
                {searchQuery ? 'No logs match your search.' : 'No audit logs recorded yet.'}
              </p>
            </div>
          ) : (
            <div className="divide-y divide-white/5 max-h-[65vh] overflow-y-auto">
              {filtered.map((log) => {
                const config = getActionConfig(log.action);
                const Icon = config.icon;

                return (
                  <div
                    key={log.id}
                    className={`grid grid-cols-1 md:grid-cols-12 gap-2 md:gap-3 px-5 py-3 hover:bg-white/5 transition-colors ${
                      !log.success ? 'bg-red-500/5' : ''
                    }`}
                  >
                    {/* Timestamp */}
                    <div className="md:col-span-3 flex items-center gap-2">
                      <span className="text-xs font-mono text-slate-400">
                        {formatTimestamp(log.timestamp)}
                      </span>
                    </div>

                    {/* User */}
                    <div className="md:col-span-2 flex items-center gap-2 min-w-0">
                      <div className="w-6 h-6 rounded-full bg-gradient-to-br from-blue-500/30 to-teal-500/30 border border-blue-500/20 flex items-center justify-center shrink-0">
                        <span className="text-[9px] font-bold text-white">
                          {(log.userEmail ?? 'S')[0].toUpperCase()}
                        </span>
                      </div>
                      <span className="text-xs text-slate-300 truncate">
                        {log.userEmail || truncateId(log.userId)}
                      </span>
                    </div>

                    {/* Action badge */}
                    <div className="md:col-span-3 flex items-center">
                      <span
                        className={`inline-flex items-center gap-1.5 px-2 py-1 rounded-md text-[10px] font-semibold border ${config.color}`}
                      >
                        <Icon className="w-3 h-3" />
                        {config.label}
                      </span>
                    </div>

                    {/* Target */}
                    <div className="md:col-span-3 flex items-center gap-1.5 min-w-0">
                      {log.targetType && (
                        <span className="text-[10px] px-1.5 py-0.5 rounded bg-white/5 text-slate-400 border border-white/5 shrink-0">
                          {log.targetType}
                        </span>
                      )}
                      <span className="text-xs font-mono text-slate-500 truncate">
                        {truncateId(log.targetId)}
                      </span>
                    </div>

                    {/* Status */}
                    <div className="md:col-span-1 flex items-center justify-center">
                      {log.success ? (
                        <CheckCircle2 className="w-4 h-4 text-emerald-400" />
                      ) : (
                        <div className="flex items-center gap-1">
                          <XCircle className="w-4 h-4 text-red-400" />
                          {log.errorCode && (
                            <span className="text-[9px] text-red-400 font-mono hidden lg:inline">
                              {log.errorCode}
                            </span>
                          )}
                        </div>
                      )}
                    </div>
                  </div>
                );
              })}
            </div>
          )}

          {/* Footer */}
          <div className="px-5 py-3 border-t border-white/10 flex items-center justify-between">
            <p className="text-[10px] text-slate-500">
              Showing {filtered.length} of {logs.length} events
            </p>
            <p className="text-[10px] text-slate-500 italic">
              Immutable append-only trail — HIPAA §164.312(b)
            </p>
          </div>
        </motion.div>
      </div>
    </div>
  );
}
