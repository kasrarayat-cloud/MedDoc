import type { Metadata } from 'next';
import { FinalLanding } from '../../components/final/FinalLanding';

export const metadata: Metadata = {
  title: 'QuillMD — The note writes itself',
  description:
    'Evidence-anchored clinical notes from the visit, machine-verified, with a review lane for anything it can’t ground. You sign every note. $49 flat, HIPAA-ready, BAA included, US-hosted.',
  robots: { index: false, follow: false }, // staging review page
};

export default function FinalPage() {
  return <FinalLanding />;
}
