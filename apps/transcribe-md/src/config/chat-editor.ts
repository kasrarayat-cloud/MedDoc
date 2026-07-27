// ============================================================================
// The pre-sign chat editor. Build-time, fail-closed, OFF.
// ----------------------------------------------------------------------------
// A conversational surface beside the document: the doctor asks, the SERVER
// dispatches into the same audited actions the buttons call, the document
// re-fills.
//
// The model never writes. It returns a structured intent from a closed union
// (see lib/chat-edit/intent.ts) and the server executes it — so everything the
// chat can do already has an owner, a refusal set, and an audit row.
//
// THE HARD GATES ARE NOT REACHABLE FROM IT. There is no intent to override a
// prescription warning, confirm an E/M change, or sign — not disabled, ABSENT,
// with a test that fails if one is ever added. A gate a conversation can talk
// its way through is not a gate.
//
// Rollback: unset NEXT_PUBLIC_CHAT_EDITOR and rebuild.
// ============================================================================

export function isChatEditor(): boolean {
  return process.env.NEXT_PUBLIC_CHAT_EDITOR === 'true';
}

export const CHAT_EDITOR_FLAG = 'NEXT_PUBLIC_CHAT_EDITOR';
