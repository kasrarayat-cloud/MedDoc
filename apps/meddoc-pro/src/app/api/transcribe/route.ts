import { NextRequest, NextResponse } from 'next/server';
import OpenAI from 'openai';
import { getSession } from '@/lib/auth';
import { logApiUsage } from '@/lib/usage';
import { checkRateLimit, RATE_LIMITS } from '@/lib/rate-limit';

// ========================================
// Transcribe API - OpenAI Whisper
// Accepts audio blob, returns transcribed text
// ========================================

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
    console.error('Transcription error:', error);

    const errorMessage =
      error instanceof Error ? error.message : 'Unknown error';

    if (errorMessage.includes('OPENAI_API_KEY')) {
      return NextResponse.json(
        {
          error: 'OpenAI API key not configured',
          details: 'Please set OPENAI_API_KEY in .env.local',
        },
        { status: 500 }
      );
    }

    return NextResponse.json(
      { error: 'Transcription failed', details: errorMessage },
      { status: 500 }
    );
  }
}
