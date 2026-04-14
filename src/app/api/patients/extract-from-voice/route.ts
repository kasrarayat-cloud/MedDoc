// ============================================================================
// /api/patients/extract-from-voice
// ----------------------------------------------------------------------------
// Accepts a voice clip from the "Add Patient" modal, runs Whisper for the
// transcript, then gpt-4o-mini with a strict JSON schema to extract the
// structured form fields. The modal pre-fills the form with whatever came
// back (unrecognized fields stay null and are left alone).
//
// Flow:
//   client MediaRecorder blob
//     ─► multipart POST here
//        ─► Whisper (verbose_json for `duration`)
//           └─ log feature=TRANSCRIBE with durationSeconds
//        ─► gpt-4o-mini chat.completions with response_format=json_schema
//           └─ log feature=GPT_TOOL with total_tokens
//        ─► return { ok, transcript, fields }
//
// Rate-limited on the transcribe bucket (same spend class) and auth-gated.
// ============================================================================

import { NextRequest, NextResponse } from 'next/server';
import OpenAI from 'openai';
import { getSession } from '@/lib/auth';
import { logApiUsage } from '@/lib/usage';
import { checkRateLimit, RATE_LIMITS } from '@/lib/rate-limit';

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

// Response shape. Every field is nullable — the model returns null when the
// doctor didn't mention it. The client merges only non-null values so a
// partially-completed form doesn't get blown away by a second voice pass.
export interface ExtractedPatientFields {
  firstName: string | null;
  lastName: string | null;
  mrn: string | null;
  chartId: string | null;
  birthYear: number | null;
  email: string | null;
  cellPhone: string | null;
  homePhone: string | null;
  insuranceVerified: boolean | null;
  sex: 'UNKNOWN' | 'MALE' | 'FEMALE' | 'OTHER' | null;
  addressLine1: string | null;
  addressLine2: string | null;
  city: string | null;
  state: string | null;
  postalCode: string | null;
  pharmacyName: string | null;
  pharmacyPhone: string | null;
  tags: string[] | null;
  briefHistory: string[] | null;
}

interface SuccessResponse {
  ok: true;
  transcript: string;
  fields: ExtractedPatientFields;
}
interface ErrorResponse {
  ok: false;
  error: string;
}

const EXTRACTION_SYSTEM_PROMPT = `You extract structured patient-intake fields from a dictated utterance for a new-patient form.

The utterance is either (a) initial intake ("New patient Sarah Mitchell, born 1978, MRN 440182…") OR (b) a correction/edit to a form the doctor has already partially filled ("The last name is Hagopian, not Hagorian", "Change the email to j.smith@clinic.com", "Actually the birth year is 1965").

The CURRENT FORM STATE is provided below. Treat the utterance as an instruction that produces the DESIRED final value for each mentioned field. Examples:

CURRENT: { lastName: "Hagorian", email: "j.smith@clinic.co" }
UTTERANCE: "It's Hagopian, not Hagorian. And the email ends in .com."
OUTPUT: { lastName: "Hagopian", email: "j.smith@clinic.com", ... (others null) }

CURRENT: { email: "s.mitchell@clinica.com" }
UTTERANCE: "Edit the last part of the email — it's clinic, not clinica."
OUTPUT: { email: "s.mitchell@clinic.com", ... (others null) }

CURRENT: {}
UTTERANCE: "Add patient John Smith, born 1960, cell 555-1212."
OUTPUT: { firstName: "John", lastName: "Smith", birthYear: 1960, cellPhone: "(555) 121-2…", ... (others null) }

Rules:
- Return STRICT JSON matching the schema. Every field MUST be present; use null when the utterance doesn't affect that field (leave the current value alone — the client only overwrites non-null fields).
- Names: capitalize appropriately ("Sarah Mitchell", not "sarah mitchell").
- birthYear: 4-digit integer (1900..current year). Accept "born 1978", "seventy-eight" → 1978 (2-digit years 30-99 → 1900s, 00-29 → 2000s). Null if out of range.
- cellPhone / homePhone: format as "(555) 123-4567" if 10 digits can be extracted.
- mrn: digits/alphanumeric only — strip "MRN", "number", etc.
- chartId: only if the speaker explicitly said one.
- email: lowercase. If the speaker gives a PARTIAL edit ("change the domain to foo.com", "it ends in .org"), apply it to the current email and return the full corrected address. Null if ambiguous.
- insuranceVerified: true only on explicit verification statements.
- tags: slugs ("chronic-pain"). Null if none mentioned.
- sex: MALE / FEMALE / OTHER if clearly stated ("male patient", "she", "they"). Pronouns are a weak signal — only infer when unambiguous. Null otherwise; never guess.
- addressLine1 / addressLine2 / city / state / postalCode: US-style address parsing. State as 2-char code ("California" → "CA"). Postal code as digits. Split "123 Main Street Apt 4B, San Francisco, CA 94103" into the five fields correctly.
- pharmacyName: the pharmacy/drug store the patient uses (e.g., "CVS on Market Street", "Walgreens #4421"). Null if not mentioned.
- pharmacyPhone: same format rules as cellPhone. Null if not mentioned.
- briefHistory: one array entry per distinct clinical fact or intake note the speaker mentioned ("chronic low back pain since 2023", "referred by Dr. Chen", "failed PT 2024"). Short prose lines, not bullet points. Null if none.

If the utterance is just noise or clearly unrelated to patient intake (e.g., random speech, nothing actionable), return all-null. Pure corrections like "it's Hagopian not Hagorian" are NOT noise — they are field edits.`;

const EXTRACTION_JSON_SCHEMA = {
  name: 'patient_intake_fields',
  strict: true,
  schema: {
    type: 'object',
    additionalProperties: false,
    required: [
      'firstName',
      'lastName',
      'mrn',
      'chartId',
      'birthYear',
      'email',
      'cellPhone',
      'homePhone',
      'insuranceVerified',
      'sex',
      'addressLine1',
      'addressLine2',
      'city',
      'state',
      'postalCode',
      'pharmacyName',
      'pharmacyPhone',
      'tags',
      'briefHistory',
    ],
    properties: {
      firstName: { type: ['string', 'null'] },
      lastName: { type: ['string', 'null'] },
      mrn: { type: ['string', 'null'] },
      chartId: { type: ['string', 'null'] },
      birthYear: { type: ['integer', 'null'] },
      email: { type: ['string', 'null'] },
      cellPhone: { type: ['string', 'null'] },
      homePhone: { type: ['string', 'null'] },
      insuranceVerified: { type: ['boolean', 'null'] },
      sex: {
        anyOf: [
          { type: 'null' },
          { type: 'string', enum: ['UNKNOWN', 'MALE', 'FEMALE', 'OTHER'] },
        ],
      },
      addressLine1: { type: ['string', 'null'] },
      addressLine2: { type: ['string', 'null'] },
      city: { type: ['string', 'null'] },
      state: { type: ['string', 'null'] },
      postalCode: { type: ['string', 'null'] },
      pharmacyName: { type: ['string', 'null'] },
      pharmacyPhone: { type: ['string', 'null'] },
      tags: {
        anyOf: [
          { type: 'null' },
          { type: 'array', items: { type: 'string' } },
        ],
      },
      briefHistory: {
        anyOf: [
          { type: 'null' },
          { type: 'array', items: { type: 'string' } },
        ],
      },
    },
  },
} as const;

export async function POST(request: NextRequest) {
  const session = await getSession();
  if (!session) {
    return NextResponse.json<ErrorResponse>(
      { ok: false, error: 'Unauthorized' },
      { status: 401 }
    );
  }

  // Reuse the transcribe bucket — same cost class, no reason to let someone
  // bypass the spend cap by routing through a new endpoint.
  const rl = checkRateLimit(session.user.id, RATE_LIMITS.transcribe);
  if (!rl.ok) {
    return NextResponse.json<ErrorResponse>(
      { ok: false, error: 'Too many voice requests. Please slow down.' },
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

  let audioFile: File | null;
  let currentFields: Partial<ExtractedPatientFields> = {};
  try {
    const form = await request.formData();
    audioFile = form.get('audio') as File | null;
    // Optional multipart field "currentFields" = JSON string of the form
    // state at the moment the recording started. Lets the model compute
    // edits ("change the email to X") against actual current values.
    const raw = form.get('currentFields');
    if (typeof raw === 'string' && raw.trim()) {
      try {
        const parsed = JSON.parse(raw) as unknown;
        if (parsed && typeof parsed === 'object') {
          currentFields = parsed as Partial<ExtractedPatientFields>;
        }
      } catch {
        // Malformed — ignore, proceed with empty current state.
      }
    }
  } catch {
    return NextResponse.json<ErrorResponse>(
      { ok: false, error: 'Invalid multipart body' },
      { status: 400 }
    );
  }

  if (!audioFile) {
    return NextResponse.json<ErrorResponse>(
      { ok: false, error: 'No audio file provided' },
      { status: 400 }
    );
  }
  if (audioFile.size > 25 * 1024 * 1024) {
    return NextResponse.json<ErrorResponse>(
      { ok: false, error: 'Audio file too large (max 25MB)' },
      { status: 400 }
    );
  }
  if (audioFile.size < 100) {
    return NextResponse.json<ErrorResponse>(
      { ok: false, error: 'Audio file is empty' },
      { status: 400 }
    );
  }

  const client = getClient();

  // 1. Whisper transcribe.
  let transcript: string;
  let whisperDurationSeconds: number | null = null;
  try {
    // `prompt` is a free-text hint Whisper uses to bias its language
    // model — not an instruction, a vocabulary prime. Listing context
    // (medical intake) and commonly-miscaught terms (ethnic surnames,
    // clinical tokens, phone/email phrasing) meaningfully lifts accuracy
    // on our hard cases without costing us anything extra.
    const whisperPrompt =
      'Patient intake dictation for a pain management clinic. Common terms: MRN, chart ID, birth year, cell phone, home phone, email, insurance verified, chronic pain, post-op, consultation, follow-up, referral. Surnames may be non-English (e.g., Hagopian, Nguyen, Okafor, Patel, Rodriguez, Chen, Al-Masri). The speaker may correct earlier dictation — phrases like "not X, Y" or "change the email to" are edits.';
    const res = await client.audio.transcriptions.create({
      file: audioFile,
      model: 'whisper-1',
      language: 'en',
      response_format: 'verbose_json',
      prompt: whisperPrompt,
    });
    transcript = (res.text ?? '').trim();
    whisperDurationSeconds =
      typeof res.duration === 'number' ? Math.round(res.duration) : null;
  } catch (err) {
    console.error('[extract-from-voice] Whisper failed:', err);
    const message = err instanceof Error ? err.message : 'Transcription failed';
    return NextResponse.json<ErrorResponse>(
      { ok: false, error: message },
      { status: 500 }
    );
  }

  void logApiUsage({
    feature: 'TRANSCRIBE',
    userId: session.user.id,
    practiceId: session.user.practiceId,
    durationSeconds: whisperDurationSeconds,
  }).catch((err) => {
    console.error('[extract-from-voice] logApiUsage TRANSCRIBE rejected:', err);
  });

  if (!transcript) {
    // Whisper gave us nothing — return an empty field set so the modal can
    // surface "didn't catch that" without a hard error.
    return NextResponse.json<SuccessResponse>({
      ok: true,
      transcript: '',
      fields: emptyFields(),
    });
  }

  // 2. Extract fields with gpt-4o-mini + strict JSON schema.
  let fields: ExtractedPatientFields;
  let extractionTokens: number | null = null;
  try {
    // Build the user message: current form state (so edits land on the
    // right value) + the transcript itself.
    const currentFieldsJson = JSON.stringify(currentFields);
    const userContent = `CURRENT FORM STATE:\n${currentFieldsJson}\n\nUTTERANCE:\n${transcript}`;

    const completion = await client.chat.completions.create({
      model: 'gpt-4o-mini',
      temperature: 0,
      messages: [
        { role: 'system', content: EXTRACTION_SYSTEM_PROMPT },
        { role: 'user', content: userContent },
      ],
      response_format: {
        type: 'json_schema',
        json_schema: EXTRACTION_JSON_SCHEMA,
      },
    });
    const raw = completion.choices[0]?.message?.content ?? '';
    fields = parseFields(raw);
    extractionTokens = completion.usage?.total_tokens ?? null;
  } catch (err) {
    console.error('[extract-from-voice] extraction failed:', err);
    // Transcript came through fine — return it so the doctor at least sees
    // what the mic heard. Empty fields means the modal won't auto-fill.
    return NextResponse.json<SuccessResponse>({
      ok: true,
      transcript,
      fields: emptyFields(),
    });
  }

  void logApiUsage({
    feature: 'GPT_TOOL',
    userId: session.user.id,
    practiceId: session.user.practiceId,
    tokens: extractionTokens,
  }).catch((err) => {
    console.error('[extract-from-voice] logApiUsage GPT_TOOL rejected:', err);
  });

  return NextResponse.json<SuccessResponse>({ ok: true, transcript, fields });
}

function emptyFields(): ExtractedPatientFields {
  return {
    firstName: null,
    lastName: null,
    mrn: null,
    chartId: null,
    birthYear: null,
    email: null,
    cellPhone: null,
    homePhone: null,
    insuranceVerified: null,
    sex: null,
    addressLine1: null,
    addressLine2: null,
    city: null,
    state: null,
    postalCode: null,
    pharmacyName: null,
    pharmacyPhone: null,
    tags: null,
    briefHistory: null,
  };
}

// Defensive parse — strict schema should guarantee shape, but a bad deploy
// or a model regression shouldn't 500 on the client. Anything that doesn't
// match the expected type of a field becomes null.
function parseFields(raw: string): ExtractedPatientFields {
  let parsed: unknown;
  try {
    parsed = JSON.parse(raw);
  } catch {
    return emptyFields();
  }
  if (!parsed || typeof parsed !== 'object') return emptyFields();
  const p = parsed as Record<string, unknown>;

  const str = (v: unknown): string | null =>
    typeof v === 'string' && v.trim() ? v.trim() : null;
  const int = (v: unknown): number | null =>
    typeof v === 'number' && Number.isFinite(v) ? Math.trunc(v) : null;
  const bool = (v: unknown): boolean | null =>
    typeof v === 'boolean' ? v : null;
  const strArr = (v: unknown): string[] | null =>
    Array.isArray(v) && v.every((s) => typeof s === 'string')
      ? (v as string[]).map((s) => s.trim()).filter(Boolean)
      : null;

  const year = int(p.birthYear);
  const currentYear = new Date().getFullYear();
  const validYear = year !== null && year >= 1900 && year <= currentYear ? year : null;

  // Sex enum — anything outside the closed set becomes null rather than
  // leaking into the UI as a stringified unknown value.
  const sexRaw = str(p.sex);
  const sex: ExtractedPatientFields['sex'] =
    sexRaw === 'MALE' || sexRaw === 'FEMALE' || sexRaw === 'OTHER' || sexRaw === 'UNKNOWN'
      ? sexRaw
      : null;

  const stateRaw = str(p.state);
  const stateNormalized =
    stateRaw && /^[A-Za-z]{2}$/.test(stateRaw) ? stateRaw.toUpperCase() : null;

  return {
    firstName: str(p.firstName),
    lastName: str(p.lastName),
    mrn: str(p.mrn),
    chartId: str(p.chartId),
    birthYear: validYear,
    email: str(p.email)?.toLowerCase() ?? null,
    cellPhone: str(p.cellPhone),
    homePhone: str(p.homePhone),
    insuranceVerified: bool(p.insuranceVerified),
    sex,
    addressLine1: str(p.addressLine1),
    addressLine2: str(p.addressLine2),
    city: str(p.city),
    state: stateNormalized,
    postalCode: str(p.postalCode),
    pharmacyName: str(p.pharmacyName),
    pharmacyPhone: str(p.pharmacyPhone),
    tags: strArr(p.tags),
    briefHistory: strArr(p.briefHistory),
  };
}
