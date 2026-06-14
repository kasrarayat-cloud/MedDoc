import type { Metadata } from 'next';
import { DashboardScreen } from '../../../../components/concepts/app/DashboardScreen';

export const metadata: Metadata = {
  title: 'QuillMD — Dashboard (concept)',
  description: 'Calm "here\'s your work" dashboard concept. Static mockup, synthetic data. Staging exploration.',
  robots: { index: false, follow: false },
};

export default function DashboardConceptPage() {
  return <DashboardScreen />;
}
