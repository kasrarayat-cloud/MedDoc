# Harness repair 3 (owner directive 2026-11-05, second message): stage 1, why 43247 was not suggested on 39f0ac49

Traced by session a12d8fb3 on 2026-11-05 between 20:26Z and 20:45Z. The owner's latest identifiable synthetic GI test is
`https://cpt.quillmd.com/#doc/39f0ac49-eecc-4c72-bd23-9d542f7f4aa3`.
- **Upload:** "GI_Procedure_Note_05.pdf", by the owner account (human), at 20:09:18Z, on the installed revision
  `e6d451f03d86`.
- **Synthetic:** the workspace is synthetic-only.
- **Newer than anything else:** no encounter was created after it. The agent account's three walk documents came
  before it (19:22Z to 19:26Z); 88d9db32, the earlier PDF, is from 07:38Z.

**How it was read:**
- Every record was read through the live database's own container, in a read-only transaction.
- The raw response bytes of all five provider runs were re-hashed against their stored hashes, and all five matched.
- The engine's admission step was reproduced offline, on the installed code, against a throwaway copy of the database
  (`cpth3_base` on the test server; nothing written, nothing sent).
- The exports sit in the session's evidence directory and are reaped at close-out.

This records what the records say, not what a model is assumed to have done.

## What the document documents (read before any output was read)

A two-procedure report with a service date of 11/05/2026, by the endoscopist.

**Upper endoscopy:**
- an impacted meat bolus at 35 cm, removed through the working channel ("A retrieval net was passed through the
  working channel and the bolus was removed through the mouth in two pieces.");
- a Schatzki ring, not dilated ("dilation was deferred");
- multiple cold-forceps biopsies of the proximal and distal esophagus;
- stomach and duodenum examined.

**Colonoscopy** to the cecum:
- a 10 mm ascending-colon polyp removed by cold snare;
- a separate 3 mm sigmoid polyp removed with cold biopsy forceps.

**Other:** monitored anesthesia care by the anesthesia service. The plan defers an elective dilation to a later visit.

**The session's provisional reading:**
- **Codes, one unit each:** 43247, 43239, 45385 and 45380. 45380 is at a separate lesion from 45385, so a
  distinct-lesion modifier is a consideration, not an assertion.
- **Not coded:** no dilation code (deferred); no moderate-sedation code (anesthesia is another provider's service).
- **Not an assertion:** whether payer edits allow 43239 beside 43247 is a reference question (NCCI PTP is not
  connected).

This is the session's reading, not a qualified coder's adjudication.

## Each stage, as recorded

| stage | 43247 (EGD with foreign-body removal) | the three codes Corti selected (43239, 45380, 45385) |
|---|---|---|
| Corti, primary run `db6f9e8a` (succeeded, 0.0879 credits) | **not returned at all**: neither selected nor among its nine candidates (G8420, 99214, 1036F, 99204, G9903, G8417, 91110, 99221, G8754) | selected, with ICD-10 codes beside them |
| Astra, first reading `a873ac6a` (gpt-6-astra) | **proposed**: in `codes`, basis "The impacted esophageal meat bolus was removed through the mouth using a retrieval net.", quoting the retrieval-net sentence verbatim | proposed all three: 43239 and 45380 with modifier 59 stated |
| Fable, first reading `cc217632` (claude-fable-5-1) | **proposed**: in `codes`, the same sentence quoted verbatim | proposed all three: 43239 and 45380 with modifier 51 stated |
| Normalization | both readings `state: read` (Fable's arrived in a json code fence, which the parser accepts); both frozen and hashed before the peer reviews | — |
| Independence | the first-reading requests carry no code number and no other participant's output; the peer-review requests (`6b3e413f`, `6053cb63`) carry the frozen conclusions | — |
| Source validation (`engine._select`, from the participants' own spans) | not excluded; matched to the upper endoscopy (S1), whose status is `uncertain`; **no act matched**; support `not_applicable` ("Not checked: the documented service or act is not established as performed") | each held `needs_clarification`: "The document does not establish the upper endoscopy [colonoscopy] as performed on the date of service (uncertain: routing holds the family ...)" |
| Admission (`engine._Harness.merge`, HARNESS.md P-ADMIT) | **refused**: the reconciliation of Corti's three codes leaves no open item, so the code "accounts for no documented service or act the other proposals left unresolved". Listed as alternative `altp:0` (informational, never approvable) in both assessments, `9ccb272d` and `e0c1c149` | — |
| Customer page | under "Other codes considered (not suggested)": "**43247** Listed as an alternative only; not suggested for approval." | three rows "Needs a detail", six questions ("Confirm whether the upper endoscopy was performed on the date of service.", "... confirm the furthest extent reached.", and the same for the colonoscopy) |
| Member answers | — | at 20:12:09Z the owner answered all six "Not documented". The page offers only "Not documented" and "Cannot confirm" (or an addendum) for these questions. All three codes became excluded ("A needed detail is not documented"), and the encounter now reads `reviewed` with no approved code and no decision row |

## Why, component by component

The exclusion is **not clinically justified**. The document plainly documents an upper endoscopy with removal of an
impacted food bolus by retrieval net on the date of service. Three components fail together, and none of them is Corti's
omission alone.

1. **Source interpretation: the act is invisible to CPT Studio's own reader.**
   - The documented-service reader (`studio/gi/services.py`, `ACTS`) knows a `foreign_body` act only by the nouns
     "foreign body", "food bolus" and "food impaction".
   - The narrative says "impacted meat bolus" and then "the bolus was removed", so S1 records the two biopsy acts and
     no foreign-body act.
   - The Impression's "Esophageal food impaction successfully cleared by endoscopic retrieval" is not read as an act
     either.
   - The catalogue does know the code (`43247` requires `foreign_body`). The gap is the reader, not catalogue
     coverage.
2. **Proposal admission is gap-filling.**
   - P-ADMIT admits a participant's code only where it "accounts for a documented service or act the decidable
     proposals left unresolved" (session interpretation (c) of the morning directive).
   - So admission depends on what Corti's selections leave open. A code Corti omitted can enter only through an act
     CPT Studio's reader also found; a code for an act Corti covered with another code never enters.
   - This is the dependence the owner's second message rules out.
3. **Source interpretation: the section reader misplaces the procedure narratives.**
   - The report writes its parts as inline labels: "Indications: ...", "Preprocedure assessment: ...",
     "Upper endoscopy: The gastroscope was advanced ...", "Colonoscopy: After repositioning, a pediatric colonoscope was
     introduced ...".
   - `studio/gi/sections.py` opens a section only for a label it knows. "Indications" is one; "Preprocedure
     assessment" (unhyphenated), "Upper endoscopy" and "Colonoscopy" with text after the colon are not.
   - So the Indications section runs on over both procedure narratives. Routing reads "performed: was advanced",
     "section: indication (Indications)" for both families, and reports both `uncertain`.
   - That one misreading holds every code on the encounter and asks the six questions.

Display then did what the stored rows say:
- the participants' code was shown as an alternative only, with nothing saying that two independent readings proposed it;
- the questions offered no way to say "yes, it was performed" except an addendum.

The second point is a product finding for item 7: the answer set makes the natural reply to a false doubt exclude the
code.

## What is preserved

Nothing was reset or re-sent:
- both assessments, the six clarifications and the six member answers;
- the five runs with their raw bytes (`db6f9e8a` sha256 `8617b2ba028c181f…`, `a873ac6a` `83f3626c581005b5…`,
  `cc217632` `ed3d0f7059fdae1e…`, `6b3e413f` `1621cb1e9974c2aa…`, `6053cb63` `1019c2ae3eab5ec2…`).

The encounter will be re-assessed from these retained responses, with every send disabled, once the repair is
installed. The prior assessments and the owner's answers are kept beside the new one.

## Offline reproduction

`/home/claude/cpt-studio-harness3-20261105/tools/trace_admit.py 39f0ac49 43247`, on `e6d451f03d86`'s code, against the
throwaway copy `cpth3_base` (dump taken 20:33:37Z, sha256 `7d7e298a412ece88…`):

    participant astra read codes ['43247', '43239', '45385', '45380']
    participant fable read codes ['43247', '43239', '45385', '45380']
    == 43247 first proposers ('astra', 'fable') excluded False status None
       match ('S1', 'uncertain', [])
       support Support(status='not_applicable', ... detail='Not checked: the documented service or act is not established as performed.')
       unresolved items: []

## What this sets for the repair

The repair follows from the trace (items 3 and 4), and none of it names this document or this code:
- the foreign-body act must be read from the document's own words;
- the inline procedure labels must stop inheriting the Indications section;
- an explicit participant proposal must be admitted on its own validated support, whatever Corti did with the code.

A forced code is not the repair. If the re-read document still leaves 43247 unestablished, it stays unestablished, and
the trace says why.
