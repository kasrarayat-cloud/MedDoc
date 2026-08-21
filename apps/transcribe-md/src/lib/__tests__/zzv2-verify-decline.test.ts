/* THROWAWAY verification of the claimed provenance-metadata finding. Deleted after run. */
import { describe, expect, it, vi, beforeEach } from 'vitest';

const H = vi.hoisted(() => {
  const NATIVE = Buffer.from('PK-NATIVE-LETTERHEAD-TWIN-DOCX-49418');
  const STYLED = Buffer.from('PK-QUILLMD-GENERIC-STYLED-DOCX');
  return {
    NATIVE,
    STYLED,
    audits: [] as any[],
    infos: [] as string[],
    // The owner's certified twin: the twin loader RETURNS the doctor's own bytes.
    nativeOutcome: () => ({ native: null, reason: "visit_not_eligible" }),
  };
});

vi.mock('@/lib/auth', () => ({
  getSession: async () => ({ user: { id: 'user-owner', practiceId: 'p1' } }),
}));
vi.mock('@/lib/visit-export-server', () => ({
  loadVisitExportData: async () => ({
    patientName: 'Test Patient',
    createdAt: new Date('2026-08-01T00:00:00Z'),
    signedAt: new Date('2026-08-02T00:00:00Z'),
  }),
}));
// FLAT-PDF feature (pdf-native) declines for a DOCX-derived twin — the exact
// mechanism the commit's own header describes.
vi.mock('@/lib/pdf-native/export', () => ({
  nativePdfExport: async () => ({ pdf: null, applied: false, reason: 'not_certified' }),
}));
vi.mock('@/lib/template-twin/native-export', () => ({
  loadOrComputeNativeTemplateDocxForVisit: async () => H.nativeOutcome(),
}));
vi.mock('@/lib/docx-generator', () => ({
  generateVisitDocx: vi.fn(async () => H.STYLED),
}));
vi.mock('@/lib/docx-preview/convert', () => ({
  convertDocxToPdf: async (docx: Uint8Array) => ({
    pdf: new Uint8Array(Buffer.concat([Buffer.from('%PDF-1.7|from='), Buffer.from(docx)])),
    reason: null,
  }),
}));
vi.mock('@/lib/deliveries', () => ({ logDelivery: vi.fn() }));
vi.mock('@/lib/audit', () => ({
  logAudit: vi.fn(async (input: any) => { H.audits.push(input); }),
}));

import { GET as PDF_GET } from '@/app/api/visits/[id]/export/pdf/route';
import { GET as DOCX_GET } from '@/app/api/visits/[id]/export/docx/route';

const call = (g: any) => g({} as any, { params: Promise.resolve({ id: 'V-twin' }) } as any);

describe('certified-twin visit: PDF is served FROM the twin — what does the record say?', () => {
  beforeEach(() => {
    H.audits.length = 0;
    H.infos.length = 0;
    process.env.NEXT_PUBLIC_TEMPLATE_NATIVE_DOCX = 'true';
    vi.spyOn(console, 'info').mockImplementation((...a: any[]) => { H.infos.push(a.join(' ')); });
  });

  it('reports the bytes, the headers, the audit rows and the console line', async () => {
    const pdfRes = await call(PDF_GET);
    const pdfBody = Buffer.from(await pdfRes.arrayBuffer()).toString();
    const pdfAudit = H.audits.find((a) => a.action === 'EXPORT_PDF_DOWNLOADED');

    const docxRes = await call(DOCX_GET);
    const docxBody = Buffer.from(await docxRes.arrayBuffer()).toString();
    const docxAudit = H.audits.find((a) => a.action === 'EXPORT_DOCX_DOWNLOADED');

    const out = {
      pdf: {
        status: pdfRes.status,
        bodyIsTwin: pdfBody.includes('NATIVE-LETTERHEAD-TWIN'),
        bodyIsStyled: pdfBody.includes('GENERIC-STYLED'),
        'X-Native-Pdf-Applied': pdfRes.headers.get('X-Native-Pdf-Applied'),
        'X-Native-Pdf-Reason': pdfRes.headers.get('X-Native-Pdf-Reason'),
        auditMetadata: pdfAudit?.metadata,
      },
      docx: {
        status: docxRes.status,
        bodyIsTwin: docxBody.includes('NATIVE-LETTERHEAD-TWIN'),
        auditMetadata: docxAudit?.metadata,
      },
      consoleInfo: H.infos,
    };
    process.stdout.write('\n===REPRO===\n' + JSON.stringify(out, null, 2) + '\n===END===\n');

    // The bytes agree (the fix works).
    expect(out.pdf.bodyIsTwin).toBe(false);
    expect(out.docx.bodyIsTwin).toBe(false);
  });
});
