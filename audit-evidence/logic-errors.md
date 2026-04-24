# Logic errors — runtime bug hunt

Hot paths reviewed: `apps/transcribe-md/src/worker/**`, `apps/transcribe-md/src/app/visits/**`, `apps/meddoc-pro/src/lib/realtime/**`, `apps/meddoc-pro/src/app/dashboard/patients/**`, `packages/auth/src/**`, `packages/ai/src/**`.

## Critical (definitely broken under normal usage)

- **Stale closure on MediaRecorder — interval captures pre-mount `stop` function**
  `apps/transcribe-md/src/app/visits/[id]/record/recording-client.tsx:147-151,161-169` — category 3. `stop` is a plain (non-useCallback) function redefined every render; the `setInterval` inside `start()` captures the `stop` that existed at the moment `start` was called. `recorder.onstop` similarly closes over `finalizeAndUpload` from that render. If the component re-renders during recording (state change from `elapsed` ticks fire `setElapsed` every 250 ms, triggering render), the interval keeps calling the original `stop` and the recorder keeps the original `onstop` — both referring to refs that are still live (good) but to the `finalizeAndUpload` of the start-time closure (which has stale `visitId`/`router` in theory; stable in practice). Concrete bad case: if `visitId` prop ever changed mid-recording (not today, but a parent re-render passing a new value), upload would POST to the old visit. Fix: wrap `stop` in `useCallback([])`, keep `finalizeAndUpload` reachable via a ref.

- **`patient.birthYear` default produces a garbage "age 30" for patients with unknown DOB**
  `apps/meddoc-pro/src/lib/data/patients.ts:483,322`, `PatientDetailClient.tsx:131`, `actions.ts:760,1192`. Category 8. `prismaToView` coerces null `birthYear` to `currentYear - 30`. Downstream `age = currentYear - patient.birthYear` always returns 30 for those patients. This value is passed to the GPT prompts that generate referral letters, prior-auth letters, disability forms, and voice-tool SOAP notes. An 85-year-old's referral letter is drafted with "age 30" context — elevated hallucination risk on recommendations. Fix: let `birthYear: number | null` flow through `PatientView` and render/prompt "age unknown" when null.

- **`recorder.onstop` fires during unmount cleanup → uploads partial blob to a dead page**
  `apps/transcribe-md/src/app/visits/[id]/record/recording-client.tsx:81-93,135-141`. Category 3+5. Unmount cleanup at L84 calls `recorderRef.current.stop()`; MediaRecorder's `onstop` fires synchronously-ish, re-entering `finalizeAndUpload()` which POSTs `/api/visits/<id>/dictation/upload` and then calls `router.push` on an unmounted component. A doctor who hits the browser back button mid-recording uploads a partial audio file and triggers a "recording uploaded" toast at their new page. Fix: set `recorderRef.current.onstop = null` before `.stop()` in the unmount handler, or use a `cancelledRef` gate in `finalizeAndUpload`.

## High (broken in specific conditions)

- **Voice-cap check is non-atomic — a doctor can open N concurrent sessions past the daily cap**
  `apps/meddoc-pro/src/lib/realtime/usage-cap.ts:51-58` + `api/realtime/session/route.ts:59`. Category 4. `checkVoiceCap` is read-only; minutes are debited only when `/api/realtime/session/end` runs, which depends on the browser firing a beacon. A doctor opening 5 patient tabs in parallel while already at 118/120 minutes gets 5 ephemeral tokens issued (all see `remaining=2`). Tab crashes never beacon end — minutes leak. Fix: include a "sessions open today" counter incremented atomically at mint-time; refuse when combined usage+open exceeds cap.

- **Stale `status` closure in `dc.onclose`**
  `apps/meddoc-pro/src/lib/hooks/useRealtimeSession.ts:474-476`. Category 3. `if (status !== 'idle' && status !== 'error') setStatus('idle')` — `status` is captured from the render that ran `start()` (always `connecting` there). The guard is effectively always true. Benign today but any future "don't double-flip status" logic will rely on a broken comparison. Fix: functional setter `setStatus(prev => prev === 'idle' || prev === 'error' ? prev : 'idle')`.

- **Appointment list in voice assistant prompt renders in server's locale, not doctor's**
  `apps/meddoc-pro/src/lib/realtime/tools.ts:588-594`. Category 8. `new Date(a.scheduledAt).toLocaleString('en-US', {weekday,...})` — no `timeZone` arg passed even though `timezone` is already plumbed into `buildSystemPrompt`. On a UTC container, a Tuesday 10 AM Pacific appointment is displayed to the model as "Tue 5 PM" or even "Wed 1 AM" depending on offset. Model reads back wrong day/time when doctor asks "what's on Tuesday?". Fix: pass `timeZone: timezone` into the Intl call at L588.

- **`validateSession.lastActiveAt` update is a floating unhandled promise**
  `packages/auth/src/user-session.ts:97-104`. Category 2. `prisma.userSession.update(...).catch(...)` returns a Promise that is neither awaited nor `void`-ed; stripped of its chained `.catch`, the raw `update()` would be floating. With the `.catch` attached rejection is handled, but on Node 24+ (unhandledRejection = throw) this pattern is flagged by the runtime if the `.catch` callback itself throws (it calls `console.error`, can't throw). Defense-in-depth fix: `void prisma.userSession.update(...).catch(...)`.

## Medium (edge cases)

- **`checkVoiceCap` off-by-zero — a user with 0.01 min left can start a session**
  `apps/meddoc-pro/src/lib/realtime/usage-cap.ts:57`. Category 7. `ok: remaining > 0`; any fractional residual passes. Fix: require `remaining >= 1` or some min-session budget.

- **`scheduleVisitAction` past-date guard allows today-but-already-happened times**
  `apps/meddoc-pro/src/app/dashboard/patients/actions.ts:1446`. Category 7. `scheduledAt < now - 24h` rejects only >24h in the past. If the voice model hallucinates today's date at 9 AM while the real time is 2 PM, the appointment books in the past. Fix: reject any past time, keep a small (e.g. 10 min) tolerance for wall-clock skew.

- **`filterUpcomingAppointments` includes appointments up to 24h stale**
  `apps/meddoc-pro/src/app/api/realtime/session/route.ts:289`. Category 7. Cutoff `>= now - 24h` means the voice assistant's `UPCOMING_APPOINTMENTS` list includes yesterday's visits. Doctor says "cancel the follow-up" → model may target a past appointment. Fix: cutoff at `now` and surface in-progress visits via an explicit `IN_PROGRESS` filter.

- **`enforceCacheBound` evicts by expiry time, not LRU**
  `apps/meddoc-pro/src/lib/realtime/intelligence.ts:49-58`. Category 6. Comment says "LRU-ish" but the algorithm sorts by `expires` ascending — a hot entry 30 s old with 9.5 min TTL left is not evicted; a cold entry 9 min old with 1 min left is. Writes don't refresh `expires`. Practical impact small (cache cap 500); fix: update `expires` on each hit, or actually sort by last-access time.

- **`EditPatientModal` / `PatientFileUploadModal` setTimeout leaks past unmount**
  `EditPatientModal.tsx:162`, `PatientFileUploadModal.tsx:217`. Category 5. `setTimeout(() => onClose(), 800–1000)` fires `onClose` even if the user navigates away mid-delay. Parent `setState` during unmount logs a dev warning. Fix: stash timeout id in a ref, clear in the unmount cleanup.

## Low (defensive programming gaps)

- **`buildClinicalTrajectory` builds a new `OpenAI()` client per cache miss**
  `apps/meddoc-pro/src/lib/realtime/intelligence.ts:96`. Wasteful; not broken. Fix: module-level singleton like `patients/actions.ts:461-471`.

- **`tools.ts:534` `new Date(currentDateIso)` — no `isFinite` guard**
  `apps/meddoc-pro/src/lib/realtime/tools.ts:534`. Malformed ISO → "Invalid Date" silently; every downstream `toLocaleString` call in the prompt renders "Invalid Date". Fix: `if (!Number.isFinite(now.getTime())) throw ...`.

- **`retention-sweep.ts:152,154` shared-counter increment inside `Promise.all`**
  `apps/transcribe-md/src/worker/cleanup/retention-sweep.ts:127-163`. Safe under Node's single-threaded event loop (microtask-serialized), but brittle pattern. Fix: collect per-promise returns and sum at the end.

- **`ClinicalSafetyPanel` handleDelete uses `confirm()` / `setError` for a non-informative failure on rejection**
  `apps/meddoc-pro/src/app/dashboard/patients/[id]/ClinicalSafetyPanel.tsx:179-189`. If the Zod schema rejects, `setError(result.error)` displays but does not clear after another click. Minor UX.

- **`InsuranceBadge` conflates two semantically-different states** (`verified === false` displays as "Self-pay / not verified")
  `PatientDetailClient.tsx:106-118`. Not a runtime bug — UX/data-model nit.

## Investigated and NOT a bug (confirmed OK patterns)

- `packages/ai/src/log.ts:27-48` — `logAiCall` intentional fire-and-forget with `void prisma…create().catch(console.error)`. Documented at top. OK.

- `apps/meddoc-pro/src/app/dashboard/patients/actions.ts:487-494` — `void logApiUsage(…).catch(…)`. `void` applies to whole expression including `.catch`; handler IS attached. Correct.

- `packages/ai/src/model-client.ts:73-94` — `for (attempt = 0; attempt <= MAX_RETRIES; attempt++)` with MAX_RETRIES=2 runs 3 total attempts (initial + 2 retries), matches the comment's "Up to 2 retries". OK.

- `apps/transcribe-md/src/app/visits/new/patient-picker.tsx:109-133` — debounced search with AbortController + cleanup. Proper abort-on-change. OK.

- `apps/meddoc-pro/src/lib/hooks/useRealtimeSession.ts:98-106` — callback refs updated via useEffect so the data channel handler reads fresh callbacks without re-subscribing. Standard pattern.

- `apps/meddoc-pro/src/lib/hooks/useVoiceRecorder.ts:69-73` — `onAutoStopRef` pattern (registered once, read lazily). Correct.

- `apps/transcribe-md/src/worker/retry-decision.ts:27-36` — `Math.max(1, attempts) - 1` guards zero-attempts misconfig. Unit-tested. OK.

- `apps/transcribe-md/src/worker/layers/02-speaker-roles.ts:80-101` — diarization-empty fallback writes confidence-0.5 single-speaker map with `needsReview: true`. Correct belt-and-suspenders.

- `apps/meddoc-pro/src/app/dashboard/patients/[id]/EditPatientModal.tsx:101-112` — `listPracticeDoctorsAction().then(...).catch(...)` with `cancelled` flag. Correct cancel-on-unmount.

- `apps/meddoc-pro/src/app/dashboard/patients/[id]/ClinicalSafetyPanel.tsx:67-69` — server-prop → local-state mirror via three useEffects. Standard Next 15 pattern.
