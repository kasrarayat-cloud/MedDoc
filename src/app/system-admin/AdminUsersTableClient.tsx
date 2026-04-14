'use client';

// ============================================================================
// Admin Users Table — Command Center with Live Actions
// ============================================================================

import { useState, useMemo, useTransition, useCallback } from 'react';
import Link from 'next/link';
import { useRouter } from 'next/navigation';
import { motion, AnimatePresence } from 'framer-motion';
import {
  Shield,
  Search,
  Users,
  Terminal,
  Activity,
  Clock,
  Globe,
  CheckCircle2,
  XCircle,
  MoreVertical,
  UserCog,
  Eye,
  Zap,
  ArrowLeft,
  Loader2,
  Power,
  PowerOff,
  UserPlus,
  Trash2,
  KeyRound,
} from 'lucide-react';

import {
  deactivateUserAction,
  activateUserAction,
  killAllSessionsAction,
  deleteUserAction,
} from './actions';
import type { AdminUserView } from './page';
import AddUserModal from './AddUserModal';
import EditUserModal, { type EditUserTarget } from './EditUserModal';
import UserSessionsModal from './UserSessionsModal';
import ResetPasswordModal, { type ResetPasswordTarget } from './ResetPasswordModal';

interface Props {
  users: AdminUserView[];
  /** ID of the currently-logged-in admin. Used to hide the Delete action
   *  on their own row so self-deletion is impossible from the UI (the
   *  server action also rejects it — belt and braces). */
  currentUserId: string | null;
}

const ROLE_BADGE: Record<string, { color: string; label: string }> = {
  DOCTOR: { color: 'text-cyan-300 bg-cyan-500/10 border-cyan-500/30', label: 'Doctor' },
  ADMIN: { color: 'text-amber-300 bg-amber-500/10 border-amber-500/30', label: 'Admin' },
  STAFF: { color: 'text-slate-300 bg-slate-500/10 border-slate-500/30', label: 'Staff' },
};

function formatRelative(iso: string | null): string {
  if (!iso) return 'Never';
  const diff = Date.now() - new Date(iso).getTime();
  const mins = Math.floor(diff / 60000);
  if (mins < 1) return 'Just now';
  if (mins < 60) return `${mins}m ago`;
  const hours = Math.floor(mins / 60);
  if (hours < 24) return `${hours}h ago`;
  return `${Math.floor(hours / 24)}d ago`;
}

export default function AdminUsersTableClient({ users, currentUserId }: Props) {
  const router = useRouter();
  const [search, setSearch] = useState('');
  const [addUserOpen, setAddUserOpen] = useState(false);
  const [editTarget, setEditTarget] = useState<EditUserTarget | null>(null);
  const [sessionsTarget, setSessionsTarget] = useState<{ id: string; label: string } | null>(null);
  const [passwordTarget, setPasswordTarget] = useState<ResetPasswordTarget | null>(null);
  const [openMenuId, setOpenMenuId] = useState<string | null>(null);
  const [pendingAction, setPendingAction] = useState<string | null>(null); // "userId:action"
  const [, startTransition] = useTransition();

  // Toast state
  const [toast, setToast] = useState<{ message: string; type: 'success' | 'error' } | null>(null);

  const showToast = useCallback((message: string, type: 'success' | 'error') => {
    setToast({ message, type });
    setTimeout(() => setToast(null), 3000);
  }, []);

  const runAction = useCallback(
    (userId: string, actionName: string, fn: (id: string) => Promise<{ ok: boolean; message?: string; error?: string }>) => {
      setOpenMenuId(null);
      setPendingAction(`${userId}:${actionName}`);
      startTransition(async () => {
        const result = await fn(userId);
        setPendingAction(null);
        if (result.ok) {
          showToast(result.message ?? 'Done.', 'success');
          router.refresh();
        } else {
          showToast(result.error ?? 'Action failed.', 'error');
        }
      });
    },
    [router, showToast]
  );

  const filtered = useMemo(() => {
    if (!search.trim()) return users;
    const q = search.toLowerCase();
    return users.filter(
      (u) => u.email.toLowerCase().includes(q) || (u.name ?? '').toLowerCase().includes(q) || u.role.toLowerCase().includes(q)
    );
  }, [users, search]);

  const activeCount = users.filter((u) => u.isActive).length;
  const totalSessions = users.reduce((a, u) => a + u.sessionCount, 0);

  return (
    <div className="min-h-screen bg-[#0a0e17] text-slate-200">
      {/* Grid overlay */}
      <div className="fixed inset-0 pointer-events-none z-0 opacity-[0.03]" style={{ backgroundImage: 'linear-gradient(rgba(255,255,255,.1) 1px,transparent 1px),linear-gradient(90deg,rgba(255,255,255,.1) 1px,transparent 1px)', backgroundSize: '40px 40px' }} />

      {/* Toast */}
      <AnimatePresence>
        {toast && (
          <motion.div
            initial={{ opacity: 0, y: -20, x: '-50%' }}
            animate={{ opacity: 1, y: 0, x: '-50%' }}
            exit={{ opacity: 0, y: -20, x: '-50%' }}
            className={`fixed top-6 left-1/2 z-[200] px-4 py-2.5 rounded-lg border text-xs font-mono shadow-2xl ${
              toast.type === 'success'
                ? 'bg-emerald-500/15 border-emerald-500/30 text-emerald-300'
                : 'bg-red-500/15 border-red-500/30 text-red-300'
            }`}
          >
            {toast.type === 'success' ? '>' : '!'} {toast.message}
          </motion.div>
        )}
      </AnimatePresence>

      <div className="relative z-10 mx-auto max-w-7xl px-6 py-8">
        {/* Top Bar */}
        <div className="flex items-center justify-between mb-8">
          <div className="flex items-center gap-4">
            <Link href="/dashboard" className="p-2 rounded-lg bg-white/5 border border-white/5 text-slate-500 hover:text-white hover:bg-white/10 transition-all">
              <ArrowLeft className="w-4 h-4" />
            </Link>
            <div className="flex items-center gap-3">
              <div className="p-2 rounded-lg bg-orange-500/10 border border-orange-500/30">
                <Terminal className="w-5 h-5 text-orange-400" />
              </div>
              <div>
                <h1 className="text-lg font-bold text-white tracking-tight">System Admin</h1>
                <p className="text-[11px] text-slate-500 font-mono">/system-admin &mdash; command center</p>
              </div>
            </div>
          </div>
          <div className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-white/5 border border-white/5">
            <div className="w-1.5 h-1.5 rounded-full bg-emerald-400 animate-pulse" />
            <span className="text-[10px] font-mono text-slate-400">SYSTEM ONLINE</span>
          </div>
        </div>

        {/* Stat Cards */}
        <div className="grid grid-cols-3 gap-4 mb-8">
          {[
            { label: 'Total Users', value: users.length, icon: Users, accent: 'text-cyan-400' },
            { label: 'Active', value: activeCount, icon: Activity, accent: 'text-emerald-400' },
            { label: 'Sessions', value: totalSessions, icon: Globe, accent: 'text-violet-400' },
          ].map((stat) => (
            <motion.div key={stat.label} initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }} className="rounded-xl bg-white/[0.02] border border-white/[0.06] p-4">
              <div className="flex items-center justify-between mb-2">
                <span className="text-[10px] font-mono text-slate-500 uppercase tracking-wider">{stat.label}</span>
                <stat.icon className={`w-3.5 h-3.5 ${stat.accent}`} />
              </div>
              <p className={`text-2xl font-bold font-mono ${stat.accent}`}>{stat.value}</p>
            </motion.div>
          ))}
        </div>

        {/* Search */}
        <div className="flex items-center gap-3 mb-6">
          <div className="relative flex-1">
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-slate-600" />
            <input type="text" value={search} onChange={(e) => setSearch(e.target.value)} placeholder="Search users..." className="w-full pl-10 pr-4 py-2.5 rounded-lg bg-white/[0.03] border border-white/[0.06] text-sm text-white placeholder-slate-600 outline-none focus:border-cyan-500/30 font-mono transition-colors" />
          </div>
          <div className="text-[10px] font-mono text-slate-600 px-3 py-2.5 rounded-lg bg-white/[0.02] border border-white/[0.06]">{filtered.length} records</div>
          <button
            onClick={() => setAddUserOpen(true)}
            className="inline-flex items-center gap-2 px-4 py-2.5 rounded-lg bg-cyan-500/15 border border-cyan-500/30 text-xs font-mono font-bold text-cyan-300 hover:bg-cyan-500/25 transition-all cursor-pointer shrink-0"
          >
            <UserPlus className="w-3.5 h-3.5" /> New User
          </button>
        </div>

        {/* Table */}
        <motion.div initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.1 }} className="rounded-xl bg-white/[0.02] border border-white/[0.06] overflow-visible">
          <div className="hidden md:grid grid-cols-12 gap-3 px-5 py-3 border-b border-white/[0.06] text-[9px] font-mono text-slate-600 uppercase tracking-widest">
            <div className="col-span-3">User</div>
            <div className="col-span-1">Role</div>
            <div className="col-span-1 text-center">Status</div>
            <div className="col-span-2">Last Login</div>
            <div className="col-span-2">Last IP</div>
            <div className="col-span-1 text-center">Sessions</div>
            <div className="col-span-1 text-center">Fails</div>
            <div className="col-span-1 text-center">Actions</div>
          </div>

          {filtered.length === 0 ? (
            <div className="py-20 text-center">
              <Terminal className="w-8 h-8 text-slate-700 mx-auto mb-3" />
              <p className="text-sm text-slate-600 font-mono">No users found</p>
            </div>
          ) : (
            <div className="divide-y divide-white/[0.04]">
              {filtered.map((user) => {
                const role = ROLE_BADGE[user.role] ?? ROLE_BADGE.STAFF;
                const isMenuOpen = openMenuId === user.id;
                const isAnyPending = pendingAction?.startsWith(user.id);

                return (
                  <div key={user.id} className={`grid grid-cols-1 md:grid-cols-12 gap-2 md:gap-3 px-5 py-3.5 hover:bg-white/[0.02] transition-colors ${!user.isActive ? 'opacity-40' : ''} ${isAnyPending ? 'animate-pulse' : ''}`}>
                    {/* User */}
                    <div className="md:col-span-3 flex items-center gap-3 min-w-0">
                      <div className="w-8 h-8 rounded-lg bg-gradient-to-br from-cyan-500/20 to-violet-500/20 border border-white/[0.06] flex items-center justify-center shrink-0">
                        <span className="text-[10px] font-bold text-white font-mono">{(user.name ?? user.email)[0].toUpperCase()}</span>
                      </div>
                      <div className="min-w-0">
                        <p className="text-xs font-medium text-white truncate">{user.name ?? 'Unnamed'}</p>
                        <p className="text-[10px] font-mono text-slate-500 truncate">{user.email}</p>
                      </div>
                    </div>

                    {/* Role */}
                    <div className="md:col-span-1 flex items-center">
                      <span className={`text-[9px] px-2 py-0.5 rounded border font-mono font-bold uppercase tracking-wider ${role.color}`}>{role.label}</span>
                    </div>

                    {/* Status */}
                    <div className="md:col-span-1 flex items-center justify-center">
                      {user.isActive ? (
                        <div className="flex items-center gap-1"><CheckCircle2 className="w-3.5 h-3.5 text-emerald-400" /><span className="text-[9px] font-mono text-emerald-400">LIVE</span></div>
                      ) : (
                        <div className="flex items-center gap-1"><XCircle className="w-3.5 h-3.5 text-red-400" /><span className="text-[9px] font-mono text-red-400">OFF</span></div>
                      )}
                    </div>

                    {/* Last Login */}
                    <div className="md:col-span-2 flex items-center gap-1.5">
                      <Clock className="w-3 h-3 text-slate-600 shrink-0" />
                      <span className="text-[10px] font-mono text-slate-400">{formatRelative(user.lastLogin)}</span>
                    </div>

                    {/* Last IP */}
                    <div className="md:col-span-2 flex items-center gap-1.5">
                      <Globe className="w-3 h-3 text-slate-600 shrink-0" />
                      <span className="text-[10px] font-mono text-slate-500 truncate">{user.lastSessionIp ?? '--'}</span>
                    </div>

                    {/* Sessions */}
                    <div className="md:col-span-1 flex items-center justify-center">
                      <span className="text-[10px] font-mono text-slate-400">{user.sessionCount}</span>
                    </div>

                    {/* Fails */}
                    <div className="md:col-span-1 flex items-center justify-center">
                      <span className={`text-[10px] font-mono ${user.failedLoginCount > 3 ? 'text-orange-400' : 'text-slate-500'}`}>{user.failedLoginCount}</span>
                    </div>

                    {/* Actions */}
                    <div className="md:col-span-1 flex items-center justify-center relative">
                      {isAnyPending ? (
                        <Loader2 className="w-4 h-4 text-orange-400 animate-spin" />
                      ) : (
                        <button onClick={() => setOpenMenuId(isMenuOpen ? null : user.id)} className="p-1.5 rounded-lg hover:bg-white/5 transition-colors cursor-pointer">
                          <MoreVertical className="w-4 h-4 text-slate-500" />
                        </button>
                      )}

                      <AnimatePresence>
                        {isMenuOpen && !isAnyPending && (
                          <motion.div
                            initial={{ opacity: 0, y: 4, scale: 0.95 }}
                            animate={{ opacity: 1, y: 0, scale: 1 }}
                            exit={{ opacity: 0, y: 4, scale: 0.95 }}
                            transition={{ duration: 0.12 }}
                            className="absolute right-0 bottom-full mb-1 z-[60] w-48 rounded-lg bg-[#111827] border border-white/10 shadow-2xl shadow-black/60 overflow-hidden"
                          >
                            <button
                              onClick={() => {
                                setOpenMenuId(null);
                                setEditTarget({
                                  id: user.id,
                                  name: user.name,
                                  email: user.email,
                                  role: user.role,
                                });
                              }}
                              className="w-full flex items-center gap-2.5 px-3 py-2 text-left text-[11px] text-slate-300 hover:bg-white/5 transition-colors cursor-pointer"
                            >
                              <UserCog className="w-3.5 h-3.5 text-cyan-400" /> Edit User
                            </button>
                            <button
                              onClick={() => {
                                setOpenMenuId(null);
                                setSessionsTarget({
                                  id: user.id,
                                  label: user.name ?? user.email,
                                });
                              }}
                              className="w-full flex items-center gap-2.5 px-3 py-2 text-left text-[11px] text-slate-300 hover:bg-white/5 transition-colors cursor-pointer"
                            >
                              <Eye className="w-3.5 h-3.5 text-violet-400" /> View Sessions
                            </button>
                            <button
                              onClick={() => {
                                setOpenMenuId(null);
                                setPasswordTarget({
                                  id: user.id,
                                  name: user.name,
                                  email: user.email,
                                });
                              }}
                              className="w-full flex items-center gap-2.5 px-3 py-2 text-left text-[11px] text-slate-300 hover:bg-white/5 transition-colors cursor-pointer"
                            >
                              <KeyRound className="w-3.5 h-3.5 text-orange-400" /> Reset Password
                            </button>

                            <div className="border-t border-white/5" />

                            {/* Kill Sessions */}
                            <button
                              onClick={() => runAction(user.id, 'kill', killAllSessionsAction)}
                              disabled={user.sessionCount === 0}
                              className="w-full flex items-center gap-2.5 px-3 py-2 text-left text-[11px] text-orange-400 hover:bg-orange-500/10 transition-colors cursor-pointer disabled:opacity-30 disabled:cursor-not-allowed"
                            >
                              <Zap className="w-3.5 h-3.5" /> Kill Sessions ({user.sessionCount})
                            </button>

                            {/* Activate / Deactivate */}
                            {user.isActive ? (
                              <button
                                onClick={() => runAction(user.id, 'deactivate', deactivateUserAction)}
                                className="w-full flex items-center gap-2.5 px-3 py-2 text-left text-[11px] text-orange-400 hover:bg-orange-500/10 transition-colors cursor-pointer"
                              >
                                <PowerOff className="w-3.5 h-3.5" /> Deactivate User
                              </button>
                            ) : (
                              <button
                                onClick={() => runAction(user.id, 'activate', activateUserAction)}
                                className="w-full flex items-center gap-2.5 px-3 py-2 text-left text-[11px] text-emerald-400 hover:bg-emerald-500/10 transition-colors cursor-pointer"
                              >
                                <Power className="w-3.5 h-3.5" /> Activate User
                              </button>
                            )}

                            {/* Delete — destructive. Hidden on the admin's own
                                row; server action also rejects self-delete. */}
                            {user.id !== currentUserId && (
                              <>
                                <div className="border-t border-white/5" />
                                <button
                                  onClick={() => {
                                    const confirmed = window.confirm(
                                      `Permanently delete user "${user.name ?? user.email}"?\n\n` +
                                        `This removes the user row, their login history, and their ` +
                                        `API usage entries. This cannot be undone.`
                                    );
                                    if (!confirmed) return;
                                    runAction(user.id, 'delete', deleteUserAction);
                                  }}
                                  className="w-full flex items-center gap-2.5 px-3 py-2 text-left text-[11px] text-red-400 hover:bg-red-500/10 transition-colors cursor-pointer"
                                >
                                  <Trash2 className="w-3.5 h-3.5" /> Delete User
                                </button>
                              </>
                            )}
                          </motion.div>
                        )}
                      </AnimatePresence>
                    </div>
                  </div>
                );
              })}
            </div>
          )}

          <div className="px-5 py-3 border-t border-white/[0.06] flex items-center justify-between">
            <p className="text-[9px] font-mono text-slate-600">{filtered.length} of {users.length} users</p>
            <div className="flex items-center gap-1.5">
              <Shield className="w-3 h-3 text-orange-500/50" />
              <span className="text-[9px] font-mono text-slate-600">HIPAA-secured endpoint</span>
            </div>
          </div>
        </motion.div>
      </div>

      {/* Add User Modal */}
      <AddUserModal
        open={addUserOpen}
        onClose={() => setAddUserOpen(false)}
        onSuccess={(msg) => showToast(msg, 'success')}
        onError={(msg) => showToast(msg, 'error')}
      />

      {/* Edit User Modal */}
      <EditUserModal
        open={editTarget !== null}
        user={editTarget}
        onClose={() => setEditTarget(null)}
        onSuccess={(msg) => showToast(msg, 'success')}
        onError={(msg) => showToast(msg, 'error')}
      />

      {/* View Sessions Modal */}
      <UserSessionsModal
        open={sessionsTarget !== null}
        userId={sessionsTarget?.id ?? null}
        userLabel={sessionsTarget?.label ?? null}
        onClose={() => setSessionsTarget(null)}
        onError={(msg) => showToast(msg, 'error')}
      />

      {/* Reset Password Modal */}
      <ResetPasswordModal
        open={passwordTarget !== null}
        user={passwordTarget}
        onClose={() => setPasswordTarget(null)}
        onSuccess={(msg) => showToast(msg, 'success')}
        onError={(msg) => showToast(msg, 'error')}
      />
    </div>
  );
}
