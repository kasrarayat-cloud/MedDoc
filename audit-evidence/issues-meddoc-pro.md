# MedDoc Pro Interactive Element Issues & Flags

**Compiled:** 2026-04-24  
**Scope:** `/opt/meddoc-pro/apps/meddoc-pro/src/`  
**Flagged Issues:** 8 total

---

## CRITICAL ISSUES

### 1. Watch Demo Button — No Handler
- **File:** `src/components/landing/Hero.tsx:141`
- **Element:** `<button className="group inline-flex items-center gap-2...">Watch Demo</button>`
- **Issue:** Button with text "Watch Demo" has no `onClick` handler attached
- **Context:**
  ```jsx
  <button className="group inline-flex items-center gap-2 rounded-xl border border-slate-700 bg-slate-900/80 backdrop-blur-sm px-8 py-3.5 text-base font-semibold text-slate-300 transition-all duration-300 hover:border-blue-500/50 hover:text-white hover:shadow-[0_0_15px_rgba(59,130,246,0.15)]">
    <Play className="h-4 w-4" />
    Watch Demo
  </button>
  ```
- **Risk:** Button visually interactive but non-functional. Users may click expecting demo video to play.
- **Recommendation:** Either attach `onClick` handler linking to demo video, or convert to disabled state with `aria-disabled="true"` and clarify in documentation.

---

### 2. Forgot Password Link — Placeholder href="#"
- **File:** `src/app/login/page.tsx:170–174`
- **Element:** `<Link href="#" className="...">Forgot?</Link>`
- **Issue:** Password reset link points to `#` (no route defined)
- **Context:**
  ```jsx
  <Link
    href="#"
    className="text-xs font-medium text-blue-400 transition-colors hover:text-blue-300"
  >
    Forgot?
  </Link>
  ```
- **Risk:** User clicks "Forgot?" expecting password reset flow; page does not navigate or show error.
- **Recommendation:** Either implement password reset route (`/password-reset` or `/forgot-password`) or hide the link until feature is ready.

---

### 3. Empty More Filters Button
- **File:** `src/app/dashboard/patients/PatientsListClient.tsx:297–300`
- **Element:** `<button className="px-3 py-2...">More</button>` with Filter icon
- **Issue:** Button has no `onClick` handler; no filter modal or dropdown appears when clicked
- **Context:**
  ```jsx
  <button className="px-3 py-2 rounded-lg border border-white/10 hover:border-white/20 text-slate-300 hover:text-white text-xs font-medium flex items-center gap-1.5 transition-colors cursor-pointer">
    <Filter className="w-3.5 h-3.5" />
    More
  </button>
  ```
- **Risk:** Placeholder UI without implementation; user clicks expecting additional filter options.
- **Recommendation:** Implement advanced filter modal (tags, date range, notes count) or mark as future feature.

---

## WARNING ISSUES

### 4. Toast Notification Auto-Dismiss
- **File:** `src/app/dashboard/patients/PatientsListClient.tsx:75–79`
- **Element:** Toast message (archive success/error feedback)
- **Issue:** Toast automatically dismisses after 3 seconds; user may miss message if distracted
- **Context:**
  ```jsx
  useEffect(() => {
    if (!toast) return;
    const t = setTimeout(() => setToast(null), 3000);
    return () => clearTimeout(t);
  }, [toast]);
  ```
- **Current Behavior:** Archive confirmation modal shown, then toast appears for 3s on list refresh
- **Recommendation:** Consider extending timeout to 5–6 seconds or allowing user to dismiss toast manually before auto-timeout.

---

### 5. Undefined Variable Reference (Potential)
- **File:** `src/app/dashboard/patients/AddPatientModal.tsx:599–604`
- **Element:** Undo button in voice fill banner
- **Issue:** `voiceNote.previousForm` dereferenced without null check on outer voiceNote
- **Context:**
  ```jsx
  {voiceNote && !voiceError && !success && (
    <div ...>
      ...
      {voiceNote.filledCount > 0 && (
        <button
          type="button"
          onClick={() => {
            if (voiceNote.previousForm) {
              setForm(voiceNote.previousForm);
            }
            setVoiceNote(null);
          }}
          ...
        >
          Undo
        </button>
      )}
    </div>
  )}
  ```
- **Status:** Mitigated by guard `if (voiceNote.previousForm)` inside onClick; no crash risk
- **Recommendation:** Comment clarifies expected structure; no action needed.

---

### 6. Race Condition: Voice Fill + Submit Overlap
- **File:** `src/app/dashboard/patients/AddPatientModal.tsx`
- **Issue:** User can submit form while voice extraction is in flight (`voiceBusy = true`)
- **Context:**
  - Line 503: Mic button disabled when `isPending` (form submit) OR `voiceBusy`
  - Line 950: Submit button disabled when `isPending` OR `success`, but NOT when `voiceBusy`
- **Risk:** User sees "Voice" button disabled but Submit is active; could submit incomplete voice fill before extraction finishes
- **Recommendation:** Also disable submit button when `voiceBusy` is true:
  ```jsx
  <button
    type="submit"
    disabled={isPending || success || voiceBusy}  // Add voiceBusy here
    ...
  >
  ```

---

### 7. Kebab Menu Close Handler — Event Propagation
- **File:** `src/app/dashboard/patients/PatientsListClient.tsx:472–479`
- **Element:** Kebab menu overlay div
- **Issue:** Click handler stops propagation but menu is inside a clickable Link; could cause unexpected behavior
- **Context:**
  ```jsx
  {openKebabId === patient.id && (
    <div
      ref={kebabRef}
      onClick={(e) => {
        e.preventDefault();  // preventDefault on <div> has no effect
        e.stopPropagation();
      }}
      className="absolute top-full right-0 mt-1 z-20 min-w-[180px] ..."
    >
  ```
- **Status:** Functionally works (stopPropagation prevents Link click) but `preventDefault` on div is unnecessary
- **Recommendation:** Remove `e.preventDefault()` for clarity; only `stopPropagation()` is needed.

---

### 8. Modal Backdrop Click Closes Without Confirmation
- **File:** `src/app/dashboard/patients/AddPatientModal.tsx:462–467`
- **Element:** Modal backdrop (motion.div)
- **Issue:** Clicking outside modal closes it without unsaved-changes check
- **Context:**
  ```jsx
  <motion.div
    initial={{ opacity: 0 }}
    animate={{ opacity: 1 }}
    exit={{ opacity: 0 }}
    onClick={onClose}
    className="fixed inset-0 z-[100] bg-black/70 backdrop-blur-sm"
  />
  ```
- **Current Behavior:** User fills form, clicks backdrop, modal closes without confirmation
- **Risk:** User loses data if form has unsaved changes
- **Recommendation:** Either:
  - Show confirmation dialog if form is dirty before allowing close, OR
  - Disable backdrop click when form has changes (set `onClick={form.isDirty ? undefined : onClose}`)

---

## MISSING HANDLERS (Low Priority)

### 9. Navigation: Unused Import
- **File:** `src/components/dashboard/Sidebar.tsx:15`
- **Import:** `usePathname` from next/navigation
- **Usage:** Line 83: `const pathname = usePathname()`
- **Context:** Used to determine active nav item for styling; not an issue, just noting for completeness
- **Status:** Correctly used; no action needed

---

## SUMMARY

| Severity | Category | Count | Examples |
|----------|----------|-------|----------|
| Critical | Unimplemented Button/Link | 2 | Watch Demo, Forgot Password |
| Critical | Empty Handler Button | 1 | More Filters |
| Warning | UI/UX Concern | 3 | Toast timeout, Submit disabled, Modal backdrop |
| Warning | Code Quality | 2 | Event propagation, Race condition |

**Total Flagged:** 8 issues  
**Critical:** 3  
**Warning:** 5  
**No Action Required:** 2

---

**Recommendations Priority:**
1. Implement password reset route or remove link
2. Add onClick to Watch Demo or disable it
3. Implement advanced filters modal or remove button
4. Disable submit button when `voiceBusy = true`
5. Confirm unsaved changes before modal close on backdrop click

---

**End of Issues Report**
