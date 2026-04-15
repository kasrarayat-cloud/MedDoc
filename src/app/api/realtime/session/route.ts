import { NextRequest, NextResponse } from 'next/server';
import { getSession } from '@/lib/auth';
import { logAudit } from '@/lib/audit';
import { getPatientById } from '@/lib/data/patients';
import { listNotesByPatient } from '@/lib/data/clinical-notes';
import { listAppointmentsByPatient, type AppointmentView } from '@/lib/data/appointments';
import { REALTIME_TOOLS, buildSystemPrompt } from '@/lib/realtime/tools';
import { checkVoiceCap } from '@/lib/realtime/usage-cap';

// ============================================================================
// /api/realtime/session — mint an ephemeral OpenAI Realtime session token
// ----------------------------------------------------------------------------
// Browser POSTs `{ patientId }`. We:
//   1. AuthZ + tenant-guard the patient
//   2. Check the user's daily voice-minutes cap
//   3. Load recent notes for the system prompt context
//   4. Call OpenAI's POST /v1/realtime/sessions with model + voice + tools
//      + system instructions
//   5. Return the ephemeral `client_secret.value` to the browser
//
// The browser uses that token to open a WebRTC peer connection directly to
// OpenAI. Our OPENAI_API_KEY never leaves the server. The token is short-
// lived (~1 minute) — long enough to establish the connection, not long
// enough to be useful if leaked.
//
// Tools: registered here (server-side) so the model knows what it can call.
// When the model decides to call one, the browser receives a function_call
// event and POSTs to /api/assistant-tool, where the actual server action
// runs with full auth + tenant + audit.
// ============================================================================

const REALTIME_MODEL = 'gpt-4o-realtime-preview';
// Voice is env-tunable so you can A/B without a redeploy. Options (per
// OpenAI Realtime docs): alloy, ash, ballad, coral, echo, sage, shimmer,
// verse. Default `coral` = warm + clinical. `alloy` = most neutral/
// professional. `shimmer` = smooth. `sage` = calm.
const REALTIME_VOICE = (process.env.REALTIME_VOICE?.trim() || 'coral') as
  | 'alloy' | 'ash' | 'ballad' | 'coral' | 'echo' | 'sage' | 'shimmer' | 'verse';
const OPENAI_REALTIME_SESSIONS_URL = 'https://api.openai.com/v1/realtime/sessions';

export async function POST(request: NextRequest) {
  const session = await getSession();
  if (!session) {
    return NextResponse.json({ error: 'Unauthorized' }, { status: 401 });
  }

  // Cost circuit-breaker — refuse new sessions once the doctor's daily
  // minute budget is gone. Real refill happens at UTC midnight.
  const cap = checkVoiceCap(session.user.id);
  if (!cap.ok) {
    return NextResponse.json(
      {
        error: `Daily voice limit reached (${cap.cap} min). Resets at midnight UTC.`,
        used: cap.used,
        cap: cap.cap,
      },
      { status: 429 }
    );
  }

  let body: { patientId?: string; timezone?: string };
  try {
    body = (await request.json()) as { patientId?: string; timezone?: string };
  } catch {
    return NextResponse.json({ error: 'Invalid JSON body' }, { status: 400 });
  }

  const patientId = body.patientId?.trim();
  if (!patientId) {
    return NextResponse.json({ error: 'patientId is required' }, { status: 400 });
  }
  const timezone = sanitizeTimezone(body.timezone);

  // Tenant guard — Patient must be visible to this session. patientAccessWhere
  // (under getPatientById) handles cross-practice + DOCTOR-scope rules.
  const patient = await getPatientById(patientId, session);
  if (!patient) {
    return NextResponse.json({ error: 'Patient not found' }, { status: 404 });
  }

  // Every chart surface the model might need to target. All tenant-
  // scoped through the patient relation filter.
  const [recentNotes, customProcedures, finalReports, patientFiles, appointments] =
    await Promise.all([
      listNotesByPatient(patientId, 'CLINICAL_NOTE', session),
      listNotesByPatient(patientId, 'CUSTOM_PROCEDURE', session),
      listNotesByPatient(patientId, 'FINAL_REPORT', session),
      listNotesByPatient(patientId, 'PATIENT_FILE', session),
      listAppointmentsByPatient(patientId, session),
    ]);
  const upcomingAppointments = filterUpcomingAppointments(appointments);

  const apiKey = process.env.OPENAI_API_KEY;
  if (!apiKey) {
    return NextResponse.json(
      { error: 'OPENAI_API_KEY is not configured' },
      { status: 500 }
    );
  }

  // Mint the ephemeral session.
  let openaiResp: Response;
  try {
    openaiResp = await fetch(OPENAI_REALTIME_SESSIONS_URL, {
      method: 'POST',
      headers: {
        Authorization: `Bearer ${apiKey}`,
        'Content-Type': 'application/json',
        // Required header for the Realtime API while in beta.
        'OpenAI-Beta': 'realtime=v1',
      },
      body: JSON.stringify({
        model: REALTIME_MODEL,
        voice: REALTIME_VOICE,
        instructions: buildSystemPrompt({
          patient,
          recentNotes: recentNotes.slice(0, 5),
          customProcedures: customProcedures.slice(0, 5),
          finalReports: finalReports.slice(0, 5),
          patientFiles: patientFiles.slice(0, 5),
          upcomingAppointments: upcomingAppointments.slice(0, 5),
          currentDateIso: new Date().toISOString(),
          timezone,
        }),
        tools: REALTIME_TOOLS,
        // Semantic VAD — ML classifier that distinguishes human speech
        // from ambient noise (breathing, chair scrapes, HVAC). Much better
        // in a clinic setting than the older server_vad threshold detector.
        //
        // eagerness="medium" — OpenAI's balanced default. "low" was
        // over-tuned for noise avoidance: the classifier already handles
        // noise, but low eagerness also delayed commit-on-speech-stop,
        // so the doctor would sometimes finish a sentence and nothing
        // would happen. Medium still respects the ML classifier's noise
        // filtering while responding promptly when the doctor's done.
        turn_detection: {
          type: 'semantic_vad',
          eagerness: 'medium',
          // Explicitly enable server-driven response creation on every
          // end-of-user-turn. Without this, subsequent turns after the
          // first can silently fail to trigger a model response — the
          // doctor asks a follow-up, the session stays quiet until they
          // make noise (which OpenAI registers as a new turn).
          create_response: true,
          // Let the doctor interrupt the AI mid-speech without waiting
          // for it to finish.
          interrupt_response: true,
        },
        // Stream both directions as PCM16 — the WebRTC pipe handles the
        // codec negotiation, so we just declare the format we want.
        input_audio_format: 'pcm16',
        output_audio_format: 'pcm16',
        input_audio_transcription: {
          model: 'whisper-1',
        },
      }),
    });
  } catch (err) {
    const message = err instanceof Error ? err.message : 'Network error';
    return NextResponse.json(
      { error: `Failed to reach OpenAI Realtime: ${message}` },
      { status: 502 }
    );
  }

  if (!openaiResp.ok) {
    const text = await openaiResp.text();
    console.error('[realtime/session] OpenAI returned', openaiResp.status, text);
    return NextResponse.json(
      { error: `OpenAI session creation failed (${openaiResp.status})` },
      { status: 502 }
    );
  }

  const sessionPayload = (await openaiResp.json()) as {
    id?: string;
    client_secret?: { value?: string; expires_at?: number };
  };

  if (!sessionPayload.client_secret?.value) {
    return NextResponse.json(
      { error: 'OpenAI did not return an ephemeral token' },
      { status: 502 }
    );
  }

  // Audit — record that a voice session was opened. Per-tool-call audits
  // happen in /api/assistant-tool when actual writes occur.
  await logAudit({
    action: 'VIEWED_PATIENT_FILE',
    targetId: patientId,
    targetType: 'Patient',
    metadata: {
      via: 'realtime-session',
      openaiSessionId: sessionPayload.id ?? null,
      voice: REALTIME_VOICE,
      model: REALTIME_MODEL,
      capRemainingMin: cap.remaining,
    },
  });

  return NextResponse.json({
    clientSecret: sessionPayload.client_secret.value,
    expiresAt: sessionPayload.client_secret.expires_at ?? null,
    sessionId: sessionPayload.id ?? null,
    model: REALTIME_MODEL,
    capRemainingMin: cap.remaining,
  });
}

// Surface "future, still-schedulable" appointments to the AI. Drops already-
// cancelled/completed rows and anything before today — those aren't things
// the doctor would ask to cancel or reference in voice.
/**
 * Accept only IANA timezone strings we can trust. Intl.DateTimeFormat will
 * throw on malformed values, so a quick construct-and-catch round-trip is
 * the safest validation. Falls back to UTC on bad input so the prompt is
 * always framed in *some* timezone.
 */
function sanitizeTimezone(tz: string | undefined): string {
  const candidate = tz?.trim();
  if (!candidate) return 'UTC';
  try {
    new Intl.DateTimeFormat('en-US', { timeZone: candidate });
    return candidate;
  } catch {
    return 'UTC';
  }
}

function filterUpcomingAppointments(all: AppointmentView[]): AppointmentView[] {
  const now = Date.now();
  return all
    .filter((a) => a.status !== 'CANCELLED' && a.status !== 'COMPLETED')
    .filter((a) => new Date(a.scheduledAt).getTime() >= now - 24 * 60 * 60 * 1000)
    .sort((x, y) => new Date(x.scheduledAt).getTime() - new Date(y.scheduledAt).getTime());
}
