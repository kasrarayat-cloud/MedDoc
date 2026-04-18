'use client';

import { useActionState } from 'react';
import { SpecularButton } from '@/components/specular-button';
import { SpecialtyDropdown, type SpecialtyOption } from '@/components/specialty-dropdown';
import { updateProfileAction, type ProfileState } from '@/actions/profile';

interface ProfileFormProps {
  defaultName: string;
  defaultSpecialty: string;
  specialties: SpecialtyOption[];
}

export function ProfileForm({
  defaultName,
  defaultSpecialty,
  specialties,
}: ProfileFormProps) {
  const [state, formAction, pending] = useActionState<ProfileState, FormData>(
    updateProfileAction,
    null
  );
  // Show "Saved" while the most recent save is still the last action. The
  // CSS transition on opacity handles the gentle fade-out — no setState
  // inside an effect, no cascading re-renders.
  const showSaved = state?.ok === true;

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

      <div>
        <label className="mb-1.5 block text-[12px] font-medium tracking-tight text-text-tertiary">
          Primary specialty
        </label>
        <SpecialtyDropdown
          options={specialties}
          name="specialty"
          defaultValue={defaultSpecialty}
        />
        <FieldError message={errors.specialty} />
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
