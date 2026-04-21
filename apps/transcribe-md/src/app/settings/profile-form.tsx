'use client';

import { useActionState, useEffect, useRef } from 'react';
import { toast } from 'sonner';
import { SpecularButton } from '@/components/specular-button';
import { updateProfileAction, type ProfileState } from '@/actions/profile';

interface ProfileFormProps {
  defaultName: string;
}

// T-M18.3 A22: specialty input removed. It was never persisted, and
// the displayed default came from the doctor's most-recent visit —
// which remains the actual source of truth and is still what the
// /visits/new form pre-fills.
export function ProfileForm({ defaultName }: ProfileFormProps) {
  const [state, formAction, pending] = useActionState<ProfileState, FormData>(
    updateProfileAction,
    null
  );
  // Show "Saved" while the most recent save is still the last action.
  const showSaved = state?.ok === true;

  // Fire a toast on each successful save. Keyed by savedAt so a repeat
  // save produces a fresh toast rather than silently updating the same
  // one. Errors also toast so the user notices them if the inline
  // field error is below the fold.
  const lastSavedAt = useRef<number | null>(null);
  useEffect(() => {
    if (state?.ok && state.savedAt !== lastSavedAt.current) {
      lastSavedAt.current = state.savedAt;
      toast.success('Profile updated', {
        description: 'Your changes are saved.',
      });
    } else if (state && !state.ok && state.errors._form) {
      toast.error('Could not save profile', {
        description: state.errors._form,
      });
    }
  }, [state]);

  const errors = state && !state.ok ? state.errors : {};

  return (
    <form action={formAction} className="space-y-4">
      <div>
        <label
          htmlFor="profile-name"
          className="mb-1.5 block text-[12px] font-medium tracking-tight text-text-tertiary"
        >
          Name
        </label>
        <input
          id="profile-name"
          name="name"
          type="text"
          defaultValue={defaultName}
          required
          className={inputClass}
        />
        <FieldError message={errors.name} />
      </div>

      <FieldError message={errors._form} />

      <div className="flex items-center gap-3 pt-1">
        <SpecularButton type="submit" variant="primary" size="md">
          {pending ? 'Saving…' : 'Save'}
        </SpecularButton>
        {showSaved && (
          <span className="text-[12px] text-success">Saved</span>
        )}
      </div>
    </form>
  );
}

const inputClass =
  'block w-full rounded-lg border border-border-default bg-bg-surface-1/60 px-3.5 py-2.5 text-[14px] text-text-primary placeholder:text-text-muted outline-none transition-colors duration-200 focus:border-violet-500 focus:ring-2 focus:ring-violet-500/30';

function FieldError({ message }: { message?: string }) {
  if (!message) return null;
  return (
    <p role="alert" className="mt-1.5 text-[12px] text-danger">
      {message}
    </p>
  );
}
