import { NextRequest, NextResponse } from 'next/server';
import { getSession } from '@/lib/auth';
import { logAudit } from '@/lib/audit';
import { getPatientById } from '@/lib/data/patients';
import { listNotesByPatient } from '@/lib/data/clinical-notes';
import { listAppointmentsByPatient, type AppointmentView } from '@/lib/data/appointments';
import { listAllergiesForPatient, listMedicationsForPatient } from '@/lib/data/clinical-safety';
import prisma from '@meddoc/db';
import { REALTIME_TOOLS, buildSystemPrompt } from '@/lib/realtime/tools';
import { checkVoiceCap } from '@/lib/realtime/usage-cap';
import {
  buildClinicalTrajectory,
  buildPatientVocabPrimer,
  fetchRecentAiActions,
} from '@/lib/realtime/intelligence';

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

// #1 — Upgraded from gpt-4o-realtime-preview to the GA gpt-realtime.
// Sharper tool-routing + better multi-step reasoning; same cost class.
// Overridable via env for easy rollback.
const REALTIME_MODEL = process.env.REALTIME_MODEL || 'gpt-realtime';
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
  // scoped through the patient relation filter. recentAiActions comes
  // from the AuditLog (cross-session memory, #5).
  const [recentNotes, customProcedures, finalReports, patientFiles, appointments, recentAiActions, allergiesRaw, medicationsRaw, safetyFlags] =
    await Promise.all([
      listNotesByPatient(patientId, 'CLINICAL_NOTE', session),
      listNotesByPatient(patientId, 'CUSTOM_PROCEDURE', session),
      listNotesByPatient(patientId, 'FINAL_REPORT', session),
      listNotesByPatient(patientId, 'PATIENT_FILE', session),
      listAppointmentsByPatient(patientId, session),
      fetchRecentAiActions(patientId, session),
      listAllergiesForPatient(session, patientId),
      listMedicationsForPatient(session, patientId, { includeInactive: true }),
      prisma.patient.findUnique({ where: { id: patientId }, select: { noKnownAllergies: true } }),
    ]);
  const upcomingAppointments = filterUpcomingAppointments(appointments);

  // Trajectory synthesis (#2). Cached per-patient so re-opening the
  // panel during the same clinic session is free. Runs in parallel
  // with the OpenAI session-creation network call below if we fire it
  // now — but it's fast enough (~400ms cold, instant warm) that the
  // sequential flow is simpler and still sub-second.
  const clinicalTrajectory = await buildClinicalTrajectory(
    patient,
    recentNotes,
    customProcedures
  );

  // Whisper vocabulary primer (#4). Feeds patient-specific names and
  // common terms to the transcription model so ethnic surnames and
  // clinic-specific drugs don't get mangled.
  const vocabPrimer = buildPatientVocabPrimer(patient, recentNotes, customProcedures);

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
          recentNotes: recentNotes.slice(0, 10),
          customProcedures: customProcedures.slice(0, 10),
          finalReports: finalReports.slice(0, 10),
          patientFiles: patientFiles.slice(0, 10),
          upcomingAppointments: upcomingAppointments.slice(0, 10),
          currentDateIso: new Date().toISOString(),
          timezone,
          clinicalTrajectory,
          recentAiActions,
          allergies: allergiesRaw.map((a) => ({ id: a.id, allergen: a.allergen, reaction: a.reaction, severity: a.severity })),
          medications: medicationsRaw.map((m) => ({ id: m.id, name: m.name, dosage: m.dosage, frequency: m.frequency, isActive: m.isActive })),
          noKnownAllergies: safetyFlags?.noKnownAllergies ?? false,
        }),
        tools: REALTIME_TOOLS,
        // NOTE: parallel_tool_calls / max_response_output_tokens are NOT
        // valid at the session level in the Realtime API (they're
        // response-level fields). Setting them here produces a 400 on
        // session creation. The prompt rule 1a ("complete every
        // requested change before speaking") is the compliance
        // mechanism for multi-edit turns instead.
        // Semantic VAD — ML classifier that distinguishes human speech
        // from ambient noise (breathing, chair scrapes, HVAC). Much better
        // in a clinic setting than the older server_vad threshold detector.
        //
        // eagerness="low" — bias toward waiting for a clear end of
        // utterance before committing. Higher selectivity on human
        // speech vs. ambient noise (typing, keyboard, HVAC) at the
        // cost of slightly slower commit after the doctor finishes.
        // Combined with create_response: true below, follow-up turns
        // still trigger reliably.
        turn_detection: {
          type: 'semantic_vad',
          // 'medium' balances speed and accuracy — commits faster than
          // 'low' (the original setting, which felt sluggish) while still
          // using OpenAI's neural turn-detection so natural pauses don't
          // prematurely commit a turn and stutter the response. Reverted
          // from server_vad (which caused choppy speech from background
          // noise triggering micro-turn commits).
          eagerness: 'medium',
          create_response: true,
          interrupt_response: true,
        },
        // Stream both directions as PCM16 — the WebRTC pipe handles the
        // codec negotiation, so we just declare the format we want.
        input_audio_format: 'pcm16',
        output_audio_format: 'pcm16',
        input_audio_transcription: {
          model: 'whisper-1',
          // #4 — Biases Whisper toward patient-specific names and terms
          // so ethnic surnames, specific medications, and procedure
          // codes are transcribed correctly on the first try.
          ...(vocabPrimer ? { prompt: vocabPrimer } : {}),
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
    // Extract a short reason from OpenAI's JSON-shaped error so the
    // client sees something actionable instead of a bare status code.
    let detail = '';
    try {
      const parsed = JSON.parse(text) as { error?: { message?: string } };
      detail = parsed.error?.message ? ` — ${parsed.error.message}` : '';
    } catch {
      // non-JSON body, leave detail empty
    }
    return NextResponse.json(
      { error: `OpenAI session creation failed (${openaiResp.status})${detail}` },
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
