import type { Metadata } from 'next';

import { AuthShell } from '@/components/ui/auth-shell';

import { WaitlistForm } from './waitlist-form';

export const metadata: Metadata = { title: 'Join the waitlist' };

// Invite-only pilot (2026-07-28). This is where every marketing CTA lands.
//
// It deliberately does NOT check for a session and does NOT redirect a signed-in
// user to the dashboard, unlike /signup: someone already using QuillMD may well
// be sending this link to a colleague, and bouncing them to their own dashboard
// would break that.
export default function WaitlistPage() {
  return (
    <AuthShell
      eyebrow="Invite-only pilot"
      title={
        <>
          Join the <em>waitlist</em>
        </>
      }
      subtitle="We're onboarding a small number of clinicians at a time. Leave your details and we'll be in touch when there's room."
    >
      <WaitlistForm />
    </AuthShell>
  );
}
