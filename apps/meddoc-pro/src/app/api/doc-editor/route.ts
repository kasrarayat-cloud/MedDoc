import { NextRequest, NextResponse } from 'next/server';
import { processWithAI, AIAction } from '@/lib/ai-service';
import { getSession } from '@/lib/auth';
import { logApiUsage } from '@/lib/usage';
import { logAudit } from '@/lib/audit';
import { checkRateLimit, RATE_LIMITS } from '@/lib/rate-limit';

// ========================================
// Doc Editor API - Upload, Parse, AI Process
// ========================================

// Helper: Extract text from .docx buffer using raw XML parsing
async function extractTextFromDocx(buffer: ArrayBuffer): Promise<string> {
  const JSZip = (await import('jszip')).default;
  const zip = await JSZip.loadAsync(buffer);

  const documentXml = await zip.file('word/document.xml')?.async('string');
  if (!documentXml) {
    throw new Error('Invalid .docx file: missing document.xml');
  }

  // Extract text from XML - simple regex-based extraction
  // Matches <w:t> and <w:t xml:space="preserve"> elements
  const textMatches = documentXml.match(/<w:t[^>]*>([\s\S]*?)<\/w:t>/g);
  if (!textMatches) return '';

  const paragraphs: string[] = [];

  // Split by paragraph markers
  const fullXml = documentXml;
  const paraRegex = /<w:p[\s>][\s\S]*?<\/w:p>/g;
  let match;

  while ((match = paraRegex.exec(fullXml)) !== null) {
    const paraXml = match[0];
    const texts = paraXml.match(/<w:t[^>]*>([\s\S]*?)<\/w:t>/g);
    if (texts) {
      const paraText = texts
        .map((t) => {
          const innerMatch = t.match(/<w:t[^>]*>([\s\S]*?)<\/w:t>/);
          return innerMatch ? innerMatch[1] : '';
        })
        .join('');

      if (paraText.trim()) {
        // Check for tab characters in the XML
        const hasTabs = paraXml.includes('<w:tab/>');
        if (hasTabs) {
          // Reconstruct with tabs
          let fullText = '';
          const runs = paraXml.match(/<w:r[\s>][\s\S]*?<\/w:r>/g) || [];
          for (const run of runs) {
            if (run.includes('<w:tab/>')) {
              fullText += '\t';
            }
            const runTexts = run.match(/<w:t[^>]*>([\s\S]*?)<\/w:t>/g);
            if (runTexts) {
              fullText += runTexts
                .map((t) => {
                  const m = t.match(/<w:t[^>]*>([\s\S]*?)<\/w:t>/);
                  return m ? m[1] : '';
                })
                .join('');
            }
          }
          paragraphs.push(fullText);
        } else {
          paragraphs.push(paraText);
        }
      }
    }
  }

  // Clean up the text - remove any leftover XML tags and decode entities
  return paragraphs
    .join('\n')
    .replace(/<[^>]+>/g, '') // Remove any remaining XML/HTML tags
    .replace(/&amp;/g, '&')
    .replace(/&lt;/g, '<')
    .replace(/&gt;/g, '>')
    .replace(/&quot;/g, '"')
    .replace(/&apos;/g, "'")
    .replace(/&#x2019;/g, '\u2019') // Right single quote
    .replace(/&#x201C;/g, '\u201C') // Left double quote
    .replace(/&#x201D;/g, '\u201D') // Right double quote
    .replace(/\t{3,}/g, '\t\t') // Collapse excessive tabs
    .trim();
}

// POST: Process document with AI
export async function POST(request: NextRequest) {
  // Auth guard — reject unauthenticated requests
  const session = await getSession();
  if (!session) {
    return NextResponse.json({ error: 'Unauthorized' }, { status: 401 });
  }

  // Rate limit per user (cheaper than transcribe, higher quota).
  const rl = checkRateLimit(session.user.id, RATE_LIMITS.docEditor);
  if (!rl.ok) {
    return NextResponse.json(
      {
        error: 'Too many doc-editor requests. Please slow down.',
        retryAfterSeconds: rl.retryAfterSeconds,
      },
      {
        status: 429,
        headers: {
          'Retry-After': String(rl.retryAfterSeconds),
          'X-RateLimit-Limit': String(rl.limit),
          'X-RateLimit-Remaining': '0',
        },
      }
    );
  }

  try {
    const contentType = request.headers.get('content-type') || '';

    // Handle multipart form data (file upload)
    if (contentType.includes('multipart/form-data')) {
      const formData = await request.formData();
      const file = formData.get('file') as File | null;
      const action = (formData.get('action') as string) || 'review';
      const message = (formData.get('message') as string) || '';
      const historyStr = formData.get('history') as string;

      if (!file) {
        return NextResponse.json({ error: 'No file uploaded' }, { status: 400 });
      }

      if (!file.name.endsWith('.docx')) {
        return NextResponse.json(
          { error: 'Only .docx files are supported' },
          { status: 400 }
        );
      }

      // Extract text from docx
      const buffer = await file.arrayBuffer();
      const documentContent = await extractTextFromDocx(buffer);

      if (!documentContent.trim()) {
        return NextResponse.json(
          { error: 'Could not extract text from the document' },
          { status: 400 }
        );
      }

      // Parse conversation history
      let conversationHistory: { role: 'user' | 'assistant'; content: string }[] = [];
      if (historyStr) {
        try {
          conversationHistory = JSON.parse(historyStr);
        } catch {
          // ignore parse errors
        }
      }

      // Process with AI
      const ai = await processWithAI({
        action: action as AIAction,
        documentContent,
        userMessage: message,
        conversationHistory,
      });

      void logApiUsage({
        feature: 'DOC_EDITOR',
        userId: session.user.id,
      practiceId: session.user.practiceId,
        tokens: ai.usage?.totalTokens ?? null,
      }).catch((err) => {
        console.error('[doc-editor] logApiUsage rejected unexpectedly:', err);
      });

      void logAudit({
        action: 'DOC_EDITOR_AI_SUGGESTED',
        targetType: 'doc_editor',
        targetId: null,
        metadata: {
          mode: 'upload',
          aiAction: action,
          documentBytes: documentContent.length,
          messageBytes: message.length,
          historyTurns: conversationHistory.length,
          suggestionBytes: ai.text.length,
          totalTokens: ai.usage?.totalTokens ?? null,
        },
      });

      // Keep client-facing shape identical to before the ai-service
      // refactor: `aiResponse` is the text string. Usage goes to the
      // metrics logger only, not down the wire.
      return NextResponse.json({
        success: true,
        documentContent,
        aiResponse: ai.text,
        fileName: file.name,
        fileSize: file.size,
      });
    }

    // Handle JSON body (follow-up messages without file re-upload)
    const body = await request.json();
    const { action, documentContent, message, conversationHistory } = body;

    if (!documentContent) {
      return NextResponse.json(
        { error: 'Missing document content' },
        { status: 400 }
      );
    }

    const ai = await processWithAI({
      action: action || 'chat',
      documentContent,
      userMessage: message || '',
      conversationHistory: conversationHistory || [],
    });

    void logApiUsage({
      feature: 'DOC_EDITOR',
      userId: session.user.id,
      practiceId: session.user.practiceId,
      tokens: ai.usage?.totalTokens ?? null,
    }).catch((err) => {
      console.error('[doc-editor] logApiUsage rejected unexpectedly:', err);
    });

    void logAudit({
      action: 'DOC_EDITOR_AI_SUGGESTED',
      targetType: 'doc_editor',
      targetId: null,
      metadata: {
        mode: 'follow_up',
        aiAction: action || 'chat',
        documentBytes: typeof documentContent === 'string' ? documentContent.length : 0,
        messageBytes: typeof message === 'string' ? message.length : 0,
        historyTurns: Array.isArray(conversationHistory) ? conversationHistory.length : 0,
        suggestionBytes: ai.text.length,
        totalTokens: ai.usage?.totalTokens ?? null,
      },
    });

    return NextResponse.json({
      success: true,
      aiResponse: ai.text,
    });
  } catch (error: unknown) {
    console.error('Doc editor error:', error);

    const errorMessage =
      error instanceof Error ? error.message : 'An unexpected error occurred';

    if (errorMessage.includes('OPENAI_API_KEY')) {
      return NextResponse.json(
        {
          error: 'API key not configured',
          details: 'Please set OPENAI_API_KEY in .env.local',
        },
        { status: 500 }
      );
    }

    return NextResponse.json(
      { error: 'Failed to process document', details: errorMessage },
      { status: 500 }
    );
  }
}
