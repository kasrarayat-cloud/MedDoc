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

Sidebar **Patients** → enter a fictional name and reference (for example *Synthetic Patient A*,
*SYN-001*) → tick *This is a synthetic test patient* → **Create patient**. A document cannot be
created without a patient.

## 3. Add your form

Sidebar **Workspace** → **Upload form ＋** (on an empty workspace: **Upload your first form**).
The upload page lists the **Supported forms**; read it before choosing a file. Enter a name,
choose the file, tick *This is a blank form with no patient data*, then **Upload and inspect
form**. The form page shows every answer field it found.

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
  box, then **Transcribe recording**. Send it within 30 minutes of opening the page; after that
  the price expires and the recording is not kept. Refresh until **Review the returned
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
It is never filled from the notes, and another person's name cannot be signed.

**On the WM IOV form** each answer also has a **Source quotation** box: paste the complete notes
line for that answer, or leave it empty when nothing is documented. Dropdowns offer *No answer
documented — preserve unselected field*; empty measurements stay blank. Below the answers come
the 14 prewritten statements and signing items. Each needs an approved wording and a review tick,
and each of the 11 clinical statements also needs a source quotation: its own notes line. If
finalizing is refused, scroll for the red lines under each answer and statement: they say what
is missing.

## 7. Finalize and download

**Finalize document**: tick the confirmation, then finalize. If it is refused on an ordinary form,
the message names the questions that still need your decision; on the WM IOV form, look for the
red lines on the page. Then choose **Export original format ↓**: you get
your own form, in its original format, with the reviewed answers filled in. **Billing & usage**
lists every charge; choose a charge's service name to see how it was calculated.

## How to write notes — what works, honestly

| form | labelled lines (`Question label: answer`) | ordinary narrative sentences |
|---|---|---|
| **A label followed by an underlined Tab** | most reliable | can be matched to the right question; check each one |
| **Question/answer tables, `{{Question}}` placeholders, multi-column or mixed forms** | most reliable | any unlabelled line sends **every** answer back to you as a **conflict** to decide |
| **The WM IOV form** | **required** | **not supported**: narrative notes cannot be finalized on this form |

- Use the form's own question wording as the label, one fact per line.
- On every form, a heading line ending in a colon, a quotation, or a word such as *if*, *would*,
  *could*, *might*, *these*, *those*, *above*, *below*, *following* or *listed* in the notes can
  send the generated answers back to you as conflicts to decide.
- A suggestion is never offered for text under a denial, a hypothetical (*if*, *would*,
  *could*, *might*) or a quotation. You then type the answer yourself.
- **WM IOV only:** every non-empty answer must be the exact value under its exact label. A
  dropdown value must match one of the form's own options, and a measurement needs its unit
  (`3.2 mm`, `400 ms`). Each of the 11 prewritten statements must also be its own line: its
  label, a colon, then one approved wording from the form page. A *not documented* or *not
  assessed* wording requires the related questions to be left unanswered. Saving changed notes
  clears the draft, so write the statement lines **before** generating.
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
| **Word (.docx)** | two-column question/answer tables, a label followed by an underlined Tab, `{{Question}}` placeholders, multi-column question rows, mixed layouts | typed underscores `____` are not answer fields; answers expand in place, so check every exported page |
| **Fillable PDF** | every field a visible plain text field in the standard Helvetica font | basic characters only: no °, µ or accented letters |
| **Qualified WM IOV form** | exactly **one** file, recognised by its fingerprint, with its dropdowns and prewritten statements | labelled notes required; its own *No answer documented* choice replaces *Leave blank — reviewed* |

**Refused at upload:** any other Word file with dropdowns, date pickers or other content controls;
text boxes, tracked changes, fields or macros; PDFs with checkboxes, radio buttons or dropdown
fields; scanned or flat PDFs; password-protected or encrypted files and old `.doc` files. A
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
