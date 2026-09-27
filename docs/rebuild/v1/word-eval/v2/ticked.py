"""Word evaluation harness v2: the `ticked` check (docs/rebuild/v1/word-harness-v2.md, declared in 64b1491d).

An INDEPENDENT reader of ticked / shown options in an exported .docx. It uses zipfile and lxml (plus the standard
library) only and never imports the candidate engine (word_v3) or core/*. For every ground-truth answer area of kind
choice, multi_choice, checkbox or checkbox_group it reads the EXPORTED package at the ground-truth slots, and the
ORIGINAL at the same slots.

    check_document(original_bytes, export_bytes, groundtruth, chosen) -> {"passed": bool, "questions": [...]}

`chosen` maps a ground-truth area id to what the profile chose for it:
    absent or None        the profile left the question unanswered
    [i, j, ...]           indices into the area's ground-truth options (a checkbox: [0] ticked, [] answered unticked)
    {"unknown": reason}   the chosen set could not be established -> the question is UNVERIFIABLE (fail closed)
    {"mapping": reason}   v2.1 reading 1: no candidate field matches the question, or the matched field did not accept
                          the ground-truth label -> the question FAILS (a mapping failure of the candidate)

Every question gets a verdict pass | fail | unverifiable and a reason. The document passes only when every question
passes: an unverifiable question fails the document (rule 4). Nothing is skipped.

v2.1 (word-harness-v2.md, "v2.1 - seven readings"): 1 the chosen answer in ground-truth terms (answering.py builds it;
this file only reads `chosen`, including the "mapping" failure); 2 printed options with no box are read by the inserted
mark in both association modes; 3 Wingdings / Wingdings 2 characters stored as text read through the w:sym table; 4
radio circles are boxes; 5 a box tied to another question's option is judged by that question only; 6 an answer
written as text into a cell empty in the original is the "cell text" box kind; 7 legacy dropdowns unchanged. Each place
is marked "v2.1 reading N:" below.

Where the declaration is silent the reading is FAIL-CLOSED; every such place is marked "FAIL-CLOSED:" below and is
listed in README.md.
"""
import difflib
import io
import re
import unicodedata
import zipfile

from lxml import etree

VERSION = "ticked-v2.1"

W = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
W14 = "http://schemas.microsoft.com/office/word/2010/wordml"
MC = "http://schemas.openxmlformats.org/markup-compatibility/2006"
DML = "http://schemas.openxmlformats.org/drawingml/2006/main"


def w(tag):
    return "{%s}%s" % (W, tag)


def w14(tag):
    return "{%s}%s" % (W14, tag)


P, R, T, TBL, TR, TC, SDT = w("p"), w("r"), w("t"), w("tbl"), w("tr"), w("tc"), w("sdt")
SDTPR, SDTCONTENT, FLDCHAR, INSTR, SYM = w("sdtPr"), w("sdtContent"), w("fldChar"), w("instrText"), w("sym")
TXBX, FALLBACK = w("txbxContent"), "{%s}Fallback" % MC
CHOICE_KINDS = ("choice", "multi_choice", "checkbox", "checkbox_group")

# ─── THE GLYPH TABLE (fixed; rule 1, "printed glyph") ────────────────────────────────────────────────────────────
# Readable Unicode box characters. True = ticked, False = unticked.
UNICODE_GLYPHS = {"☐": False,      # ☐ BALLOT BOX
                  "☒": True,       # ☒ BALLOT BOX WITH X
                  "☑": True,       # ☑ BALLOT BOX WITH CHECK
                  "✓": True,       # ✓ CHECK MARK
                  "✔": True,       # ✔ HEAVY CHECK MARK
                  # v2.1 reading 4: radio circles are boxes. FAIL-CLOSED: only these three characters; ◯ ⚪ ⚫ ◎ and
                  # the combining enclosing circle U+20DD stay recognised-but-unreadable (BOX_LIKE below)
                  "○": False,      # ○ WHITE CIRCLE
                  "◉": True,       # ◉ FISHEYE
                  "●": True}       # ● BLACK CIRCLE
# Readable symbol-font codes (w:char; F0xx and the plain byte both accepted) in the two fonts the declaration names.
# v2.0: each entry checked by rendering it as a w:sym through LibreOffice's Wingdings recoding (gotenberg:8).
# v2.1 reading 3: the SAME table reads Wingdings / Wingdings 2 characters stored as TEXT (w:t); every entry, old and
# new, was re-rendered in five storage forms (w:sym; w:t U+F0xx and w:t plain byte, each with rFonts on all four slots
# and on ascii/hAnsi only) in a package whose font table declares both fonts with charset 02, and drew the same glyph
# in all five (symcheck/wingdings-wt-render-1.png, text layer symcheck/text-layer.json: every form drawn in
# OpenSymbol). v2.1 reading 4 adds the radio circles, each checked the same way.
# FAIL-CLOSED: Wingdings 0x78 (⌧) and Wingdings 2 0x2A (☐) render as fallback glyphs in every form, so they stay OUT
# (unreadable). Circles that render as something other than ○ / ● (Wingdings 0xA2 and Wingdings 2 0x9B heavy rings,
# Wingdings 2 0x9C heavy ring with a dot, Wingdings 0xA4 ◉ which renders as a fallback glyph) are OUT as well.
SYM_GLYPHS = {
    "wingdings": {0x6F: False,    # □ white square
                  0x71: False,    # ❑ lower-right shadowed white square
                  0x72: False,    # ❒ upper-right shadowed white square
                  0xA8: False,    # ◻ ballot box
                  0xFC: True,     # ✓ check mark
                  0xFD: True,     # ☒ ballot box with X
                  0xFE: True,     # ☑ ballot box with check
                  0xA1: False,    # ○ white circle (v2.1 reading 4)
                  0x6C: True},    # ● black circle (v2.1 reading 4)
    "wingdings 2": {0xA3: False,  # □ white square
                    0x50: True,   # ✓ check mark
                    0x51: True,   # ☒ ballot box with X
                    0x52: True,   # ☑ ballot box with check
                    0x53: True,   # ☒ ballot box with bold X
                    0x54: True,   # ☒ ballot box with X (variant)
                    0x81: False,  # ○ small white circle (v2.1 reading 4)
                    0x99: False,  # ○ white circle (v2.1 reading 4)
                    0x9A: False,  # ○ white circle (v2.1 reading 4)
                    0x97: True,   # ● black circle (v2.1 reading 4)
                    0x98: True},  # ● large black circle (v2.1 reading 4)
}
# Characters RECOGNISED as boxes but not in the table: a box of UNREADABLE state ("any glyph outside the table is
# unreadable"). FAIL-CLOSED: recognition is deliberately broader than the table, so a box outside the table is never
# taken for plain text (which would let its option be read by the inserted mark beside an unread box).
BOX_LIKE = set("□■▢▣▤▥▦▧▨▩▪▫◻◼◽◾⬜⬛❏❐❑❒◯◎◌◍❍⚪⚫◇◆◊⊠⊡⊞⊟✅❎✗✘✕✖√☓⍻⮽"
               "⃝⃞⃟⃢⃣"          # combining enclosing circle / square / diamond / screen / keycap
               "\U0001F5F3\U0001F5F4\U0001F5F5\U0001F5F6\U0001F5F7\U0001F5F8\U0001F5F9\U0001F5C6\U0001F5C7"
               "\U0001F78E\U0001F78F\U0001F790\U0001F791\U0001F792\U0001F793\U0001F794")
# Fonts whose characters are pictures. A character carried as TEXT (w:t) in one of these fonts is a glyph (a box);
# v2.1 reading 3: it is READ through SYM_GLYPHS only when its drawing font is Wingdings / Wingdings 2 without doubt
# (text_symbol_glyph); FAIL-CLOSED: every other symbol-font text character is a glyph of UNREADABLE state.
SYMBOL_FONT_NAMES = {"symbol", "webdings", "marlett", "mt extra", "ms outlook", "bookshelf symbol 7", "zapfdingbats",
                     "zapf dingbats", "itc zapf dingbats", "monotype sorts", "dingbats"}
SYMBOL_FONT_PREFIXES = ("wingdings",)
# Rule 1, "a cell mark".
CELL_MARKS = {"X", "x", "✓", "✔", "☒"}
# The inserted mark (rule 1): exactly this character.
INSERTED_MARK = "☒"
# Field instructions that draw from the instruction text (otherwise invisible). FAIL-CLOSED: an unreadable glyph.
DRAWING_FIELD = re.compile(r"^\s*(?:SYMBOL|MACROBUTTON|EQ)\b", re.I)


def symbol_fonts_for(fonts, c):
    """The symbol fonts a character would be drawn in: ASCII in the ascii font; other characters in hAnsi, plus
    eastAsia under an eastAsia hint or for an East Asian character, plus cs for complex-script runs. FAIL-CLOSED: a
    private-use character is checked against every font of the run."""
    o = ord(c)
    if 0xE000 <= o <= 0xF8FF:
        names = [fonts.get(k) for k in ("ascii", "hAnsi", "eastAsia", "cs")]
    elif o < 0x80:
        names = [fonts.get("ascii")]
    else:
        names = [fonts.get("hAnsi")]
        if fonts.get("hint") == "eastAsia" or 0x2E80 <= o <= 0x9FFF or 0xAC00 <= o <= 0xD7AF or 0xF900 <= o <= 0xFAFF \
                or 0xFF00 <= o <= 0xFFEF:
            names.append(fonts.get("eastAsia"))
    if fonts.get("complex"):
        names.append(fonts.get("cs"))
    return {n for n in names if is_symbol_font(n)}


def is_symbol_font(name):
    n = (name or "").strip().lower()
    return bool(n) and (n in SYMBOL_FONT_NAMES or n.startswith(SYMBOL_FONT_PREFIXES))


def _east_asian(o):
    return 0x2E80 <= o <= 0x9FFF or 0xAC00 <= o <= 0xD7AF or 0xF900 <= o <= 0xFAFF or 0xFF00 <= o <= 0xFFEF


def drawing_slots(fonts, c):
    """v2.1 reading 3: the rFonts slots that can draw a text character: ascii AND hAnsi (Word draws ASCII in ascii and
    other characters, private-use included, in hAnsi; LibreOffice draws both in its Western font, read from ascii),
    plus eastAsia under an eastAsia hint or for an East Asian character, plus cs in a complex-script run. FAIL-CLOSED:
    ascii and hAnsi are both required whatever the character, so a run whose two Latin slots name different fonts is
    never read."""
    slots = ["ascii", "hAnsi"]
    if fonts.get("hint") == "eastAsia" or _east_asian(ord(c)):
        slots.append("eastAsia")
    if fonts.get("complex"):
        slots.append("cs")
    return slots


def text_symbol_glyph(pkg, fonts, c, symbol_fonts):
    """v2.1 reading 3: a Wingdings / Wingdings 2 character stored as text, read through the w:sym table keyed by the
    run's font and the character code (U+F0xx or the plain byte). FAIL-CLOSED -> a glyph of unreadable state when: the
    drawing slots do not all name one font; that font is not Wingdings / Wingdings 2; the code is outside the table; or
    the package's font table does not declare that font a symbol font (w:charset 02) - the configuration every entry
    was render-checked in (without it LibreOffice draws a fallback glyph)."""
    o = ord(c)
    desc = "U+%04X in symbol font %s (w:t)" % (o, "/".join(sorted(symbol_fonts)))
    names = {(fonts.get(s) or "").strip().lower() for s in drawing_slots(fonts, c)}
    if len(names) != 1:
        return Tok("glyph", ch=c, state=None, desc="%s: its drawing font slots name %s" % (desc, " / ".join(sorted(repr(n) for n in names))))
    font = names.pop()
    table = SYM_GLYPHS.get(font)
    low = o - 0xF000 if 0xF000 <= o <= 0xF0FF else (o if o <= 0xFF else None)
    if table is None or low is None or low not in table:
        return Tok("glyph", ch=c, state=None, desc="%s outside the glyph table" % desc)
    if not pkg.symbol_charset(font):
        return Tok("glyph", ch=c, state=None, desc="%s: the font table does not declare %r a symbol font (charset 02)" % (desc, font))
    return Tok("glyph", ch=c, state=table[low], desc="w:t %s %02X" % (font, low))


def ws(s):
    return re.sub(r"\s+", " ", s or "").strip()


# ─── package ─────────────────────────────────────────────────────────────────────────────────────────────────────

PARSER = etree.XMLParser(resolve_entities=False, no_network=True, huge_tree=False, load_dtd=False,
                         remove_blank_text=False)


class Package:
    def __init__(self, data):
        self.zip = zipfile.ZipFile(io.BytesIO(data))
        self.names = set(self.zip.namelist())
        self._trees, self._alive, self._pos = {}, {}, {}
        self._fonts = None

    def tree(self, part):
        if part not in self._trees:
            if part not in self.names:
                raise KeyError(part)
            root = etree.fromstring(self.zip.read(part), PARSER)
            self._trees[part] = root
            # ⚠️ keep every element proxy alive: lxml re-creates proxies on access and id() of a collected proxy is
            # reused by another element, which would corrupt every id()-keyed set below
            self._alive[part] = list(root.iter())
            self._pos[part] = {id(x): i for i, x in enumerate(self._alive[part])}
        return self._trees[part]

    def pos(self, part, el):
        self.tree(part)
        return self._pos[part].get(id(el), -1)

    @property
    def fonts(self):
        if self._fonts is None:
            self._fonts = FontResolver(self)
        return self._fonts

    @property
    def numbering(self):
        if getattr(self, "_numbering", None) is None:
            self._numbering = Numbering(self)
        return self._numbering

    def symbol_charset(self, font):
        """v2.1 reading 3: True when word/fontTable.xml declares `font` (name compared case-insensitively) with
        w:charset 02 and does not declare it otherwise. FAIL-CLOSED: no font table, no entry, or a second entry of that
        name with another charset -> False."""
        if getattr(self, "_charsets", None) is None:
            self._charsets = {}
            try:
                root = self.tree("word/fontTable.xml")
            except (KeyError, etree.XMLSyntaxError):
                root = None
            if root is not None:
                for f in root.findall(w("font")):
                    cs = f.find(w("charset"))
                    val = (cs.get(w("val")) or "").strip().upper() if cs is not None else ""
                    self._charsets.setdefault((f.get(w("name")) or "").strip().lower(), set()).add(val)
        return self._charsets.get((font or "").strip().lower()) == {"02"}


class Numbering:
    """The list label Word prints before a numbered / bulleted paragraph (numbering.xml): a bullet that is a box is a
    printed glyph like any other. numPr is read from the paragraph, else from its style chain. FAIL-CLOSED: a numPr
    that cannot be resolved to a level, or a picture bullet, is a glyph of unreadable state."""

    def __init__(self, pkg):
        self.pkg, self.abstract, self.nums, self.styles = pkg, {}, {}, {}
        try:
            root = pkg.tree("word/numbering.xml")
        except (KeyError, etree.XMLSyntaxError):
            root = None
        if root is not None:
            for a in root.findall(w("abstractNum")):
                self.abstract[a.get(w("abstractNumId"))] = a
            for n in root.findall(w("num")):
                an = n.find(w("abstractNumId"))
                over = {}
                for o in n.findall(w("lvlOverride")):
                    lv = o.find(w("lvl"))
                    if lv is not None:
                        over[o.get(w("ilvl"))] = lv
                self.nums[n.get(w("numId"))] = (an.get(w("val")) if an is not None else None, over)
        try:
            for s in pkg.tree("word/styles.xml").findall(w("style")):
                self.styles[s.get(w("styleId"))] = s
        except (KeyError, etree.XMLSyntaxError):
            pass

    def _style_numpr(self, sid):
        seen = set()
        while sid and sid in self.styles and sid not in seen:
            seen.add(sid)
            ppr = self.styles[sid].find(w("pPr"))
            if ppr is not None and ppr.find(w("numPr")) is not None:
                return ppr.find(w("numPr"))
            b = self.styles[sid].find(w("basedOn"))
            sid = b.get(w("val")) if b is not None else None
        return None

    def _level(self, num_id, ilvl, depth=0):
        if num_id not in self.nums or depth > 3:
            return None
        aid, over = self.nums[num_id]
        if ilvl in over:
            return over[ilvl]
        a = self.abstract.get(aid)
        if a is None:
            return None
        for lv in a.findall(w("lvl")):
            if lv.get(w("ilvl")) == ilvl:
                return lv
        link = a.find(w("numStyleLink"))
        if link is not None:
            np_ = self._style_numpr(link.get(w("val")))
            nid = np_.find(w("numId")) if np_ is not None else None
            if nid is not None:
                return self._level(nid.get(w("val")), ilvl, depth + 1)
        return None

    def bullet_tokens(self, p):
        if p.tag != P:
            return []
        ppr = p.find(w("pPr"))
        np_ = ppr.find(w("numPr")) if ppr is not None else None
        if np_ is None and ppr is not None and ppr.find(w("pStyle")) is not None:
            np_ = self._style_numpr(ppr.find(w("pStyle")).get(w("val")))
        if np_ is None:
            return []
        nid, il = np_.find(w("numId")), np_.find(w("ilvl"))
        nid = nid.get(w("val")) if nid is not None else None
        il = il.get(w("val")) if il is not None and il.get(w("val")) else "0"
        if nid in (None, "0"):
            return []
        lv = self._level(nid, il)
        if lv is None:
            return [Tok("glyph", state=None, desc="a list label that cannot be resolved (numId %s level %s)" % (nid, il))]
        if lv.find(w("lvlPicBulletId")) is not None:
            return [Tok("picture", state=None, desc="a picture list bullet (unreadable as a box)")]
        text = lv.find(w("lvlText"))
        text = re.sub(r"%\d", "", text.get(w("val")) or "") if text is not None else ""
        fonts = self.pkg.fonts.run_fonts(None, None, rpr=lv.find(w("rPr")))
        out = []
        for c in text:
            g = glyph_for_char(c, fonts, self.pkg)
            if g is not None:
                g.desc = "list bullet: " + g.desc
                out.append(g)
        return out


class FontResolver:
    """The fonts a run is drawn in: direct w:rFonts, then the character style chain, then the paragraph style chain
    (or the default paragraph style), then the document defaults; theme references resolved from theme1.xml.
    FAIL-CLOSED: a run is a symbol-font run when ANY of its resolved ascii / hAnsi / eastAsia / cs fonts is one."""
    ATTRS = ("ascii", "hAnsi", "eastAsia", "cs")

    def __init__(self, pkg):
        self.styles, self.default_para, self.doc_defaults, self.theme, self._rpr = {}, None, {}, {}, {}
        try:
            th = pkg.tree("word/theme/theme1.xml")
            for which in ("major", "minor"):
                f = th.find(".//{%s}%sFont" % (DML, which))
                if f is None:
                    continue
                for sub, key in (("latin", "HAnsi"), ("ea", "EastAsia"), ("cs", "Bidi")):
                    e = f.find("{%s}%s" % (DML, sub))
                    if e is not None:
                        self.theme[which + key] = e.get("typeface") or ""
                self.theme[which + "Ascii"] = self.theme.get(which + "HAnsi", "")
        except (KeyError, etree.XMLSyntaxError):
            pass
        try:
            st = pkg.tree("word/styles.xml")
        except (KeyError, etree.XMLSyntaxError):
            return
        d = st.find("%s/%s/%s/%s" % (w("docDefaults"), w("rPrDefault"), w("rPr"), w("rFonts")))
        if d is not None:
            self.doc_defaults = self._fonts_of(d)
        for s in st.findall(w("style")):
            based = s.find(w("basedOn"))
            rf = s.find("%s/%s" % (w("rPr"), w("rFonts")))
            self.styles[s.get(w("styleId"))] = (based.get(w("val")) if based is not None else None,
                                                self._fonts_of(rf) if rf is not None else {})
            self._rpr[s.get(w("styleId"))] = (s.find(w("rPr")), based.get(w("val")) if based is not None else None)
            if s.get(w("type")) == "paragraph" and s.get(w("default")) in ("1", "true"):
                self.default_para = s.get(w("styleId"))
        self._cache = {}

    def style_hidden(self, sid):
        seen = set()
        while sid and sid not in seen and sid in self._rpr:
            seen.add(sid)
            rpr, based = self._rpr[sid]
            if rpr is not None and (_on(rpr.find(w("vanish"))) or _on(rpr.find(w("specVanish")))):
                return True
            sid = based
        return False

    def _fonts_of(self, rf):
        out = {}
        for a in self.ATTRS:
            th = rf.get(w(a + "Theme"))
            if th:
                out[a] = self.theme.get(th, "")
            elif rf.get(w(a)):
                out[a] = rf.get(w(a))
        return out

    def _chain(self, sid):
        out, seen = {}, set()
        while sid and sid not in seen and sid in self.styles:
            seen.add(sid)
            based, fonts = self.styles[sid]
            for k, v in fonts.items():
                out.setdefault(k, v)
            sid = based
        return out

    def run_fonts(self, run, para, rpr=None):
        got = {}
        if rpr is None:
            rpr = run.find(w("rPr")) if run is not None else None
        if rpr is not None:
            rf = rpr.find(w("rFonts"))
            if rf is not None:
                got.update(self._fonts_of(rf))
                if rf.get(w("hint")):
                    got["hint"] = rf.get(w("hint"))
            if rpr.find(w("rtl")) is not None or rpr.find(w("cs")) is not None:
                got["complex"] = "1"
            rs = rpr.find(w("rStyle"))
            if rs is not None:
                for k, v in self._chain(rs.get(w("val"))).items():
                    got.setdefault(k, v)
        pstyle = self.default_para
        if para is not None and para.tag == P:
            ppr = para.find(w("pPr"))
            ps = ppr.find(w("pStyle")) if ppr is not None else None
            if ps is not None:
                pstyle = ps.get(w("val"))
        for k, v in self._chain(pstyle).items():
            got.setdefault(k, v)
        for k, v in self.doc_defaults.items():
            got.setdefault(k, v)
        return got


# ─── slots: the ground-truth slot grammar of ooxml_slots.py, re-implemented ─────────────────────────────────────

SEG = re.compile(r"^([a-z]+)\[(\d+)\]$")


class SlotError(Exception):
    pass


def _ffdata_begins(p):
    """Every field-begin run carrying w:ffData under p, in document order (the slot tool counts them over p.iter)."""
    out = []
    for r in p.iter(R):
        fc = r.find(FLDCHAR)
        if fc is not None and fc.get(w("fldCharType")) == "begin" and fc.find(w("ffData")) is not None:
            out.append(r)
    return out


def _txbx_contents(p):
    skip = {id(x) for fb in p.iter(FALLBACK) for x in fb.iter()}
    return [t for t in p.iter(TXBX) if id(t) not in skip]


def resolve(pkg, slot):
    """'<part>#<path>' -> (part, element, kind); kind in b | hf | p | tbl | tr | tc | sdt | ff | txbx."""
    part, _, path = slot.partition("#")
    segs = path.split("/")
    if segs and segs[-1] == "glyphs":
        segs = segs[:-1]
    try:
        root = pkg.tree(part)
    except (KeyError, etree.XMLSyntaxError) as e:
        raise SlotError("part %s unreadable (%s)" % (part, e))
    if not segs or segs[0] not in ("b", "hf"):
        raise SlotError("slot root %r" % (segs[:1],))
    cur, kind = (root.find(w("body")), "b") if segs[0] == "b" else (root, "hf")
    if cur is None:
        raise SlotError("no body")
    for seg in segs[1:]:
        m = SEG.match(seg)
        if not m:
            raise SlotError("segment %r" % seg)
        name, i = m.group(1), int(m.group(2))
        try:
            if kind in ("b", "hf", "tc", "sdt", "txbx") and name in ("p", "tbl", "sdt"):
                host = cur.find(SDTCONTENT) if kind == "sdt" else cur
                if host is None:
                    raise IndexError
                cur, kind = host.findall(w(name))[i], name
            elif kind == "tbl" and name == "tr":
                cur, kind = cur.findall(TR)[i], "tr"
            elif kind == "tr" and name in ("tc", "sdt"):
                cur, kind = cur.findall(w(name))[i], name
            elif kind == "p" and name == "sdt":
                cur, kind = cur.findall(SDT)[i], "sdt"
            elif kind == "p" and name == "ff":
                cur, kind = _ffdata_begins(cur)[i], "ff"
            elif kind == "p" and name == "txbx":
                cur, kind = _txbx_contents(cur)[i], "txbx"
            else:
                raise IndexError
        except IndexError:
            raise SlotError("does not resolve at %r" % seg)
    return part, cur, kind


# ─── tokens: what a paragraph shows, one token per character and per box ────────────────────────────────────────

class Tok:
    __slots__ = ("k", "ch", "el", "src", "state", "desc", "hidden")

    def __init__(self, k, ch="", el=None, src=None, state=None, desc="", hidden=False):
        self.k, self.ch, self.el, self.src, self.state, self.desc, self.hidden = k, ch, el, src, state, desc, hidden

    KEYS = {"glyph": "\x01G", "sdtcb": "\x01C", "sdtdd": "\x01D", "ffcb": "\x01F", "ffdd": "\x01E", "fftext": "\x01T",
            "picture": "\x01P", "cell": "\x01L"}

    @property
    def key(self):
        return self.ch if self.k == "t" else self.KEYS[self.k]

    @property
    def is_box(self):
        return self.k in ("glyph", "sdtcb", "ffcb", "picture", "cell")

    @property
    def is_control(self):
        return self.k in ("sdtdd", "ffdd")


SKIP = {w("pPr"), w("rPr"), w("del"), w("moveFrom"), FALLBACK, SDTPR, w("sdtEndPr"), w("proofErr"),
        w("bookmarkStart"), w("bookmarkEnd"), w("commentRangeStart"), w("commentRangeEnd"), w("permStart"),
        w("permEnd"), w("tblPr"), w("trPr"), w("tcPr"), w("tblGrid"), w("tblPrEx")}
PICTURES = (w("drawing"), w("pict"), w("object"))


def sdt_type(sdt):
    pr = sdt.find(SDTPR)
    if pr is None:
        return "richText"
    if pr.find(w14("checkbox")) is not None:
        return "checkbox"
    if pr.find(w("dropDownList")) is not None:
        return "dropDownList"
    if pr.find(w("comboBox")) is not None:
        return "comboBox"
    return "other"


OFF_VALUES = ("0", "false", "off")


def _on(el):
    return el is not None and (el.get(w("val")) or "true").strip().lower() not in OFF_VALUES


def invisible(pkg, run):
    """Why a run does not print, or "". FAIL-CLOSED: hidden (w:vanish / w:specVanish, direct or from its character
    style), white text, or text under 4 pt; a box, mark or tick in such a run is unreadable."""
    rpr = run.find(w("rPr")) if run is not None else None
    if rpr is None:
        return ""
    direct = _inv(run)
    if direct:
        return direct
    rs = rpr.find(w("rStyle"))
    if rs is not None and pkg.fonts.style_hidden(rs.get(w("val"))):
        return "hidden by its character style"
    return ""


def bordered_blank(run):
    """A run with a character border around nothing but spaces draws an empty box."""
    rpr = run.find(w("rPr"))
    b = rpr.find(w("bdr")) if rpr is not None else None
    if b is None or (b.get(w("val")) or "").lower() in ("nil", "none", ""):
        return False
    return not "".join(t.text or "" for t in run.findall(T)).strip()


def glyph_for_char(c, fonts, pkg):
    """A text character in a run drawn with `fonts` -> a glyph Tok, or None when it is plain text."""
    symbol_fonts = symbol_fonts_for(fonts, c)
    if symbol_fonts:
        if c.isspace() or c in ("", " "):
            return None
        return text_symbol_glyph(pkg, fonts, c, symbol_fonts)
    if c in UNICODE_GLYPHS:
        return Tok("glyph", ch=c, state=UNICODE_GLYPHS[c], desc=c)
    if c in BOX_LIKE:
        return Tok("glyph", ch=c, state=None, desc="U+%04X %s outside the glyph table" % (ord(c), c))
    if 0xE000 <= ord(c) <= 0xF8FF:
        return Tok("glyph", ch=c, state=None, desc="private-use U+%04X outside the glyph table" % ord(c))
    return None


def sym_token(sym, run):
    font = (sym.get(w("font")) or "").strip().lower()
    code = sym.get(w("char")) or ""
    try:
        value = int(code, 16)
    except ValueError:
        return Tok("glyph", el=sym, src=run, state=None, desc="w:sym with unreadable code %r" % code)
    low = value - 0xF000 if 0xF000 <= value <= 0xF0FF else value
    table = SYM_GLYPHS.get(font)
    if table is not None and low in table:
        return Tok("glyph", ch="sym:%s:%02X" % (font, low), el=sym, src=run, state=table[low],
                   desc="w:sym %s %02X" % (font, low))
    return Tok("glyph", el=sym, src=run, state=None, desc="w:sym %s %s outside the glyph table" % (font or "?", code))


def para_tokens(pkg, p):
    """A paragraph's visible content in document order: text characters and one token per box / control / picture.
    Text boxes anchored in the paragraph are separate slots; their anchor counts as a picture token."""
    toks, fields = [], []                           # fields: stack of {"phase", "suppress", "instr", "run"}

    def visible():
        return all(f["phase"] == "result" and not f["suppress"] for f in fields)

    def finish_instr(f):
        s = f["instr"]
        if DRAWING_FIELD.match(s) or any(c in BOX_LIKE or c in UNICODE_GLYPHS for c in s):
            toks.append(Tok("glyph", el=f["run"], src=f["run"], state=None,
                            desc="a field draws from its instruction %r" % ws(s)[:40]))

    def run(r):
        symbol = None                               # the run's resolved fonts, read on its first w:t
        hid = invisible(pkg, r)
        if visible() and bordered_blank(r):
            toks.append(Tok("glyph", el=r, src=r, state=None, desc="a bordered blank run (a drawn box)"))
        for ch in r:
            tag = ch.tag
            if not isinstance(tag, str) or tag in SKIP:
                continue
            if tag == FLDCHAR:
                kind = ch.get(w("fldCharType"))
                if kind == "begin":
                    data = ch.find(w("ffData"))
                    k = None
                    if data is not None:
                        k = "ffcb" if data.find(w("checkBox")) is not None else (
                            "ffdd" if data.find(w("ddList")) is not None else "fftext")
                    if k and visible():
                        toks.append(Tok(k, el=r, src=r, hidden=bool(hid)))
                    fields.append({"phase": "instr", "suppress": k in ("ffcb", "ffdd"), "instr": "", "run": r})
                elif kind == "separate" and fields:
                    if fields[-1]["phase"] == "instr":
                        finish_instr(fields[-1])
                    fields[-1]["phase"] = "result"
                elif kind == "end" and fields:
                    f = fields.pop()
                    if f["phase"] == "instr":
                        finish_instr(f)
                continue
            if tag == INSTR:
                if fields and fields[-1]["phase"] == "instr":
                    fields[-1]["instr"] += ch.text or ""
                continue
            if not visible():
                continue
            if tag == T:
                if symbol is None:
                    symbol = pkg.fonts.run_fonts(r, p)
                for c in ch.text or "":
                    g = glyph_for_char(c, symbol, pkg)
                    if g is None:
                        toks.append(Tok("t", ch=c, src=r, hidden=bool(hid)))
                    else:
                        g.src = r
                        if hid:
                            g.state, g.desc, g.hidden = None, "%s in a run that does not print (%s)" % (g.desc, hid), True
                        toks.append(g)
            elif tag in (w("tab"), w("ptab")):
                toks.append(Tok("t", ch="\t", src=r))
            elif tag in (w("br"), w("cr")):
                toks.append(Tok("t", ch="\n", src=r))
            elif tag == SYM:
                g = sym_token(ch, r)
                if hid:
                    g.state, g.desc, g.hidden = None, "%s in a run that does not print (%s)" % (g.desc, hid), True
                toks.append(g)
            elif tag == w("noBreakHyphen"):
                toks.append(Tok("t", ch="-", src=r))
            elif tag in PICTURES or tag == "{%s}AlternateContent" % MC:
                toks.append(Tok("picture", el=ch, src=r, state=None, desc="a picture or shape (unreadable as a box)"))

    def walk(el):
        for ch in el:
            tag = ch.tag
            if not isinstance(tag, str) or tag in SKIP:
                continue
            if tag == R:
                run(ch)
            elif tag == SDT:
                typ = sdt_type(ch)
                if typ in ("checkbox", "dropDownList", "comboBox"):
                    if visible():
                        toks.append(Tok("sdtcb" if typ == "checkbox" else "sdtdd", el=ch, src=ch))
                else:
                    c = ch.find(SDTCONTENT)
                    if c is not None:
                        walk(c)
            elif tag == w("fldSimple"):
                instr = ch.get(w("instr")) or ""
                if DRAWING_FIELD.match(instr) or any(c in BOX_LIKE or c in UNICODE_GLYPHS for c in instr):
                    toks.append(Tok("glyph", el=ch, src=ch, state=None,
                                    desc="a field draws from its instruction %r" % ws(instr)[:40]))
                walk(ch)
            elif tag in PICTURES:
                toks.append(Tok("picture", el=ch, src=ch, state=None, desc="a picture or shape (unreadable as a box)"))
            else:
                walk(ch)                            # hyperlink, smartTag, customXml, ins, moveTo, dir, bdo, ...
    walk(p)
    toks = typed_boxes(toks)
    return pkg.numbering.bullet_tokens(p) + toks


TYPED_OPEN = {"[": "]", "(": ")"}


def typed_boxes(toks):
    """FAIL-CLOSED (v2.1, found with reading 2): a box TYPED as brackets around nothing but spaces - '[ ]', '[  ]', '[]'
    or '( )' - is a box of UNREADABLE state, like a bordered blank run. Read as plain text, its option would be read by
    the inserted mark beside it, and a correctly marked '[X] no' would read as 'no' unticked (D29's ground truth: "mark
    inside the brackets"). The characters become ONE glyph token."""
    out, i = [], 0
    while i < len(toks):
        t = toks[i]
        if t.k == "t" and t.ch in TYPED_OPEN and not t.hidden:
            j = i + 1
            while j < len(toks) and toks[j].k == "t" and toks[j].ch in (" ", "\t", " ") and not toks[j].hidden:
                j += 1
            if j < len(toks) and toks[j].k == "t" and toks[j].ch == TYPED_OPEN[t.ch] and not toks[j].hidden \
                    and (t.ch == "[" or j > i + 1):
                shown = "".join(x.ch for x in toks[i:j + 1])
                out.append(Tok("glyph", ch=shown, src=t.src, state=None, desc="a typed bracket box %r (unreadable)" % shown))
                i = j + 1
                continue
        out.append(t)
        i += 1
    return out


def element_lines(pkg, el):
    """An element as token lines [(tag, element, tokens)]: a paragraph is one line; a checkbox / dropdown control that
    is not inside a paragraph is a one-token line; containers (cell, row, table, content, text box) are walked."""
    tag = el.tag
    if tag == P:
        return [("p", el, para_tokens(pkg, el))]
    if tag == SDT:
        typ = sdt_type(el)
        if typ in ("checkbox", "dropDownList", "comboBox"):
            return [("ctl", el, [Tok("sdtcb" if typ == "checkbox" else "sdtdd", el=el, src=el)])]
        c = el.find(SDTCONTENT)
        return element_lines(pkg, c) if c is not None else []
    out = []
    for ch in el:
        if isinstance(ch.tag, str) and ch.tag not in SKIP and ch.tag in (P, SDT, TBL, TR, TC, SDTCONTENT):
            out.extend(element_lines(pkg, ch))
    return out


def is_inline(el):
    """True when el sits inside a paragraph (an inline content control), False when it is a block."""
    a = el.getparent()
    while a is not None:
        if a.tag == P:
            return True
        if a.tag in (w("body"), TC, TR, TBL, TXBX, w("hdr"), w("ftr")):
            return False
        a = a.getparent()
    return False


def host_paragraph(el):
    p = el
    while p is not None and p.tag != P:
        p = p.getparent()
    if p is None:
        raise SlotError("not inside a paragraph")
    return p


def slot_view(pkg, slot, cell_box=None):
    """A slot -> (lines, own, cell) where own[i] is None (the slot covers line i entirely) or the set of token
    positions it covers (an ff / inline sdt slot covers only that control), and cell says whether the slot is a
    cell box (a cell empty in the original). `cell_box` forces the original's decision on the export."""
    part, el, kind = resolve(pkg, slot)
    if kind == "ff" or (kind == "sdt" and is_inline(el)):
        p = host_paragraph(el)
        toks = para_tokens(pkg, p)
        inside = {id(x) for x in el.iter()}
        own = {i for i, t in enumerate(toks) if (t.el is el) or (kind == "sdt" and t.src is not None and id(t.src) in inside)}
        return part, [("p", p, toks)], [own], False
    lines = element_lines(pkg, el)
    if kind == "tc":
        empty = all(t.k == "t" and not t.ch.strip() for _, _, toks in lines for t in toks) and \
            not any(True for _ in el.iter(*PICTURES))
        if cell_box if cell_box is not None else empty:
            return part, [("cell", el, [Tok("cell", el=el, src=el)])], [None], True
    return part, lines, [None] * len(lines), False


# ─── rule 1: states ──────────────────────────────────────────────────────────────────────────────────────────────

ON, OFF = {"1", "true", "on"}, {"0", "false", "off"}


def _content_invisible(sdt):
    content = sdt.find(SDTCONTENT)
    runs = list(content.iter(R)) if content is not None else []
    return next((why for why in (_inv(r) for r in runs) if why), "")


def _inv(run):
    """invisible() without a package (direct properties only; used on controls)."""
    rpr = run.find(w("rPr"))
    if rpr is None:
        return ""
    if _on(rpr.find(w("vanish"))) or _on(rpr.find(w("specVanish"))) or _on(rpr.find(w("webHidden"))):
        return "hidden"
    c = rpr.find(w("color"))
    if c is not None and ((c.get(w("val")) or "").upper() in ("FFFFFF", "WHITE")
                          or (c.get(w("themeColor")) or "").lower() in ("background1", "light1")):
        return "white"
    sz = rpr.find(w("sz"))
    if sz is not None and not (sz.get(w("val")) or "99").isdigit():
        return "unreadable size"
    if sz is not None and int(sz.get(w("val")) or 99) < 8:
        return "under 4 pt"
    return ""


def sdt_checkbox_state(sdt):
    """w14:checkbox/w14:checked/@w14:val in {1, true} -> ticked; no w14:checked -> unticked. FAIL-CLOSED: a value
    outside {0, 1, true, false}, a w14:checked without w14:val, several w14:checked, or a shown character that
    contradicts the state (not the control's checkedState / uncheckedState character, default ☒ / ☐) -> unreadable."""
    cb = sdt.find(SDTPR).find(w14("checkbox"))
    checked = cb.findall(w14("checked"))
    if len(checked) > 1:
        return None, "content-control checkbox with %d w14:checked" % len(checked)
    if not checked:
        state = False
    else:
        v = checked[0].get(w14("val"))
        if v is None:
            return None, "content-control checkbox w14:checked without w14:val"
        v = v.strip().lower()
        if v not in ("1", "true", "0", "false"):
            return None, "content-control checkbox w14:val=%r" % v
        state = v in ("1", "true")
    st = cb.find(w14("checkedState" if state else "uncheckedState"))
    code = st.get(w14("val")) if st is not None and st.get(w14("val")) else ("2612" if state else "2610")
    try:
        want = int(code, 16)
    except ValueError:
        return None, "content-control checkbox state character %r" % code
    content = sdt.find(SDTCONTENT)
    why = _content_invisible(sdt)
    if why:
        return None, "content-control checkbox in a run that does not print (%s)" % why
    shown = "".join(t.text or "" for t in content.iter(T)) if content is not None else ""
    shown = "".join(c for c in shown if not c.isspace())
    if not (len(shown) == 1 and ord(shown) in (want, want & 0xFF, 0xF000 | (want & 0xFF))):
        return None, "content-control checkbox shows %r but is %s (expects U+%04X)" % (
            shown, "ticked" if state else "unticked", want)
    return state, ""


def ff_checkbox_state(begin_run):
    """w:ffData/w:checkBox/w:checked (absent @w:val or a true value), else w:default. FAIL-CLOSED: several w:checked,
    a value outside {0, 1, true, false, on, off}, or neither w:checked nor exactly one w:default -> unreadable."""
    cb = begin_run.find(FLDCHAR).find(w("ffData")).find(w("checkBox"))
    if _inv(begin_run):
        return None, "legacy checkbox in a run that does not print (%s)" % _inv(begin_run)
    checked = cb.findall(w("checked"))
    if len(checked) > 1:
        return None, "legacy checkbox with %d w:checked" % len(checked)
    if checked:
        v = checked[0].get(w("val"))
        if v is None:
            return True, ""
        v = v.strip().lower()
        if v in ON or v in OFF:
            return v in ON, ""
        return None, "legacy checkbox w:checked w:val=%r" % v
    d = cb.findall(w("default"))
    if len(d) != 1:
        return None, "legacy checkbox has no w:checked and %d w:default" % len(d)
    v = (d[0].get(w("val")) or "").strip().lower()
    if v in ON or v in OFF:
        return v in ON, ""
    return None, "legacy checkbox w:default w:val=%r" % v


def _plain_text(el):
    out = []
    for n in el.iter(T, w("tab"), w("ptab")):
        a, dead = n.getparent(), False
        while a is not None and a is not el:
            if a.tag in (w("del"), w("moveFrom"), FALLBACK):
                dead = True
                break
            a = a.getparent()
        if not dead:
            out.append(n.text or "" if n.tag == T else "\t")
    return "".join(out)


def sdt_dropdown_view(sdt):
    """(shown words or None while the placeholder shows, [(displayText, value)], problem)."""
    pr = sdt.find(SDTPR)
    lst = pr.find(w("dropDownList"))
    if lst is None:
        lst = pr.find(w("comboBox"))
    entries = [(li.get(w("displayText")), li.get(w("value"))) for li in lst.findall(w("listItem"))]
    if pr.find(w("showingPlcHdr")) is not None:
        return None, entries, ""
    if _content_invisible(sdt):
        return None, entries, "the dropdown's shown text does not print (%s)" % _content_invisible(sdt)
    content = sdt.find(SDTCONTENT)
    return ws(_plain_text(content) if content is not None else ""), entries, ""


def ff_dropdown_view(begin_run):
    """(shown entry, [(entry, None)], problem): the entry at w:result, else w:default, else 0. FAIL-CLOSED: several
    w:result, an index out of range, or a visible cached field result that differs from the entry -> unreadable."""
    dd = begin_run.find(FLDCHAR).find(w("ffData")).find(w("ddList"))
    entries = [(x.get(w("val")), None) for x in dd.findall(w("listEntry"))]
    res = dd.findall(w("result"))
    if len(res) > 1:
        return None, entries, "legacy dropdown with %d w:result" % len(res)
    src = res or dd.findall(w("default"))
    try:
        at = int(src[0].get(w("val")) or 0) if src else 0
    except ValueError:
        return None, entries, "legacy dropdown index unreadable"
    if not 0 <= at < len(entries):
        return None, entries, "legacy dropdown index %d outside its %d entries" % (at, len(entries))
    shown = ws(entries[at][0])
    node, depth, phase, cached = begin_run, 0, "instr", []
    while True:
        node = node.getnext()
        if node is None:
            break
        if node.tag != R:
            continue
        fc = node.find(FLDCHAR)
        if fc is not None:
            k = fc.get(w("fldCharType"))
            if k == "begin":
                depth += 1
            elif k == "end":
                if depth == 0:
                    break
                depth -= 1
            elif k == "separate" and depth == 0:
                phase = "result"
            continue
        if phase == "result" and depth == 0:
            cached.append(_plain_text(node))
    if ws("".join(cached)) and ws("".join(cached)) != shown:
        return None, entries, "legacy dropdown's field result shows %r but it selects %r" % (ws("".join(cached)), shown)
    return shown, entries, ""


def cell_state(pkg, tc):
    """A cell empty in the original: ticked when it now holds exactly one of X x ✓ ✔ ☒ (whitespace aside); unticked
    when it is still empty. FAIL-CLOSED: anything else (other text, another glyph, a control, a picture) ->
    unreadable."""
    if any(True for _ in tc.iter(*PICTURES)):
        return None, "the cell holds a picture"
    items = [t for _, _, toks in element_lines(pkg, tc) for t in toks if not (t.k == "t" and not t.ch.strip())]
    if not items:
        return False, ""
    if any(t.hidden for t in items):
        return None, "the cell holds text that does not print"
    if len(items) == 1 and items[0].k in ("t", "glyph") and items[0].ch in CELL_MARKS:
        if items[0].k == "t" or items[0].state is not None:
            return True, ""
    shown = "".join(t.ch if t.k in ("t", "glyph") and len(t.ch) == 1 else "<%s>" % t.k for t in items)
    return None, "the cell holds %r (not exactly one of X x ✓ ✔ ☒)" % shown[:30]


def box_state(pkg, tok):
    """(True | False | None, problem) for one box token."""
    if tok.k == "glyph":
        return tok.state, ("" if tok.state is not None else "unreadable glyph: " + tok.desc)
    if tok.k == "sdtcb":
        return sdt_checkbox_state(tok.el)
    if tok.k == "ffcb":
        return ff_checkbox_state(tok.el)
    if tok.k == "cell":
        return cell_state(pkg, tok.el)
    if tok.k == "picture":
        return None, tok.desc
    return None, "not a box (%s)" % tok.k


KIND_NAME = {"glyph": "glyph", "sdtcb": "content-control checkbox", "ffcb": "legacy checkbox", "cell": "cell mark",
             "picture": "picture", "sdtdd": "content-control dropdown", "ffdd": "legacy dropdown",
             "mark": "inserted mark", "celltext": "cell text"}


# ─── the region of a question: its slots read in the original and in the export, aligned ────────────────────────

class RegionError(Exception):
    pass


class Region:
    """lines0 / lines1: [(part, tag, element, tokens)] in document order; own[i]: None (whole line) or token
    positions; slot_items[s]: [(line, position)] of the boxes / controls slot s covers; map01[i]: original position
    -> export position for tokens the alignment keeps; inserted1[i]: export positions with no original token."""

    def __init__(self, pkg0, pkg1, slots):
        self.pkg0, self.pkg1 = pkg0, pkg1
        self.lines0, self.lines1, self.own, self.slot_items = [], [], [], {}
        self.slot_lines, self.cell_slot = {}, {}      # slot -> [(line, own positions or None)]; slot -> a cell box?
        index = {}
        for s in slots:
            try:
                part, l0, own0, cell = slot_view(pkg0, s)
            except SlotError as e:
                raise RegionError("slot %s: %s" % (s, e))
            try:
                _, l1, _, _ = slot_view(pkg1, s, cell_box=cell)
            except SlotError as e:
                raise RegionError("slot %s is not in the export (%s)" % (s, e))
            if len(l0) != len(l1) or any(a[0] != b[0] for a, b in zip(l0, l1)):
                raise RegionError("slot %s: the export has a different paragraph structure there" % s)
            items, mine = [], []
            for (tag, e0, t0), (_, e1, t1), o in zip(l0, l1, own0):
                key = (part, id(e0))
                if key in index:
                    i = index[key]
                    if self.own[i] is not None:
                        self.own[i] = None if o is None else self.own[i] | o
                else:
                    i = index[key] = len(self.lines0)
                    self.lines0.append((part, tag, e0, t0))
                    self.lines1.append((part, tag, e1, t1))
                    self.own.append(o)
                mine.append((i, o))
                items.extend((i, k) for k, t in enumerate(t0) if (t.is_box or t.is_control) and (o is None or k in o))
            self.slot_items[s] = items
            self.slot_lines[s] = mine
            self.cell_slot[s] = cell
        order = sorted(range(len(self.lines0)), key=lambda i: (self.lines0[i][0] != "word/document.xml",
                                                                self.lines0[i][0], pkg0.pos(self.lines0[i][0], self.lines0[i][2])))
        remap = {old: new for new, old in enumerate(order)}
        self.lines0 = [self.lines0[i] for i in order]
        self.lines1 = [self.lines1[i] for i in order]
        self.own = [self.own[i] for i in order]
        self.slot_items = {s: [(remap[i], k) for i, k in v] for s, v in self.slot_items.items()}
        self.slot_lines = {s: [(remap[i], o) for i, o in v] for s, v in self.slot_lines.items()}
        self.map01, self.inserted1 = [], []
        for (_, _, _, t0), (_, _, _, t1) in zip(self.lines0, self.lines1):
            m = {}
            sm = difflib.SequenceMatcher(None, [t.key for t in t0], [t.key for t in t1], autojunk=False)
            for tag, i1, i2, j1, j2 in sm.get_opcodes():
                if tag == "equal":
                    m.update({i1 + k: j1 + k for k in range(i2 - i1)})
            self.map01.append(m)
            self.inserted1.append(set(range(len(t1))) - set(m.values()))

    def items(self):
        """[(line, position)] of every box and control the question's slots cover, deduplicated, in order."""
        seen = set()
        for li, (_, _, _, toks) in enumerate(self.lines0):
            own = self.own[li]
            for k, t in enumerate(toks):
                if (t.is_box or t.is_control) and (own is None or k in own) and (li, k) not in seen:
                    seen.add((li, k))
                    yield li, k

    def tok0(self, li, k):
        return self.lines0[li][3][k]

    def tok1(self, li, k):
        j = self.map01[li].get(k)
        return None if j is None else self.lines1[li][3][j]

    def global_key(self, li, k):
        part, _, el, _ = self.lines0[li]
        return (part, self.pkg0.pos(part, el), k)

    def export_key(self, li, j):
        """An export token position that means the same in every question's region (v2.1 reading 5)."""
        part, _, el, _ = self.lines1[li]
        return (part, self.pkg1.pos(part, el), j)


# ─── rule 2: options tied to boxes from the original and the ground truth alone ─────────────────────────────────

def norm_search(s):
    return ws(unicodedata.normalize("NFKC", s or "")).casefold()


def search_line(toks, own):
    """A line as a search string: its own text characters (NFKC, casefolded, whitespace runs collapsed to one space)
    and one \\x00 per box, control, picture or character the slot does not cover; plus string -> token positions."""
    chars, idx, space = [], [], True
    for i, t in enumerate(toks):
        if t.k == "t" and not t.hidden and (own is None or i in own):
            for c in unicodedata.normalize("NFKC", t.ch).casefold():
                if c.isspace():
                    if not space:
                        chars.append(" ")
                        idx.append(i)
                    space = True
                else:
                    chars.append(c)
                    idx.append(i)
                    space = False
        else:
            chars.append("\x00")
            idx.append(i)
            space = False
    return "".join(chars), idx


def occurrences(text, needle):
    """Occurrences of needle in text. FAIL-CLOSED: an option's printed text never starts or ends inside a longer
    word ('No' is not found in 'Not')."""
    out, start = [], 0
    while needle:
        at = text.find(needle, start)
        if at < 0:
            break
        end = at + len(needle)
        before = text[at - 1] if at > 0 else " "
        after = text[end] if end < len(text) else " "
        if not (needle[0].isalnum() and before.isalnum()) and not (needle[-1].isalnum() and after.isalnum()):
            out.append((at, end))
        start = at + 1
    return out


class Tie:
    def __init__(self, mode, ties, orphans):
        self.mode, self.ties, self.orphans = mode, ties, orphans


def _mark_tie_in_slot(region, s, option, options):
    """v2.1 reading 2, one slot per option: an option slot with no box is read by the inserted mark before the option's
    printed text IN ITS OWN SLOT (first word-bounded occurrence, as in the second bullet). FAIL-CLOSED: the option is
    not printed in its slot, or is printed there only inside a longer option's printed text -> unverifiable."""
    needle = norm_search(option)
    for li, own in region.slot_lines[s]:
        text, idx = search_line(region.lines0[li][3], own)
        found = occurrences(text, needle)
        if not found:
            continue
        a, b = found[0]
        for o in options:
            n2 = norm_search(o)
            if len(n2) > len(needle) and any(c <= a and b <= d for c, d in occurrences(text, n2)):
                raise RegionError("option %r is printed inside option %r" % (option[:30], o[:30]))
        return ("mark", li, (idx[a], idx[b - 1] + 1))
    raise RegionError("option %r is not printed in its slot %s, which holds no box" % (option[:40], s.split("#")[-1]))


def tie_options(region, area):
    """-> Tie, or raises RegionError (the question is unverifiable). ties[i] per option: ("box", line, pos) |
    ("mark", line, (first, last+1) token positions of its printed text) | ("dropdown", line, pos, entry index)."""
    options = list(area.get("options") or [])
    kind = area.get("kind")
    slots = area.get("slots") or []
    if kind == "checkbox" and not options:
        options = ["\x00checkbox"]                  # a single yes/no box: one implicit option
    if not options:
        raise RegionError("the ground truth lists no options")
    items = list(region.items())
    controls = [(li, k) for li, k in items if region.tok0(li, k).is_control]
    # a dropdown: every option is one of its list entries (rule 1, "a dropdown")
    if controls:
        if len(items) != 1:
            raise RegionError("the slots hold a dropdown together with %d other box(es) or control(s)" % (len(items) - 1))
        li, k = controls[0]
        tok = region.tok0(li, k)
        _, entries, prob = (sdt_dropdown_view if tok.k == "sdtdd" else ff_dropdown_view)(tok.el)
        if prob:
            raise RegionError(prob)
        labels = [ws(e[0] if e[0] is not None else e[1]) for e in entries]
        ties = []
        for o in options:
            hits = [j for j, lab in enumerate(labels) if lab == ws(o)]
            if len(hits) != 1:
                raise RegionError("option %r is %s the dropdown's list entries" % (o[:40], "not one of" if not hits else "several of"))
            ties.append(("dropdown", li, k, hits[0]))
        return Tie("dropdown", ties, [])
    # v2.1 reading 6: ONE slot that is a cell empty in the original, for a question of several options: the answer is
    # written into the cell as text (Yes / No / NA grids) - the "cell text" box kind. FAIL-CLOSED: only a cell slot
    # (…/tc[k]) with no visible text, box, control or picture in the original; a paragraph slot inside such a cell, or
    # a cell of one option (one slot per option), keeps the cell-mark reading of rule 1.
    if len(slots) == 1 and len(options) >= 2 and region.cell_slot.get(slots[0]):
        (li, _), = region.slot_lines[slots[0]]
        return Tie("cell-text", [("celltext", li, 0, i) for i in range(len(options))], [])
    # rule 2, first bullet: one slot per option; the slot must hold exactly one box or control - or, v2.1 reading 2,
    # no box at all beside the option's printed text, which is then read by the inserted mark
    if len(slots) == len(options):
        per, ties = [], []
        for s, o in zip(slots, options):
            got = region.slot_items.get(s, [])
            if len(got) == 1:
                per.append(got[0])
                ties.append(("box",) + got[0])
            elif not got and not o.startswith("\x00"):
                ties.append(_mark_tie_in_slot(region, s, o, options))
            else:
                raise RegionError("slot %s holds %d boxes (one slot per option needs exactly one)" % (s.split("#")[-1], len(got)))
        if len(set(per)) != len(per):
            raise RegionError("two options' slots hold the same box")
        marks = [(t[1], t[2]) for t in ties if t[0] == "mark"]
        if len(set(marks)) != len(marks):
            raise RegionError("two options are read from the same printed text")
        return Tie("slot-per-option", ties, [x for x in items if x not in set(per)])
    if kind == "checkbox":
        raise RegionError("a checkbox with %d slots and %d options" % (len(slots), len(options)))
    # rule 2, second bullet: each option's printed text, in document order, first unused occurrence
    lines = [search_line(toks, region.own[li]) for li, (_, _, _, toks) in enumerate(region.lines0)]
    used, occ = [], []
    for o in options:
        needle, found = norm_search(o), None
        for li, (text, _) in enumerate(lines):
            for a, b in occurrences(text, needle):
                if not any(u[0] == li and a < u[2] and u[1] < b for u in used):
                    found = (li, a, b)
                    break
            if found:
                break
        if not found:
            raise RegionError("option %r is not printed in the slots" % o[:40])
        used.append(found)
        occ.append(found)
    # FAIL-CLOSED: an option found only inside the printed text of a longer option is ambiguous
    for i, (li, a, b) in enumerate(occ):
        for j, o in enumerate(options):
            n2 = norm_search(o)
            if j != i and len(n2) > b - a and any(c <= a and b <= d for c, d in occurrences(lines[li][0], n2)):
                raise RegionError("option %r is printed inside option %r" % (options[i][:30], o[:30]))
    item_set = set(items)
    boxpos = []
    for li, (text, idx) in enumerate(lines):
        boxpos.append([p for p, c in enumerate(text) if c == "\x00" and (li, idx[p]) in item_set])

    def clean(text, a, b):
        # FAIL-CLOSED reading of "immediately": only whitespace and punctuation between a box and its option - no
        # letter, digit, other box, control or excluded character
        return all(not c.isalnum() and c != "\x00" for c in text[a:b])

    before, after = [], []
    for i, (li, a, b) in enumerate(occ):
        text = lines[li][0]
        others = [x for j, x in enumerate(occ) if j != i and x[0] == li]
        prev = [p for p in boxpos[li] if p < a]
        nxt = [p for p in boxpos[li] if p >= b]
        bb = prev[-1] if prev and clean(text, prev[-1] + 1, a) and not any(prev[-1] < x[1] < a for x in others) else None
        ab = nxt[0] if nxt and clean(text, b, nxt[0]) and not any(b <= x[1] < nxt[0] for x in others) else None
        before.append(bb)
        after.append(ab)
    use, side = (before, "before") if any(x is not None for x in before) else (after, "after")
    ties = []
    for i, (li, a, b) in enumerate(occ):
        if use[i] is not None:
            ties.append(("box", li, lines[li][1][use[i]]))
        elif not boxpos[li]:
            idx = lines[li][1]
            ties.append(("mark", li, (idx[a], idx[b - 1] + 1)))
        else:
            raise RegionError("option %r has no box immediately %s it while another option does (a mixture)" % (options[i][:40], side))
    tied = [(t[1], t[2]) for t in ties if t[0] == "box"]
    if len(set(tied)) != len(tied):
        raise RegionError("one box is tied to two options")
    return Tie("printed-text", ties, [x for x in items if x not in set(tied)])


# ─── rules 3 and 4: the verdict ──────────────────────────────────────────────────────────────────────────────────

def mark_state(region, li, span):
    """The inserted mark: a ☒ immediately before the option's printed text (whitespace aside) that the original
    does not have there. -> (state, export position of the mark or None, problem)."""
    a, b = span
    m = region.map01[li]
    # FAIL-CLOSED (v2.1): the option's printed text must survive as one unbroken run of the original's characters
    if any(k not in m for k in range(a, b)) or any(m[k + 1] != m[k] + 1 for k in range(a, b - 1)):
        return None, None, "the option's printed text changed in the export"
    toks0, toks1 = region.lines0[li][3], region.lines1[li][3]
    before = a - 1                                   # the original's last visible token before the option
    while before >= 0 and toks0[before].k == "t" and not toks0[before].ch.strip():
        before -= 1
    j = m[a] - 1
    while j >= 0 and toks1[j].k == "t" and not toks1[j].ch.strip():
        j -= 1
    if j < 0 or j not in region.inserted1[li]:
        # FAIL-CLOSED (v2.1): nothing was inserted before the option - but the token now before it must be the one
        # the original had there; otherwise the text around the option was rewritten (a label typed over bracketed
        # options lines up with the printed option's letters) and no mark can be read
        now = next((k for k, v in m.items() if v == j), None) if j >= 0 else None
        if now != (before if before >= 0 else None):
            return None, None, "the text right before the option changed in the export"
        return False, None, ""
    t = toks1[j]
    if t.k == "glyph" and t.ch == INSERTED_MARK and t.state is True:
        return True, j, ""
    if t.k == "t":
        # FAIL-CLOSED (v2.1): text inserted right before the option is no mark, and not proof of no mark either
        return None, None, "text inserted right before the option (%r) is not a ☒" % t.ch
    return None, None, "an inserted %s right before the option is not a ☒" % KIND_NAME.get(t.k, t.k)


def cell_text_view(pkg, tc, options):
    """v2.1 reading 6: what a cell (empty in the original) shows -> (option index or None when still empty, problem).
    The cell's visible text (its paragraphs joined by a line break, ends stripped) must EQUAL one option's label
    exactly - case, punctuation and inner spacing included. FAIL-CLOSED: any other text, a box, control or picture in
    the cell, text that does not print, or two options with the same label -> unreadable."""
    if any(True for _ in tc.iter(*PICTURES)):
        return None, "the cell holds a picture"
    lines = element_lines(pkg, tc)
    toks = [t for _, _, ts in lines for t in ts]
    if any(t.k != "t" for t in toks):
        return None, "the cell holds a %s" % KIND_NAME.get(next(t.k for t in toks if t.k != "t"), "box")
    if any(t.hidden and t.ch.strip() for t in toks):
        return None, "the cell holds text that does not print"
    text = "\n".join("".join(t.ch for t in ts) for _, _, ts in lines).strip()
    if not text:
        return None, ""
    hits = [i for i, o in enumerate(options) if o.strip() == text]
    if len(hits) == 1:
        return hits[0], ""
    if hits:
        return None, "the cell shows %r, the label of %d options" % (text[:40], len(hits))
    return None, "the cell holds %r, which is no option's label" % text[:40]


def judge(region, tie, chosen, options, foreign=frozenset(), foreign_marks=frozenset()):
    """-> (verdict, reasons, box kinds). v2.1 reading 5: `foreign` holds the (part, position, token) keys of boxes tied
    to ANOTHER question's option and `foreign_marks` the export keys of inserted marks read for another question's
    option; each is judged by that question only, never here."""
    pkg0, pkg1 = region.pkg0, region.pkg1
    fails, unread, kinds = [], [], set()
    answered = chosen is not None
    want = set(chosen or [])
    if tie.mode == "cell-text":
        _, li, _, _ = tie.ties[0]
        tc0, tc1 = region.lines0[li][2], region.lines1[li][2]
        kinds.add("celltext")
        s0, p0 = cell_text_view(pkg0, tc0, options)
        s1, p1 = cell_text_view(pkg1, tc1, options)
        if p0 or s0 is not None:
            return "unverifiable", ["the original cell is not empty (%s)" % (p0 or "it shows an option")], kinds
        if p1:
            return "unverifiable", [p1], kinds
        if not answered:
            if s1 is not None:
                fails.append("unanswered, but the cell now shows %r" % options[s1][:40])
        elif len(want) != 1:
            return "unverifiable", ["a cell shows one written answer; the profile chose %d options" % len(want)], kinds
        else:
            c = min(want)
            if s1 is None:
                fails.append("the cell is still empty; chosen %r" % options[c][:40])
            elif s1 != c:
                fails.append("the cell shows %r; chosen %r" % (options[s1][:40], options[c][:40]))
        return ("fail" if fails else "pass"), fails, kinds
    if tie.mode == "dropdown":
        _, li, k, _ = tie.ties[0]
        t0, t1 = region.tok0(li, k), region.tok1(li, k)
        kinds.add(t0.k)
        if t1 is None or t1.k != t0.k:
            return "unverifiable", ["the dropdown is not in the export at its slot"], kinds
        view = sdt_dropdown_view if t0.k == "sdtdd" else ff_dropdown_view
        s0, e0, p0 = view(t0.el)
        s1, e1, p1 = view(t1.el)
        if p0 or p1:
            return "unverifiable", [p0 or p1], kinds
        if e0 != e1:
            fails.append("the dropdown's list entries changed")
        if not answered:
            if s0 != s1:
                fails.append("unanswered, but the dropdown now shows %r (was %r)" % (s1, s0))
        elif len(want) != 1:
            return "unverifiable", ["a dropdown shows one entry; the profile chose %d options" % len(want)], kinds
        else:
            c = min(want)
            shown_opts = [i for i, o in enumerate(options) if s1 is not None and ws(o) == s1]
            if s1 is None:
                fails.append("the dropdown still shows its placeholder; chosen %r" % options[c][:40])
            elif shown_opts != [c]:
                fails.append("the dropdown shows %r; chosen %r" % (s1[:40], options[c][:40]))
        return ("fail" if fails else "pass"), fails, kinds
    explained = {}                                  # line -> export positions of inserted marks read for an option
    for i, t in enumerate(tie.ties):
        label = options[i][:40] if options[i] != "\x00checkbox" else "the checkbox"
        if t[0] == "box":
            _, li, k = t
            t0, t1 = region.tok0(li, k), region.tok1(li, k)
            kinds.add(t0.k)
            if t1 is None:
                unread.append("%r: its box is not in the export" % label)
                continue
            s0, p0 = box_state(pkg0, t0)
            s1, p1 = box_state(pkg1, t1)
        else:
            _, li, span = t
            kinds.add("mark")
            s0, p0 = False, ""
            s1, pos, p1 = mark_state(region, li, span)
            if pos is not None:
                explained.setdefault(li, set()).add(pos)
        if answered:
            if s1 is None:
                unread.append("%r: %s" % (label, p1))
            elif s1 != (i in want):
                fails.append("%r is %s but %s" % (label, "ticked" if s1 else "unticked", "chosen" if i in want else "not chosen"))
        else:
            if s0 is None or s1 is None:
                unread.append("%r: %s" % (label, p0 or p1))
            elif s0 != s1:
                fails.append("unanswered, but %r changed from %s to %s" % (label, "ticked" if s0 else "unticked", "ticked" if s1 else "unticked"))
    for li, k in tie.orphans:
        if region.global_key(li, k) in foreign:
            continue                                # v2.1 reading 5: another question's option box
        t0, t1 = region.tok0(li, k), region.tok1(li, k)
        kinds.add(t0.k)
        where = "a box of no option (%s)" % KIND_NAME.get(t0.k, t0.k)
        if t1 is None:
            unread.append("%s is not in the export" % where)
            continue
        s0, p0 = box_state(pkg0, t0)
        s1, p1 = box_state(pkg1, t1)
        if answered:
            if s1 is None:
                unread.append("%s: %s" % (where, p1))
            elif s1:
                fails.append("%s is ticked" % where)
        else:
            if s0 is None or s1 is None:
                unread.append("%s: %s" % (where, p0 or p1))
            elif s0 != s1:
                fails.append("unanswered, but %s changed" % where)
    # FAIL-CLOSED: a box, control or mark INSERTED in the question's slots (a whole paragraph or cell they cover)
    # that is not the inserted mark read for one of this question's options is a changed meaning - v2.1 reading 5:
    # unless it is the inserted mark read for ANOTHER question's option (judged by that question only)
    for li, (_, tag, _, toks1) in enumerate(region.lines1):
        if region.own[li] is not None or tag == "cell":
            continue
        for j in sorted(region.inserted1[li]):
            t = toks1[j]
            if (t.is_box or t.is_control) and j not in explained.get(li, set()) and region.export_key(li, j) not in foreign_marks:
                fails.append("an inserted %s%s that is no option's mark" % (KIND_NAME.get(t.k, t.k), " %s" % t.ch if t.k == "glyph" and len(t.ch) == 1 else ""))
    if fails:
        return "fail", fails + unread, kinds
    if unread:
        return "unverifiable", unread, kinds
    return "pass", [], kinds


class _TiedElsewhere:
    """v2.1 reading 5: `key in x` is true when the key is tied to a question other than `qid`."""

    def __init__(self, owner, qid):
        self.owner, self.qid = owner, qid

    def __contains__(self, key):
        ids = self.owner.get(key)
        return bool(ids) and self.qid not in ids


def check_document(original_bytes, export_bytes, groundtruth, chosen):
    """The `ticked` check of one exported document against its original and ground truth."""
    pkg0, pkg1 = Package(original_bytes), Package(export_bytes)
    chosen = chosen or {}
    results, claims, prepared = [], {}, []
    for area in groundtruth.get("answer_areas", []):
        if area.get("kind") not in CHOICE_KINDS:
            continue
        rec = {"id": area["id"], "label": (area.get("label") or "")[:80], "kind": area["kind"], "verdict": None,
               "reason": "", "box_kinds": [], "mode": "", "answered": None}
        results.append(rec)
        c = chosen.get(area["id"])
        if isinstance(c, dict) and "mapping" in c:
            # v2.1 reading 1: no candidate field matches the question, or the matched field did not accept the
            # ground-truth label -> the question FAILS as a mapping failure of the candidate, never "unverifiable"
            rec.update(verdict="fail", reason="mapping: %s" % c["mapping"], answered="mapping")
        elif isinstance(c, dict):
            rec.update(verdict="unverifiable", reason="chosen set unknown: %s" % c.get("unknown", "?"), answered="unknown")
        rec["answered"] = rec["answered"] or (c is not None)
        n_opts = len(area.get("options") or []) or (1 if area["kind"] == "checkbox" else 0)
        if isinstance(c, list) and any(not isinstance(i, int) or not 0 <= i < n_opts for i in c):
            rec.update(verdict="unverifiable", reason="chosen index outside the %d ground-truth options" % n_opts)
            c = {"unknown": "chosen index out of range"}
        try:
            region = Region(pkg0, pkg1, area.get("slots") or [])
            if not area.get("slots"):
                raise RegionError("the ground truth lists no slots")
            t = tie_options(region, area)
        except RegionError as e:
            if rec["verdict"] is None:
                rec.update(verdict="unverifiable", reason=str(e))
            else:
                rec["reason"] += "; " + str(e)
            continue
        rec["mode"] = t.mode
        for x in t.ties:
            key = ("mark",) + region.global_key(x[1], x[2][0]) if x[0] == "mark" else region.global_key(x[1], x[2])
            claims.setdefault(key, set()).add(area["id"])
        prepared.append((rec, area, region, t, c))
    # FAIL-CLOSED: one box, control or printed option tied to two ground-truth questions ties neither
    conflicted = {}
    for key, ids in claims.items():
        if len(ids) > 1:
            for i in ids:
                conflicted.setdefault(i, set()).update(ids - {i})
    # v2.1 reading 5: every box and every inserted mark a question's ties read, keyed alike in every region, so that a
    # box tied to another question's option is judged by that question only. FAIL-CLOSED: a question caught by the
    # conflict guard ties nothing, so its boxes stay "boxes tied to no question" in every other question.
    box_owner, mark_owner = {}, {}
    for rec, area, region, t, c in prepared:
        if area["id"] in conflicted:
            continue
        for x in t.ties:
            if x[0] == "mark":
                _, pos, _ = mark_state(region, x[1], x[2])
                if pos is not None:
                    mark_owner.setdefault(region.export_key(x[1], pos), set()).add(area["id"])
            else:
                box_owner.setdefault(region.global_key(x[1], x[2]), set()).add(area["id"])
    for rec, area, region, t, c in prepared:
        options = list(area.get("options") or []) or ["\x00checkbox"]
        verdict, reasons, kinds = judge(region, t, None if isinstance(c, dict) else c, options,
                                        _TiedElsewhere(box_owner, area["id"]), _TiedElsewhere(mark_owner, area["id"]))
        rec["box_kinds"] = sorted(KIND_NAME.get(k, k) for k in kinds)
        if rec["answered"] == "mapping":               # a mapping failure stands whatever the reading
            rec["reason"] += " | read unanswered: %s%s" % (verdict, (" (" + "; ".join(reasons)[:200] + ")") if reasons else "")
            continue
        if area["id"] in conflicted:
            rec.update(verdict="unverifiable", reason="a box or printed option is also tied to %s" % ", ".join(sorted(conflicted[area["id"]])))
            continue
        if rec["verdict"] == "unverifiable":           # chosen set unknown: the reading is informative only
            rec["reason"] += " | read: %s%s" % (verdict, (" (" + "; ".join(reasons)[:200] + ")") if reasons else "")
            continue
        rec.update(verdict=verdict, reason="; ".join(reasons))
    passed = all(r["verdict"] == "pass" for r in results)
    return {"version": VERSION, "passed": passed, "questions": results,
            "counts": {v: sum(r["verdict"] == v for r in results) for v in ("pass", "fail", "unverifiable")}}


# ─── the profile's chosen set in ground-truth terms (a join; never the engine's option -> box tie) ─────────────────

TRUE_WORDS = {True, "true", "True", "checked", "yes", "Yes"}
FALSE_WORDS = {False, "false", "False", "unchecked", "no", "No"}


def join_chosen(groundtruth, matched, fields, answers, related):
    """v2.0's dev join, SUPERSEDED for scoring by v2.1 reading 1 (answering.py fixes the chosen answer in ground-truth
    terms). Kept only so the self-tests can rebuild the chosen sets of the frozen v1-profile exports they use as bases.

    The profile's chosen options per ground-truth question, by OPTION TEXT only.

    matched:  {area id: detected field key} from a field-level matcher (the v1 scorer's GT <-> field rows)
    related:  related(area, field) -> bool, the v1 scorer's slot relation (field level)
    An answer's text names a ground-truth option by three tiers, each needing exactly ONE hit (several hits at a tier
    stop the search - ambiguous, unknown): the option equals it (NFKC, case and whitespace aside); the option has the
    same sequence of letter/digit words ('] kg [' names 'kg'; 'Alkali ……' names 'Alkali'); one word sequence starts
    the other ('Yes – If yes, specify type' names 'Yes'; '] Other Investigators' names 'Other Investigators
    participating in this study'). A question is UNANSWERED when no detected field matched it and no UNMATCHED answered tick-writing
    field touches its slots (a field matched to another question is that question's answer; its ticks in this
    question's slots are judged by this question's orphan-box rule).
    FAIL-CLOSED -> {"unknown": reason}: the matched field is not a choice-like field; an answer names no option or
    several; an unmatched answered tick-writing field touches the slots."""
    by_key = {f["key"]: f for f in fields}
    matched_keys = set(matched.values())
    out = {}

    def option_for(gopts, raw_opts, text):
        t = norm_search(str(text))
        hits = [i for i, o in enumerate(gopts) if o == t]
        if len(hits) == 1:
            return hits[0]
        if hits:
            return None
        words = re.findall(r"[^\W_]+", t)
        if not words:
            return None
        ow = [re.findall(r"[^\W_]+", norm_search(o)) for o in raw_opts]
        hits = [i for i, x in enumerate(ow) if x == words]
        if len(hits) == 1:
            return hits[0]
        if hits:
            return None
        hits = [i for i, x in enumerate(ow) if x and (x == words[:len(x)] or words == x[:len(words)])]
        return hits[0] if len(hits) == 1 else None

    def is_answered(v):
        return not (v is None or v == "" or v == [])

    for area in groundtruth.get("answer_areas", []):
        if area.get("kind") not in CHOICE_KINDS:
            continue
        key = matched.get(area["id"])
        others = [f for f in fields if f["key"] != key and f["key"] not in matched_keys
                  and f["kind"] in ("choice", "multi_choice", "checkbox")
                  and is_answered(answers.get(f["key"])) and related(area, f)]
        if others:
            out[area["id"]] = {"unknown": "answered by %d more detected field(s) touching its slots (%s)" % (
                len(others), ", ".join(f["key"] for f in others[:4]))}
            continue
        if key is None:
            continue                                  # unanswered
        f = by_key[key]
        ans = answers.get(key)
        if not is_answered(ans):
            continue
        raw = list(area.get("options") or [])
        gopts = [norm_search(o) for o in raw]
        if f["kind"] == "checkbox":
            if ans in TRUE_WORDS:
                on = True
            elif ans in FALSE_WORDS:
                on = False
            else:
                out[area["id"]] = {"unknown": "checkbox answer %r" % (ans,)}
                continue
            if area["kind"] == "checkbox" and not gopts:
                out[area["id"]] = [0] if on else []
                continue
            names = [x for x in (f.get("options") or [])[:1]] or [f.get("label") or ""]
            hit = option_for(gopts, raw, names[0])
            if hit is None:
                out[area["id"]] = {"unknown": "a checkbox field %r names no single ground-truth option" % names[0][:40]}
                continue
            out[area["id"]] = [hit] if on else []
            continue
        if f["kind"] not in ("choice", "multi_choice"):
            out[area["id"]] = {"unknown": "matched to a %s field" % f["kind"]}
            continue
        if area["kind"] == "checkbox" and not gopts:
            out[area["id"]] = {"unknown": "a %s answer on a single checkbox" % f["kind"]}
            continue
        vals = ans if isinstance(ans, list) else [ans]
        idx, bad = [], None
        for v in vals:
            hit = option_for(gopts, raw, v)
            if hit is None:
                bad = v
                break
            if hit not in idx:
                idx.append(hit)
        out[area["id"]] = {"unknown": "answer %r names no single ground-truth option" % str(bad)[:40]} if bad is not None else idx
    return out
