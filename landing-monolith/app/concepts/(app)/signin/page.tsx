import type { Metadata } from 'next';
import { SigninScreen } from '../../../../components/concepts/app/SigninScreen';

export const metadata: Metadata = {
  title: 'QuillMD — Sign in (concept)',
  description: 'Calm dark sign-in concept with explicit sign-in / sign-up / MFA states. Static mockup. Staging exploration.',
  robots: { index: false, follow: false },
};

export default function SigninConceptPage() {
  return <SigninScreen />;
}
