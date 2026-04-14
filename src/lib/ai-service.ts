import OpenAI from 'openai';

// ========================================
// MedDoc Pro - AI Service (OpenAI GPT-4o-mini)
// Uses same OPENAI_API_KEY as Whisper transcription
// ========================================

let openaiClient: OpenAI | null = null;

function getClient(): OpenAI {
  if (!openaiClient) {
    const apiKey = process.env.OPENAI_API_KEY;
    if (!apiKey || apiKey === 'your-api-key-here') {
      throw new Error('OPENAI_API_KEY is not configured. Please set it in .env.local');
    }
    openaiClient = new OpenAI({ apiKey });
  }
  return openaiClient;
}

const SYSTEM_PROMPT = `You are MedDoc — an expert Medical Document Assistant built for pain management physicians. You edit medical procedure notes with clinical precision.

STRICT RULES:
1. ONLY modify what the doctor explicitly asks for
2. NEVER add, remove, or change anything the doctor didn't mention
3. Understand clinical terminology: LESI, CESI, PRP, LFB, epidural, transforaminal, etc.

RESPONSE FORMAT - ALWAYS use this exact format when making edits:

First, a short confirmation (2-3 lines max).

Then ALWAYS output the COMPLETE updated document inside a code block tagged "UPDATED_DOC":

\`\`\`UPDATED_DOC
(the entire document text with changes applied)
\`\`\`

This is CRITICAL - the save feature depends on this format. Always include the full document.

When the doctor uploads a document:
- Say what type of document it is in 1 sentence
- List which fields are currently empty
- Ask: "Which fields would you like me to fill?"
- Do NOT include UPDATED_DOC block on first upload

The doctor may speak via voice so requests can be conversational. Examples:
- "fill the date 12/10/2026" → fill DATE, output UPDATED_DOC with full document
- "patient name is John Smith, DOB March 5 1980" → fill PATIENT and DOB, output UPDATED_DOC

Known procedure types: CESI, CE PRP, LESI, LE PRP, LFB
Known fields: DATE, PATIENT, DOB, DOI, SURGEON, TITLE OF PROCEDURE, ANESTHESIA, BRIEF HISTORY, DESCRIPTION/PROCEDURE, Diagnosis codes

BRIEF HISTORY EXAMPLES - When asked to write a brief history, use EXACTLY this style from Dr. Moussazadeh:

For CESI:
- "1st CESI for refractory neck pain with radiculopathy."
- "2nd CESI for refractory neck pain with radiculopathy."

For CE PRP:
- "1st cervical epidural PRP injection for refractory neck and upper back pain."

For LESI (Bilateral):
- "1st LESI for refractory low back pain with radiculopathy."
For LESI (Left):
- "1st LESI for refractory low back pain with left sided radiculopathy."
For LESI (Right):
- "1st LESI for refractory low back pain with right sided radiculopathy."

For LE PRP (Bilateral):
- "1st LE PRP injection for refractory low back pain with bilateral radiculopathy."
For LE PRP (Left):
- "1st LE PRP injection for refractory low back pain with left sided radiculopathy."
For LE PRP (Right):
- "1st LE PRP injection for refractory low back pain with right sided radiculopathy."

For LESI + LFB combo:
- "1st LEFSI for refractory low back pain with bilateral radiculopathy."

For LFB (2 levels):
- "1st/2nd LFB for refractory axial low back pain."
For LFB (3 levels):
- "LFB for refractory axial low back pain"

RULES for brief history:
- Always match the procedure type from the document TITLE OF PROCEDURE
- Use the injection number (1st, 2nd, 3rd) if the doctor specifies it
- For bilateral: say "radiculopathy" (LESI) or "bilateral radiculopathy" (LE PRP)
- For left/right: say "left sided radiculopathy" or "right sided radiculopathy"
- Keep it SHORT - one sentence only, exactly like the examples above
- NEVER add extra information or make it longer than the examples`;

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
   *  omitted it (which it shouldn't for chat.completions). */
  usage?: {
    promptTokens: number;
    completionTokens: number;
    totalTokens: number;
  };
}

export async function processWithAI(request: AIRequest): Promise<AIResponse> {
  const client = getClient();

  let userPrompt = '';

  switch (request.action) {
    case 'review':
      userPrompt = `Please review the following medical procedure document for any issues, missing fields, or errors.\n\nDOCUMENT:\n---\n${request.documentContent}\n---\n\n${request.userMessage || 'Please provide a thorough review.'}`;
      break;

    case 'edit':
      userPrompt = `Here is a medical procedure document. Please make the following changes as requested by the doctor.\n\nDOCUMENT:\n---\n${request.documentContent}\n---\n\nREQUESTED CHANGES: ${request.userMessage}\n\nPlease return the COMPLETE modified document text with all changes applied. Clearly indicate what was changed.`;
      break;

    case 'extract':
      userPrompt = `Extract all structured data from the following medical procedure document. Return the data as a JSON object.\n\nDOCUMENT:\n---\n${request.documentContent}\n---\n\nExtract: patient name, date, DOB, DOI, procedure type, side (bilateral/left/right), spinal level, injection number, surgeon, anesthesia type, diagnosis codes, and any other relevant fields. Return ONLY valid JSON.`;
      break;

    case 'chat':
      userPrompt = `Context - The doctor has uploaded the following medical procedure document:\n\nDOCUMENT:\n---\n${request.documentContent}\n---\n\nDoctor's message: ${request.userMessage}`;
      break;
  }

  // Build messages array for OpenAI Chat Completions
  const messages: OpenAI.Chat.ChatCompletionMessageParam[] = [
    { role: 'system', content: SYSTEM_PROMPT },
  ];

  // Add conversation history if present
  if (request.conversationHistory && request.conversationHistory.length > 0) {
    for (const msg of request.conversationHistory) {
      messages.push({
        role: msg.role as 'user' | 'assistant',
        content: msg.content,
      });
    }
  }

  // Add the current message
  messages.push({
    role: 'user',
    content: userPrompt,
  });

  const response = await client.chat.completions.create({
    model: 'gpt-4o-mini',
    max_tokens: 4096,
    temperature: 0.3, // low temperature for precise medical edits
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
