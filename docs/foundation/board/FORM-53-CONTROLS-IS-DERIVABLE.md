# THE 53-CONTROL FORM IS GONE FROM DISK, AND IT IS DERIVABLE — the arithmetic that proves it

**Filed 2026-09-06 by the custom-file session, at the head of the owner's-form
lane.** Ruling #192's sequence step is *"transfer/certify the 53-control form"*.
**That file does not exist on this machine.** This note records what it was,
that it is reconstructible, and the measurement that proves the reconstruction
is the same document.

## THE FORM IS ABSENT — measured, with a probe that had to be fixed first

    find / -name "*.docx" -print0 | while IFS= read -r -d '' f; do
      n=$(unzip -p "$f" word/document.xml 2>/dev/null | grep -o '<w:sdtPr>' | wc -l)
      [ "$n" -gt 30 ] && printf '%s\t%s\n' "$n" "$f"
    done

**Exactly one hit: `35  /home/claude/r5-handoff/GI Consultation Note - fillable.docx`.**
Nothing on this box has more than 35 content controls. Not prod (4 compiled
versions at 35/35/35/80), not QA, not MinIO, not Trash.

⚠️ **AND THE FIRST RUN OF THAT PROBE RETURNED A FALSE ZERO, WHICH IS THE PART
WORTH KEEPING.** It was written `for f in $(find ...)`, which word-splits on
spaces — and the one file that mattered is named `GI Consultation Note -
fillable.docx`. The probe reported no form above 30 controls **while looking
straight at a 35-control form**, because `unzip` was being handed the token
`GI`. *A zero measures your pattern first*, and the pattern here was the shell's
word splitting. The null-delimited form above is the one that answers.

## IT DID EXIST — three independent records, none of them a file

| where | what it says |
|---|---|
| `note-template-docx/compiler.ts:344-346` | *"the regenerated consult form — **53 controls, 0 placeholders, 0 empty, SCAFFOLDED 53**"*, recorded as MEASURED ON BOTH REAL DOCUMENTS BEFORE THIS SHIPPED |
| ruling #192, line 15 | `w:showingPlcHdr` present **28/28** on WM IOV and **0/53** on the regenerated form |
| ruling #191, line 77 | *"53 controls as regenerated, all five additive proofs held"* |

The compiler comment is the strongest: it is source, it is dated by its commit,
and it states the partition reconciles to its total — which is what says there is
no unnamed bucket.

## THE DERIVATION — 35 + 18, and every number is read off the document

The regenerated form is the current one with eighteen spans of STATIC PROSE
wrapped in content controls. Read directly out of
`word/document.xml` of the 35-control form:

| # | source paragraph in the current form | becomes |
|---|---|---|
| 12 | *"The patient denies heartburn, odynophagia, dysphagia. The patient denies nausea or vomiting. The patient denies abdominal pain. The patient denies diarrhea or constipation…"* | **6** ROS clause controls — one per sentence, ruling #191(2) |
| 41–50 | General / HEENT / Neck / Lungs / CV / Abdomen / Extremity / Neurologic / Psychological / Rectal | **10** exam clause controls |
| 52 | *"Patient verbalized informed consent to proceed with the audio telephone/telehealth visit."* | **1** — the `omit` control, acceptance row 6 |
| 67 | *"A total time of \_\_\_\_\_\_ minutes was spent on today's encounter…"* | **1** — pairs with control #35 *"Total minutes spent with patient"*, ruling #191's *"one datum, two renders"* |
| — | the 35 controls already present | **35** |
| | | **= 53** |

**Every one of ruling #191's own numbers falls out of this and none was assumed:**
six ROS controls because the GI-ROS paragraph is six sentences; ten exam controls
because the exam block is ten lines; the telehealth line; the second time render.

⚠️ **PARAGRAPH 39 IS DELIBERATELY NOT ONE OF THEM.** *"A thorough 14-point review
of systems was performed and remarkable findings were documented in the HPI."*
sits under a second *Review of Systems* heading and is a different sentence from
the GI-ROS block. It stays static prose — and **the arithmetic is what pins
that**: including it gives 54, and the ruled total is 53.

## THE SCAFFOLD DETECTION WILL FIRE, AND THAT IS ALSO MEASURED

`isScaffolded` (`compiler.ts:348`) is `no showingPlcHdr && visible text`.

| document | controls | `showingPlcHdr` |
|---|---|---|
| `WM IOV Template.docx` | 28 | **28** |
| the GI consultation form | 35 | **0** |

Measured here, and it reproduces ruling #192's population fact exactly: the
placeholder flag is a property of **who authored the document**, not of the
format. The GI form declares none, so a form regenerated from it declares none —
which is why the compiler comment records **0 placeholders** and **SCAFFOLDED 53**
rather than some smaller number.

## WHAT THIS DOES NOT SETTLE

- **The exact clause boundaries of paragraph 12** are a reading of the owner's
  prose. Six sentences is ruled (#191); which words fall in which control is a
  reconstruction, and a re-upload by the owner would settle it authoritatively.
- **`scaffoldText` byte-identity.** `kept_default` is proved by byte-identity
  (#191(4)), so a reconstruction that differs from the lost original by a space
  is a different document. The `structureSha256` of the rebuilt form will NOT
  match whatever the lost one had — nothing certified is orphaned by that,
  because nothing was ever certified against it, but no claim of byte-identity
  with the original may be made.

**So the reconstruction is offered as a reconstruction.** It is not the owner's
file recovered; it is his file rebuilt to a ruled specification, and the
difference is stated rather than papered over.
