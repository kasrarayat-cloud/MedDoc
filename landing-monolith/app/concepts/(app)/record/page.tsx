import type { Metadata } from 'next';
import { RecordScreen } from '../../../../components/concepts/app/RecordScreen';

export const metadata: Metadata = {
  title: 'QuillMD — New visit (concept)',
  description: 'Calm "just start" create/record concept with an honest recording state. Static mockup, synthetic data. Staging exploration.',
  robots: { index: false, follow: false },
};

export default function RecordConceptPage() {
  return <RecordScreen />;
}
