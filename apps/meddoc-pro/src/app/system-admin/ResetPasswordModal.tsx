'use client';

// ============================================================================
// Reset Password Modal — admin force-reset of any user's password
// ----------------------------------------------------------------------------
// Emergency feature. Admin enters a new password for the target user;
// bcrypt hash is computed server-side in resetUserPasswordAction. The new
// password is NEVER stored in browser history or persisted anywhere
// client-side — we just ship it once and forget.
//
// The modal shows a one-time "copy me" display of the password AFTER the
// server confirms success, because the admin needs to communicate it to
// the user out-of-band (phone, in person, etc.). If the admin reloads
// before copying, the password is gone — that's a feature, not a bug.
// ============================================================================

import { useState, useEffect, useTransition } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import {
  X,
  Loader2,
  Shield,
  Eye,
  EyeOff,
  Check,
  Copy,
  AlertTriangle,
} from 'lucide-react';

import { resetUserPasswordAction } from './actions';
import { validatePassword } from '@/lib/password-schema';

export interface ResetPasswordTarget {
  id: string;
  name: string | null;
  email: string;
}

interface Props {
  open: boolean;
  user: ResetPasswordTarget | null;
  onClose: () => void;
  onSuccess: (msg: string) => void;
  onError: (msg: string) => void;
}

function randomPassword(): string {
  // 16 chars. Resample once if the draw happens to miss a required
  // class — with 16 chars over a 60-char alphabet this is effectively
  // never hit, but the guard means we never hand back a value that
  // fails validatePassword on submit.
  const alphabet =
    'ABCDEFGHJKLMNPQRSTUVWXYZabcdefghjkmnpqrstuvwxyz23456789!@#$%';
  const draw = () => {
    const bytes = new Uint8Array(16);
    crypto.getRandomValues(bytes);
    let out = '';
    for (let i = 0; i < bytes.length; i++) {
      out += alphabet[bytes[i] % alphabet.length];
    }
    return out;
  };
  for (let attempt = 0; attempt < 5; attempt++) {
    const candidate = draw();
    if (validatePassword(candidate).ok) return candidate;
  }
  return draw();
}

// Outer wrapper: AnimatePresence owns open/close. Inner content holds
// state so each open mounts fresh — no reset useEffect needed.
export default function ResetPasswordModal({
  open,
  user,
  onClose,
  onSuccess,
  onError,
}: Props) {
  return (
    <AnimatePresence>
      {open && user && (
        <ResetPasswordModalContent
          user={user}
          onClose={onClose}
          onSuccess={onSuccess}
          onError={onError}
        />
      )}
    </AnimatePresence>
  );
}

function ResetPasswordModalContent({
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
  const [isPending, startTransition] = useTransition();
  const [password, setPassword] = useState('');
  const [showPassword, setShowPassword] = useState(false);
  const [copied, setCopied] = useState(false);
  // `issued` mirrors the password the admin just shipped, shown in a
  // "here's what you set" state after server success.
  const [issued, setIssued] = useState<string | null>(null);

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
    const policy = validatePassword(password);
    if (!policy.ok) {
      onError(policy.error);
      return;
    }
    const attempted = password;
    startTransition(async () => {
      const result = await resetUserPasswordAction(user.id, attempted);
      if (result.ok) {
        setIssued(attempted);
        onSuccess(result.message);
      } else {
        onError(result.error);
      }
    });
  };

  const handleCopy = async () => {
    if (!issued) return;
    try {
      await navigator.clipboard.writeText(issued);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    } catch {
      onError('Copy failed — select the password manually.');
    }
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
                  <div className="p-2 rounded-lg bg-orange-500/10 border border-orange-500/30">
                    <Shield className="w-4 h-4 text-orange-400" />
                  </div>
                  <div className="min-w-0">
                    <h2 className="text-sm font-bold text-white tracking-tight">
                      Reset Password
                    </h2>
                    <p className="text-[10px] font-mono text-slate-500 truncate">
                      {user.name ?? user.email}
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

              {/* Warning banner */}
              <div className="px-6 py-3 bg-orange-500/5 border-b border-orange-500/20">
                <div className="flex items-start gap-2">
                  <AlertTriangle className="w-3.5 h-3.5 text-orange-400 shrink-0 mt-0.5" />
                  <p className="text-[11px] text-orange-200/90 leading-relaxed">
                    <span className="font-semibold">Audited action.</span>{' '}
                    Communicate the new password to the user out-of-band. They
                    should change it on next login.
                  </p>
                </div>
              </div>

              {/* Post-success: show the password so admin can copy it */}
              {issued ? (
                <div className="p-6 space-y-4">
                  <p className="text-[11px] text-slate-400 leading-relaxed">
                    Password reset. Copy this now — it won&apos;t be shown again
                    once you close this dialog.
                  </p>
                  <div className="flex items-stretch gap-2">
                    <code className="flex-1 min-w-0 px-3 py-2.5 rounded-lg bg-black/40 border border-emerald-500/30 text-sm font-mono text-emerald-200 break-all">
                      {issued}
                    </code>
                    <button
                      type="button"
                      onClick={handleCopy}
                      className="inline-flex items-center justify-center gap-1.5 px-3 py-2.5 rounded-lg bg-emerald-500/15 border border-emerald-500/30 text-xs font-mono font-bold text-emerald-300 hover:bg-emerald-500/25 transition-all cursor-pointer shrink-0"
                    >
                      {copied ? (
                        <>
                          <Check className="w-3.5 h-3.5" /> Copied
                        </>
                      ) : (
                        <>
                          <Copy className="w-3.5 h-3.5" /> Copy
                        </>
                      )}
                    </button>
                  </div>
                  <button
                    type="button"
                    onClick={onClose}
                    className="w-full px-4 py-2.5 rounded-lg bg-white/[0.03] border border-white/[0.08] text-xs font-mono font-semibold text-slate-400 hover:text-white hover:bg-white/5 transition-all cursor-pointer"
                  >
                    Done
                  </button>
                </div>
              ) : (
                // Input form
                <form onSubmit={handleSubmit} className="p-6 space-y-4">
                  <div>
                    <div className="flex items-center justify-between mb-1.5">
                      <label className="block text-[10px] font-mono text-slate-500 uppercase tracking-widest">
                        New Password
                      </label>
                      <button
                        type="button"
                        onClick={() => setPassword(randomPassword())}
                        className="text-[10px] font-mono text-cyan-400 hover:text-cyan-300 transition-colors cursor-pointer"
                      >
                        Generate
                      </button>
                    </div>
                    <div className="relative">
                      <input
                        type={showPassword ? 'text' : 'password'}
                        value={password}
                        onChange={(e) => setPassword(e.target.value)}
                        disabled={isPending}
                        autoComplete="new-password"
                        minLength={8}
                        placeholder="min 8 characters"
                        className="w-full pl-3 pr-10 py-2.5 rounded-lg bg-white/[0.03] border border-white/[0.08] text-sm text-white placeholder-slate-600 outline-none focus:border-orange-500/40 font-mono transition-colors"
                      />
                      <button
                        type="button"
                        onClick={() => setShowPassword((s) => !s)}
                        className="absolute right-2 top-1/2 -translate-y-1/2 p-1.5 rounded-md text-slate-500 hover:text-white transition-colors cursor-pointer"
                        aria-label={showPassword ? 'Hide password' : 'Show password'}
                      >
                        {showPassword ? (
                          <EyeOff className="w-3.5 h-3.5" />
                        ) : (
                          <Eye className="w-3.5 h-3.5" />
                        )}
                      </button>
                    </div>
                    <p className="mt-1.5 text-[10px] font-mono text-slate-600">
                      {password.length === 0
                        ? 'Type a password or click Generate'
                        : validatePassword(password).ok
                        ? `${password.length} characters · strong enough`
                        : `${password.length} chars · need 10+ with upper, lower, digit`}
                    </p>
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
                      disabled={isPending || !validatePassword(password).ok}
                      className="flex-1 inline-flex items-center justify-center gap-2 px-4 py-2.5 rounded-lg bg-orange-500/15 border border-orange-500/30 text-xs font-mono font-bold text-orange-300 hover:bg-orange-500/25 transition-all cursor-pointer disabled:opacity-50 disabled:cursor-not-allowed"
                    >
                      {isPending ? (
                        <>
                          <Loader2 className="w-3.5 h-3.5 animate-spin" /> Resetting...
                        </>
                      ) : (
                        'Reset Password'
                      )}
                    </button>
                  </div>
                </form>
              )}
            </div>
      </motion.div>
    </>
  );
}
