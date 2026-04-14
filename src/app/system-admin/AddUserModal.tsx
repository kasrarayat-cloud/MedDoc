'use client';

// ============================================================================
// Add User Modal — Command Center aesthetic
// ============================================================================

import { useState, useEffect, useTransition } from 'react';
import { useRouter } from 'next/navigation';
import { motion, AnimatePresence } from 'framer-motion';
import {
  X,
  Loader2,
  UserPlus,
  Terminal,
} from 'lucide-react';

import { createUserAction } from './actions';

interface AddUserModalProps {
  open: boolean;
  onClose: () => void;
  onSuccess: (msg: string) => void;
  onError: (msg: string) => void;
}

// Outer wrapper: AnimatePresence owns open/close. Inner content holds
// state so each open mounts fresh — no reset useEffect needed.
export default function AddUserModal({ open, onClose, onSuccess, onError }: AddUserModalProps) {
  return (
    <AnimatePresence>
      {open && (
        <AddUserModalContent onClose={onClose} onSuccess={onSuccess} onError={onError} />
      )}
    </AnimatePresence>
  );
}

function AddUserModalContent({
  onClose,
  onSuccess,
  onError,
}: {
  onClose: () => void;
  onSuccess: AddUserModalProps['onSuccess'];
  onError: AddUserModalProps['onError'];
}) {
  const router = useRouter();
  const [isPending, startTransition] = useTransition();

  const [name, setName] = useState('');
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [role, setRole] = useState('DOCTOR');

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => { if (e.key === 'Escape') onClose(); };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, [onClose]);

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();

    const fd = new FormData();
    fd.append('name', name);
    fd.append('email', email);
    fd.append('password', password);
    fd.append('role', role);

    startTransition(async () => {
      const result = await createUserAction(fd);
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
                    <UserPlus className="w-4 h-4 text-cyan-400" />
                  </div>
                  <div>
                    <h2 className="text-sm font-bold text-white">Create New User</h2>
                    <p className="text-[10px] font-mono text-slate-500">system-admin / users / create</p>
                  </div>
                </div>
                <button onClick={onClose} className="absolute top-3 right-3 p-2 rounded-lg text-slate-500 hover:text-white hover:bg-white/5 transition-colors">
                  <X className="w-4 h-4" />
                </button>
              </div>

              {/* Form */}
              <form onSubmit={handleSubmit} className="px-6 py-5 space-y-4">
                {/* Name */}
                <div>
                  <label className="block text-[10px] font-mono text-slate-500 uppercase tracking-widest mb-1.5">
                    Full Name
                  </label>
                  <input
                    type="text"
                    value={name}
                    onChange={(e) => setName(e.target.value)}
                    required
                    disabled={isPending}
                    placeholder="Dr. Jane Smith"
                    className="w-full px-3 py-2.5 rounded-lg bg-white/[0.03] border border-white/[0.08] text-sm text-white placeholder-slate-600 font-mono outline-none focus:border-cyan-500/40 transition-colors disabled:opacity-50"
                  />
                </div>

                {/* Email */}
                <div>
                  <label className="block text-[10px] font-mono text-slate-500 uppercase tracking-widest mb-1.5">
                    Email
                  </label>
                  <input
                    type="email"
                    value={email}
                    onChange={(e) => setEmail(e.target.value)}
                    required
                    disabled={isPending}
                    placeholder="jane@clinic.com"
                    className="w-full px-3 py-2.5 rounded-lg bg-white/[0.03] border border-white/[0.08] text-sm text-white placeholder-slate-600 font-mono outline-none focus:border-cyan-500/40 transition-colors disabled:opacity-50"
                  />
                </div>

                {/* Password */}
                <div>
                  <label className="block text-[10px] font-mono text-slate-500 uppercase tracking-widest mb-1.5">
                    Password
                  </label>
                  <input
                    type="password"
                    value={password}
                    onChange={(e) => setPassword(e.target.value)}
                    required
                    minLength={8}
                    disabled={isPending}
                    placeholder="Min 8 characters"
                    className="w-full px-3 py-2.5 rounded-lg bg-white/[0.03] border border-white/[0.08] text-sm text-white placeholder-slate-600 font-mono outline-none focus:border-cyan-500/40 transition-colors disabled:opacity-50"
                  />
                </div>

                {/* Role */}
                <div>
                  <label className="block text-[10px] font-mono text-slate-500 uppercase tracking-widest mb-1.5">
                    Role
                  </label>
                  <select
                    value={role}
                    onChange={(e) => setRole(e.target.value)}
                    disabled={isPending}
                    className="w-full px-3 py-2.5 rounded-lg bg-white/[0.03] border border-white/[0.08] text-sm text-white font-mono outline-none focus:border-cyan-500/40 appearance-none cursor-pointer transition-colors disabled:opacity-50"
                  >
                    <option value="DOCTOR">Doctor</option>
                    <option value="STAFF">Staff</option>
                    <option value="ADMIN">Admin</option>
                  </select>
                </div>

                {/* Footer */}
                <div className="flex items-center justify-between pt-3 border-t border-white/[0.06]">
                  <div className="flex items-center gap-1.5">
                    <Terminal className="w-3 h-3 text-slate-600" />
                    <span className="text-[9px] font-mono text-slate-600">bcrypt hashed</span>
                  </div>
                  <div className="flex items-center gap-2">
                    <button
                      type="button"
                      onClick={onClose}
                      disabled={isPending}
                      className="px-3 py-2 rounded-lg text-xs font-mono text-slate-400 hover:text-white hover:bg-white/5 transition-colors disabled:opacity-50"
                    >
                      Cancel
                    </button>
                    <button
                      type="submit"
                      disabled={isPending}
                      className="inline-flex items-center gap-2 px-4 py-2 rounded-lg bg-cyan-500/15 border border-cyan-500/30 text-xs font-mono font-bold text-cyan-300 hover:bg-cyan-500/25 transition-all disabled:opacity-50 cursor-pointer"
                    >
                      {isPending ? (
                        <><Loader2 className="w-3 h-3 animate-spin" /> Creating...</>
                      ) : (
                        <><UserPlus className="w-3 h-3" /> Create User</>
                      )}
                    </button>
                  </div>
                </div>
              </form>
            </div>
      </motion.div>
    </>
  );
}
