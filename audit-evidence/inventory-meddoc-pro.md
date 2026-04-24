# MedDoc Pro Interactive Element Inventory

**Compiled:** 2026-04-24  
**Scope:** `/opt/meddoc-pro/apps/meddoc-pro/src/`  
**Coverage:** Landing pages, dashboard, patient management, schedule, settings, admin console

---

## LANDING PAGES & AUTH

### Home Page (`/`)
- **File:** `src/app/page.tsx` — Landing wrapper
  - Composes: Navbar, Hero, Features, HowItWorks, Pricing, Testimonials, Footer

### Navbar Component
- **File:** `src/components/landing/Navbar.tsx:1` (use client)
- **Buttons:**
  - Line 61: `<button onClick={() => setMobileOpen(!mobileOpen)}` → Toggle mobile menu (hamburger)
  - Line 544: `<button onClick={onClose}` → Close mobile menu (X icon)
- **Links:**
  - Line 22: `<Link href="/">` → Logo home link
  - Line 34–40: Nav links with `onClick={() => setMobileOpen(false)}` → #features, #how-it-works, #pricing
  - Line 46: `<Link href="/login">` → Login link (desktop)
  - Line 52: `<Link href="/register">` → Get Started CTA (desktop)
  - Line 99–112: Mobile nav links + Login/Register with close handler

### Hero Section
- **File:** `src/components/landing/Hero.tsx:1` (use client)
- **Buttons:**
  - Line 141: `<button className="group inline-flex items-center gap-2...">` → Watch Demo (no onClick handler assigned)
- **Links:**
  - Line 134: `<Link href="/register">` → Start Free Trial button
- **Handlers:**
  - Line 33–45: `useEffect` with `setInterval` → Typing effect for headline (displayText state update)

### Login Page
- **File:** `src/app/login/page.tsx:1` (use client)
- **Forms:**
  - Line 138: `<form onSubmit={handleSubmit}>` → Credentials login
    - `handleSubmit` (line 28): Calls `signIn('credentials')` from next-auth/react
    - Email input: Line 149 (onChange not shown but form-managed)
    - Password input: Line 179 (onChange not shown but form-managed)
- **Links:**
  - Line 107: `<Link href="/">` → Logo click returns home
  - Line 170: `<Link href="#">` → Forgot password (no onClick intercept)
  - Line 207: `<Link href="/register">` → Request access
- **Buttons:**
  - Line 232: `<SubmitButton>` (line 229) → Sign In (controlled by `isPending`, `isNavigating`)

### Register Page (Invite-Only)
- **File:** `src/app/register/page.tsx`
- **Links:**
  - Line 31: `<Link href="/">` → Logo
  - Line 78: `<Link href="/login">` → Go to sign in

---

## DASHBOARD

### Dashboard Home
- **File:** `src/app/dashboard/page.tsx` — Server component
- **Client Component:** `src/app/dashboard/DashboardClient.tsx:1` (use client)
  - Passes stats, appointments, activity to client

### Sidebar Navigation
- **File:** `src/components/dashboard/Sidebar.tsx:1` (use client)
- **Buttons:**
  - Line 285: `<button onClick={() => setMobileOpen(true)}>` → Open mobile menu (hamburger)
  - Line 317: `<button onClick={() => setMobileOpen(false)}>` → Close mobile menu (X)
  - Line 344: `<motion.button ... onClick={() => setCollapsed(!collapsed)}>` → Collapse/expand sidebar toggle
- **Links:**
  - Line 131: `<Link href={item.href} onClick={() => isMobile && setMobileOpen(false)}>` (7 nav items)
    - Dashboard, Patients, Schedule, Doc Editor, Document History, Audit Logs, Settings
  - Line 212: `<a href="/system-admin">` → Back to Admin (for ADMIN/SUPER_ADMIN users)
- **Logout:**
  - Line 273: `<LogoutButton iconOnly ariaLabel="Logout" />` → Sign out

### Patients List
- **File:** `src/app/dashboard/patients/page.tsx` — Server component
- **Client Component:** `src/app/dashboard/patients/PatientsListClient.tsx:1` (use client)

**Interactive Elements in PatientsListClient:**
- **State Management:**
  - Line 49: `useState('')` → Search query
  - Line 50: `useState<'ALL' | PatientStatus>('ALL')` → Status filter
  - Line 54: `useState<'ALL' | 'VERIFIED' | 'UNVERIFIED' | 'PENDING'>('ALL')` → Insurance filter
  - Line 57: `useState(false)` → Add modal toggle
  - Line 58: `useState<string | null>(null)` → Kebab menu open state
  - Line 60: `useTransition()` → Archive action pending

- **Buttons:**
  - Line 191: `<button onClick={() => setShowAddModal(true)}>` → Add Patient CTA
  - Line 251: Filter status buttons (ALL, ACTIVE, INACTIVE, ARCHIVED) → `onClick={() => setStatusFilter(s)}`
  - Line 276: Insurance filter buttons (ALL, VERIFIED, UNVERIFIED, PENDING) → `onClick={() => setInsuranceFilter(key)}`
  - Line 297: `<button className="px-3 py-2...">` → More filters (no onClick attached)
  - Line 453: `<button ... onClick={(e) => { e.preventDefault(); e.stopPropagation(); setOpenKebabId(...) }}>` → Kebab menu toggle per patient
  - Line 481: Archive patient action button → `onClick={(e) => { ... handleArchive(patient) }}`

- **Links:**
  - Line 351: `<Link href={`/dashboard/patients/${patient.id}`}>` → Patient detail row (clickable)

- **Modals:**
  - Line 511: `<AddPatientModal open={showAddModal} onClose={() => setShowAddModal(false)} />`

### Add Patient Modal
- **File:** `src/app/dashboard/patients/AddPatientModal.tsx:1` (use client)
- **Form:** `onSubmit={handleSubmit}` (line 553)
  - Line 417: `handleSubmit` → `createPatientAction(payload)` server action
  - Line 631: `<input onChange={(e) => update('firstName', e.target.value)}>` (repeated for all form fields)
  
- **Buttons:**
  - Line 500: `<button type="button" onClick={handleMicClick}>` → Voice recorder mic button
    - Text, recording state, and disabled states
  - Line 543: `<button onClick={onClose}>` → Close modal (X)
  - Line 597: `<button type="button" onClick={() => { setForm(voiceNote.previousForm); setVoiceNote(null); }}>` → Undo voice fill
  - Line 611: `<button type="button" onClick={() => setVoiceNote(null)}>` → Dismiss voice banner
  - Line 940: `<button type="button" onClick={onClose}>` → Cancel
  - Line 948: `<button type="submit">` → Create Patient

- **Voice Handler:**
  - Line 338: `const handleMicClick = useCallback(async () => { ... })` 
    - Calls `voice.start()` or `voice.stop()` and `handleAudioBlob(blob)`
    - handleAudioBlob (line 229) → POST to `/api/patients/extract-from-voice`

- **Server Actions:**
  - `createPatientAction()` — Creates patient record
  - `getNextChartIdAction()` — Fetches next auto-chart ID
  - `listPracticeDoctorsAction()` — Fetches doctor list for assignment dropdown

- **onChange Handlers (all text/select/textarea):**
  - Line 631: firstName
  - Line 645: lastName
  - Line 663: chartId
  - Line 674: mrn
  - Line 691: birthYear
  - Line 708: phoneLast4
  - Line 729: cellPhone (special: derives phoneLast4)
  - Line 740: homePhone
  - Line 754: email
  - Line 766: sex (select)
  - Line 783: assignedDoctorId (select)
  - Line 801: addressLine1
  - Line 816: addressLine2
  - Line 827: city
  - Line 838: state
  - Line 857: postalCode
  - Line 876: pharmacyName
  - Line 886: pharmacyPhone
  - Line 903: initialHistory (textarea)
  - Line 924: tags

### Edit Patient Modal
- **File:** `src/app/dashboard/patients/[id]/EditPatientModal.tsx:1` (use client)
- **Form:** `onSubmit={(e: React.FormEvent) => { handleSubmit(...) }}` (line 127)
- **Server Action:** `updatePatientAction(patient.id, payload)`

- **Buttons:**
  - Line 208: Close button (X)
  - Cancel / Save buttons in footer

### Insurance Status Toggle
- **File:** `src/app/dashboard/patients/InsuranceStatusToggle.tsx`
- **Buttons:** Tri-state toggle (verified / unverified / pending)
  - Three clickable states controlled by onChange callback

---

## SCHEDULE

### Schedule Page
- **File:** `src/app/dashboard/schedule/page.tsx` — Server component
- **Client Component:** `src/app/dashboard/schedule/ScheduleViewClient.tsx:1` (use client)

**Interactive Elements:**
- **Navigation:**
  - Line 12: `<ChevronLeft>`, `<ChevronRight>` → Calendar date navigation (onClick handlers)
  - Line 24: `<LayoutGrid>`, `<LayoutList>` → View mode toggle buttons

- **Buttons:**
  - Quick Add Appointment modal toggle
  - Status transition buttons per appointment (SCHEDULED → WAITING → IN_ROOM → COMPLETED)
  - Delete appointment (soft via CANCELLED status)

- **Modals:**
  - Line 36: `<QuickAddModal>` — Add appointment with patient select
    - Form: `quickAddAppointmentAction(formData)`
    - Submit button creates appointment

- **Server Actions:**
  - `generateAIPrepNoteAction(appointmentId, patientId)` — AI prep note from recent notes
  - `updateAppointmentStatusAction(appointmentId, newStatus)` — Status transitions
  - `deleteAppointmentAction(appointmentId)` — Soft delete

### QuickAddModal
- **File:** `src/app/dashboard/schedule/QuickAddModal.tsx` (use client)
- **Form:** Submit creates appointment via `quickAddAppointmentAction`
- **Fields:** Patient select, date/time, visit type, notes

---

## PATIENT DETAIL PAGE

### Patient Detail
- **File:** `src/app/dashboard/patients/[id]/page.tsx` — Server component
- **Client Component:** `src/app/dashboard/patients/[id]/PatientDetailClient.tsx:1` (use client) — 81K file

**Key Interactive Elements:**
- **Back Navigation:** `<ArrowLeft>` → `/dashboard/patients`

- **Modals:**
  - Edit Patient (EditPatientModal)
  - Schedule Visit (ScheduleVisitModal)
  - Document Generator (DocumentGeneratorModal)
  - Upload Patient Files (PatientFileUploadModal)

- **Note Management Buttons:**
  - Create note from template
  - Edit note manually
  - Generate final report (AI-synthesized)
  - Delete document
  - Upload custom procedure files

- **Clinical Safety Panel:**
  - Add allergy
  - Mark "no known allergies"
  - Add medication
  - Edit/delete allergies and medications

- **Server Actions (all in `/app/dashboard/patients/actions.ts`):**
  - `archivePatientAction(patientId)`
  - `createNoteFromTemplateAction(patientId, templateKey)`
  - `updateNoteManuallyAction(noteId, content)`
  - `uploadCustomProcedureAction(patientId, title, content)`
  - `generateFinalReportAction(patientId, noteIds[])`
  - `deleteDocumentAction(noteId)`

### Clinical Safety Panel
- **File:** `src/app/dashboard/patients/[id]/ClinicalSafetyPanel.tsx` (use client)
- **Toggle:** Expand/collapse allergy and medication sections
- **Add Buttons:** Allergy / Medication add modals
- **Delete Buttons:** Per allergy / medication

### Document Generator Modal
- **File:** `src/app/dashboard/patients/[id]/DocumentGeneratorModal.tsx` (use client)
- **Form Selectors:** Procedure type, template selection
- **Generate Button:** Triggers `createNoteFromTemplateAction`

### Schedule Visit Modal
- **File:** `src/app/dashboard/patients/[id]/ScheduleVisitModal.tsx` (use client)
- **Form:** Date/time/visit type selection
- **Submit:** Creates appointment via `quickAddAppointmentAction`

### Global AI Assistant
- **File:** `src/app/dashboard/patients/[id]/GlobalAIAssistant.tsx` (use client)
- **Floating Button:** Opens chat widget
- **Chat Input:** onChange handlers for user message composition
- **Send Button:** Submits to `/api/assistant-tool`

### Patient File Upload Modal
- **File:** `src/app/dashboard/patients/[id]/PatientFileUploadModal.tsx` (use client)
- **File Input:** Drag-drop or file picker
- **Upload Button:** POST multipart to `/api/patients/upload` (implied)

---

## SETTINGS

### Settings Page
- **File:** `src/app/dashboard/settings/page.tsx` — Server component wrapper
- **Client Component:** `src/app/dashboard/settings/SettingsClient.tsx` (use client)

**Forms & Handlers:**
- **Profile Update Form:** `onSubmit={(e) => { ... updateProfile(formData) }}`
  - Line 19: Name input onChange
  - Submit button

- **Password Change Form:** `onSubmit={(e) => { ... updatePassword(formData) }}`
  - Current password input
  - New password input
  - Confirm password input
  - Submit button (disabled during submission)

**Server Actions:**
- `updateProfile(formData)` — Update user display name
- `updatePassword(formData)` — Change password (validates policy, compares current)

---

## SYSTEM ADMIN

### System Admin Home
- **File:** `src/app/system-admin/page.tsx` — Server component
- **Client Component:** `src/app/system-admin/AdminUsersTableClient.tsx` (use client)

**Table Interactions:**
- **Kebab Menus:** Per user row
  - Edit User Modal
  - Reset Password Modal
  - View Sessions Modal
  - Deactivate/Activate User button
  - Delete User button
  - Kill All Sessions button

### Admin Users Table
- **File:** `src/app/system-admin/AdminUsersTableClient.tsx` (use client)
- **Buttons:**
  - Line ~: "Add User" CTA → opens AddUserModal
  - Per-row kebab menus with: Edit, Reset PW, Sessions, Deactivate/Activate, Delete, Kill Sessions

- **Server Actions:**
  - `deactivateUserAction(userId)`
  - `activateUserAction(userId)`
  - `killAllSessionsAction(userId)`
  - `deleteUserAction(userId)` — Hard delete
  - `resetUserPasswordAction(userId)` — Generate temp password
  - `viewUserSessionsAction(userId)` — Fetch session history

### Add User Modal
- **File:** `src/app/system-admin/AddUserModal.tsx` (use client)
- **Form:** Email, role select, name input
- **Submit:** `createUserAction(payload)` — Creates user with temp password

### Edit User Modal
- **File:** `src/app/system-admin/EditUserModal.tsx` (use client)
- **Form:** Email (read-only), role select, name, isActive toggle
- **Submit:** `updateUserAction(userId, payload)`

### Reset Password Modal
- **File:** `src/app/system-admin/ResetPasswordModal.tsx` (use client)
- **Button:** Generate new temp password → `resetUserPasswordAction(userId)`
- **Display:** Shows generated password for copy

### User Sessions Modal
- **File:** `src/app/system-admin/UserSessionsModal.tsx` (use client)
- **Display:** Table of user sessions (read-only, for audit)
- **Action:** Kill all sessions button

### Metrics Dashboard
- **File:** `src/app/system-admin/metrics/page.tsx` (use client)
- **Visualizations:** Charts (read-only or filter controls)

### Admin Sidebar
- **File:** `src/components/system-admin/AdminSidebar.tsx` (use client)
- **Nav Links:** Users, Metrics, Audit Logs
- **Back to Clinician:** Link to `/dashboard`

---

## AUDIT & COMPLIANCE

### Audit Logs (Dashboard)
- **File:** `src/app/dashboard/audit/page.tsx` — Server component
- **Client Component:** `src/app/dashboard/audit/AuditLogTable.tsx` (use client)
- **Display:** Read-only audit table (filters for user's own actions)

### Audit Logs (Admin)
- **File:** `src/app/system-admin/audit/page.tsx` — Server component
- **Display:** Read-only audit table across all users (admin-only view)

---

## SERVER ACTIONS (All 'use server')

### Patient Actions
- **File:** `src/app/dashboard/patients/actions.ts`
  - `createPatientAction(payload)` — Insert patient + audit log
  - `updatePatientAction(patientId, payload)` — Update + audit log
  - `archivePatientAction(patientId)` — Soft delete + audit
  - `getNextChartIdAction()` — Advisory chart ID generator
  - `listPracticeDoctorsAction()` — Fetch doctor options
  - `createNoteFromTemplateAction(patientId, templateKey)` — Template → note
  - `updateNoteManuallyAction(noteId, content)` — Edit note content
  - `uploadCustomProcedureAction(patientId, title, content)` — Custom template
  - `generateFinalReportAction(patientId, noteIds)` — AI summary
  - `deleteDocumentAction(noteId)` — Soft delete note

### Schedule Actions
- **File:** `src/app/dashboard/schedule/actions.ts`
  - `generateAIPrepNoteAction(appointmentId, patientId)` — GPT-4o-mini summary
  - `quickAddAppointmentAction(formData)` — Create appointment
  - `updateAppointmentStatusAction(appointmentId, newStatus)` — Status transition
  - `deleteAppointmentAction(appointmentId)` — Soft delete (CANCELLED)

### Settings Actions
- **File:** `src/app/dashboard/settings/actions.ts`
  - `updateProfile(formData)` — Update user name
  - `updatePassword(formData)` — Change password

### System Admin Actions
- **File:** `src/app/system-admin/actions.ts`
  - `deactivateUserAction(userId)` — Soft deactivate
  - `activateUserAction(userId)` — Reactivate
  - `killAllSessionsAction(userId)` — Expire all sessions
  - `deleteUserAction(userId)` — Hard delete
  - `createUserAction(payload)` — Provision new user
  - `updateUserAction(userId, payload)` — Modify user
  - `resetUserPasswordAction(userId)` — Generate temp password
  - `viewUserSessionsAction(userId)` — Fetch sessions (audit)

---

## API ROUTES (All `/api/**/route.ts`)

### Health Check
- **File:** `src/app/api/health/route.ts`
- **Method:** GET
- **Response:** `{ status, uptime_seconds, checks: { postgres }, version }`
- **Purpose:** Uptime monitoring, docker healthcheck

### Auth
- **File:** `src/app/api/auth/[...nextauth]/route.ts`
- **Methods:** POST (credential verification), GET (callback)
- **Purpose:** NextAuth v5 credential flow

### Transcribe (Whisper)
- **File:** `src/app/api/transcribe/route.ts`
- **Method:** POST
- **Body:** Audio blob (webm), session-scoped
- **Rate Limit:** Per-user (RATE_LIMITS.transcribe)
- **Returns:** `{ text: string }` or error
- **Purpose:** Voice→text for note generation and voice fill

### TTS (Text-to-Speech)
- **File:** `src/app/api/tts/route.ts`
- **Method:** POST
- **Body:** `{ text: string }`
- **Returns:** Audio stream (mp3)
- **Purpose:** Read notes aloud

### Patient Voice Extract
- **File:** `src/app/api/patients/extract-from-voice/route.ts`
- **Method:** POST
- **Body:** FormData with audio blob + currentFields (JSON) + doctors (JSON)
- **Returns:** `{ ok, transcript, fields: ExtractedFields }` or error
- **Purpose:** Intake form voice fill (GPT-4o-mini multimodal)

### Document Editor (Save)
- **File:** `src/app/api/doc-editor/save/route.ts`
- **Method:** POST
- **Body:** Note content (rich text / markdown)
- **Purpose:** Persist editor changes

### Document Editor (Fetch)
- **File:** `src/app/api/doc-editor/route.ts`
- **Method:** GET
- **Returns:** Template / saved note content
- **Purpose:** Load editor state

### Assistant Tool
- **File:** `src/app/api/assistant-tool/route.ts`
- **Method:** POST
- **Body:** User query + context (patient, notes)
- **Returns:** AI response (streaming or buffered)
- **Purpose:** Global AI assistant in patient detail page

### Realtime Session (Create)
- **File:** `src/app/api/realtime/session/route.ts`
- **Method:** POST
- **Body:** (empty or minimal)
- **Returns:** `{ clientSecret, sessionId }`
- **Purpose:** OpenAI Realtime API session token

### Realtime Session (End)
- **File:** `src/app/api/realtime/session/end/route.ts`
- **Method:** POST
- **Body:** `{ sessionId }`
- **Purpose:** Cleanup realtime session

### Realtime Refresh Context
- **File:** `src/app/api/realtime/refresh-context/route.ts`
- **Method:** POST
- **Body:** `{ sessionId, patientId }`
- **Purpose:** Update realtime agent's system context (patient context refresh)

---

## HELPER COMPONENTS & UTILITIES

### LogoutButton
- **File:** `src/components/LogoutButton.tsx`
- **Props:** `className?`, `iconOnly?`, `ariaLabel?`
- **Handler:** `onClick={handleLogout}` → `signOut({ callbackUrl: '/login' })`
- **States:** Loading spinner during sign-out

### Field Wrapper (AddPatientModal)
- **File:** `src/app/dashboard/patients/AddPatientModal.tsx:1006`
- **Component:** Wraps label + input + hint/error text
- **No interactive handlers** (children manage state)

---

## LANDING PAGE COMPONENTS (Read-Only / Animation-Only)

### Features
- **File:** `src/components/landing/Features.tsx`
- **Content:** Static card grid (no buttons or links with handlers)

### How It Works
- **File:** `src/components/landing/HowItWorks.tsx`
- **Content:** Step cards + animations (no interactive elements)

### Pricing
- **File:** `src/components/landing/Pricing.tsx`
- **Content:** Plan cards (likely includes CTA links to /register or /login)

### Testimonials
- **File:** `src/components/landing/Testimonials.tsx`
- **Content:** Testimonial slider (may have prev/next buttons)

### Footer
- **File:** `src/components/landing/Footer.tsx`
- **Content:** Links to /about, /pricing, /contact, social links, legal

---

## SUMMARY STATISTICS

| Category | Count |
|----------|-------|
| Buttons (onClick) | ~80+ |
| Links (href) | ~50+ |
| Forms (onSubmit) | ~15 |
| onChange Handlers | ~150+ (in form fields) |
| Server Actions | ~25 |
| API Routes | ~11 |
| Modals | ~8 |
| Input Fields (text/email/number/tel) | ~100+ |
| Select Dropdowns | ~20+ |
| Toggles / Chips | ~20+ |

**Total Interactive Elements:** 500+

---

**End of Inventory**
