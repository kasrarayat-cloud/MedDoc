'use client';

import { useState } from 'react';
import { motion } from 'framer-motion';
import { Check } from 'lucide-react';
import { GradientBorder } from '@/components/gradient-border';
import { GradientText } from '@/components/gradient-text';
import { SpecularButton } from '@/components/specular-button';

const SPECIALTIES = [
  'Primary Care / Family Medicine',
  'Internal Medicine',
  'Cardiology',
  'Dermatology',
  'Psychiatry',
  'Pediatrics',
  'Orthopedics',
  'OB/GYN',
  'Other',
];

export function SignupForm() {
  const [state, setState] = useState<'idle' | 'submitting' | 'done'>('idle');

  async function handleSubmit(e: React.FormEvent<HTMLFormElement>) {
    e.preventDefault();
    setState('submitting');
    // TODO: Connect to real auth (Scribe shares NextAuth) in T-M2.
    // For now, simulate a network round-trip so the submit feels real.
    await new Promise((r) => setTimeout(r, 800));
    setState('done');
  }

  if (state === 'done') {
    return (
      <motion.div
        initial={{ opacity: 0, y: 12 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.4, ease: [0.4, 0, 0.2, 1] }}
        className="text-center"
      >
        <GradientBorder className="p-10">
          <div className="mx-auto flex h-12 w-12 items-center justify-center rounded-full bg-success/15">
            <Check className="h-5 w-5 text-success" />
          </div>
          <h1 className="mt-6 type-h2 text-text-primary">
            You&apos;re on the list.
          </h1>
          <p className="mt-4 text-[15px] leading-relaxed text-text-tertiary">
            We&apos;ll send your signin link once you&apos;re invited out of
            the private beta. In the meantime we&apos;ll only email you when
            there&apos;s actually news.
          </p>
        </GradientBorder>
      </motion.div>
    );
  }

  return (
    <motion.div
      initial={{ opacity: 0, y: 12 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.45, ease: [0.4, 0, 0.2, 1] }}
    >
      <h1 className="type-h1 text-text-primary">
        Start your <GradientText>free trial</GradientText>.
      </h1>
      <p className="mt-3 text-[15px] text-text-tertiary">
        10 free signed notes. 14 days. No credit card.
      </p>

      <form onSubmit={handleSubmit} className="mt-8 space-y-5">
        <Field label="Full name" name="fullName" type="text" required autoComplete="name" />
        <Field label="Email" name="email" type="email" required autoComplete="email" />
        <Field
          label="Password"
          name="password"
          type="password"
          required
          autoComplete="new-password"
          minLength={10}
          hint="At least 10 characters."
        />
        <div>
          <label
            className="block text-[13px] font-medium text-text-secondary"
            htmlFor="specialty"
          >
            Specialty
          </label>
          <select
            id="specialty"
            name="specialty"
            required
            defaultValue=""
            className="mt-2 w-full rounded-lg border border-border-default bg-bg-surface-2/80 px-3.5 py-2.5 text-[14px] text-text-primary outline-none transition-colors focus:border-violet-500 focus:ring-2 focus:ring-violet-500/30"
          >
            <option value="" disabled>
              Pick one…
            </option>
            {SPECIALTIES.map((s) => (
              <option key={s} value={s}>
                {s}
              </option>
            ))}
          </select>
        </div>

        <SpecularButton
          type="submit"
          variant="primary"
          size="lg"
          className="w-full"
          disabled={state === 'submitting'}
        >
          {state === 'submitting' ? 'Creating your account…' : 'Create account'}
        </SpecularButton>

        <p className="text-center text-[12px] text-text-muted">
          By signing up you agree to our{' '}
          <a href="/terms" className="text-text-tertiary underline-offset-4 hover:text-text-secondary hover:underline">
            Terms
          </a>{' '}
          and{' '}
          <a href="/privacy" className="text-text-tertiary underline-offset-4 hover:text-text-secondary hover:underline">
            Privacy Policy
          </a>
          .
        </p>
      </form>
    </motion.div>
  );
}

function Field({
  label,
  name,
  type,
  required,
  minLength,
  autoComplete,
  hint,
}: {
  label: string;
  name: string;
  type: React.HTMLInputTypeAttribute;
  required?: boolean;
  minLength?: number;
  autoComplete?: string;
  hint?: string;
}) {
  return (
    <div>
      <label
        htmlFor={name}
        className="block text-[13px] font-medium text-text-secondary"
      >
        {label}
      </label>
      <input
        id={name}
        name={name}
        type={type}
        required={required}
        minLength={minLength}
        autoComplete={autoComplete}
        className="mt-2 w-full rounded-lg border border-border-default bg-bg-surface-2/80 px-3.5 py-2.5 text-[14px] text-text-primary placeholder-text-muted outline-none transition-colors focus:border-violet-500 focus:ring-2 focus:ring-violet-500/30"
      />
      {hint && <p className="mt-1.5 text-[12px] text-text-muted">{hint}</p>}
    </div>
  );
}
