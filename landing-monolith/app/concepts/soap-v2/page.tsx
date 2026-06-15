import type { Metadata } from 'next';
import { SoapLabV2 } from '../../../components/concepts/soap-v2/SoapLabV2';

export const metadata: Metadata = {
  title: 'QuillMD — SOAP review v2 concepts',
  description:
    'Two full-width SOAP-review redesigns that never place secondary content beside the note. Static mockups, synthetic data. Staging exploration.',
  robots: { index: false, follow: false },
};

export default function ConceptsSoapV2Page() {
  return <SoapLabV2 />;
}
