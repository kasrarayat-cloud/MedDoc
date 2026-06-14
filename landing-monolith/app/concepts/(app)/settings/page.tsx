import type { Metadata } from 'next';
import { SettingsScreen } from '../../../../components/concepts/app/SettingsScreen';

export const metadata: Metadata = {
  title: 'QuillMD — Settings (concept)',
  description: 'Calm settings concept — section rail + panel, opt-in note format, one danger zone. Static mockup. Staging exploration.',
  robots: { index: false, follow: false },
};

export default function SettingsConceptPage() {
  return <SettingsScreen />;
}
