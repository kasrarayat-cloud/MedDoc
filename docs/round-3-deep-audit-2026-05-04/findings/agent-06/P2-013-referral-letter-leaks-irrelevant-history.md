---
id: A06-P2-013
title: Referral letter prompt has no relevance filter; psych history can leak into ortho referral
severity: P2
domain: AI safety / patient privacy / specialty-appropriate disclosure
files:
  - apps/transcribe-md/src/worker/layers/07d-referrals.ts (lines 51-54)
---

## Issue

The L7d (referrals) prompt asks the model to populate a
`relevant_history` field as "2-3 sentences summarising pertinent
PMH / current meds / exam/labs that the recipient needs to triage."

The interpretation of "pertinent" is left entirely to the model,
which has the full SOAP and full entity list as input. The prompt
gives no exclusion guidance for:

- Mental health history (depression, anxiety, prior SI, PTSD,
  substance use disorders) when referring to a non-psychiatry
  specialist.
- Sexual / reproductive history when referring to non-OB-Gyn /
  non-urology specialists.
- HIV / STI status when not directly relevant.
- Domestic-violence history when documented.
- Adoption / family-structure facts irrelevant to the referral.

A textbook risk:

> Patient referred to **orthopedics** for knee MRI. The SOAP
> documents history of MDD, prior suicide attempt, current SSRI.
> The model writes a referral letter to ortho saying:
> "Relevant history: MDD on sertraline 100mg, prior suicide attempt 2019, knee pain..."

The orthopedist now has stigmatizing PHI they didn't need to triage
the knee MRI. The patient's privacy expectation around mental-health
history is violated by an automated system.

## Evidence

```ts
// 07d-referrals.ts:45-53
const system = [
  'Review the SOAP plan for referrals (to specialists, imaging, labs,',
  'therapy, etc.). Draft a brief referral note for each referral the',
  'plan mentions...',
  ...
  '- relevant_history: 2-3 sentences summarising pertinent PMH /',
  '  current meds / exam/labs that the recipient needs to triage',
];
```

No exclusion list. No "minimum-necessary" framing. No specialty-
specific filter (e.g., "exclude psychiatric history when referring
to ortho/derm/etc unless the chief complaint is psych-related").

## Risk

P2 because:

- Direct HIPAA-relevant disclosure: the "minimum necessary" rule
  (45 CFR §164.502(b)) requires that disclosed PHI be limited to
  the minimum necessary for the purpose. An orthopedic referral
  doesn't need a suicide-attempt history. This is a recurring
  failure pattern in non-AI documentation too, but a deterministic
  AI system that emits it consistently is worse than human
  variability.
- Patient stigma: mental-health history shared with non-mental-
  health providers can subtly affect the doctor-patient
  relationship, especially in pain management or surgery contexts.
- Discoverable in a privacy complaint review.

## Recommended Fix (plan only)

1. **Add specialty-aware exclusion list to the L7d prompt**:
   ```
   Exclude from "relevant_history" unless the receiving specialty
   is mental-health-adjacent OR the chief complaint is mental-
   health-related:
     - prior suicide attempts / SI history
     - psychiatric medication history beyond what affects the
       organ system being referred
     - substance use disorder history beyond what affects
       perioperative or pharmacology decisions
     - sexual / reproductive history
     - HIV status
     - history of intimate-partner violence
   When uncertain, default to OMIT and add a note "PMH may be
   shared on request" to the referral.
   ```

2. **Code-side filter** (deterministic): for non-psych specialty
   targets, post-process `referrals[i].relevant_history` to redact
   any sentence containing tokens from a stop-list (`suicid`,
   `psychotic`, `MDD`, `PTSD`, `SUD`, `IPV`, `HIV`, `domestic
   violence`, etc.). Replace with `[mental-health history available
   on request]`.

3. **Doctor-review prompt**: surface a yellow banner in the
   Referrals tab — "Verify minimum-necessary disclosure before
   sending. Click to edit relevant_history."

4. **Referral target classification**: extract the receiving
   specialty from `referrals[i].to`. If non-psych and the SOAP
   contains psych content, log a privacy-review event for the
   admin dashboard.
