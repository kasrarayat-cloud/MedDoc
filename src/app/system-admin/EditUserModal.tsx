'use client';

// ============================================================================
// Edit User Modal — name / email / role
// ----------------------------------------------------------------------------
// Pre-fills from the currently-selected user. Only POSTs fields that actually
// changed so the audit log correctly shows `changedFields: [...]` for what
// the admin modified, not a full snapshot.
// ============================================================================

import { useState, useEffect, useTransition } from 'react';
import { useRouter } from 'next/navigation';
import { motion, AnimatePresence } from 'framer-motion';
import { X, Loader2, UserCog } from 'lucide-react';

import { updateUserAction } from './actions';

export interface EditUserTarget {
  id: string;
  name: string | null;
  email: string;
  role: string;
}

interface Props {
  open: boolean;
  user: EditUserTarget | null;
  onClose: () => void;
  onSuccess: (msg: string) => void;
  onError: (msg: string) => void;
}

const ROLES = ['DOCTOR', 'STAFF', 'ADMIN'] as const;

// Outer wrapper: AnimatePresence owns open/close. Inner content holds
// state so each open mounts fresh — no reset useEffect needed.
export default function EditUserModal({
  open,
  user,
  onClose,
  onSuccess,
  onError,
}: Props) {
  return (
    <AnimatePresence>
      {open && user && (
        <EditUserModalContent
          user={user}
          onClose={onClose}
          onSuccess={onSuccess}
          onError={onError}
        />
      )}
    </AnimatePresence>
  );
}

function EditUserModalContent({
  user,
  onClose,
  onSuccess,
  onError,
}: {
  user: NonNullable<Props['user']>;
  onClose: Props['onClose'];
  onSuccess: Props['onSuccess'];
  onError: Props['onError'];
}) {
  const router = useRouter();
  const [isPending, startTransition] = useTransition();

  // Initialize from the user prop on mount — fresh values each open.
  const [name, setName] = useState(user.name ?? '');
  const [email, setEmail] = useState(user.email);
  const [role, setRole] = useState<string>(user.role);

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape') onClose();
    };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, [onClose]);

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!user) return;

    // Diff against initial values so the server action only rewrites what
    // actually changed (cleaner audit log).
    const patch: { name?: string; email?: string; role?: string } = {};
    const nextName = name.trim();
    const nextEmail = email.trim().toLowerCase();
    if (nextName && nextName !== (user.name ?? '')) patch.name = nextName;
    if (nextEmail && nextEmail !== user.email.toLowerCase()) patch.email = nextEmail;
    if (role !== user.role) patch.role = role;

    if (Object.keys(patch).length === 0) {
      onError('No changes to save.');
      return;
    }

    startTransition(async () => {
      const result = await updateUserAction(user.id, patch);
      if (result.ok) {
        onSuccess(result.message);
        onClose();
        router.refresh();
      } else {
        onError(result.error);
      }
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
            initial={{ opacity: 0, scale: 0.95, y: 20 }}
            animate={{ opacity: 1, scale: 1, y: 0 }}
            exit={{ opacity: 0, scale: 0.95, y: 20 }}
            transition={{ type: 'spring', stiffness: 300, damping: 30 }}
            role="dialog"
            aria-modal="true"
            className="fixed inset-0 z-[101] flex items-center justify-center p-4 pointer-events-none"
          >
            <div className="pointer-events-auto w-full max-w-md rounded-xl bg-[#0d1117] border border-white/[0.08] shadow-2xl shadow-black/60 overflow-hidden">
              {/* Header */}
              <div className="relative px-6 py-4 border-b border-white/[0.06] bg-white/[0.02]">
                <div className="flex items-center gap-3">
                  <div className="p-2 rounded-lg bg-cyan-500/10 border border-cyan-500/30">
                    <UserCog className="w-4 h-4 text-cyan-400" />
                  </div>
                  <div>
                    <h2 className="text-sm font-bold text-white tracking-tight">
                      Edit User
                    </h2>
                    <p className="text-[10px] font-mono text-slate-500 truncate">
                      {user.email}
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

              {/* Form */}
              <form onSubmit={handleSubmit} className="p-6 space-y-4">
                <div>
                  <label className="block text-[10px] font-mono text-slate-500 uppercase tracking-widest mb-1.5">
                    Name
                  </label>
                  <input
                    type="text"
                    value={name}
                    onChange={(e) => setName(e.target.value)}
                    disabled={isPending}
                    className="w-full px-3 py-2.5 rounded-lg bg-white/[0.03] border border-white/[0.08] text-sm text-white placeholder-slate-600 outline-none focus:border-cyan-500/40 font-mono transition-colors"
                  />
                </div>

                <div>
                  <label className="block text-[10px] font-mono text-slate-500 uppercase tracking-widest mb-1.5">
                    Email
                  </label>
                  <input
                    type="email"
                    value={email}
                    onChange={(e) => setEmail(e.target.value)}
                    disabled={isPending}
                    className="w-full px-3 py-2.5 rounded-lg bg-white/[0.03] border border-white/[0.08] text-sm text-white placeholder-slate-600 outline-none focus:border-cyan-500/40 font-mono transition-colors"
                  />
                </div>

                <div>
                  <label className="block text-[10px] font-mono text-slate-500 uppercase tracking-widest mb-1.5">
                    Role
                  </label>
                  <select
                    value={role}
                    onChange={(e) => setRole(e.target.value)}
                    disabled={isPending}
                    className="w-full px-3 py-2.5 rounded-lg bg-white/[0.03] border border-white/[0.08] text-sm text-white outline-none focus:border-cyan-500/40 font-mono transition-colors cursor-pointer"
                  >
                    {ROLES.map((r) => (
                      <option key={r} value={r}>
                        {r}
                      </option>
                    ))}
                  </select>
                </div>

                <div className="flex items-center gap-2 pt-2">
                  <button
                    type="button"
                    onClick={onClose}
                    disabled={isPending}
                    className="flex-1 px-4 py-2.5 rounded-lg bg-white/[0.03] border border-white/[0.08] text-xs font-mono font-semibold text-slate-400 hover:text-white hover:bg-white/5 transition-all cursor-pointer disabled:opacity-50"
                  >
                    Cancel
                  </button>
                  <button
                    type="submit"
                    disabled={isPending}
                    className="flex-1 inline-flex items-center justify-center gap-2 px-4 py-2.5 rounded-lg bg-cyan-500/15 border border-cyan-500/30 text-xs font-mono font-bold text-cyan-300 hover:bg-cyan-500/25 transition-all cursor-pointer disabled:opacity-50"
                  >
                    {isPending ? (
                      <>
                        <Loader2 className="w-3.5 h-3.5 animate-spin" /> Saving...
                      </>
                    ) : (
                      'Save Changes'
                    )}
                  </button>
                </div>
              </form>
            </div>
      </motion.div>
    </>
  );
}
