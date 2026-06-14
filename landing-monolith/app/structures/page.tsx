import type { Metadata } from 'next';
import { StructureLab } from '../../components/structures/StructureLab';

export const metadata: Metadata = {
  title: 'QuillMD — Structure Concepts',
  description: 'Five structurally-distinct landing architectures for QuillMD. Staging exploration.',
  robots: { index: false, follow: false },
};

export default function StructuresPage() {
  return <StructureLab />;
}
