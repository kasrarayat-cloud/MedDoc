"""PDF adapter behaviour that pypdf 6.21.1, 6.21.2 and 6.21.4 must share. Synthetic forms only.

Each case is a row of docs/rebuild/pypdf-6.21.4.md, built here from a ReportLab text-field form
whose /DR font or outline is edited with pypdf; no PDF is committed and no patient data is used.
Everything runs through the real sandboxed worker, as an upload and an export do.

F2/F3 are refused at INSPECTION on every version, so the outcome is the same and explicit
everywhere. F4 is judged: 6.21.4 drops a malformed bookmark and exports the same pages and answers
as a well-formed copy, so the test pins 6.21.4's export and the earlier versions' refusal.
"""

from pathlib import Path
import tempfile
import unittest

import pypdf
from pypdf import PdfReader, PdfWriter
from pypdf.generic import (ArrayObject, DictionaryObject, NameObject, NullObject, NumberObject,
                           TextStringObject)
from reportlab.pdfgen import canvas

from .engine import glyph_name_read_differently
from .service import DocumentError, fill_template, inspect_template

ANSWER = "Mild symptoms, Amy"
PYPDF = tuple(int(part) for part in pypdf.__version__.split(".")[:3])


def codes(*items):
    """A /Differences array from ints (codes) and strs (glyph names without the slash)."""
    return ArrayObject(NumberObject(item) if isinstance(item, int) else NameObject("/" + item) for item in items)


def encoding(base="/WinAnsiEncoding", differences=None):
    value = DictionaryObject()
    if base is not None:
        value[NameObject("/BaseEncoding")] = NameObject(base) if isinstance(base, str) else base
    if differences is not None:
        value[NameObject("/Differences")] = differences
    return value


class PypdfCompatibilityTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.directory = Path(self.temp.name)
        self.count = 0

    def tearDown(self):
        self.temp.cleanup()

    def path(self, stem):
        self.count += 1
        return self.directory / f"{self.count:02d}-{stem}.pdf"

    def form(self):
        """The ordinary supported shape: one Helvetica 10 text field, ReportLab's own /DR font."""
        path = self.path("form")
        document = canvas.Canvas(str(path))
        document.drawString(20, 780, "Clinical question: Symptoms")
        document.acroForm.textfield(name="Symptoms", tooltip="Symptoms", x=20, y=730, width=300, height=30,
                                    fontName="Helvetica", fontSize=10, maxlen=1000)
        document.showPage()
        document.save()
        return path

    def edited(self, change, stem="edited"):
        """The ordinary form with `change(writer, acro, widget)` applied."""
        writer = PdfWriter(clone_from=str(self.form()))
        acro = writer.root_object["/AcroForm"]
        change(writer, acro, writer.pages[0]["/Annots"][0].get_object())
        path = self.path(stem)
        writer.write(str(path))
        return path

    def with_font_encoding(self, value, stem="encoding"):
        def change(writer, acro, widget):
            font = acro["/DR"]["/Font"]["/Helv"].get_object()
            if value is None:
                del font["/Encoding"]
            else:
                font[NameObject("/Encoding")] = value
        return self.edited(change, stem)

    def f3_font(self, writer):
        """A font that looks like the standard Helvetica and carries F3's array /BaseEncoding."""
        return writer._add_object(DictionaryObject({
            NameObject("/Type"): NameObject("/Font"), NameObject("/Subtype"): NameObject("/Type1"),
            NameObject("/BaseFont"): NameObject("/Helvetica"),
            NameObject("/Encoding"): encoding(ArrayObject([NameObject("/WinAnsiEncoding")])),
        }))

    def assert_refused(self, path, reason):
        with self.assertRaises(DocumentError) as caught:
            inspect_template(path)
        self.assertEqual(caught.exception.code, "unsupported_font", str(caught.exception))
        # The upload page keys its hint on "Helvetica" (core.views.UPLOAD_REFUSAL_HINTS).
        self.assertIn("standard Helvetica font only", str(caught.exception))
        self.assertIn(reason, str(caught.exception))

    def fill(self, path):
        fields = inspect_template(path)["fields"]
        output = self.directory / (path.stem + "-filled.pdf")
        fill_template(path, fields, {field["key"]: ANSWER for field in fields}, output)
        return output

    def painted(self, output):
        """The widget's normal appearance: its font name and the bytes of its text operator."""
        reader = PdfReader(output)
        self.assertEqual(reader.get_form_text_fields(), {"Symptoms": ANSWER})
        stream = reader.pages[0]["/Annots"][0].get_object()["/AP"]["/N"].get_object().get_data()
        font = stream.split(b" Tf", 1)[0].rsplit(b"\n", 1)[-1].split(b" ")[0]
        text = stream.split(b"(", 1)[1].rsplit(b") Tj", 1)[0]
        return font, text

    # F3 -----------------------------------------------------------------------------------------

    def test_f3_a_base_encoding_that_is_not_a_name_is_refused_at_inspection(self):
        # 6.21.4 raised TypeError in every fill, after this upload had been accepted.
        for base in (ArrayObject([NameObject("/WinAnsiEncoding")]),
                     DictionaryObject({NameObject("/Type"): NameObject("/Encoding")})):
            with self.subTest(base=type(base).__name__):
                self.assert_refused(self.with_font_encoding(encoding(base)), "base encoding")

    def test_an_encoding_that_is_neither_a_name_nor_a_dictionary_is_refused(self):
        for value in (ArrayObject([NameObject("/WinAnsiEncoding")]), NumberObject(1),
                      TextStringObject("/WinAnsiEncoding")):
            with self.subTest(value=repr(value)):
                self.assert_refused(self.with_font_encoding(value), "neither a name nor a dictionary")

    # F2 and N1 ----------------------------------------------------------------------------------

    def test_f2_a_letter_named_by_a_character_code_is_refused_at_inspection(self):
        # /uni006d and /u41: 6.21.4 painted nothing at that code (the letter vanished in pdf.js).
        # /uni006D and /u0041 (N1): bytes differ from 6.21.2, and at another code than the
        # letter's own, /uni006D was painted at the wrong width and the letters overlapped.
        for differences in (codes(109, "uni006d"), codes(65, "u41"), codes(200, "uni006d"),
                            codes(109, "uni006D"), codes(65, "u0041"), codes(200, "uni006D"),
                            codes(32, "uni0020"), codes(109, "u+6D"), codes(109, "u0x6d"), codes(109, "u6_d")):
            with self.subTest(differences=[str(item) for item in differences]):
                self.assert_refused(self.with_font_encoding(encoding(differences=differences)),
                                    "character-code glyph name")

    def test_differences_hold_only_codes_from_0_to_255_and_direct_names(self):
        def raw(*items):
            def change(writer, acro, widget):
                font = acro["/DR"]["/Font"]["/Helv"].get_object()
                # A plain str "&/name" stands for an INDIRECT name; PDF objects (strings too) go in as given.
                built = [writer._add_object(NameObject(item[1:])) if type(item) is str else item for item in items]
                font[NameObject("/Encoding")] = encoding(differences=ArrayObject(built))
            return self.edited(change, "raw")

        cases = {
            # pdf.js painted none of the answer: the string makes it reject the font.
            "string": raw(NumberObject(200), TextStringObject("/A")),
            # 6.21.4 reads the referenced /uni006d as 'm'; pdf.js painted no 'm'.
            "indirect name": raw(NumberObject(109), "&/uni006d"),
            # wraps to code 200 inside pypdf only: "Amy" was painted as "Èmy" on every version.
            "negative code": raw(NumberObject(-56), NameObject("/A")),
            "code above 255": raw(NumberObject(256), NameObject("/A")),
            "null": raw(NumberObject(65), NullObject()),
        }
        for label, path in cases.items():
            with self.subTest(label):
                self.assert_refused(path, "character difference")
        self.assert_refused(self.with_font_encoding(encoding(differences=NumberObject(1))), "not a list")

    def test_glyph_names_every_version_paints_alike_are_kept(self):
        # Nothing here moves an answer letter on any version, so each is exported as before.
        plain = {
            "ReportLab's own encoding": "unchanged",
            "WinAnsi by name": NameObject("/WinAnsiEncoding"),
            "no encoding": None,
            "dictionary without a base": encoding(None, codes(39, "quotesingle", 96, "grave")),
            "named base with glyph-list names": encoding(differences=codes(39, "quotesingle", 96, "grave")),
            # character-code names that are not answer characters never reach the painter
            "spec name for a letter no answer holds": encoding(differences=codes(233, "uni00E9")),
            "lower-case name for a letter no answer holds": encoding(differences=codes(200, "uni00e9")),
            "suffixed name 6.21.4 does not read": encoding(differences=codes(200, "uni006D.alt")),
        }
        for label, value in plain.items():
            with self.subTest(label):
                path = self.form() if value == "unchanged" else self.with_font_encoding(value)
                self.assertEqual(self.painted(self.fill(path)), (b"/Helv", ANSWER.encode("ascii")))
        # A glyph-list name at another code: 'A' is painted at 200 by its own name on every version.
        remapped = self.with_font_encoding(encoding(differences=codes(109, "m", 200, "A")))
        self.assertEqual(self.painted(self.fill(remapped)), (b"/Helv", ANSWER.encode("ascii").replace(b"A", b"\xc8")))

    def test_the_rule_is_about_answer_characters_not_spelling(self):
        self.assertTrue(glyph_name_read_differently("uni006d"))
        self.assertTrue(glyph_name_read_differently("uni006D"))
        self.assertTrue(glyph_name_read_differently("u41"))
        self.assertTrue(glyph_name_read_differently("uni007E"))
        self.assertTrue(glyph_name_read_differently("u+6D"))       # int() takes a sign, so 6.21.4 does too
        self.assertFalse(glyph_name_read_differently("uniF"))      # read as U+000F, which no answer holds
        self.assertFalse(glyph_name_read_differently("uni001F"))
        self.assertFalse(glyph_name_read_differently("uni007F"))
        self.assertFalse(glyph_name_read_differently("uni00e9"))
        self.assertFalse(glyph_name_read_differently("u1F600"))
        self.assertFalse(glyph_name_read_differently("ue"))         # the only glyph-list name that parses
        self.assertFalse(glyph_name_read_differently("uacute"))
        self.assertFalse(glyph_name_read_differently("u-41"))       # chr() refuses it on 6.21.4 as well
        self.assertFalse(glyph_name_read_differently("m"))
        self.assertFalse(glyph_name_read_differently("uni006D.alt"))

    # The painter, not the check, picks the font ----------------------------------------------------

    def test_every_font_the_painter_can_select_is_checked(self):
        # Each left an ordinary /Helv for the old check while 6.21.4's painter used the F3 font,
        # and every fill failed after the upload had been accepted.
        def widget_dr(writer, acro, widget):
            widget[NameObject("/DR")] = DictionaryObject({NameObject("/Font"): DictionaryObject(
                {NameObject("/Helv"): self.f3_font(writer)})})

        def appearance(text, rename=False):
            def change(writer, acro, widget):
                fonts = acro["/DR"]["/Font"]
                if rename:
                    fonts[NameObject("/Good")] = fonts["/Helv"]
                    fonts[NameObject("/Helv")] = self.f3_font(writer)
                else:
                    fonts[NameObject("/Bad")] = self.f3_font(writer)
                widget[NameObject("/DA")] = TextStringObject(text)
            return change

        for label, change in {"widget /DR": widget_dr,
                              "second Tf": appearance("/Helv 10 Tf /Bad 10 Tf 0 g"),
                              "Tf after a comment": appearance("/Helv 10 Tf %c\n/Bad 10 Tf 0 g"),
                              "unparsable /DA tail falls back to /Helv": appearance("/Good 10 Tf 0 g ]", rename=True),
                              }.items():
            with self.subTest(label):
                self.assert_refused(self.edited(change), "base encoding")

    def test_a_font_no_field_can_select_is_not_judged(self):
        # Only fonts used by a field are checked: an unused /DR entry keeps the ordinary verdict.
        def change(writer, acro, widget):
            acro["/DR"]["/Font"][NameObject("/Unused")] = self.f3_font(writer)
        self.assertEqual(self.painted(self.fill(self.edited(change))), (b"/Helv", ANSWER.encode("ascii")))

    # F4 -----------------------------------------------------------------------------------------

    def outline(self, shape):
        def change(writer, acro, widget):
            page = writer.pages[0].indirect_reference
            root = DictionaryObject({NameObject("/Type"): NameObject("/Outlines"), NameObject("/Count"): NumberObject(2)})
            root_ref = writer._add_object(root)
            items = []
            for title in ("Section one", "Section two"):
                item = DictionaryObject({NameObject("/Title"): TextStringObject(title), NameObject("/Parent"): root_ref,
                                         NameObject("/Dest"): ArrayObject([page, NameObject("/XYZ"), NullObject(),
                                                                           NullObject(), NullObject()])})
                items.append((item, writer._add_object(item)))
            (first, first_ref), (second, second_ref) = items
            first[NameObject("/Next")] = second_ref
            second[NameObject("/Prev")] = first_ref
            root.update({NameObject("/First"): first_ref, NameObject("/Last"): second_ref})
            writer.root_object[NameObject("/Outlines")] = root_ref
            if shape == "not a dictionary":
                first[NameObject("/Next")] = writer._add_object(NumberObject(7))
            elif shape == "null /Next":
                first[NameObject("/Next")] = NullObject()
        return self.edited(change, "outline")

    def test_f4_a_malformed_bookmark_is_dropped_and_the_pages_and_answers_are_kept(self):
        reference = PdfReader(self.fill(self.outline("well formed")))
        self.assertEqual([item.title for item in reference.outline], ["Section one", "Section two"])
        for shape in ("not a dictionary", "null /Next"):
            with self.subTest(shape):
                original = self.outline(shape)
                if PYPDF < (6, 21, 4):
                    # Recorded behaviour of 6.21.1 and 6.21.2: accepted, then the export failed.
                    with self.assertRaises(DocumentError) as caught:
                        self.fill(original)
                    self.assertEqual(caught.exception.code, "invalid_document")
                    continue
                exported = PdfReader(self.fill(original))
                # The judgement: only the unreachable bookmark goes; everything a reader sees stays.
                self.assertEqual([item.title for item in exported.outline], ["Section one"])
                self.assertEqual(exported.get_form_text_fields(), {"Symptoms": ANSWER})
                self.assertEqual(len(exported.pages), len(reference.pages))
                for page, expected in zip(exported.pages, reference.pages):
                    self.assertEqual(page.get_contents().get_data(), expected.get_contents().get_data())
                    self.assertEqual(page.extract_text(), expected.extract_text())
                    appearance = lambda p: p["/Annots"][0].get_object()["/AP"]["/N"].get_object().get_data()
                    self.assertEqual(appearance(page), appearance(expected))


if __name__ == "__main__":
    unittest.main()
