"""Word engine precision: signing structures and non-answer text, on synthetic python-docx shapes built here.

Every shape mirrors a STRUCTURE (a placeholder naming the signing act, a caption ruled along its top, an attestation
line, a phrase printed underlined, a bracketed aside inside a sentence ...) in wording written for these tests, never a
particular form or its wording. Each rule has a positive control that must keep today's answer place, and every shape
a refutation pass found (named by its finding, e.g. L1:R3) is pinned where the answer place must stay.
"""
import io
import unittest
from zipfile import ZipFile

from docx import Document
from docx.enum.style import WD_STYLE_TYPE
from docx.oxml import OxmlElement
from docx.oxml.ns import qn

from . import word_v3 as word

SIGNING = ("signature", "initials")
FILLABLE = ("text", "long_text", "date", "time", "number", "measurement")


def build(*lines, style=None):
    """A document whose body paragraphs are `lines`; a line may be a callable(doc) that adds its own paragraph."""
    doc = Document()
    for line in lines:
        if callable(line):
            line(doc)
        else:
            doc.add_paragraph(line)
    out = io.BytesIO()
    doc.save(out)
    return out.getvalue()


def fields_of(data):
    return word.inspect(data)["fields"]


def at(fields, n):
    return [f for f in fields if f["locator"]["slot"] == "b/p[%d]" % n]


def kinds(fields):
    return [f["kind"] for f in fields]


def _document_xml(data):
    return ZipFile(io.BytesIO(data)).read("word/document.xml")


def body_texts(data):
    return [p.text for p in Document(io.BytesIO(data)).paragraphs]


def filled(data, value="Jane Example", date="03/14/2026"):
    """Fill every ordinary answer place (a date with `date`, any other free text with `value`); signing places stay."""
    fields = fields_of(data)
    answers = {f["key"]: (date if f["kind"] == "date" else value) for f in fields if f["kind"] in FILLABLE}
    return word.fill(data, fields, answers)


def border(element, edges=("top",)):
    box = OxmlElement("w:pBdr")
    for name in edges:
        edge = OxmlElement("w:" + name)
        edge.set(qn("w:val"), "single")
        edge.set(qn("w:sz"), "4")
        box.append(edge)
    element.append(box)


def top_border(element):
    border(element, ("top",))


def caption(text, *, how="direct", edges=("top",)):
    def add(doc):
        p = doc.add_paragraph()
        for n, part in enumerate(text.split("\t")):
            if n:
                p.add_run("\t")
            p.add_run(part)
        if how == "direct":
            border(p._p.get_or_add_pPr(), edges)
        elif how == "style":
            name = "Signing Rule"
            try:
                style = doc.styles[name]
            except KeyError:
                style = doc.styles.add_style(name, WD_STYLE_TYPE.PARAGRAPH)
                top_border(style.element.get_or_add_pPr())
            p.style = style
    return add


def underlined(*parts, hint=()):
    """A paragraph of runs; parts are (text, underline) pairs; indexes in `hint` are written in guidance ink."""
    def add(doc):
        p = doc.add_paragraph()
        for n, (text, under) in enumerate(parts):
            r = p.add_run(text)
            r.underline = under
            if n in hint:
                color = OxmlElement("w:color")
                color.set(qn("w:val"), "0070C0")
                r._r.get_or_add_rPr().append(color)
    return add


def hint_cell(cell, text):
    cell.text = ""
    r = cell.paragraphs[0].add_run(text)
    color = OxmlElement("w:color")
    color.set(qn("w:val"), "0070C0")
    r._r.get_or_add_rPr().append(color)


def table(rows, *, merge_first=False):
    """A table of `rows` (lists of cell texts; '~text' is written in guidance ink; '\\n' splits a cell's paragraphs)."""
    def add(doc):
        t = doc.add_table(rows=len(rows), cols=max(len(r) for r in rows))
        if merge_first:
            t.cell(0, 0).merge(t.cell(0, len(rows[1]) - 1))
        for i, r in enumerate(rows):
            for j, txt in enumerate(r):
                if merge_first and i == 0 and j:
                    continue
                if txt.startswith("~"):
                    hint_cell(t.cell(i, j), txt[1:])
                    continue
                lines = txt.split("\n")
                t.cell(i, j).text = lines[0]
                for extra in lines[1:]:
                    t.cell(i, j).add_paragraph(extra)
    return add


def listed(doc, items, *, num, fmt="decimal"):
    """List paragraphs [(text, level)] of a list of its own (numId `num`, every level printed as `fmt`)."""
    numbering = doc.part.numbering_part.element
    abstract = OxmlElement("w:abstractNum")
    abstract.set(qn("w:abstractNumId"), str(100 + int(num)))
    for lvl in range(3):
        level = OxmlElement("w:lvl")
        level.set(qn("w:ilvl"), str(lvl))
        f = OxmlElement("w:numFmt")
        f.set(qn("w:val"), fmt)
        level.append(f)
        abstract.append(level)
    numbering.append(abstract)
    number = OxmlElement("w:num")
    number.set(qn("w:numId"), str(num))
    ref = OxmlElement("w:abstractNumId")
    ref.set(qn("w:val"), str(100 + int(num)))
    number.append(ref)
    numbering.append(number)
    for text, lvl in items:
        p = doc.add_paragraph(text)
        props = OxmlElement("w:numPr")
        ilvl = OxmlElement("w:ilvl")
        ilvl.set(qn("w:val"), str(lvl))
        nid = OxmlElement("w:numId")
        nid.set(qn("w:val"), str(num))
        props.append(ilvl)
        props.append(nid)
        p._p.get_or_add_pPr().append(props)


def spans_of(data):
    out = []
    for f in fields_of(data):
        t = f["locator"]["target"]
        if t.get("type") == "span":
            idx = word.SlotIndex(word.open_package(data)).by_id[f["locator"]["part"] + "#" + f["locator"]["slot"]]
            out.append(word.paragraph_text(idx.el)[0][t["start"]:t["end"]])
    return out


class SigningPlaceholders(unittest.TestCase):
    """K7: a placeholder whose own words are the signing act is a signature place."""

    def test_sign_token_is_a_signature_place_and_ends_the_area(self):
        data = build("With kind regards,", "[Sign]", "[Name of sender]", "[Role of sender]")
        fields = fields_of(data)
        sign = at(fields, 1)
        self.assertEqual(kinds(sign), ["signature"])
        self.assertNotIn("extra", sign[0]["locator"])
        self.assertEqual(sign[0]["locator"]["target"]["type"], "span")
        # the placeholders below it are their own place, not lines of the signature
        self.assertTrue(at(fields, 2))
        self.assertTrue(all(f["kind"] not in SIGNING for f in at(fields, 2)))

    def test_signing_token_variants_and_controls(self):
        cases = [("[Signature]", "signature"), ("<e-signature>", "signature"), ("{{Sign here}}", "signature"),
                 ("[Initials]", "initials"), ("[Signature of investigator]", "signature"),
                 ("[Examiner signature]", "signature"),
                 # a signing act that is also dated is signed, never typed (L2:R2-11)
                 ("[Sign and date]", "signature"), ("[Signature/Date]", "signature"), ("[Initial and date]", "initials"),
                 ("[Countersign]", "signature"), ("[Patient to sign]", "signature"), ("[Sign name here]", "signature"),
                 ("[Initial assessment]", None), ("[Name of signatory]", None), ("[Date of signature]", None),
                 ("[Sign-off date]", None), ("[Name of person who signed]", None)]
        for token, kind in cases:
            with self.subTest(token=token):
                fields = at(fields_of(build("Closing line.", token)), 1)
                self.assertEqual(len(fields), 1)
                if kind in SIGNING:
                    self.assertEqual(fields[0]["kind"], kind)
                else:
                    self.assertNotIn(fields[0]["kind"], SIGNING)

    def test_signing_token_in_a_placeholder_cell(self):
        def grid(doc):
            t = doc.add_table(rows=2, cols=2)
            t.cell(0, 0).text, t.cell(0, 1).text = "Clinician", "[Sign]"
            t.cell(1, 0).text, t.cell(1, 1).text = "Clinic", "[Name of clinic]"
        fields = fields_of(build(grid))
        self.assertEqual(kinds(fields), ["signature", "text"])

    def test_a_placeholder_mentioning_a_signing_asks_for_a_name(self):
        """L1:R9: '[Name of person who signed]' in a placeholder cell is the signer's NAME, answered like any name."""
        for row in (["Witness", "[Name of witness who signed]"], ["Consent taken by", "[Name of person who signed]"]):
            with self.subTest(row=row):
                data = build(table([row]))
                self.assertEqual(kinds(fields_of(data)), ["text"])
                self.assertEqual(_document_xml(filled(data)).count(b"Jane Example"), 1)

    def test_sign_token_inside_a_line_keeps_its_neighbours(self):
        data = build("Yours faithfully [Sign] on [date of letter] at [Name of clinic]")
        allf = fields_of(data)
        self.assertEqual(kinds(at(allf, 0)), ["signature", "date", "text"])
        answers = {f["key"]: "03/14/2026" if f["kind"] == "date" else "Synthetic Clinic"
                   for f in allf if f["kind"] not in SIGNING}
        out = word.fill(data, allf, answers)
        self.assertIn(b"Synthetic Clinic", _document_xml(out))
        with self.assertRaises(word.V3Failure):
            word.fill(data, allf, {[f for f in allf if f["kind"] == "signature"][0]["key"]: "X"})

    def test_signing_placeholder_in_a_content_control(self):
        """L2:R2-12: a text control showing 'Sign here' / '[Signature]', or named a countersignature, is signed."""
        W = 'xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"'
        from docx.oxml import parse_xml

        def control(label, shown, alias=None):
            def add(doc):
                p = doc.add_paragraph(label)
                named = '<w:alias w:val="%s"/>' % alias if alias else ""
                p._p.append(parse_xml('<w:sdt %s><w:sdtPr>%s<w:showingPlcHdr/><w:text/></w:sdtPr><w:sdtContent><w:r>'
                                      '<w:t>%s</w:t></w:r></w:sdtContent></w:sdt>' % (W, named, shown)))
            return add
        for label, shown, alias, kind in (("Patient: ", "Sign here", None, "signature"),
                                          ("", "[Signature]", None, "signature"),
                                          ("Review: ", "Enter text.", "Countersignature", "signature"),
                                          ("Patient: ", "Enter text.", None, "text")):
            with self.subTest(shown=shown, alias=alias):
                data = build(control(label, shown, alias))
                fields = fields_of(data)
                self.assertEqual(kinds(fields), [kind])
                if kind in SIGNING:
                    with self.assertRaises(word.V3Failure):
                        word.fill(data, fields, {fields[0]["key"]: "Jane Example"})


class DisplacedSigningLine(unittest.TestCase):
    """K7: 'Signature:' / spacing / a drawn line - the drawn line is the signature place."""

    def test_drawn_line_after_spacing_is_the_signature(self):
        data = build("Patient's signature:", "", "______________________________", "Date: ____________")
        fields = fields_of(data)
        self.assertEqual(at(fields, 1), [])
        sign = at(fields, 2)
        self.assertEqual(kinds(sign), ["signature"])
        self.assertEqual((sign[0]["locator"]["target"]["start"], sign[0]["locator"]["target"]["end"]), (0, 30))
        self.assertEqual(kinds(at(fields, 3)), ["date"])
        self.assertEqual(sum(f["kind"] == "signature" for f in fields), 1)

    def test_two_spacing_lines_and_initials(self):
        fields = fields_of(build("Initials of the witness:", "", "", "__________"))
        self.assertEqual(kinds(at(fields, 3)), ["initials"])
        self.assertEqual(at(fields, 1) + at(fields, 2), [])

    def test_any_number_of_spacing_lines(self):
        """L2:R2-08: three empty lines between the label and its drawn line - the line is still the signature."""
        data = build("Patient's signature:", "", "", "", "______________________________")
        fields = fields_of(data)
        self.assertEqual(kinds(at(fields, 4)), ["signature"])
        self.assertFalse([f for f in fields if f["kind"] in FILLABLE])

    def test_drawn_line_straight_under_a_signing_label(self):
        """L2:R2-08: 'Patient's signature:' holds its place after the colon; the drawn line under it is signed too."""
        data = build("Patient's signature:", "______________________________")
        fields = fields_of(data)
        self.assertEqual(kinds(at(fields, 1)), ["signature"])
        self.assertFalse([f for f in fields if f["kind"] in FILLABLE])
        self.assertEqual(body_texts(filled(data))[1], "______________________________")
        # a label that is not a signing act keeps an ordinary line under it
        self.assertEqual(kinds(at(fields_of(build("Name:", "______________________________")), 1)), ["text"])
        # a line with a caption of its own under it is that caption's; a label holding its own drawn blank does not
        # reach the next line
        for lines in (("Patient's signature:", "______________________", "Printed name"),
                      ("Patient's signature:", "______________________", "Date"),
                      ("Patient signature: ____________", "______________________", "Printed name"),
                      ("Patient signature: ____________", "______________________")):
            with self.subTest(lines=lines):
                data = build(*lines)
                self.assertTrue(all(f["kind"] in FILLABLE for f in at(fields_of(data), 1)))
                self.assertNotEqual(body_texts(filled(data))[1], "______________________")

    def test_line_under_a_label_line_naming_a_signature_and_a_date(self):
        fields = fields_of(build("Examiner Signature:\t\t\tDate:", ""))
        self.assertTrue(fields)
        self.assertTrue(all(f["kind"] == "signature" for f in fields if f["locator"]["slot"] == "b/p[1]"))
        fields = fields_of(build("Date of signature:", ""))
        self.assertEqual(kinds(at(fields, 1)), ["date"])

    def test_leading_line_of_a_date_line_under_a_signing_label(self):
        """L2:R2-10: '______        Date: ____' under 'Patient's signature:' - 'Date:' labels the NEXT blank only."""
        data = build("Patient's signature:", "", "______________________        Date: __________")
        line = at(fields_of(data), 2)
        self.assertEqual(kinds(line), ["signature", "date"])
        self.assertEqual(body_texts(filled(data))[2], "______________________        Date: 03/14/2026")
        # a leading blank under a label that is not a signing act keeps its reading
        self.assertEqual(kinds(at(fields_of(build("Comments", "", "______________        Date: ______")), 2)),
                         ["date", "date"])

    def test_controls_keep_their_lines(self):
        for label in ("Name:", "Signature date:", "Date:"):
            with self.subTest(label=label):
                fields = fields_of(build(label, "", "______________________________"))
                self.assertFalse([f for f in fields if f["kind"] in SIGNING])

    def test_a_line_with_its_own_caption_below_is_not_displaced(self):
        """L1:R5: '____' / 'Signature of patient' / '' / '____' / 'Printed name' - the second line is the printed
        name's (its caption is under it), never the signature of the caption above it."""
        line = "______________________"
        for last in ("Printed name", "Date", "Name of person obtaining consent"):
            with self.subTest(last=last):
                data = build(line, "Signature of patient", "", line, last)
                fields = fields_of(data)
                self.assertEqual(kinds(at(fields, 0)), ["signature"])      # the line the caption is printed under
                self.assertTrue(at(fields, 3))
                self.assertTrue(all(f["kind"] in FILLABLE for f in at(fields, 3)))
                texts = body_texts(filled(data))
                self.assertEqual(texts[0], line)
                self.assertNotEqual(texts[3], line)
        fields = fields_of(build(line, "Signature of patient", "", "", line, "Printed name"))
        self.assertTrue(all(f["kind"] in FILLABLE for f in at(fields, 4)))
        # a line with its own caption under it is not the displaced line of a signing label above it
        fields = fields_of(build("Signature of patient:", "", line, "Printed name"))
        self.assertTrue(at(fields, 2))
        self.assertTrue(all(f["kind"] in FILLABLE for f in at(fields, 2)))
        # the caption is printed under its own line: a later line with no caption is not its displaced signature
        fields = fields_of(build(line, "Signature of patient", "", line, "", "Thank you."))
        self.assertTrue(at(fields, 3))
        self.assertTrue(all(f["kind"] in FILLABLE for f in at(fields, 3)))

    def test_drawn_line_over_a_signing_caption(self):
        """L2:R2-09: a drawn line whose caption under it names a signing act is signed, never typed on."""
        data = build("______________________________        ______________",
                     "Signature of Patient                          Date")
        self.assertEqual(kinds(fields_of(data)), ["signature"])
        self.assertEqual(body_texts(filled(data))[0], "______________________________        ______________")
        # a caption naming something else leaves the line an answer, and a colon-ended line labels what follows it
        self.assertEqual(kinds(fields_of(build("______________________", "Printed name"))), ["text"])
        fields = fields_of(build("______________________", "Signature:", "_____________"))
        self.assertNotIn("signature", kinds(at(fields, 0)))


class CaptionRuledSigningLine(unittest.TestCase):
    """K7: an empty line over a caption ruled along its top ('Signature Line' style)."""

    def form(self, how="direct", captions="Signature of Volunteer\t\t\tPrint Name of Volunteer\t\t\tDate"):
        return build("Please sign below.", "", caption(captions, how=how), "",
                     caption("Signature of Staff Member\t\t\tPrint Name\t\t\tDate", how=how))

    def test_signature_on_the_line_above_each_ruled_caption(self):
        for how in ("direct", "style"):
            with self.subTest(how=how):
                result = word.inspect(self.form(how))
                fields = result["fields"]
                self.assertEqual([(f["kind"], f["label"]) for f in at(fields, 1)],
                                 [("signature", "Signature of Volunteer")])
                self.assertEqual([(f["kind"], f["label"]) for f in at(fields, 3)],
                                 [("signature", "Signature of Staff Member")])
                self.assertEqual(at(fields, 2) + at(fields, 4), [])
                self.assertFalse([f for f in fields if f["kind"] in ("date", "text", "long_text")])
                self.assertTrue(any("completed at signing" in n for n in result["notes"]))

    def test_initials_caption(self):
        fields = fields_of(build("", caption("Initials of Volunteer\t\tDate")))
        self.assertEqual(kinds(at(fields, 0)), ["initials"])

    def test_controls(self):
        # no rule along the caption: not this structure
        fields = fields_of(self.form(how="none"))
        self.assertFalse([f for f in at(fields, 1) if f["kind"] == "signature"])
        # a ruled caption with no signing caption
        fields = fields_of(build("", caption("Print Name\t\t\tDate")))
        self.assertFalse([f for f in fields if f["kind"] in SIGNING])
        # the line above holds text: not an empty writing line
        fields = fields_of(build("Witnessed", caption("Signature of Witness\t\tDate")))
        self.assertFalse(at(fields, 0))

        # a ruled section heading is not a caption
        def heading(doc):
            p = doc.add_heading("Signature", 2)
            top_border(p._p.get_or_add_pPr())
        self.assertFalse(fields_of(build("", heading)))
        # more than four captions, or a caption longer than eight words, is not a caption row
        self.assertEqual(at(fields_of(build("", caption("Signature\t\tName\t\tDate\t\tTime\t\tWard"))), 0), [])
        self.assertEqual(at(fields_of(build("", caption("Signature of the member of staff who explained the visit "
                                                          "plan"))), 0), [])

    def test_boxed_notices_and_label_lines_are_not_signature_lines(self):
        """L1:R6: a notice boxed on every side, or an empty line that is the answer line of a colon-ended label above
        it, is not a Signature Line - the label keeps its line."""
        box = ("top", "left", "bottom", "right")
        for data in (build("Additional comments:", "", caption("Signed forms go back to the front desk", edges=box)),
                     build("Please return the form.", "", caption("Signed forms go back to the front desk", edges=box)),
                     build("Referral reason:", "", caption("A doctor's signature is needed", edges=box)),
                     build("Comments:", "", caption("Part 4 - Agreement and signature"),
                           "I agree to the plan described above.")):
            with self.subTest(text=body_texts(data)[2]):
                fields = fields_of(data)
                self.assertFalse([f for f in fields if f["kind"] in SIGNING])
                if body_texts(data)[0].endswith(":"):
                    self.assertEqual(len(at(fields, 1)), 1)
                self.assertEqual(at(fields, 0), [])


class ESignatureAttestation(unittest.TestCase):
    """K7: 'Electronically signed on <date> by:' - the place after 'by' is the signing act."""

    def attestation(self, doc):
        p = doc.add_paragraph()
        p.add_run("\t")
        for text in ("Electronically Signed On ", "<<insert date>>", " ", "By:"):
            p.add_run(text).underline = True

    def test_attestation_by_is_a_signature_owning_the_signer_line(self):
        data = build(self.attestation, "\tJane Q. Example, MD")
        fields = fields_of(data)
        line = at(fields, 0)
        self.assertEqual(sorted(kinds(line)), ["date", "signature"])
        sign = [f for f in line if f["kind"] == "signature"][0]
        self.assertEqual([x["slot"] for x in sign["locator"]["extra"]], ["b/p[1]"])
        date = [f for f in line if f["kind"] == "date"][0]
        text = word.paragraph_text(word.open_package(data).tree("word/document.xml").find(".//" + word.q("w:p")))[0]
        self.assertEqual(text[date["locator"]["target"]["start"]:date["locator"]["target"]["end"]], "<<insert date>>")
        out = word.fill(data, fields, {date["key"]: "03/14/2026"})
        xml = _document_xml(out)
        self.assertIn(b"03/14/2026", xml)
        self.assertNotIn(b"&lt;03/14/2026", xml)
        with self.assertRaises(word.V3Failure):
            word.fill(data, fields, {sign["key"]: "Jane Q. Example"})

    def test_word_order_variants(self):
        """L3:R3-06: 'Signed electronically', 'Signed digitally' and 'Electronic signature' attest the same act."""
        for first in ("Signed electronically on <<date>> by:", "Signed digitally on <<date>> by:",
                      "Electronic signature on <<date>> by:", "Digital signature on <<date>> by:"):
            with self.subTest(first=first):
                data = build(first, "Dr A. Example, Consultant")
                fields = fields_of(data)
                sign = [f for f in fields if f["kind"] == "signature"]
                self.assertEqual(len(sign), 1)
                self.assertEqual([x["slot"] for x in sign[0]["locator"]["extra"]], ["b/p[1]"])
                self.assertFalse([f for f in fields if f["kind"] in ("text", "long_text")])
                self.assertTrue(body_texts(filled(data))[0].endswith("by:"))

    def test_controls(self):
        fields = fields_of(build(self.attestation, "Comments"))
        self.assertFalse([f for f in fields if f["locator"].get("extra")])
        fields = fields_of(build("Reviewed by:", "Jane Q. Example, MD"))
        self.assertFalse([f for f in fields if f["kind"] == "signature"])
        self.assertFalse([f for f in fields if f["locator"].get("extra")])
        fields = fields_of(build("Electronically signed by: ______________"))
        self.assertEqual(kinds(fields), ["signature"])


class SegmentedLabels(unittest.TestCase):
    """K7: an 'Initials:' label printed after another label's answer gap is its own place."""

    def test_initials_after_ticked_options(self):
        data = build("Tick Yes or No:      Yes      No      Initials:          Date: ")
        fields = fields_of(data)
        by_label = {f["label"]: f["kind"] for f in fields}
        self.assertEqual(by_label.get("Initials"), "initials")
        self.assertEqual(by_label.get("Date"), "date")
        self.assertFalse([f for f in fields if f["kind"] == "date" and "Initials" in f["label"]])
        spans = [(f["locator"]["target"]["start"], f["locator"]["target"]["end"]) for f in fields]
        self.assertEqual(len(set(spans)), len(spans))

    def test_a_role_printed_in_a_signature_gap_is_not_typed(self):
        """L2:R2-01: a second label printed inside a signature's gap never becomes a typed answer beside it."""
        for text in ("Signed:              Countersigned:           ", "Signed:\t\tCountersigned:\t\t",
                     "Signature of Patient:          or Legally Authorized Representative:          ",
                     "Patient Signature:        Parent/Guardian (if minor):        ",
                     "Signature:          Witness:          "):
            with self.subTest(text=text):
                data = build(text)
                self.assertFalse([f for f in fields_of(data) if f["kind"] in FILLABLE])
                self.assertEqual(body_texts(filled(data)), [text])

    def test_a_label_after_a_tab_gap_keeps_all_its_words(self):
        """L2:R2-02: 'Signature of parent     (or guardian):' is one signing label, never '(or guardian)'."""
        for text in ("Name:\t\tSignature of parent     (or guardian):\t\t",
                     "Name:\t\tSignature of Patient     or Legally Authorized Representative:\t\t"):
            with self.subTest(text=text):
                fields = fields_of(build(text))
                self.assertEqual(kinds(fields), ["text", "signature"])
                self.assertTrue(fields[1]["label"].startswith("Signature of"))

    def test_a_label_after_a_drawn_blank_is_read(self):
        """L2:R2-07: 'Physician signature: ______ Date:' keeps its date place after the drawn line; a signing label
        printed straight after a drawn blank is a signing place of its own."""
        for text in ("Physician signature: ______________ Date:", "Physician signature: ______________   Date:"):
            with self.subTest(text=text):
                self.assertEqual(kinds(fields_of(build(text))), ["signature", "date"])
        self.assertEqual(kinds(fields_of(build("Name:______ Signature:"))), ["text", "signature"])

    def test_ordinary_labels_in_a_gap_stay_as_printed(self):
        self.assertEqual(kinds(fields_of(build("Name:          Date:          "))), ["text"])

    def test_name_signature_date_on_one_line_stay_separately_answerable(self):
        data = build("Name: ____________   Signature: ____________   Date: ____________")
        fields = fields_of(data)
        self.assertEqual(kinds(fields), ["text", "signature", "date"])
        name, sign, date = fields
        out = word.fill(data, fields, {name["key"]: "Jane Example", date["key"]: "03/14/2026"})
        self.assertIn(b"Jane Example", _document_xml(out))
        with self.assertRaises(word.V3Failure):
            word.fill(data, fields, {sign["key"]: "Jane Example"})


class DrawnLeadersAndDates(unittest.TestCase):
    """A dotted leader typed as mixed dots and ellipses, and a drawn dd/mm/yyyy after a date label, are one place."""

    def test_signature_leader_and_drawn_date(self):
        text = "Signature:……………........................…………\t\t\t\tDate: _____/_____/_____"
        data = build(text)
        fields = fields_of(data)
        self.assertEqual([(f["kind"], f["label"]) for f in fields], [("signature", "Signature"), ("date", "Date")])
        sign, date = fields
        self.assertEqual(text[sign["locator"]["target"]["start"]:sign["locator"]["target"]["end"]],
                         "……………........................…………")
        self.assertEqual(text[date["locator"]["target"]["start"]:date["locator"]["target"]["end"]], "_____/_____/_____")
        out = word.fill(data, fields, {date["key"]: "03/14/2026"})
        filled_text = word.paragraph_text(word.open_package(out).tree("word/document.xml").find(".//" + word.q("w:p")))[0]
        self.assertEqual(filled_text, text.replace("_____/_____/_____", "03/14/2026"))

    def test_a_date_shaped_blank_after_a_signing_label_is_signed(self):
        self.assertEqual(kinds(fields_of(build("Sign here: __/__/____"))), ["signature"])
        self.assertEqual(kinds(fields_of(build("Sign here: |__|__|/|__|__|/|__|__|__|__|"))), ["signature"])
        self.assertEqual(kinds(fields_of(build("Visit: |__|__|/|__|__|/|__|__|__|__|"))), ["date"])

    def test_two_groups_are_not_a_date(self):
        fields = fields_of(build("Blood pressure: ____/____ mmHg"))
        self.assertFalse([f for f in fields if f["kind"] == "date"])

    def test_three_groups_after_a_label_that_is_not_a_date(self):
        """L2:R2-05: 'BP/HR/RR: ___/___/___' is three answers; one date would have been written over them."""
        data = build("BP/HR/RR: ___/___/___")
        fields = fields_of(data)
        self.assertFalse([f for f in fields if f["kind"] == "date"])
        self.assertEqual(len(fields), 3)
        self.assertEqual(fields_of(build("G/P/A: __/__/__")), [])
        self.assertEqual(kinds(fields_of(build("Date of birth: __/__/____"))), ["date"])

    def test_mixed_separators_are_not_one_date(self):
        text = "Date of birth: ___/___-____"
        self.assertNotIn("___/___-____", spans_of(build(text)))


class UnderlinedPhrase(unittest.TestCase):
    """K11: one space printed underlined inside an underlined phrase is emphasis, not a drawn blank."""

    def test_underlined_phrase_has_no_answer_place(self):
        data = build(underlined(("Say how you slept ", False), ("over", True), (" ", True),
                                ("the last week", True), (".", False)))
        self.assertEqual(fields_of(data), [])

    def test_controls(self):
        fields = fields_of(build(underlined(("Name:", False), ("\t\t\t", True))))
        self.assertEqual(len(fields), 1)
        # a guidance-ink neighbour: a hint in the answer position keeps its place
        fields = fields_of(build(underlined(("Completed by: ", False), ("Print", True), (" ", True), ("Name", True),
                                            hint=(1, 3))))
        self.assertTrue([f for f in fields if f["locator"]["target"].get("shape") == "utab"])
        # three or more underlined spaces are a drawn blank
        fields = fields_of(build(underlined(("Signed", True), ("      ", True), ("here", True))))
        self.assertEqual(len(fields), 1)

    def test_a_gap_after_an_underlined_label_is_a_blank(self):
        """L1:R11: 'Age:' + two underlined spaces + 'years', all underlined, keeps its blank; so does one space after
        a label's colon."""
        for gap in ("  ", " "):
            with self.subTest(gap=gap):
                fields = fields_of(build(underlined(("Age:", True), (gap, True), ("years", True))))
                self.assertEqual([f["locator"]["target"].get("shape") for f in fields], ["utab"])
        self.assertEqual(len(fields_of(build(underlined(("Weight", True), ("  ", True), ("kg", True))))), 1)
        self.assertEqual(len(fields_of(build(underlined(("Height", True), (" ", True), ("cm", True))))), 1)
        self.assertEqual(len(fields_of(build(underlined(("Seen", True), ("  ", True), ("today", True))))), 1)
        self.assertEqual(len(fields_of(build(underlined(("Name:", True), (" ", True), ("Jane", True))))), 1)


class AuthorsBracketedText(unittest.TestCase):
    """K10: a bracketed or angled phrase inside running prose that is the author's text, not a place to write."""

    def test_conditions_examples_and_instruction_groups_are_printed(self):
        for text in ("Taking part is optional. <unless the clinic objects> You were asked because you attended.",
                     "Taking part is optional. <for clinic sites> You were asked because you attended.",
                     "Take 1 tablet [for X days] then stop.", "Bring [e.g. your inhaler] to the visit.",
                     "<add local guidance (e.g. a code of practice) as applicable> Your rights are described there.",
                     "<if applicable> The visits would last for [X weeks].",
                     "Records <if kept><coded scans and coded images> will be stored.",
                     "[IF YES] Which school year are you in?",
                     "You will receive (*insert name of product [e.g., cream] for [number of weeks] weeks*).",
                     "<delete this line for day cases> Your stay will be [X nights].",
                     "Call the review board <remove if not applicable> first."):
            with self.subTest(text=text):
                result = word.inspect(build(text))
                self.assertEqual(spans_of(build(text)), [])
                self.assertTrue(any("kept as printed" in n for n in result["notes"]))

    def test_instruction_group_alone(self):
        self.assertEqual(spans_of(build("(* You will receive [name of product] each day *)")), [])
        self.assertEqual(len(spans_of(build("You will receive [name of product] each day."))), 1)

    def test_note_worded_placeholders_in_an_answer_position_are_places_to_write(self):
        """L1:R1, L3:R3-02: after a 'Label:' or a question, alone on a line, or printed last, a placeholder that opens
        with a condition, an example or 'optional' asks for the answer; an explicit {{merge field}} always does."""
        for text in ("Clinician note: {{note}}", "Follow-up: {{when}}", "Location: {{where}}", "Clinician note: [Note]",
                     "Other: [If other, please specify]", "Occupation: [e.g. teacher]",
                     "Mobility aid: [e.g. walking stick, frame]", "Mobile: [Optional mobile number]",
                     "Urgency reason: [Only if urgent]", "Have you had surgery? [If yes, give details]",
                     "[Optional: your e-mail address]", "Comments: [Optional comments]",
                     "Allergies: [Note any known allergies]", "Onset: [When the symptoms first started]",
                     "Mobility: [Use of walking aids]", "Allergies:\t[Note any known allergies]",
                     "Allergies: [Note any known allergies] and reactions",
                     "Ethnicity: White / Other [If other, please specify]", "The review is due {{when}} after discharge.",
                     "The review happens {{if needed}} after discharge.",
                     "Referral details: [if any]", "Your next visit is on [when booked] at the clinic.",
                     "Bring your [optional carer's letter] to the visit.", "The form asks for [note of any allergies] here.",
                     "Staff will record [use of walking aids] at each visit.", "Call us [only if urgent] on the ward.",
                     "They will ask [where treated] during the visit."):
            with self.subTest(text=text):
                self.assertEqual(len(spans_of(build(text))), 1)
        fields = fields_of(build("Nursing note", "{{note}}"))
        self.assertEqual(len(at(fields, 1)), 1)
        fields = fields_of(build("<if applicable>", "[Name of the second parent]"))
        self.assertEqual(len(at(fields, 0)), 1)

    def test_a_note_does_not_govern_a_placeholder_after_a_label(self):
        """L1:R2, L3:R3-03: '[If applicable] Surgeon: [surgeon]' - the note governs nothing after 'Surgeon:'."""
        for text, placeholder, label in (("[If applicable] Surgeon: [surgeon]", "[surgeon]", "Surgeon surgeon"),
                                         ("<if applicable> Hospital: [hospital]", "[hospital]", "Hospital hospital"),

                                         ("[IF YES] Type of cancer: [cancer type]", "[cancer type]",
                                          "Type of cancer cancer type"),
                                         ("[IF YES] Date of diagnosis: [date]", "[date]", "Date of diagnosis date")):
            with self.subTest(text=text):
                data = build(text)
                self.assertEqual(spans_of(data), [placeholder])
                self.assertEqual([f["label"] for f in fields_of(data)], [label])
        # a placeholder opening with words that also open what to write is not a note, and governs nothing
        self.assertEqual(spans_of(build("[Where relevant] Referring clinic: [clinic]")), ["[Where relevant]", "[clinic]"])
        # a note-worded placeholder answering a label governs nothing after it either
        self.assertEqual(spans_of(build("Referral details: [if any] [clinic]")), ["[if any]", "[clinic]"])

    def test_wording_for_another_respondent_is_printed(self):
        for text in ("I sleep [My child sleeps] well at night.", "What is your [your child’s] favourite subject?",
                     "The staff helping me [my child] listened to me [us].", "I felt I had [my child had] enough time.",
                     "The advice I [we] needed arrived soon."):
            with self.subTest(text=text):
                self.assertEqual(spans_of(build(text)), [])

    def test_a_second_person_placeholder_after_a_first_person_pronoun_is_a_place_to_write(self):
        """L1:R10: 'We [your organisation] agree' asks for the organisation; it is not wording for another reader."""
        self.assertEqual(spans_of(build("We [your organisation] agree to the terms above.")), ["[your organisation]"])
        self.assertEqual(len(spans_of(build("We [your practice name] confirm the terms above."))), 1)

    def test_bracketed_heading_and_printed_notice(self):
        self.assertEqual(fields_of(build("[PARENT SECTION:]", "[This page intentionally left blank]")), [])

    def test_header_prose_placeholders(self):
        for header, n in (("This leaflet <insert programme title> is funded by the trust.", 0),
                          ("Clinic letter for [patient name] dated [date]", 2)):
            with self.subTest(header=header):
                doc = Document()
                doc.sections[0].header.paragraphs[0].text = header
                doc.add_paragraph("Visit notes")
                out = io.BytesIO()
                doc.save(out)
                self.assertEqual(len(fields_of(out.getvalue())), n)

    def test_grid_row_aside(self):
        def grid(doc, box):
            t = doc.add_table(rows=1, cols=2)
            t.cell(0, 0).text = "pain medicines (tramadol [Zydol], codeine)"
            t.cell(0, 1).text = "☐ Yes ☐ No" if box else "Used in the past month"
        with_box = fields_of(build(lambda doc: grid(doc, True)))
        self.assertFalse([f for f in with_box if f["locator"]["target"].get("shape") == "bracket"])
        without = fields_of(build(lambda doc: grid(doc, False)))
        self.assertTrue([f for f in without if f["locator"]["target"].get("shape") == "bracket"])

    def test_a_bracket_printed_last_in_a_grid_row_is_a_place_to_write(self):
        """L1:R10: 'Other [drug]' beside its Yes/No boxes asks which drug."""
        fields = fields_of(build(table([["Other [drug]", "☐ Yes ☐ No"]])))
        self.assertTrue([f for f in fields if f["locator"]["target"].get("shape") == "bracket"])

    def test_places_to_write_stay(self):
        cases = [("I understand that [Name of referrer] wishes to apply.", 1),
                 ("The applicant confirmed that [he/she] attended.", 1),
                 ("Dear [Insert name of addressee],", 1),
                 ("[Your Address]", 1), ("[Your phone number (if known)]", 1),
                 ("Other carers you may call are: [Name], at [Telephone number].", 2),
                 ("The aim of this treatment is [insert reason].", 1),
                 ("It is licensed to treat [X disease].", 1),
                 ("Name of referrer: [Name of referrer]", 1),
                 ("I, [your name], agree to take part in this programme.", 1),
                 ("We [your practice name] confirm the referral.", 1),
                 ("[IF YES] Date of diagnosis: [date]", 1),
                 ("The visit took place on [Date of visit, e.g. DD/MM/YYYY].", 1),
                 ("The visit on [Date of visit, e.g. DD/MM/YYYY] was routine.", 1),
                 ("<if applicable> The visit on [date] was cancelled.", 1),
                 ("I, [my full name], agree to take part.", 1),
                 # an example inside a placeholder that names what to write is not an author's note (L3:R3-02)
                 ("Your [relationship, e.g. mother] may sign too.", 1),
                 ("Readings from a [insert device here, e.g. a step counter] may be used.", 1)]
        for text, n in cases:
            with self.subTest(text=text):
                self.assertEqual(len(spans_of(build(text))), n)


def bullets(*items):
    return [lambda doc, t=t: doc.add_paragraph("- " + t) for t in items]


class LeadInsAndHeadings(unittest.TestCase):
    """K11: colon-ended text that heads printed content is not a label with an answer space - decided by structure
    (sub-labels, deeper list items, column headers, a signer row), never by the label reading as a sentence."""

    def test_colon_ended_sentences_keep_their_answer_place(self):
        """L1:R3, L3:R3-01, L2:R2-06: a colon-ended label worded like a sentence keeps its answer place whatever
        follows it - another label, a question, a drawn line, prose, a list, nothing - and with a printed gap after its
        colon (a rule reading such labels as lead-ins was removed)."""
        for label, after in (("Reason you are seeking care today:", "Allergies:"),
                             ("Date you first noticed the symptoms:", "Where is the pain located?"),
                             ("If you smoke, how many packs per day:", "Alcohol use:"),
                             ("Hospital where you were treated:", "Dates of admission:"),
                             ("Any other conditions we should know about:", "Signature:"),
                             ("Medications you are currently taking:", "Allergies:"),
                             ("Reason you are seeing the doctor today:", "Allergies:"),
                             ("Reason you are seeking care today:        ", "Allergies:"),
                             ("Date you first noticed the symptoms:\t\t", "Allergies:"),
                             ("Medications you are currently taking:", "Please include vitamins."),
                             ("Medications you are currently taking:", "- Include the dose and how often you take it."),
                             ("Medications you are currently taking:", "______________________"),
                             ("Medications you are currently taking:", ""),
                             ("Please read the following before you sign:", "Name of subject: ____________"),
                             ("Symptoms you have had in the last week:", "- Fever"),
                             ("Have you ever been diagnosed with cancer:", "- Nausea and vomiting are common."),
                             ("If yes, please specify the reason:", "- Nausea and vomiting are common."),
                             ("Name:", "- Nausea and vomiting are common.")):
            with self.subTest(label=label, after=after):
                fields = fields_of(build(label, after) if after else build(label))
                self.assertEqual(len(at(fields, 0)), 1)
        for rows in ([["Reason you are seeking care today:"], ["Allergies:"]], [["Reason you are seeking care today:"]],
                     [["In ten people taking it, two may have:"], ["- a headache after each dose."]]):
            with self.subTest(rows=rows):
                fields = fields_of(build(table(rows)))
                self.assertTrue([f for f in fields if f["locator"]["slot"] == "b/tbl[0]/tr[0]/tc[0]/p[0]"])

    def test_a_signing_label_is_never_a_lead_in(self):
        """L2:R2-06: a long signing label keeps its signature place whatever follows it."""
        for label in ("Signature of the person obtaining consent who has explained the study:",
                      "If the patient is unable to sign, the witness must sign here:"):
            with self.subTest(label=label):
                for after in (("Printed name: ________",), bullets("They explained the risks.", "They answered.")):
                    fields = at(fields_of(build(label, *after)), 0)
                    self.assertEqual(kinds(fields), ["signature"])

    def test_heading_over_typed_bullet_labels(self):
        fields = fields_of(build("Before surgery:", "- Wound status:  ", "- Pain score:  "))
        self.assertEqual(at(fields, 0), [])
        self.assertEqual(len(at(fields, 1)) + len(at(fields, 2)), 2)
        # an item that is a label itself keeps its answer space
        fields = fields_of(build("- Outcome:  ", "  - Improved:  ", "  - Unchanged:  "))
        self.assertEqual([len(at(fields, n)) for n in range(3)], [1, 1, 1])

    def test_a_label_over_one_typed_instruction_keeps_its_answer(self):
        """L1:R7: an instruction bullet under a label is not a block the label heads."""
        fields = fields_of(build("Past surgical history:", "- include dates where known", "", "", "Allergies:"))
        self.assertEqual(len(at(fields, 0)), 1)
        fields = fields_of(build("Current medications:", "- please list them below", "", "Allergies:"))
        self.assertEqual(len(at(fields, 0)), 1)

    def test_list_heading_over_deeper_prose_items(self):
        long_items = ("For studies with one group only, describe every effect that the study team expects, how often it "
                      "happens and how serious it is.", "For studies with several groups, put the effects of each group "
                      "in its own table and explain how the groups differ from each other.")
        data = build(lambda doc: listed(doc, [("Effects seen in each group:", 0)] + [(x, 1) for x in long_items], num=21))
        self.assertEqual(at(fields_of(data), 0), [])
        # deeper items that are labels themselves are not its content
        data = build(lambda doc: listed(doc, [("Effects seen in each group:", 0)] +
                                        [(x[:-1] + ":", 1) for x in long_items], num=27))
        self.assertEqual(len(at(fields_of(data), 0)), 1)
        # items that are labels themselves, and label items of one list level, keep their answer spaces
        data = build(lambda doc: listed(doc, [("Height:", 0), ("Weight:", 0), ("Pulse:", 0)], num=22))
        self.assertEqual([len(at(fields_of(data), n)) for n in range(3)], [1, 1, 1])
        data = build(lambda doc: listed(doc, [("Vital signs:", 0)], num=25),
                     lambda doc: listed(doc, [("Weight: ", 0), ("Pulse: ", 0)], num=26))
        self.assertEqual([len(at(fields_of(data), n)) for n in range(3)], [1, 1, 1])

    def test_a_list_label_over_another_list_or_one_deeper_item_keeps_its_answer(self):
        """L1:R7: 'Patient name:' (one list) over a numbered question (another list) is still answered, and so is a
        label over a single deeper instruction."""
        data = build(lambda doc: listed(doc, [("Patient name:", 0)], num=31),
                     lambda doc: listed(doc, [("Have you been in hospital in the last year?", 0)], num=32))
        self.assertEqual(len(at(fields_of(data), 0)), 1)
        data = build(lambda doc: listed(doc, [("Allergies:", 0), ("Please list drug allergies.", 1)], num=33))
        self.assertEqual(len(at(fields_of(data), 0)), 1)
        data = build(lambda doc: listed(doc, [("Patient name:", 0)], num=34),
                     lambda doc: listed(doc, [("I agree to the plan.", 0), ("I consent to the visit.", 0)], num=35))
        self.assertEqual(len(at(fields_of(data), 0)), 1)

    def test_unclosed_bracketed_instruction(self):
        self.assertEqual(fields_of(build("[FOR FOLLOW-UP VISITS ONLY:", "Record the date of the review.")), [])

    def test_column_header_over_answers(self):
        def answers(doc):
            t = doc.add_table(rows=2, cols=2)
            t.cell(0, 0).text = "Visit"
            t.cell(0, 1).text = "Admission Date:"
            t.cell(1, 0).text = "First visit"
        fields = fields_of(build(answers))
        self.assertFalse([f for f in fields if f["locator"]["slot"].startswith("b/tbl[0]/tr[0]")])
        self.assertTrue([f for f in fields if f["locator"]["slot"] == "b/tbl[0]/tr[1]/tc[1]"])

        def named_below(doc):
            # the answer cell under the header is two rows down; the row between answers with boxes
            t = doc.add_table(rows=3, cols=2)
            t.cell(0, 0).text, t.cell(0, 1).text = "Unit", "Admission Date:"
            t.cell(1, 0).text, t.cell(1, 1).text = "Intensive care", "☐ Yes ☐ No"
            t.cell(2, 0).text = "Step-down"
        fields = fields_of(build(named_below))
        self.assertFalse([f for f in fields if f["locator"]["slot"].startswith("b/tbl[0]/tr[0]")])
        self.assertEqual([f["label"] for f in fields if f["locator"]["slot"] == "b/tbl[0]/tr[2]/tc[1]"],
                         ["Step-down — Admission Date"])

        def one_printed_row(doc):
            # one printed line under a label is not a column of printed values: the label keeps its answer space
            t = doc.add_table(rows=2, cols=1)
            t.cell(0, 0).text, t.cell(1, 0).text = "Allergies:", "Please list all known allergies"
        self.assertEqual([f["label"] for f in fields_of(build(one_printed_row))], ["Allergies"])

        def one_row(doc):
            t = doc.add_table(rows=1, cols=3)
            for n, text in enumerate(("Clinician Name:", "Study:", "Clinic Name:")):
                t.cell(0, n).text = text
        self.assertEqual(len(fields_of(build(one_row))), 3)

    def test_a_label_over_printed_rows_keeps_its_answer(self):
        """L3:R3-04: 'Clinical findings:' over two printed instruction rows is not a column header."""
        fields = fields_of(build(table([["Clinical findings:"], ["Please use block capitals."],
                                        ["Thank you for your referral."]])))
        self.assertEqual([f["label"] for f in fields], ["Clinical findings"])

    def test_section_captions_over_options_signing_rows_and_grids(self):
        def options(doc):
            t = doc.add_table(rows=2, cols=3)
            a = t.cell(0, 0).merge(t.cell(0, 2))
            a.text = "Known conditions:"
            for n, text in enumerate(("Diabetes", "Hypertension", "Asthma")):
                t.cell(1, n).text = text
        self.assertEqual(fields_of(build(options)), [])

        def signing(doc):
            t = doc.add_table(rows=3, cols=3)
            a = t.cell(0, 0).merge(t.cell(0, 2))
            a.text = "Doctor:"
            for n, text in enumerate(("Signature of Doctor", "Print Name", "Date")):
                t.cell(2, n).text = text
        fields = fields_of(build(signing))
        self.assertFalse([f for f in fields if f["locator"]["slot"].startswith("b/tbl[0]/tr[0]")])
        self.assertEqual([(f["kind"], f["locator"]["slot"]) for f in fields if f["kind"] == "signature"],
                         [("signature", "b/tbl[0]/tr[1]/tc[0]")])

        def grid(doc):
            t = doc.add_table(rows=4, cols=3)
            for n, text in enumerate(("Medication", "Dose", "Ongoing:")):
                t.cell(0, n).text = text
        fields = fields_of(build(grid))
        self.assertFalse([f for f in fields if f["locator"]["target"]["type"] == "span"])

    def test_signer_row_heading(self):
        def row(doc, cells):
            t = doc.add_table(rows=1, cols=len(cells))
            for n, text in enumerate(cells):
                t.cell(0, n).text = text
        for name in ("Name:", "Full name:", "Printed name:"):
            with self.subTest(name=name):
                fields = fields_of(build(lambda doc: row(doc, ("Completed by:", name, "Signature:", "Date:"))))
                self.assertEqual(kinds(fields), ["text", "signature", "date"])
        fields = fields_of(build(lambda doc: row(doc, ("Completed by:", "Protocol:"))))
        self.assertEqual([f["label"] for f in fields], ["Completed by", "Protocol"])

    def test_options_that_read_as_sentences_stay_options(self):
        """L1:R4, L3:R3-05: a pain scale, symptoms under a lead-in question and self-rating statements are options."""
        data = build(lambda doc: listed(doc, [("How would you rate your pain today?", 0), ("No pain at all.", 1),
                                              ("Mild pain that does not limit my activity.", 1),
                                              ("Severe pain that stops me from working.", 1)], num=51),
                     "Comments:")
        self.assertIn("choice", kinds(fields_of(data)))
        data = build(lambda doc: listed(doc, [("Symptoms you have noticed in the past week:", 0), ("Fever", 1),
                                              ("Cough", 1)], num=52))
        self.assertIn("choice", kinds(fields_of(data)))
        for items in (("Chest pain on exertion.", "Breathlessness when lying flat."),
                      ("I have no problems walking about.", "I have some problems walking about.",
                       "I am confined to bed.")):
            with self.subTest(items=items):
                data = build(lambda doc: doc.add_paragraph("Which statement best describes you?"),
                             lambda doc: listed(doc, [(x, 0) for x in items], num=53, fmt="lowerLetter"))
                self.assertEqual(kinds(fields_of(data)), ["choice"])
        data = build(lambda doc: doc.add_paragraph("Which arm was treated:"),
                     lambda doc: listed(doc, [("Left", 0), ("Right", 0)], num=24, fmt="lowerLetter"))
        self.assertEqual(kinds(fields_of(data)), ["choice"])


class TableHeadingsAndAnswerLines(unittest.TestCase):
    """K5 (subset) and K15."""

    def test_signing_row_captions_under_a_section_caption(self):
        def grid(doc, caption_line):
            t = doc.add_table(rows=3, cols=3)
            a = t.cell(0, 0).merge(t.cell(0, 2))
            a.text = "Agreement of Young Person"
            for n, text in enumerate(("Signature of Young Person", "Print Name of Young Person", "Date")):
                t.cell(2, n).text = text
            if caption_line:
                t.cell(2, 2).add_paragraph()
        fields = fields_of(build(lambda doc: grid(doc, False)))
        # the signature cell is a signature place; its neighbours keep their own (cell-keyed) answer places
        self.assertEqual([(f["kind"], f["label"], f["locator"]["slot"]) for f in fields],
                         [("signature", "Signature of Young Person", "b/tbl[0]/tr[1]/tc[0]"),
                          ("text", "Print Name of Young Person", "b/tbl[0]/tr[1]/tc[1]"),
                          ("date", "Date", "b/tbl[0]/tr[1]/tc[2]")])
        # a caption's own empty line is spacing: never the date answer of the signing row
        fields = fields_of(build(lambda doc: grid(doc, True)))
        self.assertFalse([f for f in fields if f["locator"]["slot"].startswith("b/tbl[0]/tr[2]")])

    def test_dated_signing_captions_do_not_type_a_date_on_the_signing_cell(self):
        """L2:R2-03: 'Signature/Date' or 'Initials/Date' under a blank cell never makes it a typed date."""
        for captions in (("Signature/Date", "Print Name"), ("Initials/Date", "Print Name"),
                         ("Signature and date", "Relationship", "Time")):
            with self.subTest(captions=captions):
                data = build(table([["Consent of Patient:"] + [""] * (len(captions) - 1), [""] * len(captions),
                                    list(captions)], merge_first=True))
                fields = fields_of(data)
                self.assertFalse([f for f in fields if f["locator"]["slot"] == "b/tbl[0]/tr[1]/tc[0]"
                                  and f["kind"] in FILLABLE])
                out = Document(io.BytesIO(filled(data))).tables[0]
                self.assertEqual(out.cell(1, 0).text, "")

    def test_heading_cell_of_a_repeated_section_header(self):
        """K5 subset: '~** Lower Arm ** | WIDTH (mm) | FLOW (ms)' repeating the first row's section header after rows of
        its own - the coloured cell is that section's heading, not an instruction cell to answer under."""
        for second in ("~** Lower Arm **", "~** Upper Arm **"):
            with self.subTest(second=second):
                fields = fields_of(build(table([["~** Upper Arm **", "WIDTH (mm)", "FLOW (ms)"],
                                                ["Vein at the elbow", "", ""], [second, "WIDTH (mm)", "FLOW (ms)"],
                                                ["Vein at the elbow", "", ""]])))
                self.assertFalse([f for f in fields if f["locator"]["slot"] == "b/tbl[0]/tr[2]/tc[0]"])
                self.assertEqual(len([f for f in fields if f["locator"]["slot"].startswith("b/tbl[0]/tr[3]/")]), 2)

    def test_instruction_cells_in_rows_that_repeat_printed_cells_stay_answers(self):
        """An instruction cell in a row whose other cells repeat the first row's is an answer place unless the row is a
        section header: the first row's cell in its column is guidance ink too, rows of their own lie between, the
        repeated cells are unclaimed printed text, and the cell is not an instruction to write."""
        cases = (([["Item", "Grade", "Notes"], ["~Describe swelling", "Grade", "Notes"],
                   ["~Describe redness", "Grade", "Notes"]], ["b/tbl[0]/tr[1]/tc[0]", "b/tbl[0]/tr[2]/tc[0]"]),
                 ([["~Enter the left value", "mm", "ms"], ["Left", "", ""], ["~Enter the right value", "mm", "ms"],
                   ["Right", "", ""]], None),
                 ([["~Describe each lesion", "Size", "Colour"], ["Lesion 1", "", ""],
                   ["~Describe the largest lesion", "Size", "Colour"], ["Lesion 2", "", ""]], ["b/tbl[0]/tr[2]/tc[0]"]),
                 ([["~** Upper Arm **", "WIDTH (mm)", "FLOW (ms)"], ["~** Lower Arm **", "WIDTH (mm)", "FLOW (ms)"]],
                  ["b/tbl[0]/tr[1]/tc[0]"]),
                 ([["~Describe the left knee", "Yes", "No"], ["Knee", "", ""], ["~Describe the right knee", "Yes", "No"]],
                  ["b/tbl[0]/tr[2]/tc[0]"]),
                 # the first row's cell is printed, not guidance: no section heading pair
                 ([["Item", "Grade", "Notes"], ["~Swelling", "Grade", "Notes"], ["Knee", "", ""],
                   ["~Redness", "Grade", "Notes"]], ["b/tbl[0]/tr[1]/tc[0]", "b/tbl[0]/tr[3]/tc[0]"]),
                 # the repeated cells are answers (Yes/No boxes), not printed column headers
                 ([["~Left knee swelling", "Yes", "No"], ["Knee", "", ""], ["~Right knee swelling", "Yes", "No"]],
                  ["b/tbl[0]/tr[2]/tc[0]"]))
        for rows, appended in cases:
            with self.subTest(rows=rows):
                data = build(table(rows))
                base_like = [f["locator"]["slot"] for f in fields_of(data)
                             if f["locator"]["target"]["type"] in ("cell_append", "cell_replace")
                             and f["locator"]["slot"].endswith("/tc[0]")]
                if appended is None:
                    self.assertEqual(len(base_like), 2)
                else:
                    self.assertEqual([x for x in base_like if x in appended], appended)

    def test_instruction_cells_in_rows_that_repeat_the_header_directly(self):
        """An instruction cell in a row whose other cells repeat the first row's ('~Describe swelling | Grade |
        Notes' under 'Item | Grade | Notes') is an answer place, as before (a repeated-header rule removed it)."""
        fields = fields_of(build(table([["Item", "Grade", "Notes"], ["~Describe swelling", "Grade", "Notes"],
                                        ["~Describe redness", "Grade", "Notes"]])))
        self.assertEqual([f["locator"]["slot"] for f in fields if f["locator"]["target"]["type"] == "cell_append"],
                         ["b/tbl[0]/tr[1]/tc[0]", "b/tbl[0]/tr[2]/tc[0]"])

    def instruction(self, line=None):
        def grid(doc):
            t = doc.add_table(rows=2, cols=2)
            t.cell(0, 0).text, t.cell(0, 1).text = "Item", "Findings"
            t.cell(1, 0).text = "Left knee"
            hint_cell(t.cell(1, 1), "If swollen, describe here")
            if line is not None:
                p = t.cell(1, 1).add_paragraph()
                if line:
                    line(doc, p)
        return build(grid)

    def appended(self, data, answer="Mild effusion"):
        fields = fields_of(data)
        appended = [f for f in fields if f["locator"]["target"]["type"] == "cell_append"]
        self.assertEqual(len(appended), 1)
        out = word.fill(data, fields, {appended[0]["key"]: answer})
        cell = word.SlotIndex(word.open_package(out)).by_id["word/document.xml#b/tbl[0]/tr[1]/tc[1]"].el
        return cell.findall(word.q("w:p"))

    def test_cell_append_uses_the_empty_answer_line(self):
        for line, paragraphs in (("", 2), (None, 2)):
            with self.subTest(empty_line=line is not None):
                paras = self.appended(self.instruction(line))
                self.assertEqual(len(paras), paragraphs)
                self.assertEqual(word.text_of(paras[-1]), "Mild effusion")
                self.assertEqual(word.text_of(paras[0]), "If swollen, describe here")

    def test_a_spacer_line_is_not_the_answer_line(self):
        """L1:R8, L2:R2-04: a line sized, styled or ruled to vanish, or holding a section break, is left alone - the
        answer gets its own paragraph; empty runs on a plain line never lend the answer their properties."""
        def mark(*props):
            def add(doc, p):
                rpr = OxmlElement("w:rPr")
                for tag, val in props:
                    e = OxmlElement(tag)
                    if val is not None:
                        e.set(qn("w:val"), val)
                    rpr.append(e)
                p._p.get_or_add_pPr().append(rpr)
            return add

        def styled(doc, p):
            style = doc.styles.add_style("Row Spacer", WD_STYLE_TYPE.PARAGRAPH)
            style.element.get_or_add_rPr().append(OxmlElement("w:vanish"))
            p.style = style

        def exact(doc, p):
            spacing = OxmlElement("w:spacing")
            spacing.set(qn("w:line"), "20")
            spacing.set(qn("w:lineRule"), "exact")
            p._p.get_or_add_pPr().append(spacing)

        def section(doc, p):
            p._p.get_or_add_pPr().append(OxmlElement("w:sectPr"))

        for name, line in (("tiny mark", mark(("w:sz", "2"), ("w:szCs", "2"))), ("hidden mark", mark(("w:vanish", None))),
                           ("hidden style", styled), ("exact line", exact), ("section break", section)):
            with self.subTest(line=name):
                paras = self.appended(self.instruction(line))
                self.assertEqual(len(paras), 3)
                self.assertEqual(word.text_of(paras[-1]), "Mild effusion")

        def run(tag, **attrs):
            def add(doc, p):
                r = p.add_run("")
                e = OxmlElement(tag)
                for k, v in attrs.items():
                    e.set(qn(k), v)
                r._r.get_or_add_rPr().append(e)
                r._r.append(OxmlElement("w:t"))         # an empty text node, as Word writes it
            return add
        for name, line in (("struck run", run("w:strike")), ("condensed run", run("w:w", **{"w:val": "1"})),
                           ("symbol-font run", run("w:rFonts", **{"w:ascii": "Wingdings", "w:hAnsi": "Wingdings"}))):
            with self.subTest(line=name):
                paras = self.appended(self.instruction(line))
                self.assertEqual(len(paras), 2)
                answer = [r for r in paras[-1].iter(word.R) if word.text_of(r)]
                self.assertEqual(len(answer), 1)
                props = answer[0].find(word.q("w:rPr"))
                self.assertEqual([word.etree.QName(x).localname for x in props], ["color"])
                self.assertEqual(word.text_of(paras[-1]), "Mild effusion")

    def test_a_chosen_option_written_into_an_instruction_cell_gets_its_own_line(self):
        def grid(doc):
            t = doc.add_table(rows=2, cols=2)
            t.cell(0, 0).text, t.cell(0, 1).text = "Finding", "Yes / No"
            t.cell(1, 0).text = "Swelling"
            hint_cell(t.cell(1, 1), "Tick one")
            t.cell(1, 1).add_paragraph()
        data = build(grid)
        fields = fields_of(data)
        self.assertEqual([(f["kind"], f["locator"]["target"].get("write")) for f in fields], [("choice", "option_text")])
        out = word.fill(data, fields, {fields[0]["key"]: "Yes"})
        cell = word.SlotIndex(word.open_package(out)).by_id["word/document.xml#b/tbl[0]/tr[1]/tc[1]"].el
        self.assertEqual([word.text_of(p) for p in cell.findall(word.q("w:p"))], ["Tick one", "", "Yes"])


if __name__ == "__main__":
    unittest.main()
