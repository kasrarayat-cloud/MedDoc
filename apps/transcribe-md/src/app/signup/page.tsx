import type { Metadata } from 'next';
import { redirect } from 'next/navigation';

import { auth } from '@/lib/nextauth';
import { AuthShell } from '@/components/ui/auth-shell';
import { SignupForm } from './signup-form';

export const metadata: Metadata = { title: 'Sign up' };

export default async function SignupPage() {
  const session = await auth();
  if (session?.user?.id) {
    redirect('/dashboard');
  }

  return (
    <AuthShell
      eyebrow="New to QuillMD"
      title={
        <>
          Create your <em>account</em>
        </>
      }
      // ⚠️ COPY REGISTER, and this one was a FALSE CLAIM rather than a tone
      // problem. The old subtitle read "Free for 14 days. No credit card."
      // There is no trial: no `trial*` field in the Prisma schema, no trial
      // logic in `actions/auth.ts` or `lib/signup-invite.ts`, and the only
      // occurrence of "14 days" in `src/` was this string. It sat directly
      // above a REQUIRED invite-code field, on a product that has been
      // invite-only since 2026-07-28. Restyling that into new type is the
      // failure C1-g's copy sweep exists to prevent, so it is fixed here
      // rather than carried — C1-g's bullet for this string is DISCHARGED.
      //
      // The replacement deliberately does NOT contain "invite-only during
      // the pilot", which is the helper paragraph inside signup-form.tsx.
      // (The reason is now weaker than it was when this was written: the same
      // change rescoped `14-auth-signup-onboarding.spec.ts` to
      // `getByRole('alert')`, which is indifferent to DOM order, so a second
      // occurrence no longer moves that assertion. Keeping the strings
      // distinct is still right — duplicated product copy drifts, and a page
      // that says the same sentence twice reads as a mistake — but it is a
      // copy decision now, not a test constraint. Said precisely because a
      // comment asserting a live constraint that has been removed is how the
      // next reader inherits a rule nobody is enforcing.)
      subtitle="You'll need the invite code for your practice."
    >
      <SignupForm />
    </AuthShell>
  );
}
