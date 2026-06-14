import type { Metadata } from 'next';
import { SoapLab } from '../../../components/concepts/soap/SoapLab';

export const metadata: Metadata = {
  title: 'QuillMD — SOAP review concepts',
  description: 'Three redesign concepts for the SOAP review screen. Static mockups, synthetic data. Staging exploration.',
  robots: { index: false, follow: false },
};

export default function ConceptsSoapPage() {
  return <SoapLab />;
}
