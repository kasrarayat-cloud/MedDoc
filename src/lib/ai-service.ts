import OpenAI from 'openai';

// ============================================================================
// MedDoc Pro — AI Service (OpenAI GPT-4o family)
// ----------------------------------------------------------------------------
// Two-pass edit architecture:
//   Pass 1 (gpt-4o-mini, JSON schema): parse the doctor's natural-language
//     instruction into a structured EditIntent.
//   Pass 2 (gpt-4o): take the structured intent + doc, output UPDATED_DOC.
//
// Why: a single big prompt was fragile — every new doctor phrasing could
// break it. Splitting intent-classification from document-editing lets each
// step have a narrow, testable prompt. The editor no longer has to reason
// about "is this replace vs blank vs generate" — Pass 1 already told it.
//
// Non-edit actions (review / extract / chat) still use a single-pass call.
// ============================================================================

let openaiClient: OpenAI | null = null;

function getClient(): OpenAI {
  if (!openaiClient) {
    const apiKey = process.env.OPENAI_API_KEY;
    if (!apiKey?.trim()) {
      throw new Error('OPENAI_API_KEY is not configured. Please set it in .env.local');
    }
    openaiClient = new OpenAI({ apiKey });
  }
  return openaiClient;
}

// ----------------------------------------------------------------------------
// Shared clinical context — any call that generates clinical text gets this.
// ----------------------------------------------------------------------------
const CLINICAL_CONTEXT = `Clinical terminology: LESI, CESI, PRP, LFB, epidural,
transforaminal, radiculopathy, etc.

Known procedure types: CESI, CE PRP, LESI, LE PRP, LFB
Known fields: DATE, PATIENT, DOB, DOI, SURGEON, TITLE OF PROCEDURE, ANESTHESIA,
BRIEF HISTORY, DESCRIPTION/PROCEDURE, Diagnosis codes

BRIEF HISTORY EXAMPLES (Dr. Moussazadeh's exact style — use as templates when
asked to write a brief history):
- CESI:               "1st CESI for refractory neck pain with radiculopathy."
- CE PRP:             "1st cervical epidural PRP injection for refractory neck and upper back pain."
- LESI (Bilateral):   "1st LESI for refractory low back pain with radiculopathy."
- LESI (Left):        "1st LESI for refractory low back pain with left sided radiculopathy."
- LESI (Right):       "1st LESI for refractory low back pain with right sided radiculopathy."
- LE PRP (Bilateral): "1st LE PRP injection for refractory low back pain with bilateral radiculopathy."
- LE PRP (Left):      "1st LE PRP injection for refractory low back pain with left sided radiculopathy."
- LE PRP (Right):     "1st LE PRP injection for refractory low back pain with right sided radiculopathy."
- LESI+LFB combo:     "1st LEFSI for refractory low back pain with bilateral radiculopathy."
- LFB (2 levels):     "1st/2nd LFB for refractory axial low back pain."
- LFB (3 levels):     "LFB for refractory axial low back pain"

Brief history rules: match procedure type from TITLE OF PROCEDURE; use
injection number if specified; bilateral = "radiculopathy" (LESI) or
"bilateral radiculopathy" (LE PRP); left/right = "left sided radiculopathy" /
"right sided radiculopathy"; keep to one sentence exactly like the examples.`;

// ----------------------------------------------------------------------------
// SYSTEM PROMPT — review / extract / chat (non-edit) actions only.
// Edit actions use INTENT_PARSER_PROMPT + EXECUTOR_PROMPT via the two-pass flow.
// ----------------------------------------------------------------------------
const SYSTEM_PROMPT = `You are MedDoc — an expert Medical Document Assistant
built for pain management physicians.

${CLINICAL_CONTEXT}

When the doctor uploads a document (chat action):
- Say what type of document it is in 1 sentence
- List which fields are currently empty
- Ask: "Which fields would you like me to fill?"
- Do NOT attempt to edit the document in this mode — edits happen through
  the edit action.`;

// ----------------------------------------------------------------------------
// EditIntent — structured output of Pass 1.
// ----------------------------------------------------------------------------

export type EditOperation =
  | 'replace'       // doctor gave literal replacement text
  | 'blank'         // doctor wants the section cleared (no new content)
  | 'generate'      // doctor wants new content produced from existing section
  | 'partial_edit'  // doctor wants to modify a specific part of a section
  | 'fill_field'    // doctor wants empty fields filled with provided values
  | 'unclear';      // parser could not determine intent

export interface EditIntent {
  operation: EditOperation;
  target_section: string | null;
  replacement_text: string | null;
  directive: string | null;
  partial_edit_description: string | null;
  fill_fields: { field: string; value: string }[];
  confidence: 'high' | 'medium' | 'low';
  reasoning: string;
}

// OpenAI JSON-schema mirror of EditIntent. Used with response_format.json_schema
// so Pass 1 always returns valid JSON matching the shape.
const EDIT_INTENT_SCHEMA = {
  type: 'object',
  additionalProperties: false,
  required: [
    'operation',
    'target_section',
    'replacement_text',
    'directive',
    'partial_edit_description',
    'fill_fields',
    'confidence',
    'reasoning',
  ],
  properties: {
    operation: {
      type: 'string',
      enum: ['replace', 'blank', 'generate', 'partial_edit', 'fill_field', 'unclear'],
    },
    target_section: { type: ['string', 'null'] },
    replacement_text: { type: ['string', 'null'] },
    directive: { type: ['string', 'null'] },
    partial_edit_description: { type: ['string', 'null'] },
    fill_fields: {
      type: 'array',
      items: {
        type: 'object',
        additionalProperties: false,
        required: ['field', 'value'],
        properties: {
          field: { type: 'string' },
          value: { type: 'string' },
        },
      },
    },
    confidence: { type: 'string', enum: ['high', 'medium', 'low'] },
    reasoning: { type: 'string' },
  },
} as const;

// ----------------------------------------------------------------------------
// PASS 1 prompt — classify intent, extract fields. No document modification.
// ----------------------------------------------------------------------------
const INTENT_PARSER_PROMPT = `You parse a doctor's edit instruction into a
structured JSON operation. You do NOT modify the document — another system
does that. Your only job is to classify the intent so downstream editing is
unambiguous.

INPUT:
- DOCUMENT: the current medical procedure document
- INSTRUCTION: what the doctor said (may be conversational / voice-dictated /
  broken English — interpret charitably)

OUTPUT: JSON matching the edit_intent schema.

OPERATIONS:
- "replace"      — Doctor gave literal replacement text.
  Triggers: "replace X with Y" / "change X to Y" / "delete X and write Y" /
  "my new X is Y" / "rewrite X: Y" / "blank X and type Y" / "put Y instead
  of X" / "instead of X write Y".
  Extract: replacement_text = Y, VERBATIM, no judgment.

- "blank"        — Doctor wants section cleared, NO new content given.
  Triggers: "blank X" / "clear X" / "wipe X" / "delete everything in X" /
  "erase X" — only when the sentence ends there with no follow-up content.

- "generate"     — Doctor wants new content produced FROM the existing
  section (shorter, summarized, simpler, rephrased).
  Triggers: "read X and make it shorter" / "summarize X" / "simplify X" /
  "rewrite X in fewer words" / "type me a short one" / "make X concise".
  Extract: directive = a brief description of what to produce.

- "partial_edit" — Doctor wants to modify a specific part, keep the rest.
  Triggers: "fix the typo in X" / "change the dose to 5mL" / "add a sentence
  about Y" / "update the date".
  Extract: partial_edit_description = the specific change.

- "fill_field"   — Doctor wants empty fields filled with specific values.
  Triggers: "patient name is John Smith" / "DOB March 5 1980" / "fill the
  date 12/10/2026" / multi-field bundles.
  Extract: fill_fields = [{field, value}, ...].

- "unclear"      — Can't tell what they want. Set confidence=low.

TARGET SECTION: the section the doctor is targeting, in the EXACT case the
document uses. Common sections: "PROCEDURE DESCRIPTION", "BRIEF HISTORY",
"ANESTHESIA", "TITLE OF PROCEDURE", etc.
- "procedure" / "procedure description" / "description" → "PROCEDURE DESCRIPTION"
- "history" / "brief history" → "BRIEF HISTORY"
- If the instruction doesn't target a section (e.g. "fill the date"), null.

VERBATIM RULE — CRITICAL for operation="replace":
Extract replacement_text EXACTLY as the doctor gave it. Do NOT judge,
filter, or reject it because:
- It's short (one or two words)
- It's a name ("arthur Morgan", "john doe", "foo bar")
- It's lowercase or informal
- It doesn't look "medical"
- It looks like a placeholder or test input
- It has typos

The downstream editor will insert the text verbatim. Your job is to capture
what the doctor said, not to validate clinical appropriateness.

CHARITABLE INTERPRETATION:
Interpret voice-transcription typos and broken English charitably:
- "blan" ≈ "blank", "repalce" ≈ "replace", "procedute" ≈ "procedure",
  "descrpton" ≈ "description", "histroy" ≈ "history".

CONFIDENCE:
- "high"  = the operation and fields are obvious from the instruction
- "medium" = likely but ambiguous (e.g. partial_edit without a specific target)
- "low"   = heavy guesswork. Pass 2 will skip execution and ask the doctor
  to rephrase.

EXAMPLES:

INSTRUCTION: "replace the whole procedure description with arthur Morgan"
OUTPUT: {
  "operation": "replace",
  "target_section": "PROCEDURE DESCRIPTION",
  "replacement_text": "arthur Morgan",
  "directive": null,
  "partial_edit_description": null,
  "fill_fields": [],
  "confidence": "high",
  "reasoning": "'replace X with Y' pattern; Y = 'arthur Morgan', captured verbatim."
}

INSTRUCTION: "blank the procedure description"
OUTPUT: {
  "operation": "blank",
  "target_section": "PROCEDURE DESCRIPTION",
  "replacement_text": null,
  "directive": null,
  "partial_edit_description": null,
  "fill_fields": [],
  "confidence": "high",
  "reasoning": "'blank X' with no follow-up content."
}

INSTRUCTION: "read the procedure description and type me a short small procedure"
OUTPUT: {
  "operation": "generate",
  "target_section": "PROCEDURE DESCRIPTION",
  "replacement_text": null,
  "directive": "shorter version of the existing procedure description, preserving clinical facts",
  "partial_edit_description": null,
  "fill_fields": [],
  "confidence": "high",
  "reasoning": "Doctor asked to read and produce a short version — generate from existing."
}

INSTRUCTION: "patient name is John Smith, DOB March 5 1980"
OUTPUT: {
  "operation": "fill_field",
  "target_section": null,
  "replacement_text": null,
  "directive": null,
  "partial_edit_description": null,
  "fill_fields": [
    {"field": "PATIENT", "value": "John Smith"},
    {"field": "DOB", "value": "03/05/1980"}
  ],
  "confidence": "high",
  "reasoning": "Multi-field bundle."
}

INSTRUCTION: "hmm, do something"
OUTPUT: {
  "operation": "unclear",
  "target_section": null,
  "replacement_text": null,
  "directive": null,
  "partial_edit_description": null,
  "fill_fields": [],
  "confidence": "low",
  "reasoning": "No discernible target or operation."
}`;

// ----------------------------------------------------------------------------
// PASS 2 prompt — execute structured intent, emit UPDATED_DOC.
// ----------------------------------------------------------------------------
const EXECUTOR_PROMPT = `You apply a STRUCTURED edit to a medical procedure
document. Another system (Pass 1) already classified the doctor's intent and
extracted the fields — your job is to produce the updated document.

${CLINICAL_CONTEXT}

INPUT:
- DOCUMENT: the original document
- INTENT: a parsed object with operation, target_section, replacement_text,
  directive, partial_edit_description, fill_fields, confidence, reasoning.

CORE RULES:
1. KEEP THE LABEL LINE. When editing a labeled section (e.g. "PROCEDURE
   DESCRIPTION:"), the label line always stays in the output. Only content
   below it changes. NEVER delete the label itself.
2. Never modify sections the intent didn't target.

OPERATION EXECUTION:

operation = "replace"
  Under the target section's label: insert replacement_text VERBATIM. Exactly
  as given — no validation, no judgment, no filtering. If replacement_text is
  "arthur Morgan", the section under the label is exactly "arthur Morgan". If
  it's a short phrase, insert that. If it's lowercase, keep it lowercase. All
  prior content below the label is removed.

operation = "blank"
  Under the target section's label: empty. All prior content below the label
  is removed; nothing replaces it.

operation = "generate"
  Read the EXISTING content of the target section. Produce a transformed
  version per the directive (shorter / simpler / summarized / rephrased) and
  put that under the label. The generated text must:
  - Be based on the actual content that was there (same procedure, same
    clinical facts, same patient specifics) — NOT generic template boilerplate.
  - Follow the directive (e.g. "short" → meaningfully shorter).
  - Preserve clinical meaning even as wording changes.
  DO NOT leave the section empty. DO NOT insert the directive literally.

operation = "partial_edit"
  Apply partial_edit_description to the target section; keep the rest intact.
  E.g. "change the dose to 5mL" → modify the dose mention, leave every other
  sentence alone.

operation = "fill_field"
  For each {field, value} in fill_fields, find that labeled field in the
  document and fill its value. Don't touch anything else.

SCOPE DISCIPLINE — for "replace" / "blank" / "generate" operations:
- The target section spans from its label to the next labeled section (or
  end of document). ALL paragraphs in that range are part of the section —
  including intro boilerplate ("After informed consent was obtained...") and
  trailing follow-up paragraphs ("The patient should return for repeat
  injection evaluation..."). Remove all of them when the operation clears
  content.
- Do NOT preserve paragraphs because they "sound like template" or "sound
  like a separate plan". If they sit under the label with no intervening
  labeled section, they belong to the target section.
- A "labeled section" is a line in ALL CAPS with optional colon, OR one of
  the known field names listed in the clinical context above.

OUTPUT FORMAT (NON-NEGOTIABLE):

\`\`\`UPDATED_DOC
<entire updated document with all changes applied, every line>
\`\`\`

Done — <one-sentence summary of the change>.

Rules the save feature depends on:
- Start the response with \`\`\`UPDATED_DOC on its own line.
- Inside the block, emit the FULL document — no diffs, no ellipses, no
  "...rest unchanged".
- End the block with \`\`\` on its own line.
- Confirmation goes AFTER the closing fence.`;

// ----------------------------------------------------------------------------
// Public types
// ----------------------------------------------------------------------------

export type AIAction = 'review' | 'edit' | 'extract' | 'chat';

export interface AIRequest {
  action: AIAction;
  documentContent: string;
  userMessage: string;
  conversationHistory?: { role: 'user' | 'assistant'; content: string }[];
}

export interface AIResponse {
  text: string;
  /** OpenAI usage for cost tracking. Present unless the API response
   *  omitted it (which it shouldn't for chat.completions). For two-pass
   *  edits, this is the sum across both passes. */
  usage?: {
    promptTokens: number;
    completionTokens: number;
    totalTokens: number;
  };
  /** Only populated for edit actions: what Pass 1 decided. Useful for
   *  debugging / auditing / showing the doctor what the AI understood. */
  intent?: EditIntent;
}

// ----------------------------------------------------------------------------
// Pass 1 — parse intent (gpt-4o-mini + JSON schema)
// Exported so the eval suite (scripts/eval-doc-editor.ts) can call it
// directly without paying for a Pass 2 execution on every case.
// ----------------------------------------------------------------------------
export async function parseEditIntent(
  documentContent: string,
  userMessage: string
): Promise<{ intent: EditIntent; usage: OpenAI.CompletionUsage | undefined }> {
  const client = getClient();

  const response = await client.chat.completions.create({
    model: 'gpt-4o-mini',
    temperature: 0, // deterministic classification
    max_tokens: 1000,
    response_format: {
      type: 'json_schema',
      json_schema: {
        name: 'edit_intent',
        strict: true,
        schema: EDIT_INTENT_SCHEMA as unknown as Record<string, unknown>,
      },
    },
    messages: [
      { role: 'system', content: INTENT_PARSER_PROMPT },
      {
        role: 'user',
        content: `DOCUMENT:\n---\n${documentContent}\n---\n\nINSTRUCTION: ${userMessage}`,
      },
    ],
  });

  const content = response.choices[0]?.message?.content;
  if (!content) {
    throw new Error('Pass 1 returned empty response');
  }

  let intent: EditIntent;
  try {
    intent = JSON.parse(content) as EditIntent;
  } catch {
    throw new Error('Pass 1 returned invalid JSON');
  }

  return { intent, usage: response.usage ?? undefined };
}

// ----------------------------------------------------------------------------
// Pass 2 — execute intent → UPDATED_DOC (gpt-4o)
// ----------------------------------------------------------------------------
function formatIntentForExecutor(intent: EditIntent): string {
  return `INTENT (parsed by Pass 1):
  operation: ${intent.operation}
  target_section: ${intent.target_section === null ? 'null' : JSON.stringify(intent.target_section)}
  replacement_text: ${intent.replacement_text === null ? 'null' : JSON.stringify(intent.replacement_text)}
  directive: ${intent.directive === null ? 'null' : JSON.stringify(intent.directive)}
  partial_edit_description: ${intent.partial_edit_description === null ? 'null' : JSON.stringify(intent.partial_edit_description)}
  fill_fields: ${JSON.stringify(intent.fill_fields)}
  confidence: ${intent.confidence}
  reasoning: ${intent.reasoning}`;
}

async function executeEditIntent(
  documentContent: string,
  intent: EditIntent
): Promise<{ text: string; usage: OpenAI.CompletionUsage | undefined }> {
  const client = getClient();

  const response = await client.chat.completions.create({
    model: 'gpt-4o',
    temperature: 0.2,
    max_tokens: 12000,
    messages: [
      { role: 'system', content: EXECUTOR_PROMPT },
      {
        role: 'user',
        content: `DOCUMENT:\n---\n${documentContent}\n---\n\n${formatIntentForExecutor(intent)}\n\nApply the intent per the OPERATION EXECUTION rules and return the UPDATED_DOC block.`,
      },
    ],
  });

  const text = response.choices[0]?.message?.content ?? '';
  return { text, usage: response.usage ?? undefined };
}

// ----------------------------------------------------------------------------
// Two-pass edit dispatcher
// ----------------------------------------------------------------------------
async function processEditTwoPass(request: AIRequest): Promise<AIResponse> {
  const { intent, usage: pass1Usage } = await parseEditIntent(
    request.documentContent,
    request.userMessage
  );

  // Low-confidence or unclear intent: do NOT run Pass 2. Ask the doctor to
  // rephrase so we don't burn a gpt-4o call on guesswork, and so we don't
  // silently apply a misinterpretation.
  if (intent.operation === 'unclear' || intent.confidence === 'low') {
    return {
      text: `I'm not sure what you want me to change. Could you rephrase?\n\n(Parser note: ${intent.reasoning})`,
      usage: pass1Usage
        ? {
            promptTokens: pass1Usage.prompt_tokens,
            completionTokens: pass1Usage.completion_tokens,
            totalTokens: pass1Usage.total_tokens,
          }
        : undefined,
      intent,
    };
  }

  const { text, usage: pass2Usage } = await executeEditIntent(
    request.documentContent,
    intent
  );

  const combinedUsage = pass1Usage || pass2Usage
    ? {
        promptTokens:
          (pass1Usage?.prompt_tokens ?? 0) + (pass2Usage?.prompt_tokens ?? 0),
        completionTokens:
          (pass1Usage?.completion_tokens ?? 0) + (pass2Usage?.completion_tokens ?? 0),
        totalTokens:
          (pass1Usage?.total_tokens ?? 0) + (pass2Usage?.total_tokens ?? 0),
      }
    : undefined;

  return {
    text: text || 'No response generated.',
    usage: combinedUsage,
    intent,
  };
}

// ----------------------------------------------------------------------------
// Main dispatch
// ----------------------------------------------------------------------------
export async function processWithAI(request: AIRequest): Promise<AIResponse> {
  if (request.action === 'edit') {
    return processEditTwoPass(request);
  }

  // Single-pass path for review / extract / chat.
  const client = getClient();

  let userPrompt = '';
  switch (request.action) {
    case 'review':
      userPrompt = `Please review the following medical procedure document for any issues, missing fields, or errors.\n\nDOCUMENT:\n---\n${request.documentContent}\n---\n\n${request.userMessage || 'Please provide a thorough review.'}`;
      break;
    case 'extract':
      userPrompt = `Extract all structured data from the following medical procedure document. Return the data as a JSON object.\n\nDOCUMENT:\n---\n${request.documentContent}\n---\n\nExtract: patient name, date, DOB, DOI, procedure type, side (bilateral/left/right), spinal level, injection number, surgeon, anesthesia type, diagnosis codes, and any other relevant fields. Return ONLY valid JSON.`;
      break;
    case 'chat':
      userPrompt = `Context - The doctor has uploaded the following medical procedure document:\n\nDOCUMENT:\n---\n${request.documentContent}\n---\n\nDoctor's message: ${request.userMessage}`;
      break;
  }

  const messages: OpenAI.Chat.ChatCompletionMessageParam[] = [
    { role: 'system', content: SYSTEM_PROMPT },
  ];

  if (request.conversationHistory && request.conversationHistory.length > 0) {
    for (const msg of request.conversationHistory) {
      messages.push({
        role: msg.role as 'user' | 'assistant',
        content: msg.content,
      });
    }
  }

  messages.push({ role: 'user', content: userPrompt });

  const response = await client.chat.completions.create({
    model: 'gpt-4o-mini',
    max_tokens: 12000,
    temperature: 0.3,
    messages,
  });

  const textContent = response.choices[0]?.message?.content ?? '';
  const usage = response.usage
    ? {
        promptTokens: response.usage.prompt_tokens,
        completionTokens: response.usage.completion_tokens,
        totalTokens: response.usage.total_tokens,
      }
    : undefined;

  return {
    text: textContent || 'No response generated.',
    usage,
  };
}
