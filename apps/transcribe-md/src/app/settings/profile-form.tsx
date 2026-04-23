'use client';

import { useActionState, useEffect, useRef } from 'react';
import { toast } from 'sonner';
import { updateProfileAction, type ProfileState } from '@/actions/profile';

interface ProfileFormProps {
  defaultName: string;
  defaultSpecialty?: string;
  defaultNpi?: string;
  defaultClinicName?: string;
  defaultTimeZone?: string;
}

const SPECIALTY_OPTIONS = [
  '',
  'cardiology',
  'pain',
  'ortho',
  'primary',
  'pulmonology',
  'ophthalmology',
] as const;

export function ProfileForm({
  defaultName,
  defaultSpecialty = '',
  defaultNpi = '',
  defaultClinicName = '',
  defaultTimeZone = '',
}: ProfileFormProps) {
  const [state, formAction, pending] = useActionState<ProfileState, FormData>(
    updateProfileAction,
    null
  );
  const showSaved = state?.ok === true;

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
    <form
      action={formAction}
      style={{ display: 'flex', flexDirection: 'column', gap: 14 }}
    >
      <Row>
        <Field
          label="Display name"
          name="name"
          defaultValue={defaultName}
          required
          error={errors.name}
        />
        <Field
          label="Specialty"
          name="specialty"
          defaultValue={defaultSpecialty}
          as="select"
          options={SPECIALTY_OPTIONS.map((s) => ({
            value: s,
            label: s === '' ? 'Unspecified' : s[0].toUpperCase() + s.slice(1),
          }))}
          error={errors.specialty}
        />
      </Row>
      <Row>
        <Field
          label="NPI"
          name="npi"
          defaultValue={defaultNpi}
          placeholder="10-digit NPI"
          error={errors.npi}
        />
        <Field
          label="Clinic name"
          name="clinicName"
          defaultValue={defaultClinicName}
          placeholder="Optional — overrides practice name on exports"
          error={errors.clinicName}
        />
      </Row>
      <Field
        label="Time zone"
        name="timeZone"
        defaultValue={defaultTimeZone}
        placeholder="e.g. America/Los_Angeles"
        error={errors.timeZone}
      />
      {errors._form && (
        <p role="alert" style={{ fontSize: 12, color: 'var(--coral)' }}>
          {errors._form}
        </p>
      )}
      <div style={{ display: 'flex', alignItems: 'center', gap: 12, marginTop: 4 }}>
        <button
          type="submit"
          disabled={pending}
          className="qm-btn qm-btn-primary"
          style={{ padding: '9px 16px' }}
        >
          {pending ? 'Saving…' : 'Save profile'}
        </button>
        {showSaved && (
          <span
            style={{
              fontSize: 12,
              color: 'var(--mint)',
              fontFamily: 'var(--mono)',
            }}
          >
            Saved
          </span>
        )}
      </div>
    </form>
  );
}

function Row({ children }: { children: React.ReactNode }) {
  return (
    <div
      style={{
        display: 'grid',
        gridTemplateColumns: '1fr 1fr',
        gap: 14,
      }}
    >
      {children}
    </div>
  );
}

function Field({
  label,
  name,
  defaultValue,
  required,
  placeholder,
  error,
  as = 'input',
  options,
}: {
  label: string;
  name: string;
  defaultValue?: string;
  required?: boolean;
  placeholder?: string;
  error?: string;
  as?: 'input' | 'select';
  options?: { value: string; label: string }[];
}) {
  const id = `profile-${name}`;
  return (
    <div>
      <label
        htmlFor={id}
        style={{
          display: 'block',
          marginBottom: 6,
          fontSize: 11.5,
          color: 'var(--fg-3)',
          letterSpacing: '0.04em',
          textTransform: 'uppercase',
          fontFamily: 'var(--mono)',
        }}
      >
        {label}
      </label>
      {as === 'select' ? (
        <select
          id={id}
          name={name}
          defaultValue={defaultValue}
          className="qm-input"
        >
          {options?.map((o) => (
            <option key={o.value} value={o.value}>
              {o.label}
            </option>
          ))}
        </select>
      ) : (
        <input
          id={id}
          name={name}
          type="text"
          defaultValue={defaultValue}
          required={required}
          placeholder={placeholder}
          className="qm-input"
        />
      )}
      {error && (
        <p
          role="alert"
          style={{ marginTop: 6, fontSize: 12, color: 'var(--coral)' }}
        >
          {error}
        </p>
      )}
    </div>
  );
}
