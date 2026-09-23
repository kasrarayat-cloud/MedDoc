# QuillMD pilot — doctor guide (fictional cases only)

This preview is for testing with **fictional patients and notes only**. It is not approved for real
patient information. You confirm this each time you add a patient, a form, a document or a
recording; nothing in the product can detect real data for you.

**Preview address: https://app.quillmd.com:9443/**

Sessions end after 30 minutes without activity, both the preview gate and your account, and
the preview gate also ends 2 hours after you sign in to it, however active you are. Save your
notes every few minutes; an unsaved page is lost when a session ends.

## 1. Sign in

1. Open **https://app.quillmd.com:9443/**. You first see **Private preview**: enter the shared
   preview access details the pilot coordinator gave you.
2. Then sign in with **your own account** (email and password). If you do not have one, choose
   **Create an account**, fill in your name, email and password, and tick *I will use synthetic
   test data only*. Open the verification link in the email you receive, choose **Confirm and
   continue**, then sign in. If the email does not arrive, tell the pilot coordinator; do not
   create a second account.
3. A new account opens on an empty **Workspace**, with no forms or patients yet.

## 2. Add a fictional patient

Sidebar **Patients** → choose your department (a new account has one, *Personal practice*, already
selected) → enter a fictional name and reference (for example *Synthetic Patient A*, *SYN-001*) →
tick *This is a synthetic test patient* → **Create patient**. A document cannot be
created without a patient.

## 3. Add your form

Sidebar **Workspace** → **Upload form ＋** (on an empty workspace: **Upload your first form**).
The upload page lists the **Supported forms**; read it before choosing a file. Enter a name,
choose your department, choose the file, tick *This is a blank form with no patient data*, then
**Upload and inspect form**. The form page shows every answer field it found.

- **The qualified WM IOV form:** upload the blank WM IOV file provided for this pilot **exactly as
  you received it**. Do not open and save it in Word first: it is recognised by its fingerprint,
  and a re-saved copy is refused. Once recognised, the form page says *This qualified Word form
  uses fixed question labels…* and has a section **Prewritten statements to include in your
  notes (11)**.
- **Your own form:** it must use one of the supported layouts in the table below. Anything else
  is refused at upload, and the message says why.

## 4. Create a document

On the form page choose **Use this form →** (or **Use form →** beside it in the Form library).
The form is already selected. Choose the patient and the **date of service** (it cannot be
changed later). Then either type your notes, or leave the notes empty to record voice on the
next page. Tick *These are synthetic clinical notes* → **Create document**.

## 5. Notes or voice

The document page starts with **1. Type or dictate your notes**.

- **Typing:** edit the **Source notes** box, then **Save source notes**.
- **Voice:** choose **Use voice**, then **Record voice** (up to 5 minutes) and **Stop**, or
  upload a recording (.wav, .webm, .mp3 or .m4a, up to 15 MB). Listen to it, tick the consent
  box, then **Transcribe recording**. Send it within 30 minutes of opening the page and before your
  preview access ends; after that the recording is not kept. Refresh until **Review the returned
  transcript** appears. The transcript has no punctuation and writes numbers as words, so
  correct it there. Choose **Append** or **Replace**, tick the review box, then **Save reviewed
  transcript to notes**. Nothing reaches your notes without this step.

## 6. Generate and review

**2. Generate supported answers** shows the maximum charge, then queues the request. Refresh the
page until the answer draft appears. For every question, read the answer and its **source
evidence**, then make one decision:

- keep or correct the answer in its box;
- tick **Accept this suggestion as my answer**, where a suggestion is offered;
- tick **Leave blank — reviewed** when no answer belongs there, and leave the answer box empty.
  This is not offered on signature questions or on the WM IOV form.

Then tick **I reviewed this answer…** and **Save answers and review decisions**. A review tick
is always your own. On ordinary forms, if a colleague reviewed an answer earlier, the page says
so and leaves the box for you to tick; saving without ticking it removes their review.

**Signature questions:** type your account name exactly as the page shows it, or leave it empty.
It is never filled from the notes, and another person's name cannot be signed. A fillable PDF
holds plain ASCII only, so if your account name has accented letters, leave a PDF signature empty.

**On the WM IOV form** each answer also has a **Source quotation** box: paste the complete notes
line for that answer, or leave it empty when nothing is documented. Dropdowns offer *No answer
documented — preserve unselected field*; empty measurements stay blank. Below the answers come
the 14 prewritten statements and signing items. Each needs an approved wording and a review tick,
and each of the 11 clinical statements also needs a source quotation: its own notes line. If
finalizing is refused, scroll for the red lines under each answer and statement: they say what
is missing. When chosen statement wordings and the answers disagree, the notice at the top of
the page lists each conflict: the statement, its chosen wording, the answers it clashes with and
why. The same line appears under that statement and under each answer involved. Examples: a
side's reflux answer *reflux positive.* with any wording other than that side's positive reflux
statement; a reflux time over 500 ms with a *No saphenous reflux* wording; measurements or
locations on a side whose wording says *not assessed*; the indication *Previous vein treatment*
while both legs' statements say there was none.

## 7. Finalize and download

**Finalize document**: tick the confirmation, then finalize. If it is refused on an ordinary form,
the message names the questions that still need your decision; on the WM IOV form, look for the
red lines on the page. Then choose **Export original format ↓**: you get
your own form, in its original format, with the reviewed answers filled in. **Billing & usage**
lists every charge; choose a charge's service name to see how it was calculated.

## How to write notes — what works, honestly

| form | labelled lines (`Question label: answer`) | ordinary narrative sentences |
|---|---|---|
| **Lines with a label and an underlined Tab** | most reliable | can be matched when every sentence is complete: a verb QuillMD recognises (*is*, *are*, *was*, *were*, *has*, *have*, *had*, *denies*, *reports*, *reported*, *showed*, *revealed*, *advanced*, *seen*, *collected*, *recommend*, *received*, *underwent*) and a final `.` `!` or `?`; *The patient has right calf pain.* works, *The patient complains of right calf pain.* does not; otherwise answers come back for your decision |
| **Question/answer tables, `{{Question}}` placeholders, multi-column or mixed forms, fillable PDFs** | most reliable | any line that is not a label with its answer (a label left empty counts) sends **every** answer back to you as a **conflict** to decide |
| **The WM IOV form** | **required** | **not supported**: narrative notes cannot be finalized on this form |

- Use each question's label exactly as the form page lists it, one fact per line. On Word forms
  that is the printed question; on a fillable PDF it is the field's tooltip or internal name,
  which can differ from the printed text (rename it under the form's field mapping if needed).
- On underlined-Tab forms, a heading line ending in a colon, a quotation, an extra line without
  final punctuation, or a word such as *if*, *would*, *could*, *might*, *these*, *those*, *above*,
  *below*, *following* or *listed* anywhere in the notes sends the generated answers back to you as
  conflicts to decide. On every other form, a line that is not a label with its answer does
  (a label left empty counts); separately, a heading, a sentence ending on a forward pointer or a
  correction makes the answers it governs a decision on every form (below).
- **A heading governs what comes after it.** A line ending in a colon (`Review of systems:
  negative for the following:`, `Family hx: the following conditions:`; markup or a closing mark
  after the colon still counts: `**Mother:**`, `(Mother:)`, `Signed by: ____`), even when it is itself
  one of the form's questions, makes every answer written after it, to the end of the notes, a
  decision for you: it is never filled in and never offered for one click. What was read is shown
  beside it, with the lines that govern it (*Written under* above it, *Followed by* below it; up to
  15 lines, nearest and denials first, and the rest counted: read the full note then; a line that
  is the answer's own is shown as *In the same line*; when the same words also appear elsewhere in
  the notes, the page says where, because a line may govern them there). A question left
  empty mid-note (`Allergies:`) counts, because it may be a heading (`Pertinent negatives:`). A
  heading at the very end, or one that contains *above*, *these*, *those* or *listed* (`… all of
  the above denied:`, and also `Discharge medications as listed below:`), governs the lines before
  it as well; at the end of a paragraph it reaches back from its own sentence. A bare label at the
  end does not: one with no other colon in what follows a form question's label (a clock time does
  not count) and no denial, family history, hypothetical or pointer word (`Signed by:`,
  `**Signed by:**`, `Signed by: ______`, `Electronically signed on 09/21/2026 at 10:42 by:`, an
  empty `Allergies:`). A dash after a colon is an answer, not a heading (`Allergies: -`, `Nose: —`
  mean none), and so is a value in angle brackets (`Allergies: <penicillin>`, `PSA: <0.1>`); only a
  real HTML tag after the colon (`<br>`, `</b>`, Word's `<o:p></o:p>`), a footnote mark (`¹`), `\`
  or `~~` is markup; a blank or filled clock (`Time out: __:__`, `__ : __`) is not a heading, but a
  number before closing markup is (`_Mother, age 72:_`). A sign-off row whose every field is a
  signature, date, time or signer label (`Signature: ____ Date: ____`, `Signed by: Dr A  Date:`,
  `Surgeon: ____ Signature: ____`) is a bare label; a row with any other field is not. A bare signature or date row after a closing
  heading (`Review of systems: negative for:` then `Signed by: ____`) does not stop that heading
  closing the notes. A sentence break inside brackets does not end a heading's or a pointer's
  sentence (`… all of the above were denied (per intake form. Reviewed today):`), and markup around a
  sentence's period does not hide where it ends (`*Negative for the following.* Reviewed today.`).
  `Dictated by: Dr A, diagnosis:` (another colon that is not a sign-off field, unless *Dictated by*
  is one of the form's questions) and `Dictated but not read:` (*not*) are headings. A closing line with words the vocabulary does not know
  (`Ruled out:`) is read as bare: write those as answers.
- **A sentence that ends by pointing forward works the same way, whatever its words.** A sentence
  that **ends** on *following*, *below*, *as follows* or *the following* and one more word (`…
  patient denies the following.`, `Her mother had the following.`, `… is as follows.`, `… the
  following symptom(s).`, `… the following co-morbidities.`), including after an aside of any
  length (`… the following (reviewed today).`) or before a colon and a list on the same line (`…
  as follows: polyps.`), makes every answer after it a decision, in the same paragraph and on later
  lines, whatever non-word characters trail it to the end of its line (`… the following.*`, `…
  the following.<br>`). A period ends such a sentence only before a new sentence (`… the following
  wk. at the GP` does not). A form question's own label is not read as a pointer (`Patient was
  informed of the following risks:` is a question, and its answer is an answer). This
  includes exception lists (`… negative except as noted below.`: type the positives below it
  yourself), references (`see the instructions below`), anatomy (`competent below.`) and times
  (`Do not drive until the following day.`). The same words inside a sentence (`No reflux below
  the knee.`, `…the following morning; able to bear weight.`, `No driving for the following 24
  hours.`, `fixes and follows`) do not make later answers a decision (on underlined-Tab forms some
  of these words still send answers back, above). ⚠️ **Only these words are read.** Two words or
  more after *the following* (`… the following medical problems.`), *that follow*, *preceding*
  and *aforementioned* are not: end such a line with a colon, which is read whatever its words. A
  sentence that refers back without a colon (`… negative except as noted above.`) is not read.
- **A correction governs what came before it.** The word *correction* where a line, an answer or
  a sentence starts — after any bullet, bracket, quote or list marker (`● Correction: …`, `1-
  Correction: …`, `#2 Correction: …`, `(Correction: …)`, `a) Correction: …`, `Addendum: Correction:
  …`), or after one word before a colon, comma or dash (`Transcription correction: …`, `Physician's
  correction: …`) — makes every answer before it a decision, in the same paragraph too, whatever
  follows it (`Correction to my dictation, …`) — except a treatment or a target: `Correction of …`,
  `Correction scale`, `factor`, `dose` or `insulin`, `Correction (sliding scale)`, `Correction to`
  a number, `Correction-scale`, `Correction/…`, `Corrections officer` or `facility`. So
  `Corrections (state prison officer)`, `Correction to no more than 8 mmol/L`, an insulin order line
  `Correction: 2 units per 50 mg/dL` and `Correction: Bazett` are read as corrections too, and the
  answers above them need your decision. Only the word *correction* is read (`Erratum:` and
  `Corrected:` are not), and not when *correction* is part of a form question's own label
  (`Correction achieved: 10 degrees`, `Refractive correction:`). After a label, a number before the
  word is a value, not a list marker (`Glucose: 312 correction given` is not a correction), unless
  it is a list number (`Comments: 1. Correction: …`) or the word is followed by a colon, comma or
  dash (`Glucose: 312 correction: 4 units` is read as a correction, like `Transcription
  correction:`). One exception: a correction that opens the whole answer to a
  question already answered above it (`Pain score: Correction: three out of ten`) corrects that
  question only, which already needs your decision because it has two answers — on an underlined-Tab
  form anywhere in a paragraph, on every other form only at the start of its line. ⚠️ So a
  correction of another question written under a question already answered (`Comments:
  Correction: the allergy is sulfa`) is NOT applied to that other answer: write it under the
  question it corrects. A note line that starts with the word *Correction* or *Corrections*, after
  any bullet or list number, also withholds every suggestion (below) — even a treatment line
  (`Correction scale:`, `Correction insulin:`, `Correction of …`) or a line naming a form question
  (`Correction achieved: 10 degrees`) — and so does a line that opens with a correction such as
  `Transcription correction:`.
- **Write each denial as its own answer** (`Symptoms: no chest pain`) when you can: nothing
  governs it, so it comes back ready.
- **On the WM IOV form, labelled lines never govern**: every label there names its own side, vein
  and measure, so a heading, pointer or correction written inside a labelled answer changes no
  other answer. An unlabelled line (which already sends every answer back) is read in full: a
  heading, a sentence ending on a forward pointer or a correction there withholds the suggestions
  it governs.
- **A draft from before this release** is shown by the same rule: an answer it filled in from a
  governed line is shown empty, with its candidate and the lines that govern it, and an accepted
  suggestion there is shown the same way with a warning. Neither can be finalized as it is. Type
  your own answer (its words may be the same) or choose "Leave blank — reviewed"; saving with the
  box empty keeps the earlier acceptance. (On the WM IOV form, which has no "Leave blank —
  reviewed", such an acceptance is replaced by choosing or typing an answer; none exists in the
  pilot's drafts.) Edited on a page opened before this release, the answer keeps its candidate and
  the lines that govern it beside your text; cleared there, it stays held. An answer you typed on a
  governed line before this release keeps your text and is shown with those lines: check it against
  them. An answer the note withholds suggestions for (from either release), typed over and cleared,
  still needs "Leave blank — reviewed", as the page says. An answer such a draft
  could only store with the whole note as its source, cleared, needs "Leave blank — reviewed"
  whenever anything in the note may govern it or withholds suggestions (for example *if* in a plan).
- **An answer written under a governing line needs a decision.** If you type it and then clear it,
  choose "Leave blank — reviewed" before finalizing: an empty box there is not a decision. (Elsewhere,
  clearing an answer and ticking it reviewed leaves it empty, as before.) Invisible characters count
  as empty.
- **Read the whole note before accepting a suggestion.** Suggestions are never offered for an
  answer governed by a heading or a governing sentence (above). Otherwise they are withheld in
  five cases: a denial line that governs other lines, meaning a line containing *denied*, *denies*,
  *deny*, *absent*, *negative*, *negatives*, *no*, *not*, *without* or *never* that ends in a
  colon
  (`ROS: negative for the following:`), points at other lines with *following*, *these*,
  *those*, *above*, *below* or *listed* (`The patient denied each of the symptoms below.`), or
  has the denial word before its first colon (`Not seen: …`); the words *if*, *would*, *could*,
  *might*, *family history*, *hypothetical*, *imagine* or *suppose* anywhere in the notes; a
  line that starts with the word *Correction*, even for a treatment (`Correction scale:`), or opens
  with a correction such as `Transcription correction:`; a line break the page shows inline (pasted
  text can carry a Unicode line separator that looks like a space); or a quotation. A denial word next to one of those pointer words withholds every suggestion in the
  note even in an ordinary sentence (*no driving for the following 24 hours*); type those answers
  yourself. A denial written any other way (for example *Chest pain was denied.* on one line and
  *Symptoms: chest pain* on another) is not read as one: on underlined-Tab forms the opposite
  finding can come back as a ready answer already filled in, and on other forms as a suggestion
  that states the opposite of what you meant.
- **WM IOV only:** every non-empty answer must be the exact value under its exact label. A
  dropdown value must match one of the form's own options, and a measurement is the number, a
  space, then its unit (`3.2 mm`, `400 ms`; `3.2mm` and `3,2 mm` are refused). Each of the 11 prewritten statements must also be its own line: its
  label, a colon, then one approved wording from the form page. Some wordings need particular
  questions answered, or left unanswered; the form page says which for each wording. Saving
  changed notes clears the draft, so write the statement lines **before** generating.
- Answers come only from your notes; nothing is inferred from outside them.

## A fictional example

For a form whose questions are *Symptoms*, *Examination* and *Plan*, labelled notes:

```
Symptoms: intermittent right calf ache for three weeks, worse at the end of the day
Examination: mild right ankle swelling; no skin changes
Plan: duplex ultrasound of both legs; review in two weeks
```

The same facts as narrative, to compare what the form does with them:

```
Fictional patient with a right calf ache for three weeks, worse in the evening.
On examination there is mild right ankle swelling and no skin change.
Plan a duplex ultrasound of both legs and review in two weeks.
```

On the WM IOV form the notes are all labelled lines. The form page lists all 90 question labels
and the prewritten statements. An excerpt:

```
Clinical indication: leg pain: Leg pain
Prewritten statement: Right saphenous reflux finding: No saphenous reflux in right lower extremity.
Prewritten statement: Clinical correlation: Clinical correlation with the above findings is required.
```

## Supported forms

| kind | what works | notes |
|---|---|---|
| **Word (.docx)** | two-column question/answer tables, `{{Question}}` placeholders, multi-column question rows, mixed layouts, and lines of a label plus an underlined Tab (an ordinary paragraph, not inside a table, nothing typed after the Tab) | typed underscores `____` are not answer fields; answers expand in place, so check every exported page |
| **Fillable PDF** | every field a visible plain text field with a fixed font size (not Auto), standard Helvetica font, no format scripts, not rotated, read-only, comb or rich-text; no links, attachments or other actions anywhere in the file | answers in plain ASCII only (no curly quotes or apostrophes, long dashes, °, µ, accented letters or no-break spaces) and must fit their box; a character outside ASCII is refused at finalize, naming the question and the character |
| **Qualified WM IOV form** | exactly **one** file, recognised by its fingerprint, with its dropdowns and prewritten statements | labelled notes required; its own *No answer documented* choice replaces *Leave blank — reviewed* |

**Refused at upload:** any other Word file with dropdowns, date pickers or other content controls;
text boxes, tracked changes, fields or macros; Word files with web or email links or linked
images, including in a letterhead, header or footer; PDFs with checkboxes, radio buttons,
dropdown, signature or button fields, or with links, attachments or actions; scanned or flat PDFs; password-protected or encrypted files and old
`.doc` files. A
form with dropdowns is **not** qualified because it resembles the WM IOV form. CPT coding is off
during the pilot.

## "Leave blank — reviewed"

It records that **you** decided no answer belongs to that question. Your name, the document
revision and the time are kept, together with the original conflict, any suggestion and the
evidence. It is different from an untouched empty answer (still shown as `missing`) and from
accepting a suggestion. The export keeps that answer area empty. To withdraw it, untick it, type
an answer, or accept the suggestion.

## Please do not

- enter real patient information, real names or real identifiers;
- send invitations from **Organization** during the pilot, because they send real email;
- open and re-save the WM IOV file before uploading it.

## Not yet checked by a person — please help

- **Microphone recording** has only been tested with synthetic audio. Nobody has yet dictated
  into a real microphone.
- **Word appearance** of exported documents has not been inspected in Microsoft Word for this
  release.

## Feedback checklist

Send the coordinator a note for each item: what you did, what you expected, and what happened.
Add a screenshot of anything fictional that looks wrong.

- [ ] Signing in: preview gate, account creation, verification email, sign-in
- [ ] Finding the upload page and understanding which forms are supported
- [ ] Uploading your form, or the WM IOV file; was it recognised?
- [ ] Adding a fictional patient and creating a document
- [ ] Typed labelled notes: did each answer land on the right question?
- [ ] Typed narrative notes: what happened, and was it clear what to do next?
- [ ] Voice: recording, playback before sending, transcript accuracy, correcting it, saving it
- [ ] Reviewing evidence, accepting a suggestion, "Leave blank — reviewed"
- [ ] WM IOV only: writing the prewritten statement lines, source quotations, statement review
- [ ] Finalizing: any refusal message you could not act on
- [ ] The exported document opened in Word or a PDF reader: layout, page breaks, anything missing
- [ ] Charges on Billing & usage: were they what you expected?
- [ ] Any wording that was confusing, and anything you looked for and could not find
