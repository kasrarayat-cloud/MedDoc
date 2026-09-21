# Original colonoscopy template compatibility

The owner's unchanged blank `Colonoscopy_Operative_Template.docx` is 38,393 bytes,
SHA256 `8ae1e2b0ebeec317c038b8bfeed6a0824055f44d689c039ab450404593f2815a`.
The previous application at `47374a9462dfe5bceb0947c831fc23e35a01e239` refused
it at the `no_fields` branch in both the isolated real parser and authenticated
private upload. The document is an ordinary labelled underlined-tab form;
the earlier adapter recognized only brace placeholders and blank table cells.
The refusal was a compatibility gap, not evidence of corruption or unsafe content.

The narrow adapter maps 28 physical answer tabs to 24 reviewable logical fields.
Name/DOB, patient ID/date, anesthesia/preparation, blood loss/complications and
dictated/transcribed dates stay separate. Three findings and three recommendations
retain their own headings. Consent's two lines form one answer, and procedure's
four lines form one answer. Five separator tabs and decorative rules are excluded.
The original bytes remain retained; review saves a new mapping version without
altering any mapping already used by another document.

Upload the original under **Form library → Upload form**, select the department,
and confirm it is blank. Review the 24 labels and grouping notes; use **Edit field
mapping** to clarify labels and save a new mapping version. Choose **Use this
form**, select an eligible synthetic patient, enter fictional typed notes and
create the document. Enter or generate documented answers, review each including
missing information, save, then finalize and choose **Export original format**.
Generation remains optional and has its existing disclosed billing; the installed
qualification uses manual answers and makes no provider calls.

Blank information remains blank. Consent, findings and dates are never inferred
as default assertions. A recognized signature field stays blank during generation;
if supplied manually, it must be the authenticated finalizer's identity and must
be reviewed by that same clinician. This is not a digital-signature feature.

Answers flow in their original regions. Long paired answers separate onto flowing
lines at the original separator; multiline sections use their existing areas and
expand the last one as needed. Page count can increase. This does not promise
pixel-identical pagination or support for arbitrary/scanned forms. Review every
exported page before use. Existing placeholders, SOAP tables and the qualified
WM controls retain their existing adapter contracts.

Protected proof and final installed outcome are recorded in
`rebuild/.runtime/colonoscopy-compatibility-20260921/FINAL-REPORT.md` and its evidence
index. Parser fixtures, authenticated installed exports and evaluation render
evidence are labelled separately. Evaluation rendering is not native Microsoft
Word appearance acceptance; the optional original/export comparison package is
kept in that same protected directory. No public release or patient-data approval
is implied.
