'use client';

// ============================================================================
// "Add user" — create an account INSIDE AN EXISTING PRACTICE
// ----------------------------------------------------------------------------
// Console port (#310 step 3) of meddoc-pro's AddUserModal, pointed at
// POST /api/admin/users. Deliberately NOT ported from the original:
//   · the password field — the person sets their own password from the
//     reset-token email the route sends; an admin never types one;
//   · the implicit practice — the admin names the practice by id (the drawer's
//     "Add user to this practice" pre-fills it), and the route refuses one that
//     does not exist rather than minting it.
//
// Shell and tokens are ConfirmationModal's — no new design language while the
// admin shell waits for the owner's design pick.
// ============================================================================

import { useEffect, useRef, useState } from 'react';
import { toast } from 'sonner';
import { UserPlus } from 'lucide-react';

interface Props {
  initialPracticeId?: string;
  onCancel: () => void;
  onCreated: () => void;
}

const FIELD =
  'block h-9 w-full rounded-md border border-linear-border bg-linear-surface-1 px-3 py-1.5 text-sm text-linear-text placeholder:text-linear-text-3 focus-visible:border-linear-border-strong focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-linear-sage/40';
const LABEL = 'mb-1.5 block font-mono text-[10px] uppercase tracking-[0.08em] text-linear-text-3';

export default function AddUserModal({ initialPracticeId = '', onCancel, onCreated }: Props) {
  const [email, setEmail] = useState('');
  const [name, setName] = useState('');
  const [practiceId, setPracticeId] = useState(initialPracticeId);
  const [practiceRole, setPracticeRole] = useState('');
  const [role, setRole] = useState('DOCTOR');
  const [busy, setBusy] = useState(false);
  const firstRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    firstRef.current?.focus();
    const onKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape' && !busy) onCancel();
    };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, [onCancel, busy]);

  // The role within the practice has NO default on purpose: the original made
  // every account an OWNER, and a pre-selected value is how that comes back.
  const valid =
    email.trim().length > 3 && name.trim().length > 0 && practiceId.trim().length > 0 && practiceRole !== '';

  async function submit() {
    if (!valid || busy) return;
    setBusy(true);
    try {
      const res = await fetch('/api/admin/users', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          email: email.trim(),
          name: name.trim(),
          practiceId: practiceId.trim(),
          practiceRole,
          role,
        }),
      });
      const data: {
        ok?: boolean;
        error?: string;
        user?: { practiceName?: string };
        credentialEmail?: { sent: boolean };
      } = await res.json().catch(() => ({}));
      if (res.ok && data.ok) {
        if (data.credentialEmail?.sent) {
          toast.success('User created', {
            description: `Added to ${data.user?.practiceName ?? 'the practice'}. A set-your-password link was emailed (valid 1 hour).`,
          });
        } else {
          toast.warning('User created — but the password email did not send', {
            description: 'Use “Reset password” on the account once email delivery works.',
          });
        }
        onCreated();
      } else {
        toast.error('Could not create user', { description: data.error ?? `HTTP ${res.status}` });
      }
    } catch (err) {
      toast.error('Could not create user', {
        description: err instanceof Error ? err.message : 'network error',
      });
    } finally {
      setBusy(false);
    }
  }

  return (
    <>
      <div onClick={busy ? undefined : onCancel} className="fixed inset-0 z-50 bg-black/60 backdrop-blur-[2px]" />
      <div
        role="dialog"
        aria-label="Add user"
        className="fixed left-1/2 top-1/2 z-50 w-[460px] max-w-[calc(100vw-32px)] -translate-x-1/2 -translate-y-1/2 overflow-hidden rounded-lg border border-linear-border-strong bg-linear-surface-2 shadow-[0_30px_80px_rgba(0,0,0,0.6)]"
      >
        <div className="border-b border-linear-border px-5 py-4">
          <div className="flex items-start gap-2.5">
            <div className="mt-0.5 flex h-6 w-6 shrink-0 items-center justify-center rounded-full bg-linear-surface-3 text-linear-text">
              <UserPlus className="h-3.5 w-3.5" strokeWidth={2.25} />
            </div>
            <div>
              <div className="text-sm font-semibold text-linear-text">Add user to a practice</div>
              <div className="mt-1 text-xs leading-relaxed text-linear-text-2">
                The account joins an existing practice. They set their own password from the emailed
                link — you never choose it.
              </div>
            </div>
          </div>
        </div>
        <div className="flex flex-col gap-3 px-5 py-4">
          <div>
            <label className={LABEL} htmlFor="add-user-email">Email</label>
            <input
              id="add-user-email"
              ref={firstRef}
              type="email"
              maxLength={254}
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              disabled={busy}
              className={`${FIELD} font-mono`}
              placeholder="doctor@clinic.com"
            />
          </div>
          <div>
            <label className={LABEL} htmlFor="add-user-name">Full name</label>
            <input
              id="add-user-name"
              maxLength={200}
              value={name}
              onChange={(e) => setName(e.target.value)}
              disabled={busy}
              className={FIELD}
            />
          </div>
          <div>
            <label className={LABEL} htmlFor="add-user-practice">Practice id</label>
            <input
              id="add-user-practice"
              maxLength={64}
              value={practiceId}
              onChange={(e) => setPracticeId(e.target.value)}
              disabled={busy}
              className={`${FIELD} font-mono`}
              placeholder="the practice's id"
            />
          </div>
          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className={LABEL} htmlFor="add-user-prole">Role in practice</label>
              <select
                id="add-user-prole"
                value={practiceRole}
                onChange={(e) => setPracticeRole(e.target.value)}
                disabled={busy}
                className={FIELD}
              >
                <option value="">Choose…</option>
                <option value="OWNER">Owner</option>
                <option value="CLINICIAN">Clinician</option>
                <option value="TECH">Tech</option>
              </select>
            </div>
            <div>
              <label className={LABEL} htmlFor="add-user-role">Account type</label>
              <select
                id="add-user-role"
                value={role}
                onChange={(e) => setRole(e.target.value)}
                disabled={busy}
                className={FIELD}
              >
                <option value="DOCTOR">Doctor</option>
                <option value="STAFF">Staff</option>
                <option value="ADMIN">Admin</option>
              </select>
            </div>
          </div>
        </div>
        <div className="flex items-center justify-end gap-2 border-t border-linear-border bg-linear-surface-1/40 px-5 py-3">
          <button type="button" onClick={onCancel} disabled={busy} className="qm-lin-btn">
            Cancel
          </button>
          <button
            type="button"
            onClick={submit}
            disabled={!valid || busy}
            className="qm-lin-btn qm-lin-btn-primary disabled:cursor-not-allowed disabled:opacity-60"
          >
            {busy ? 'Working…' : 'Create user'}
          </button>
        </div>
      </div>
    </>
  );
}
