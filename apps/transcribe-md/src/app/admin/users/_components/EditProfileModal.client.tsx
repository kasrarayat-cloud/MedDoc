'use client';

// ============================================================================
// "Edit" — name and legacy account role
// ----------------------------------------------------------------------------
// Console port (#310 step 3) of meddoc-pro's EditUserModal, pointed at
// POST /api/admin/users/[id]/profile. The email field is deliberately NOT
// ported: an address change goes through the confirm-email token flow, and the
// route refuses an `email` key outright. Platform admin (SUPER_ADMIN) is not a
// role here either — it has its own confirm-email doors.
// ============================================================================

import { useEffect, useRef, useState } from 'react';
import { toast } from 'sonner';
import { Pencil } from 'lucide-react';

interface Props {
  user: { id: string; email: string; fullName: string; legacyRole: string };
  onCancel: () => void;
  onSaved: () => void;
}

const FIELD =
  'block h-9 w-full rounded-md border border-linear-border bg-linear-surface-1 px-3 py-1.5 text-sm text-linear-text focus-visible:border-linear-border-strong focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-linear-sage/40';
const LABEL = 'mb-1.5 block font-mono text-[10px] uppercase tracking-[0.08em] text-linear-text-3';
const EDITABLE = ['DOCTOR', 'STAFF', 'ADMIN'];

export default function EditProfileModal({ user, onCancel, onSaved }: Props) {
  const initialName = user.fullName === user.email ? '' : user.fullName;
  const [name, setName] = useState(initialName);
  const [role, setRole] = useState(user.legacyRole);
  const [busy, setBusy] = useState(false);
  const inputRef = useRef<HTMLInputElement>(null);
  const roleEditable = EDITABLE.includes(user.legacyRole);

  useEffect(() => {
    inputRef.current?.focus();
    const onKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape' && !busy) onCancel();
    };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, [onCancel, busy]);

  const body: { name?: string; role?: string } = {};
  if (name.trim() && name.trim() !== initialName) body.name = name.trim();
  if (roleEditable && role !== user.legacyRole) body.role = role;
  const dirty = Object.keys(body).length > 0;

  async function save() {
    if (!dirty || busy) return;
    setBusy(true);
    try {
      const res = await fetch(`/api/admin/users/${user.id}/profile`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(body),
      });
      const data: { ok?: boolean; error?: string } = await res.json().catch(() => ({}));
      if (res.ok && data.ok) {
        toast.success('Profile updated');
        onSaved();
      } else {
        toast.error('Could not update profile', { description: data.error ?? `HTTP ${res.status}` });
      }
    } catch (err) {
      toast.error('Could not update profile', {
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
        aria-label={`Edit ${user.email}`}
        className="fixed left-1/2 top-1/2 z-50 w-[420px] max-w-[calc(100vw-32px)] -translate-x-1/2 -translate-y-1/2 overflow-hidden rounded-lg border border-linear-border-strong bg-linear-surface-2 shadow-[0_30px_80px_rgba(0,0,0,0.6)]"
      >
        <div className="border-b border-linear-border px-5 py-4">
          <div className="flex items-start gap-2.5">
            <div className="mt-0.5 flex h-6 w-6 shrink-0 items-center justify-center rounded-full bg-linear-surface-3 text-linear-text">
              <Pencil className="h-3.5 w-3.5" strokeWidth={2.25} />
            </div>
            <div>
              <div className="text-sm font-semibold text-linear-text">Edit profile</div>
              <div className="mt-1 font-mono text-xs text-linear-text-2">{user.email}</div>
              <div className="mt-1 text-xs text-linear-text-3">
                Email changes go through the account&apos;s own confirm-email flow.
              </div>
            </div>
          </div>
        </div>
        <div className="flex flex-col gap-3 px-5 py-4">
          <div>
            <label className={LABEL} htmlFor="edit-name">Full name</label>
            <input
              id="edit-name"
              ref={inputRef}
              maxLength={200}
              value={name}
              onChange={(e) => setName(e.target.value)}
              disabled={busy}
              className={FIELD}
            />
          </div>
          <div>
            <label className={LABEL} htmlFor="edit-role">Account type</label>
            {roleEditable ? (
              <select
                id="edit-role"
                value={role}
                onChange={(e) => setRole(e.target.value)}
                disabled={busy}
                className={FIELD}
              >
                <option value="DOCTOR">Doctor</option>
                <option value="STAFF">Staff</option>
                <option value="ADMIN">Admin</option>
              </select>
            ) : (
              <div className="text-xs text-linear-text-3">
                {user.legacyRole} — not editable here.
              </div>
            )}
          </div>
        </div>
        <div className="flex items-center justify-end gap-2 border-t border-linear-border bg-linear-surface-1/40 px-5 py-3">
          <button type="button" onClick={onCancel} disabled={busy} className="qm-lin-btn">
            Cancel
          </button>
          <button
            type="button"
            onClick={save}
            disabled={!dirty || busy}
            className="qm-lin-btn qm-lin-btn-primary disabled:cursor-not-allowed disabled:opacity-60"
          >
            {busy ? 'Working…' : 'Save'}
          </button>
        </div>
      </div>
    </>
  );
}
