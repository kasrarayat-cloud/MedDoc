QuillMD native Microsoft Word review package — SYNTHETIC DATA ONLY (2026-09-19)

WHY THERE IS A SECOND PACKAGE
  The 2026-09-18 package was inspected in Word 2608 (build 20326.20144) on Windows 11 and three findings
  came back. All three reproduced. Two of them were about the package itself:

    * "05-all-blanks-fixture-no-AI.docx" was labelled "every answer reviewed as missing". It fills EVERY
      blank — all 52 measurements, 6 locations and 4 demographics. The label was the exact opposite of the
      file. It is included here under a truthful name; its bytes are unchanged.
    * "04-long-answer-fixture-no-AI.docx" was labelled a long-answer case. Its 19,931 characters are a
      BODY PARAGRAPH inserted next to the mapped fields, and the longest MAPPED answer in it is 89
      characters. Renamed, bytes unchanged.

  The third was real and is repaired: the measurement table let its section headings separate from the
  measurements they label.

CONTENTS
  01-original-blank-WM-IOV-Template.docx
        The customer's blank form. Unchanged, and its sha256 is checked by the builder.

  02 / 03  export, ABSENT scenario, BEFORE and AFTER the layout repair
  04 / 05  export, POSITIVE scenario, BEFORE and AFTER the layout repair
        Two real exports, each in both states. ⚠️ OPEN THE PAIR SIDE BY SIDE — the whole point of the
        repair is the difference between them, and only Word can show it. Not one visible character
        differs; what differs is where the page breaks.

  06-sdk-fixture-EVERY-BLANK-FILLED-not-missing.docx
  07-sdk-fixture-LONG-BODY-PARAGRAPH-not-a-mapped-answer.docx
        The two SDK qualification fixtures, under names that say what they are. They are qualification
        evidence for the processor, NOT examples of missing answers or of long mapped answers.

  word-acceptance-checklist.md   The checklist, with section F2 added for the table pagination and three
                                 claims corrected (see below).
  SHA256SUMS.txt                 Verify with: sha256sum -c SHA256SUMS.txt
                                 (Windows: certutil -hashfile <file> SHA256)

WHAT THE CHECKLIST GOT WRONG, NOW CORRECTED
  * FONTS — there is NO font defect and none should be raised. Selecting the same referring physician in
    the ORIGINAL Word dropdown produces the same Aptos 12-point answer as the export. The Liberation Serif
    / DejaVu Sans note applied only to a Linux evaluation render with no Aptos installed.
  * HEADER XML — the old line said "headers and media byte-identical". The MEDIA are. The HEADERS are not:
    header1.xml is 4,188 bytes in the original against 3,435 in the export, header2.xml 4,205 against
    3,451, and both .rels differ. Read the headers in Word; do not trust a byte comparison.
  * UNITS — all 52 measurement rows said the unit was "printed by the original cell". The cells hold bare
    numbers (2.25, 501). The unit is printed ONCE in the column heading.

WHAT IS NOT IN THIS PACKAGE, AND WHY
  ⚠️ A genuine missing-answer document and a genuine long-mapped-answer document are NOT here. They can
  only be produced through the real export path, and that path refuses a Word processor owned by the
  calling account — which is true on the engineering host AND on the CI runner, so the eight live Word
  tests skip in both. Producing them means driving the deployed application, and six attempts hit the
  clinical review model rather than the exporter: prewritten statements need evidence quotations, and the
  statement alternatives must be consistent with the answers. That work is described in the checkpoint and
  is not finished. Nothing here pretends otherwise.

  ⚠️ The layout repair is MERGED AND TESTED BUT NOT YET DEPLOYED. Files 03 and 05 were produced by applying
  the shipped repair to real exports — the same function at the same seam the exporter now calls — so they
  are what the exporter will emit once the release ships. They are not, today, what the running service
  would hand a doctor.

Every document contains synthetic patient and clinician text only. No credentials, keys or runtime files
are included. Open 01 beside the BEFORE/AFTER pairs in Microsoft Word, complete the checklist, and report
the Word version, the OS and each row's ACCEPT or REJECT.
