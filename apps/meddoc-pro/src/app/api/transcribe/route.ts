import { NextRequest, NextResponse } from 'next/server';
import OpenAI from 'openai';
import { getSession } from '@/lib/auth';
import { logApiUsage } from '@/lib/usage';
import { checkRateLimit, RATE_LIMITS } from '@/lib/rate-limit';

// ========================================
// Transcribe API - OpenAI Whisper
// Accepts audio blob, returns transcribed text
// ========================================

// Whisper-supported formats. Reject anything outside this list before
// bytes traverse the stack — avoids spending the round-trip to OpenAI
// on audio the API will bounce back anyway, and closes the audit H4
// "no MIME whitelist on uploaded audio" finding.
const ALLOWED_MIME = new Set([
  'audio/webm',
  'audio/ogg',
  'audio/wav',
  'audio/x-wav',
  'audio/mp4',
  'audio/mpeg',
  'audio/mp3',
  'audio/flac',
  'audio/m4a',
  'audio/x-m4a',
]);

let openaiClient: OpenAI | null = null;

function getClient(): OpenAI {
  if (!openaiClient) {
    const apiKey = process.env.OPENAI_API_KEY;
    if (!apiKey?.trim()) {
      throw new Error('OPENAI_API_KEY is not configured');
    }
    openaiClient = new OpenAI({ apiKey });
  }
  return openaiClient;
}

export async function POST(request: NextRequest) {
  // Auth guard — reject unauthenticated requests
  const session = await getSession();
  if (!session) {
    return NextResponse.json({ error: 'Unauthorized' }, { status: 401 });
  }

  // Rate limit per user. Protects against a runaway client burning the
  // OpenAI bill. Returns 429 with Retry-After so clients can back off.
  const rl = checkRateLimit(session.user.id, RATE_LIMITS.transcribe);
  if (!rl.ok) {
    return NextResponse.json(
      {
        error: 'Too many transcription requests. Please slow down.',
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
    const formData = await request.formData();
    const audioFile = formData.get('audio') as File | null;

    if (!audioFile) {
      return NextResponse.json(
        { error: 'No audio file provided' },
        { status: 400 }
      );
    }

    // MIME whitelist — see ALLOWED_MIME at top of file.
    const mime = (audioFile.type ?? '').split(';')[0]!.trim();
    if (!ALLOWED_MIME.has(mime)) {
      return NextResponse.json(
        {
          error: `Unsupported audio format: ${mime || '(missing)'}. Expected webm/ogg/wav/mp4/mpeg/flac/m4a.`,
        },
        { status: 415 }
      );
    }

    // Validate file size (max 25MB per Whisper API)
    if (audioFile.size > 25 * 1024 * 1024) {
      return NextResponse.json(
        { error: 'Audio file too large (max 25MB)' },
        { status: 400 }
      );
    }

    // Validate file is not empty
    if (audioFile.size < 100) {
      return NextResponse.json(
        { error: 'Audio file is empty', text: '' },
        { status: 200 }
      );
    }

    const client = getClient();

    // Using `verbose_json` (not plain `json`) so we get `duration` back —
    // Whisper bills $0.006/minute and without duration we can only fall
    // back to a flat per-hit estimate. `verbose_json` also returns
    // segments/language we don't currently use but doesn't cost extra
    // (billing is always per audio-minute).
    const transcription = await client.audio.transcriptions.create({
      file: audioFile,
      model: 'whisper-1',
      language: 'en',
      response_format: 'verbose_json',
    });

    // verbose_json schema: { task, language, duration, text, segments }.
    // `duration` is a float in seconds; round for the Int column.
    const durationSeconds =
      typeof transcription.duration === 'number'
        ? Math.round(transcription.duration)
        : null;

    void logApiUsage({
      feature: 'TRANSCRIBE',
      userId: session.user.id,
      practiceId: session.user.practiceId,
      durationSeconds,
    }).catch((err) => {
      console.error('[transcribe] logApiUsage rejected unexpectedly:', err);
    });

    return NextResponse.json({
      success: true,
      text: transcription.text || '',
    });
  } catch (error: unknown) {
    // Log server-side (scrub once we adopt redactPhi across meddoc-pro).
    // Don't leak OpenAI error text to the client — it can echo prompt
    // fragments containing PHI.
    console.error('[api:transcribe] failed:', error);
    return NextResponse.json(
      { error: 'Transcription failed' },
      { status: 500 }
    );
  }
}
