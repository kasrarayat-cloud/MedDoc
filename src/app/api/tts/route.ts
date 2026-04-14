import { NextRequest, NextResponse } from 'next/server';
import OpenAI from 'openai';
import { getSession } from '@/lib/auth';
import { logApiUsage } from '@/lib/usage';
import { checkRateLimit, RATE_LIMITS } from '@/lib/rate-limit';

// ============================================================================
// TTS API — OpenAI gpt-4o-mini-tts (voice: nova)
// ----------------------------------------------------------------------------
// Accepts JSON `{ text }`, returns audio/mpeg. Used by the GlobalAIAssistant
// voice mode to speak each assistant turn back to the doctor.
//
// Voice = "nova" — warm, professional, clear on medical terminology. Picked
// over alloy (too neutral), sage (too soft), onyx (too deep) for the clinic
// context.
//
// Auth-gated and rate-limited per user (60/min) so a runaway client can't
// burn the OpenAI bill. Costs scale with audio LENGTH not request count, so
// length cap is the real spend protection — enforced at 4000 input chars
// (~30 seconds of speech), more than any natural assistant reply.
// ============================================================================

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

const MAX_INPUT_CHARS = 4000;

export async function POST(request: NextRequest) {
  const session = await getSession();
  if (!session) {
    return NextResponse.json({ error: 'Unauthorized' }, { status: 401 });
  }

  const rl = checkRateLimit(session.user.id, RATE_LIMITS.tts);
  if (!rl.ok) {
    return NextResponse.json(
      {
        error: 'Too many TTS requests. Please slow down.',
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

  let text: string;
  try {
    const body = (await request.json()) as { text?: string };
    text = (body.text ?? '').trim();
  } catch {
    return NextResponse.json({ error: 'Invalid JSON body' }, { status: 400 });
  }

  if (!text) {
    return NextResponse.json({ error: 'No text provided' }, { status: 400 });
  }
  if (text.length > MAX_INPUT_CHARS) {
    return NextResponse.json(
      { error: `Text exceeds ${MAX_INPUT_CHARS}-char limit` },
      { status: 400 }
    );
  }

  try {
    const client = getClient();
    const speech = await client.audio.speech.create({
      model: 'gpt-4o-mini-tts',
      voice: 'nova',
      input: text,
      response_format: 'mp3',
    });
    const buffer = Buffer.from(await speech.arrayBuffer());

    // Log usage. Cost scales with input chars, not buffer size; we log the
    // input length so metrics has something honest to aggregate on.
    void logApiUsage({
      feature: 'TTS',
      userId: session.user.id,
      practiceId: session.user.practiceId,
      tokens: text.length,
    }).catch((err) => {
      console.error('[tts] logApiUsage rejected:', err);
    });

    return new NextResponse(new Uint8Array(buffer), {
      status: 200,
      headers: {
        'Content-Type': 'audio/mpeg',
        'Cache-Control': 'no-store',
      },
    });
  } catch (error) {
    console.error('[tts] OpenAI call failed:', error);
    const message = error instanceof Error ? error.message : 'TTS failed';
    if (message.includes('OPENAI_API_KEY')) {
      return NextResponse.json(
        {
          error: 'OpenAI API key not configured',
          details: 'Please set OPENAI_API_KEY in .env.local',
        },
        { status: 500 }
      );
    }
    return NextResponse.json({ error: 'TTS failed', details: message }, { status: 500 });
  }
}
