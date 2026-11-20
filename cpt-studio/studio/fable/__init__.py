"""The Fable coding step (BUILD-SPEC section 4; DECISIONS D351-D353): one READER and one independent CHECKER, both
Claude Fable 5.2 reading the original document through the Anthropic API.

- credentials.py: the Anthropic credentials file, read strictly as data.
- client.py: the request and the one streamed send per request (official SDK), its outcome; live, replay or disabled.
- prompts.py: the reader's and checker's instructions and the practice context.
- document.py: the document block (PDF, Word converted to PDF, text).
- result.py: the final JSON, the combination of the two reads (the only glue logic) and the citations per code.
- pricing.py: claude-fable-5-2's rates, a run's priced cost and a send's worst case.

Nothing here decides, holds or changes a code: the codes are Fable's (BUILD-SPEC section 0).
"""

# Why a coding round failed (CodingRound.failure_kind). One copy, read by every module of the step and by studio.jobs.
UNREADABLE = 'unreadable'  # the answer held no readable final JSON (4.4); nothing is resent
CEILING = 'ceiling'  # the document's spending ceiling would be passed by the next send (3.2)
HOLD = 'hold'  # an account refusal set a hold, or a hold stands (3.3)
BUSY = 'busy'  # rate-limited or overloaded; a human may retry (3.3)
CONVERT = 'convert'  # the Word file could not be converted to PDF (4.3)
DOCUMENT = 'document'  # the API refused the document (encrypted, damaged, too large), or it is empty (4.3)
DECLINED = 'declined'  # the answer ended with stop reason refusal, after the fallbacks (4.1)
TOO_LONG = 'too_long'  # the answer reached max_tokens (4.1)
UNKNOWN = 'unknown'  # the request may have reached the vendor and its outcome is not known (4.1)
FAILED = 'failed'  # any other definite failure
UNAVAILABLE = 'unavailable'  # nothing was sent: coding disabled, credentials unusable, no recording, the live gate
STORAGE = 'storage'  # the stored original could not be read back unchanged
FAILURE_KINDS = (UNREADABLE, CEILING, HOLD, BUSY, CONVERT, DOCUMENT, DECLINED, TOO_LONG, UNKNOWN, FAILED, UNAVAILABLE,
                 STORAGE)
