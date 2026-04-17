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
  /** Model picks one of the provided doctor names verbatim (or null).
   *  The client resolves the name back to a user ID before submit so
   *  the model never has to emit opaque cuids. */
  assignedDoctorName: string | null;
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

const EXTRACTION_SYSTEM_PROMPT = `You extract structured patient-intake fields from a dictated utterance for a new-patient form. Your job is ALWAYS to extract whatever the speaker names, regardless of phrasing style. Never return all-null for an utterance that mentions any field.

Speakers use wildly different phrasings. ALL of these are valid intake — extract the same fields from each:
- "Add patient John Smith, born 1960, cell 555-1212." (narrative)
- "For first name put Sarah. For last name put Wilson. MRN is MRN-440184." (imperative)
- "First name Sarah, last name Wilson, MRN MRN-440184." (telegraphic)
- "Put sex as female and assign to Dr. Chen." (imperative with keywords)
- "It's Hagopian, not Hagorian." (correction to existing value)
- "Change the email to it ends in .com." (partial correction)

The CURRENT FORM STATE is provided below. Treat the utterance as producing the DESIRED final value for each mentioned field. The client overwrites only non-null fields, so null means "don't change this."

Examples:

CURRENT: {}
UTTERANCE: "For first name, put Sarah. For last name, put Wilson. MRN is MRN-440184. Home phone is 818-854-1585. Email is sarah.wilson at gmail.com. Put sex on female and assign provider to Dr. Alvarez. Address is 5325 New Castle Avenue, Apartment 105. City is Encino, state California. Postal code 91316. Also put a note that she needs follow-up tomorrow. Brief history: had injections for L4 and L5."
OUTPUT: {
  firstName: "Sarah", lastName: "Wilson", mrn: "MRN-440184",
  homePhone: "(818) 854-1585", email: "sarah.wilson@gmail.com",
  sex: "FEMALE", assignedDoctorName: "Dr. Alvarez",
  addressLine1: "5325 New Castle Avenue", addressLine2: "Apartment 105",
  city: "Encino", state: "CA", postalCode: "91316",
  briefHistory: ["Follow-up needed tomorrow", "Had injections for L4 and L5"],
  ... (others null)
}

CURRENT: { lastName: "Hagorian", email: "j.smith@clinic.co" }
UTTERANCE: "It's Hagopian, not Hagorian. And the email ends in .com."
OUTPUT: { lastName: "Hagopian", email: "j.smith@clinic.com", ... (others null) }

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
- sex: MALE / FEMALE / OTHER when stated directly — "male", "female", "she's a woman", "he's a man", "non-binary", "choose female", "set sex to male", "mark as male". Extract whenever the speaker's intent is clear, even in short phrases. Do NOT infer from surname or isolated pronouns used only in passing. If the speaker didn't mention sex at all, return null.
- assignedDoctorName: exact string match against the AVAILABLE DOCTORS list below. If the speaker says "assign to Dr. Smith" or "Dr. Smith will see them" and "Dr. Smith" is in the list, return that name verbatim as listed (with the "Dr." prefix, full name). Fuzzy match is OK on first/last name ("assign to Smith" → "Dr. Jane Smith" if only one Smith). Null if no close match.
- addressLine1 / addressLine2 / city / state / postalCode: US-style address parsing. State as 2-char code ("California" → "CA"). Postal code as digits. Split "123 Main Street Apt 4B, San Francisco, CA 94103" into the five fields correctly.
- pharmacyName: the pharmacy/drug store the patient uses (e.g., "CVS on Market Street", "Walgreens #4421"). Null if not mentioned.
- pharmacyPhone: same format rules as cellPhone. Null if not mentioned.
- briefHistory: one array entry per distinct clinical fact or intake note the speaker mentioned ("chronic low back pain since 2023", "referred by Dr. Chen", "failed PT 2024"). Short prose lines, not bullet points. Null if none.

Only return all-null when the utterance is completely incoherent (e.g., "uh what" or static) AND mentions no field value whatsoever. If ANY field is nameable from the utterance, extract it.

birthYear out of range (< 1900 or > current year): return null for THAT field only. Do NOT let one bad field wipe out the rest of the extraction.`;

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
      'assignedDoctorName',
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
      assignedDoctorName: { type: ['string', 'null'] },
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
  let availableDoctors: string[] = [];
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
    // Optional multipart field "doctors" = JSON string array of display
    // names ("Dr. Jane Smith", "Dr. Raj Patel"). Fed to the extractor so
    // "assign to Dr. Smith" can resolve to a name the client then maps
    // back to a user ID at submit time.
    const docs = form.get('doctors');
    if (typeof docs === 'string' && docs.trim()) {
      try {
        const parsed = JSON.parse(docs) as unknown;
        if (Array.isArray(parsed)) {
          availableDoctors = parsed.filter((s): s is string => typeof s === 'string');
        }
      } catch {
        // Ignore — no matching means model returns null assignedDoctorName.
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
    // Build the user message: current form state, available doctor names,
    // then the transcript. Doctor names let the model pick a valid option
    // rather than hallucinating.
    const currentFieldsJson = JSON.stringify(currentFields);
    const doctorsBlock = availableDoctors.length
      ? availableDoctors.map((d) => `  - ${d}`).join('\n')
      : '  (none)';
    const userContent =
      `CURRENT FORM STATE:\n${currentFieldsJson}\n\n` +
      `AVAILABLE DOCTORS:\n${doctorsBlock}\n\n` +
      `UTTERANCE:\n${transcript}`;

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
    // Surface the real error. Previously we returned "ok: true, fields: empty"
    // which made the UI say "nothing matched" — indistinguishable from a
    // model refusal. Now the client can show "extractor error: <message>"
    // instead, which is at least actionable (means the OpenAI call failed
    // — schema mismatch, quota, etc., not a dictation problem).
    const message = err instanceof Error ? err.message : 'Extraction failed';
    return NextResponse.json<ErrorResponse>(
      { ok: false, error: `Extractor failed: ${message}` },
      { status: 500 }
    );
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
    assignedDoctorName: null,
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
    assignedDoctorName: str(p.assignedDoctorName),
    tags: strArr(p.tags),
    briefHistory: strArr(p.briefHistory),
  };
}
