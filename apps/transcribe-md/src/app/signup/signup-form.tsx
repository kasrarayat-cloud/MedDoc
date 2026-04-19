'use client';

import { useActionState, useEffect } from 'react';
import { useRouter } from 'next/navigation';
import Link from 'next/link';
import { ArrowRight } from 'lucide-react';
import { toast } from 'sonner';

import { SpecularButton } from '@/components/specular-button';
import { SpecialtyDropdown, type SpecialtyOption } from '@/components/specialty-dropdown';
import { signupAction, type AuthActionState } from '@/actions/auth';

const initialState: AuthActionState = null;

interface SignupFormProps {
  specialties: SpecialtyOption[];
}

export function SignupForm({ specialties }: SignupFormProps) {
  const [state, formAction, pending] = useActionState(signupAction, initialState);
  const router = useRouter();

  useEffect(() => {
    if (state && state.ok) {
      toast.success('Welcome to TranscribeMD', {
        description: "You're in. Start your first visit whenever you're ready.",
      });
      router.push(state.redirect);
      router.refresh();
    } else if (state && !state.ok && state.errors._form) {
      toast.error('Signup failed', { description: state.errors._form });
    }
  }, [state, router]);

  const errors = state && !state.ok ? state.errors : {};
  const values = state && !state.ok ? state.values ?? {} : {};

  return (
    <form action={formAction} className="space-y-4">
      <FieldLabel htmlFor="name" label="Full name">
        <input
          id="name"
          name="name"
          type="text"
          autoComplete="name"
          defaultValue={values.name ?? ''}
          required
          className={inputClass}
        />
        <FieldError message={errors.name} />
      </FieldLabel>

      <FieldLabel htmlFor="email" label="Email">
        <input
          id="email"
          name="email"
          type="email"
          autoComplete="email"
          defaultValue={values.email ?? ''}
          required
          className={inputClass}
        />
        <FieldError message={errors.email} />
      </FieldLabel>

      <FieldLabel htmlFor="password" label="Password">
        <input
          id="password"
          name="password"
          type="password"
          autoComplete="new-password"
          required
          className={inputClass}
        />
        <p className="mt-1.5 text-[11px] text-text-muted">
          At least 10 characters, with upper + lowercase letters and a digit.
        </p>
        <FieldError message={errors.password} />
      </FieldLabel>

      <FieldLabel htmlFor="specialty" label="Specialty">
        <SpecialtyDropdown
          options={specialties}
          name="specialty"
          defaultValue={values.specialty ?? ''}
        />
        <FieldError message={errors.specialty} />
      </FieldLabel>

      <label className="flex items-start gap-2.5 pt-1 text-[12px] text-text-tertiary">
        <input
          type="checkbox"
          name="acceptTerms"
          required
          className="mt-0.5 h-3.5 w-3.5 rounded border-border-emphasis bg-bg-surface-1 text-violet-500 focus:ring-violet-500/40"
        />
        <span>
          I agree to the terms of service and privacy policy.
        </span>
      </label>
      <FieldError message={errors.acceptTerms} />
      <FieldError message={errors._form} />

      <SpecularButton type="submit" variant="primary" size="lg" className="w-full">
        {pending ? 'Creating account…' : 'Create account'}
        {!pending && <ArrowRight className="h-4 w-4" />}
      </SpecularButton>

      <p className="text-center text-[13px] text-text-muted">
        Have an account?{' '}
        <Link
          href="/login"
          className="text-violet-400 hover:text-violet-300 transition-colors"
        >
          Sign in →
        </Link>
      </p>
    </form>
  );
}

const inputClass =
  'block w-full rounded-lg border border-border-default bg-bg-surface-1/60 px-3.5 py-2.5 text-[14px] text-text-primary placeholder:text-text-muted outline-none transition-colors duration-200 focus:border-violet-500 focus:ring-2 focus:ring-violet-500/30';

function FieldLabel({
  htmlFor,
  label,
  children,
}: {
  htmlFor: string;
  label: string;
  children: React.ReactNode;
}) {
  return (
    <div>
      <label
        htmlFor={htmlFor}
        className="mb-1.5 block text-[12px] font-medium tracking-tight text-text-tertiary"
      >
        {label}
      </label>
      {children}
    </div>
  );
}

function FieldError({ message }: { message?: string }) {
  if (!message) return null;
  return (
    <p role="alert" className="mt-1.5 text-[12px] text-danger">
      {message}
    </p>
  );
}
