'use client';

import { useActionState, useEffect, useRef } from 'react';
import { toast } from 'sonner';
import { updateProfileAction, type ProfileState } from '@/actions/profile';

// Phase 5 — Linear V1 Faithful profile form. Server-action signature
// (updateProfileAction, ProfileState) and field validation are
// unchanged per PROTECTED_CONTRACTS.

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

const inputStyle: React.CSSProperties = {
  width: '100%',
  height: 32,
  padding: '0 10px',
  background: 'var(--color-linear-surface-2)',
  border: '1px solid var(--color-linear-border)',
  borderRadius: 6,
  color: 'var(--color-linear-text)',
  fontFamily: 'var(--font-sans)',
  fontSize: 13,
  outline: 'none',
  transition: 'border-color 100ms ease',
};

export function ProfileForm({
  defaultName,
  defaultSpecialty = '',
  defaultNpi = '',
  defaultClinicName = '',
  defaultTimeZone = '',
}: ProfileFormProps) {
  const [state, formAction, pending] = useActionState<ProfileState, FormData>(
    updateProfileAction,
    null,
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
        <p
          role="alert"
          style={{
            fontFamily: 'var(--font-sans)',
            fontSize: 12,
            color: 'var(--color-linear-coral)',
          }}
        >
          {errors._form}
        </p>
      )}
      <div
        style={{
          display: 'flex',
          alignItems: 'center',
          gap: 12,
          marginTop: 4,
        }}
      >
        <button
          type="submit"
          disabled={pending}
          className="qm-lin-btn-primary"
          style={{ height: 30, padding: '0 14px', fontSize: 12.5 }}
        >
          {pending ? 'Saving…' : 'Save profile'}
        </button>
        {showSaved && (
          <span
            style={{
              fontFamily: 'var(--font-mono)',
              fontSize: 11,
              color: 'var(--color-linear-sage-bright)',
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
          fontFamily: 'var(--font-mono)',
          fontSize: 10.5,
          color: 'var(--color-linear-text-3)',
          letterSpacing: '0.06em',
          textTransform: 'uppercase',
          fontWeight: 500,
        }}
      >
        {label}
      </label>
      {as === 'select' ? (
        <select id={id} name={name} defaultValue={defaultValue} style={inputStyle}>
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
          style={inputStyle}
        />
      )}
      {error && (
        <p
          role="alert"
          style={{
            marginTop: 6,
            fontFamily: 'var(--font-sans)',
            fontSize: 12,
            color: 'var(--color-linear-coral)',
          }}
        >
          {error}
        </p>
      )}
    </div>
  );
}
