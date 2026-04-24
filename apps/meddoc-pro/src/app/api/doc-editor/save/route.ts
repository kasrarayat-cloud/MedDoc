import { NextRequest, NextResponse } from 'next/server';
import { z } from 'zod';
import {
  Document,
  Packer,
  Paragraph,
  TextRun,
  AlignmentType,
  TabStopType,
} from 'docx';
import { getSession } from '@/lib/auth';

// Audit H4 — reject oversized content before building docx. 100 KB
// is ~50 pages of plain text; comfortably more than any real doctor
// note, while keeping the docx generator out of OOM territory.
const MAX_CONTENT_BYTES = 100_000;

const SaveBodySchema = z.object({
  content: z
    .string()
    .min(1, 'No content provided')
    .max(MAX_CONTENT_BYTES, `Content exceeds ${MAX_CONTENT_BYTES} byte limit`),
  format: z.enum(['docx', 'pdf']).optional(),
  fileName: z.string().max(255).optional(),
});

// ========================================
// Save Document API - Export as Word / PDF
// ========================================

const FONT = 'Times New Roman';
const FONT_SIZE = 24; // 12pt

function textToDocxParagraphs(text: string): Paragraph[] {
  const lines = text.split('\n');
  const paragraphs: Paragraph[] = [];

  for (const line of lines) {
    const trimmed = line.trim();

    // Detect header fields (e.g., "DATE:", "PATIENT:", etc.)
    const isHeader = /^[A-Z][A-Z\s]+:/.test(trimmed);
    const isBold = isHeader || trimmed === 'Bakhtiar Moussazadeh, M.D.';

    if (trimmed === '') {
      paragraphs.push(new Paragraph({ spacing: { after: 80 }, children: [] }));
      continue;
    }

    // Handle tabs in content
    if (line.includes('\t')) {
      const parts = line.split('\t');
      const runs: TextRun[] = [];
      parts.forEach((part, idx) => {
        if (idx > 0) {
          runs.push(new TextRun({ text: '\t', font: FONT, size: FONT_SIZE }));
        }
        if (part.trim()) {
          const isLabelPart = idx === 0 && isHeader;
          runs.push(
            new TextRun({
              text: part,
              bold: isLabelPart,
              font: FONT,
              size: FONT_SIZE,
            })
          );
        }
      });

      paragraphs.push(
        new Paragraph({
          tabStops: [
            { type: TabStopType.LEFT, position: 3600 },
            { type: TabStopType.LEFT, position: 4800 },
          ],
          spacing: { after: 40 },
          children: runs,
        })
      );
    } else {
      // Regular paragraph
      paragraphs.push(
        new Paragraph({
          spacing: { after: isHeader ? 40 : 80 },
          alignment: !isHeader ? AlignmentType.JUSTIFIED : undefined,
          children: [
            new TextRun({
              text: trimmed,
              bold: isBold,
              font: FONT,
              size: FONT_SIZE,
            }),
          ],
        })
      );
    }
  }

  return paragraphs;
}

export async function POST(request: NextRequest) {
  // Auth guard — reject unauthenticated requests
  const session = await getSession();
  if (!session) {
    return NextResponse.json({ error: 'Unauthorized' }, { status: 401 });
  }

  try {
    const raw = await request.json().catch(() => null);
    const parsed = SaveBodySchema.safeParse(raw);
    if (!parsed.success) {
      return NextResponse.json(
        {
          error: 'Invalid request body',
          issues: parsed.error.issues.map((i) => ({
            path: i.path.join('.'),
            message: i.message,
          })),
        },
        { status: 400 }
      );
    }
    const { content, format, fileName } = parsed.data;

    // Clean the content - remove markdown artifacts that AI might add
    const cleanContent = content
      .replace(/```[\s\S]*?```/g, '') // Remove code blocks
      .replace(/\*\*(.*?)\*\*/g, '$1') // Remove bold markdown
      .replace(/\*(.*?)\*/g, '$1') // Remove italic markdown
      .replace(/^#+\s/gm, '') // Remove headers markdown
      .replace(/^-{3,}$/gm, '') // Remove horizontal rules
      .trim();

    // Build Word document from text
    const paragraphs = textToDocxParagraphs(cleanContent);

    const doc = new Document({
      styles: {
        default: {
          document: {
            run: { font: FONT, size: FONT_SIZE },
          },
        },
      },
      sections: [
        {
          properties: {
            page: {
              size: { width: 12240, height: 15840 },
              margin: { top: 1440, right: 1440, bottom: 1440, left: 1440 },
            },
          },
          children: paragraphs,
        },
      ],
    });

    const buffer = await Packer.toBuffer(doc);

    if (format === 'pdf') {
      // For PDF: return a note that server-side PDF needs LibreOffice
      // For now, we generate the docx and indicate the format
      // In production, you would use LibreOffice or a service to convert
      // For local dev, we return the docx with a note

      // Simple approach: return docx as pdf mimetype with a system note
      // Real implementation would use: soffice --headless --convert-to pdf
      return new NextResponse(new Uint8Array(buffer), {
        status: 200,
        headers: {
          'Content-Type': 'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
          'Content-Disposition': `attachment; filename="${encodeURIComponent(
            (fileName || 'document').replace(/\.docx$/i, '') + '_edited.docx'
          )}"`,
        },
      });
    }

    // Return Word document
    return new NextResponse(new Uint8Array(buffer), {
      status: 200,
      headers: {
        'Content-Type':
          'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
        'Content-Disposition': `attachment; filename="${encodeURIComponent(
          (fileName || 'document').replace(/\.docx$/i, '') + '_edited.docx'
        )}"`,
      },
    });
  } catch (error) {
    // Don't leak internal error details to the client — log server-side
    // and return an opaque failure. Matches the pattern transcribe-md
    // uses via withApiHandler.
    console.error('[api:doc-editor:save] failed:', error);
    return NextResponse.json(
      { error: 'Failed to save document' },
      { status: 500 }
    );
  }
}
