'use client';

// ============================================================================
// User Sessions Modal — SessionLog history for a single user
// ----------------------------------------------------------------------------
// JWT strategy caveat: our NextAuth session lives in a signed cookie, not
// the DB. `SessionLog` rows are an audit trail of past logins, NOT a list
// of "active sessions". Deleting a row here only removes the history entry
// — the user's current JWT cookie remains valid until it expires (8h).
// The UI banner makes this explicit so admins don't misread the action.
// ============================================================================

import { useState, useEffect, useCallback, useTransition } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import {
  X,
  Loader2,
  Eye,
  Globe,
  Clock,
  Monitor,
  Trash2,
  AlertTriangle,
} from 'lucide-react';

import {
  getUserSessionsAction,
  deleteSessionLogAction,
  type UserSessionRow,
} from './actions';

interface Props {
  open: boolean;
  userId: string | null;
  userLabel: string | null;
  onClose: () => void;
  onError: (msg: string) => void;
}

function formatTimestamp(iso: string): string {
  const d = new Date(iso);
  return (
    d.toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' }) +
    ' · ' +
    d.toLocaleTimeString('en-US', { hour: '2-digit', minute: '2-digit', second: '2-digit' })
  );
}

function shortUA(ua: string | null): string {
  if (!ua) return 'Unknown agent';
  // Extract browser family — enough signal for a sessions list.
  const m =
    ua.match(/(Edg|OPR|Chrome|Safari|Firefox|curl|Postman|wget)\/([\d.]+)/) ||
    null;
  if (m) return `${m[1]} ${m[2].split('.')[0]}`;
  return ua.slice(0, 48) + (ua.length > 48 ? '…' : '');
}

// Outer wrapper: AnimatePresence owns open/close. Inner content holds
// state + does the data load on mount — fresh per open.
export default function UserSessionsModal({
  open,
  userId,
  userLabel,
  onClose,
  onError,
}: Props) {
  return (
    <AnimatePresence>
      {open && userId && (
        <UserSessionsModalContent
          userId={userId}
          userLabel={userLabel}
          onClose={onClose}
          onError={onError}
        />
      )}
    </AnimatePresence>
  );
}

function UserSessionsModalContent({
  userId,
  userLabel,
  onClose,
  onError,
}: {
  userId: string;
  userLabel: Props['userLabel'];
  onClose: Props['onClose'];
  onError: Props['onError'];
}) {
  // Start in loading state — we always fetch on mount, no point flashing
  // an empty list for one tick. The effect below performs the load and
  // flips loading off when done, so no synchronous setState in the effect
  // body (avoids React 19's set-state-in-effect warning).
  const [isLoading, setIsLoading] = useState(true);
  const [sessions, setSessions] = useState<UserSessionRow[]>([]);
  const [deletingId, setDeletingId] = useState<string | null>(null);
  const [, startTransition] = useTransition();

  // Initial load on mount + reload helper for after-mutation refreshes.
  // `reload` is also exposed via the closure for delete handlers below.
  const reload = useCallback(
    async (id: string) => {
      setIsLoading(true);
      const result = await getUserSessionsAction(id);
      if (result.ok) {
        setSessions(result.sessions);
      } else {
        onError(result.error);
        setSessions([]);
      }
      setIsLoading(false);
    },
    [onError]
  );

  useEffect(() => {
    let cancelled = false;
    (async () => {
      const result = await getUserSessionsAction(userId);
      if (cancelled) return;
      if (result.ok) {
        setSessions(result.sessions);
      } else {
        onError(result.error);
        setSessions([]);
      }
      setIsLoading(false);
    })();
    return () => { cancelled = true; };
  }, [userId, onError]);

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape') onClose();
    };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, [onClose]);

  const handleDelete = (sessionLogId: string) => {
    if (!userId) return;
    setDeletingId(sessionLogId);
    startTransition(async () => {
      const result = await deleteSessionLogAction(sessionLogId);
      setDeletingId(null);
      if (!result.ok) {
        onError(result.error);
        return;
      }
      await reload(userId);
    });
  };

  return (
    <>
      <motion.div
        initial={{ opacity: 0 }}
        animate={{ opacity: 1 }}
        exit={{ opacity: 0 }}
        onClick={onClose}
        className="fixed inset-0 z-[100] bg-black/80 backdrop-blur-sm"
      />

          <motion.div
            initial={{ opacity: 0, scale: 0.97, y: 20 }}
            animate={{ opacity: 1, scale: 1, y: 0 }}
            exit={{ opacity: 0, scale: 0.97, y: 20 }}
            transition={{ type: 'spring', stiffness: 300, damping: 30 }}
            role="dialog"
            aria-modal="true"
            className="fixed inset-0 z-[101] flex items-center justify-center p-4 pointer-events-none"
          >
            <div className="pointer-events-auto w-full max-w-2xl rounded-xl bg-[#0d1117] border border-white/[0.08] shadow-2xl shadow-black/60 overflow-hidden flex flex-col max-h-[85vh]">
              {/* Header */}
              <div className="relative px-6 py-4 border-b border-white/[0.06] bg-white/[0.02] shrink-0">
                <div className="flex items-center gap-3">
                  <div className="p-2 rounded-lg bg-violet-500/10 border border-violet-500/30">
                    <Eye className="w-4 h-4 text-violet-400" />
                  </div>
                  <div className="min-w-0">
                    <h2 className="text-sm font-bold text-white tracking-tight">
                      Session History
                    </h2>
                    <p className="text-[10px] font-mono text-slate-500 truncate">
                      {userLabel ?? userId}
                    </p>
                  </div>
                </div>
                <button
                  type="button"
                  onClick={onClose}
                  className="absolute top-3 right-3 p-1.5 rounded-md text-slate-500 hover:text-white hover:bg-white/5 transition-colors cursor-pointer"
                  aria-label="Close"
                >
                  <X className="w-4 h-4" />
                </button>
              </div>

              {/* JWT-limitation banner — keep admins honest about what delete does */}
              <div className="px-6 py-3 bg-amber-500/5 border-b border-amber-500/20 shrink-0">
                <div className="flex items-start gap-2">
                  <AlertTriangle className="w-3.5 h-3.5 text-amber-400 shrink-0 mt-0.5" />
                  <p className="text-[11px] text-amber-200/90 leading-relaxed">
                    <span className="font-semibold">History view only.</span> Sessions
                    are JWT-backed; deleting a row below removes the audit entry but
                    does NOT invalidate an active cookie. To force sign-out, use{' '}
                    <span className="font-mono text-amber-300">Deactivate User</span>.
                  </p>
                </div>
              </div>

              {/* Body */}
              <div className="flex-1 overflow-y-auto">
                {isLoading ? (
                  <div className="py-20 text-center">
                    <Loader2 className="w-6 h-6 text-violet-400 animate-spin mx-auto mb-3" />
                    <p className="text-[11px] font-mono text-slate-500">
                      Loading session history...
                    </p>
                  </div>
                ) : sessions.length === 0 ? (
                  <div className="py-20 text-center">
                    <Eye className="w-8 h-8 text-slate-700 mx-auto mb-3" />
                    <p className="text-sm text-slate-600 font-mono">
                      No sessions logged for this user
                    </p>
                  </div>
                ) : (
                  <div className="divide-y divide-white/[0.04]">
                    {sessions.map((s) => {
                      const isDeleting = deletingId === s.id;
                      return (
                        <div
                          key={s.id}
                          className="px-6 py-3 hover:bg-white/[0.02] transition-colors flex items-center gap-3"
                        >
                          <div className="flex-1 min-w-0 grid grid-cols-1 md:grid-cols-3 gap-2 md:gap-4 items-center">
                            <div className="flex items-center gap-2">
                              <Clock className="w-3 h-3 text-slate-600 shrink-0" />
                              <span className="text-[11px] font-mono text-slate-400 truncate">
                                {formatTimestamp(s.createdAt)}
                              </span>
                            </div>
                            <div className="flex items-center gap-2">
                              <Globe className="w-3 h-3 text-slate-600 shrink-0" />
                              <span className="text-[11px] font-mono text-slate-400 truncate">
                                {s.ipAddress ?? '—'}
                              </span>
                            </div>
                            <div className="flex items-center gap-2">
                              <Monitor className="w-3 h-3 text-slate-600 shrink-0" />
                              <span className="text-[11px] font-mono text-slate-500 truncate">
                                {shortUA(s.userAgent)}
                              </span>
                            </div>
                          </div>
                          <button
                            type="button"
                            onClick={() => handleDelete(s.id)}
                            disabled={isDeleting}
                            title="Delete this history entry"
                            className="p-1.5 rounded-md text-slate-500 hover:text-red-300 hover:bg-red-500/10 transition-colors cursor-pointer disabled:opacity-40 disabled:cursor-not-allowed shrink-0"
                            aria-label="Delete session entry"
                          >
                            {isDeleting ? (
                              <Loader2 className="w-3.5 h-3.5 animate-spin" />
                            ) : (
                              <Trash2 className="w-3.5 h-3.5" />
                            )}
                          </button>
                        </div>
                      );
                    })}
                  </div>
                )}
              </div>

              {/* Footer */}
              <div className="px-6 py-3 border-t border-white/[0.06] flex items-center justify-between shrink-0">
                <p className="text-[10px] font-mono text-slate-600">
                  {sessions.length} record{sessions.length === 1 ? '' : 's'} · newest 50
                </p>
                <button
                  type="button"
                  onClick={onClose}
                  className="text-[10px] font-mono text-slate-500 hover:text-white transition-colors cursor-pointer"
                >
                  Close
                </button>
              </div>
            </div>
      </motion.div>
    </>
  );
}
