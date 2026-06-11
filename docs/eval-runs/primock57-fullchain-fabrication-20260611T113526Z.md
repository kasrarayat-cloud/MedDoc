# PriMock57 FULL-CHAIN fabrication eval — 20260611T113526Z

**Question answered:** what is the CURRENT full-pipeline clinical-fabrication rate (class-c) on PriMock57, real-model?

## Environment (exact)

| Field | Value |
|---|---|
| Pipeline | real Deepgram nova-3-medical → L3 entities → L4 SOAP → L5 self-critique → L6 polish |
| L3 model | `claude-sonnet-4-6` (tm_entities) |
| L4 model | `claude-opus-4-8` (tm_soap_draft) |
| L5 model | `claude-opus-4-8` (tm_critique) |
| L6 model | `claude-sonnet-4-6` (tm_polish) |
| Judge model | `claude-sonnet-4-6` temp 0; one combined call per case rates BOTH SOAPs, a/b/c rubric, present_in dedup |
| MOCK_AI_CALLS | false (real models) |
| DATABASE_URL | meddoc_qa_test on isolated meddoc-qa stack (NOT prod `meddoc`); prisma writes additionally stubbed to no-ops (zero rows) |
| Visits signed | 0 (chain stops at L6; no sign, no email) |

## HEADLINE

- **TODAY's total class-(c) genuine fabrications across the sample (FINAL post-L6 SOAP): 0** across n=0 cases (0 case(s) carry ≥1 class-c).
- Post-L4 (pre-critique) class-(c): 0. Net L5/L6 change on class-c: +0.
- **Polish-survival rate:** 0/0 polished notes kept (0 L6b gate fallbacks → pre-L6 draft served).
- (a)=ASR-propagation, (b)=benign inference, (c)=genuine fabrication. Only (c) is the dangerous "hallucination" number.

## Per-case table

| Case | src | WER | post-L4 (a/b/c) | FINAL (a/b/c) | L5 overall (crit) | L6b gate | notes |
|---|---|---|---|---|---|---|---|
| day5_consultation10 | audio | — | — | — | — | — | ERROR: 400 {"type":"error","error":{"type":"invalid_request_error","message":"Your credit balance is too low to access the Anthropic API. Please go to Plans & Billing to upgrade or purchase credits."},"request_id":"req_011CbwQLDK4vbSyY4XFYShYg"} |
| day1_consultation05 | audio | — | — | — | — | — | ERROR: 400 {"type":"error","error":{"type":"invalid_request_error","message":"Your credit balance is too low to access the Anthropic API. Please go to Plans & Billing to upgrade or purchase credits."},"request_id":"req_011CbwQLin7pVNwYoHGp2B43"} |
| day1_consultation02 | audio | — | — | — | — | — | ERROR: 400 {"type":"error","error":{"type":"invalid_request_error","message":"Your credit balance is too low to access the Anthropic API. Please go to Plans & Billing to upgrade or purchase credits."},"request_id":"req_011CbwQM3pMGo1mkZsmnpnA5"} |
| day1_consultation08 | audio | — | — | — | — | — | ERROR: 400 {"type":"error","error":{"type":"invalid_request_error","message":"Your credit balance is too low to access the Anthropic API. Please go to Plans & Billing to upgrade or purchase credits."},"request_id":"req_011CbwQMHx9dwDcD4Qbj66cF"} |
| day4_consultation08 | audio | — | — | — | — | — | ERROR: 400 {"type":"error","error":{"type":"invalid_request_error","message":"Your credit balance is too low to access the Anthropic API. Please go to Plans & Billing to upgrade or purchase credits."},"request_id":"req_011CbwQMatswTir2aeoJq9qu"} |
| day1_consultation01 | audio | — | — | — | — | — | ERROR: 400 {"type":"error","error":{"type":"invalid_request_error","message":"Your credit balance is too low to access the Anthropic API. Please go to Plans & Billing to upgrade or purchase credits."},"request_id":"req_011CbwQMpja9ynnSsGtJnF6G"} |
| day1_consultation03 | audio | — | — | — | — | — | ERROR: 400 {"type":"error","error":{"type":"invalid_request_error","message":"Your credit balance is too low to access the Anthropic API. Please go to Plans & Billing to upgrade or purchase credits."},"request_id":"req_011CbwQN5pBPBHJaBFt1ijbc"} |
| day1_consultation04 | audio | — | — | — | — | — | ERROR: 400 {"type":"error","error":{"type":"invalid_request_error","message":"Your credit balance is too low to access the Anthropic API. Please go to Plans & Billing to upgrade or purchase credits."},"request_id":"req_011CbwQNMxHQ3pKMJz1EHSCf"} |
| day2_consultation01 | audio | — | — | — | — | — | ERROR: 400 {"type":"error","error":{"type":"invalid_request_error","message":"Your credit balance is too low to access the Anthropic API. Please go to Plans & Billing to upgrade or purchase credits."},"request_id":"req_011CbwQNcDXWSQDoUaQYuYD2"} |
| day2_consultation05 | audio | — | — | — | — | — | ERROR: 400 {"type":"error","error":{"type":"invalid_request_error","message":"Your credit balance is too low to access the Anthropic API. Please go to Plans & Billing to upgrade or purchase credits."},"request_id":"req_011CbwQNzTVPeDj7XHzivFEM"} |
| day3_consultation01 | audio | — | — | — | — | — | ERROR: 400 {"type":"error","error":{"type":"invalid_request_error","message":"Your credit balance is too low to access the Anthropic API. Please go to Plans & Billing to upgrade or purchase credits."},"request_id":"req_011CbwQPH2Q8yRFM8i7YeyaC"} |
| day3_consultation05 | audio | — | — | — | — | — | ERROR: 400 {"type":"error","error":{"type":"invalid_request_error","message":"Your credit balance is too low to access the Anthropic API. Please go to Plans & Billing to upgrade or purchase credits."},"request_id":"req_011CbwQPXsNDHWbZspwfTcCX"} |

**Totals (FINAL):** class-a=0, class-b=0, class-c=0.

## Class-(c) genuine fabrications — verbatim evidence

_No class-(c) genuine fabrications found in EITHER the post-L4 or the final SOAP across the sample._

## Did L5 self-critique / L6 polish change the fabrication set?

- class-(c) REMOVED by L5/L6 (in L4, gone from FINAL): 0
- class-(c) INTRODUCED at/after L6 (not in L4): 0
- class-(c) SURVIVED L4→FINAL unchanged: 0

## Raw per-case dump (combined-judge flags + both SOAPs)
