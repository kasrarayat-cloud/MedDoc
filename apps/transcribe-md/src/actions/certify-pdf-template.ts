'use server';

// ============================================================================
// Doctor-facing PDF-native certification (feat/pdf-native-finish-setup).
// ----------------------------------------------------------------------------
// The "My Note Format" upload extracts text and DISCARDS the PDF bytes, and the
// certify path had no caller — so a doctor who uploaded a flat-PDF form could
// never reach native export (his own page filled). This action is the missing
// self-serve step: the doctor re-uploads his blank form ONCE, we extract anchors
// + store the canvas + derive the header fields from the PDF + mark certified,
// and return a synthetic PREVIEW so he confirms placement. Doctor-scoped; the
// template must be his own. Certifying is independent of the export flag (it just
// prepares); the export gate still honors NEXT_PUBLIC_TEMPLATE_NATIVE_PDF.
// ============================================================================
import prisma from '@meddoc/db';
import { requireSession } from '@/lib/auth';
import { certifyPdfTemplate, previewPdfTemplateFill } from '@/lib/pdf-native/certify';

export type CertifyPdfResult =
  | { ok: true; anchors: number; missing: string[]; headerFields: number; previewBase64?: string }
  | { ok: false; error: string };

export async function certifyPdfTemplateAction(formData: FormData): Promise<CertifyPdfResult> {
  const session = await requireSession();
  const doctorId = session.user.id;

  const templateId = String(formData.get('templateId') ?? '');
  const file = formData.get('file');
  if (!templateId) return { ok: false, error: 'Missing template.' };
  if (!(file instanceof File) || file.size === 0) {
    return { ok: false, error: 'Choose your blank form PDF to finish setup.' };
  }
  const isPdf =
    file.type === 'application/pdf' || file.name.toLowerCase().endsWith('.pdf');
  if (!isPdf) {
    return {
      ok: false,
      error: 'Native export needs the original flat PDF form — not a Word doc or image.',
    };
  }

  // Ownership — the template must be the caller's own (never another doctor's).
  const owned = await prisma.noteTemplate.findFirst({
    where: { id: templateId, doctorId },
    select: { id: true, sections: true, styleProfile: true },
  });
  if (!owned) return { ok: false, error: "That template doesn't exist or isn't yours." };

  const bytes = Buffer.from(await file.arrayBuffer());
  try {
    // Scoped to the caller; when no anchor resolves, certify leaves any prior
    // canvas + cert INTACT and only flags pending (never clobbers a good cert).
    const res = await certifyPdfTemplate({ templateId, pdfBytes: bytes, doctorId });

    if (res.anchors.length === 0) {
      return {
        ok: false,
        error:
          "Couldn't find the form's fields in this PDF. Upload the original flat form (with labels like PATIENT NAME: and PROCEDURE:) — a scanned image or a re-export won't work.",
      };
    }

    // One-time synthetic preview so the doctor confirms the answers land in his
    // blanks before he relies on it (no visit, no patient data).
    let previewBase64: string | undefined;
    try {
      const sections =
        ((owned.sections as unknown) as Array<{ key: string; label: string }>) ?? [];
      const preview = await previewPdfTemplateFill({
        sections,
        headerFields: res.headerFields,
        pdfBytes: bytes,
      });
      previewBase64 = Buffer.from(preview).toString('base64');
    } catch {
      // Preview is a nicety; certification already succeeded.
    }

    return {
      ok: true,
      anchors: res.anchors.length,
      missing: res.missing,
      headerFields: res.headerFields.length,
      previewBase64,
    };
  } catch {
    return { ok: false, error: 'Setup failed — please try again.' };
  }
}
