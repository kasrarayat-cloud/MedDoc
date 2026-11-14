"""pypdf 6.21.4 read the way pypdf 6.21.2 reads (ARCHITECTURE 5.1).

CPT Studio pins pypdf 6.21.4 for its fixes of seven advisories against 6.21.2 (CVE-2026-119203 to CVE-2026-119209:
denial of service from a crafted PDF). The reader was built and judged on 6.21.2, and 6.21.4 also changes how some
documents read in ways that are not part of those fixes. ``apply`` restores 6.21.2's behaviour for each such change
the reader reaches, by replacing the smallest pypdf function that holds it, and keeps every change that is part of
an advisory fix, and 6.21.4's MemoryError handling. It changes nothing else.

Where it is applied, which is every place CPT Studio reads a PDF with pypdf: the extraction child, before it imports
the reader (studio/ingest/_child.py parse); ops/verify_passages.py page_texts; the tests package
(tests/__init__.py, for the reader tests that run in the test process); and ops/verification/test_generate.py, the
one suite CI discovers on its own. The web and worker processes import parts of pypdf (its code tables) but never
build a PdfReader: every upload is read by the child.

- pypdf must be exactly the 6.21.4 the patches were proven against: its version, the sha256 of every one of its
  source files (_MANIFEST), and the sha256 of each replaced function's source, whose loaded code must be what that
  source compiles to where it stands. The source is read as a line range of the proven file's bytes (the text
  inspect.getsource gives), never through inspect, tokenize or linecache, which keep a copy of each whole file in the
  process (pypdf-r6 F3: about 1.1 MiB of the extraction child's address-space limit).
- the advisory fixes the reader depends on and the layer does not replace (#4269: PdfReader.__init__,
  _read_xref_tables_and_trailers, _read_xref, _read_pdf15_xref_stream; #4290: PdfDocCommon._flatten,
  _flatten_leaf_page) are checked the same way, never patched (_CHECKED).
- each replacement is that source with the listed edits, each found exactly once, and its sha256 is checked. Seven
  replacements are, byte for byte, pypdf 6.21.2's function; two are 6.21.4's with 6.21.2's lines put back and
  6.21.4's MemoryError lines kept; two are 6.21.4's with an edit to an advisory fix's lines, below.
- every binding of a replaced function is rebound (its module or class attribute, and each module that imported it
  by name, all listed in _BINDINGS); afterwards nothing may still reach the replaced function (it must be
  collected).
- two edits of an advisory fix's lines, each keeping the fix:
  * #4265: where pypdf 6.21.4 turns a MemoryError inside a dictionary into a read error,
    DictionaryObject.read_from_stream raises the MemoryError itself, so the reader names it as it names every memory
    failure; its RecursionError, message and warning changes stay 6.21.4's. It is an edit, never a wrapper: a wrapper
    adds a Python frame to every nested dictionary, so a dictionary nested a few hundred levels deep, which pypdf
    6.21.2 and 6.21.4 both read, would meet the recursion limit (pypdf-r6 reconcile).
  * #4269 (PdfReader._sanitize_pdf15_xref_stream_index_pairs): a negative /Index count takes part in the clamp's
    arithmetic as in 6.21.2 (pypdf-r6 F1: 6.21.4's count of 0 changed which entries an update shadows), and is passed
    on as 0, so it reads no entry and counts no entry toward the limit.
- #4269's count is pypdf 6.21.4's, unchanged: a cross-reference stream's entries count at every read of it, so a
  stream that an older trailer's /XRefStm or the /Prev or startxref chain names again is read and counted again. A
  document whose reads add up past 2,000,000 entries is refused whatever its distinct entries: studio/ingest/pdf.py
  names it LIMIT_REACHED (advisory_limit), and ops/verify_passages.py cannot check it (CannotCheck, exit 2). That
  refusal is the named class S-limit. pypdf 6.21.2 read such a file (a re-read added no entry); plain 6.21.4, past the
  limit, leaves out the section whose read passed it and reads on, so a distinct section can be missing at status ok
  (pypdf-r6 V3). The refusal keeps a reading from ever being partial. The count is not deduplicated: reproducing
  6.21.2's re-reads needs re-reading, and re-reading without counting would reopen #4269's bound (pypdf-r7, -r8).

What the checks are for: they catch a pypdf that is not the proven one by accident (another version, a changed,
missing or extra file, a stale or foreign .pyc for a replaced or checked function, a binding the layer does not know).
They are not a defence against bytecode forged into site-packages (a module's loaded code is compared only for the
functions above): whoever can write there can change pypdf's behaviour without the layer noticing, as they could
without the layer.

Every check of the installed pypdf runs before anything is changed, and the checks after patching (each binding
holds its replacement; nothing reaches a replaced function) refuse too. Any failure raises PypdfCompatError and the
refusal sticks for the life of the process: the extraction child then fails the document with a named message and
records the reason for operators (engine 'pypdf_compat'), and never reads with unpatched behaviour. Importable
without Django; imports pypdf only when applied.
"""
from __future__ import annotations

import gc
import hashlib
import importlib
import os
import pathlib
import sys
import types
import weakref
from dataclasses import dataclass, field

PYPDF_VERSION = '6.21.4'
_FUTURE_ANNOTATIONS = 0x1000000  # __future__.annotations.compiler_flag: kept from the replaced code's own flags


class PypdfCompatError(Exception):
    """pypdf is not exactly what this layer was proven against, or the layer could not be applied completely."""


@dataclass(frozen=True)
class _Patch:
    target: str  # 'module:qualname'
    hunks: tuple  # the hunks of the pypdf 6.21.2 -> 6.21.4 diff it restores (HUNKS.tsv)
    lines: tuple  # (first, last): its lines in pypdf 6.21.4's file, decorators included (inspect.getsource's extent)
    original_sha256: str  # sha256 of those lines: pypdf 6.21.4's inspect.getsource text
    edits: tuple  # (old, new): each old occurs exactly once in that text
    result_sha256: str


@dataclass(frozen=True)
class _Checked:
    """A function the layer does not replace, whose loaded code must be what its proven source compiles to."""
    target: str  # 'module:qualname'
    fix: str  # the advisory fix it holds
    lines: tuple  # (first, last) in pypdf 6.21.4's file
    sha256: str


@dataclass
class _Plan:
    patch: _Patch
    owner: object  # the module or class that holds it
    name: str
    raw: object  # the attribute as held: a function, or a staticmethod wrapping one
    func: object
    replacement: object  # what the owner holds afterwards
    new_func: types.FunctionType
    bindings: list = field(default_factory=list)  # (module, attribute) that imported the function by name


_PATCHES = (
    _Patch('pypdf._cmap:_parse_encoding', ('_cmap.py @@ -114,7 +114,7 @@', '_cmap.py @@ -139,7 +139,9 @@'),
           (70, 150), '55fb9322af220378f5f15b327a507f60363cebc4dbbcd7be23bdb32f9b1325da',
           (
               ('            encoding = charset_encoding[cast(str, enc["/BaseEncoding"])].copy()\n'
                '        except KeyError:\n',
                '            encoding = charset_encoding[cast(str, enc["/BaseEncoding"])].copy()\n'
                '        except MemoryError:  # pypdf 6.21.4 lets MemoryError through (M, kept)\n'
                '            raise\n'
                '        except Exception:  # pypdf 6.21.2: any failure (an array or dictionary /BaseEncoding too)\n'),
               ('                        encoding[x] = _glyph_name_to_unicode(o) or o  # type: ignore[index]\n',
                '                        encoding[x] = adobe_glyphs[o]  # type: ignore[index]\n'),
           ),
           '58eedaefdeabfb64635561c1ced4c13a871b913fac0d136fff06cf69d202e80c'),
    _Patch('pypdf._cmap:_glyph_name_to_unicode', ('_cmap.py @@ -456,17 +458,20 @@',),
           (463, 476), '754a54900ba1b9aa563edbc7f8697e3855b9a949e31c790fc0f5f222975e0e46',
           (
               ('        if glyph_name.startswith("/uni"):\n'
                '            code_point = glyph_name[4:]\n'
                '        elif glyph_name.startswith("/u"):\n'
                '            code_point = glyph_name[2:]\n'
                '        else:\n'
                '            return None\n',
                '        if not glyph_name.startswith("/uni"):\n'
                '            return None\n'),
               ('            return chr(int(code_point, 16))\n',
                '            return chr(int(glyph_name[4:], 16))\n'),
           ),
           'd8203db34f5db94e60a7585b4670ca8f088e0bb1293dfda8c422cbdc5233eda0'),
    _Patch('pypdf._text_extraction:get_text_operands', ('_text_extraction/__init__.py @@ -214,7 +214,7 @@',),
           (187, 230), '493501e21a37f28fdf2fbeaf7aa64dda7d81b3cd8e0b82b5abf7c8ad3a5567f0',
           (
               ('                    text = tt.decode(font.encoding, "replace")\n',
                '                    text = tt.decode(font.encoding, "surrogateescape")\n'),
           ),
           '2da6ff077f90d1dd7801abeb386fd564c2ee6d7452a332b0d2fed725be82626b'),
    _Patch('pypdf.generic._font:Font._collect_cid_character_widths', ('generic/_font.py @@ -238,7 +238,7 @@',),
           (205, 279), '2d1e0d7fd521eee5dca83a9dfbc10593353799e4a93be17e8bf7203b97cfbb89',
           (
               ('                        chr(_cidx): _width.get_object()\n',
                '                        chr(_cidx): _width\n'),
           ),
           '6ddf7c26a2616860e70f65f89078b967fd8c99ae56f83211034e7f4eb1639939'),
    _Patch('pypdf._encryption:Encryption.read', ('_encryption.py @@ -1310,11 +1310,6 @@',),
           (1241, 1353), '9b4a70af3e55f39fe5d6a3db59ea59ef0029ca7b4d52541ad6e0259beece6e71',
           (
               ('            ) * 8\n'
                '        encrypt_metadata = ',
                '            ) * 8\n'
                '        if key_bits % 8 != 0 or not (40 <= key_bits <= 128 or key_bits == 256):\n'
                '            # ISO 32000-1:2008, 7.6.2 limits legacy key lengths to 40 to 128 bits\n'
                '            # in 8-bit increments. ISO 32000-2:2020, 7.6.6 allows 256-bit\n'
                '            # AESV3 keys. Reject other lengths before they reach cryptography.\n'
                '            raise PdfReadError(f"Invalid encryption key length: {key_bits} bits")\n'
                '        encrypt_metadata = '),
           ),
           '93f9ace9eb4bb1e24d866d483b429f6325751929d4539a39adbd73ed99201aab'),
    _Patch('pypdf.filters:FlateDecode.decode', ('filters.py @@ -198,13 +198,10 @@',),
           (179, 243), '9682e530f16925337f4ae88f50ebcf66ac6494f54595e61f951bf120654d3558',
           (
               ('        if isinstance(decode_parms, dict):\n'
                '            parameters = decode_parms\n'
                '        else:\n'
                '            if not is_null_or_none(decode_parms):\n',
                '        processed_parms: Optional[PdfObject] = decode_parms\n'
                '        if isinstance(decode_parms, IndirectObject) and processed_parms is not None:\n'
                '            processed_parms = processed_parms.get_object()\n'
                '        if isinstance(processed_parms, dict):\n'
                '            parameters = processed_parms\n'
                '        else:\n'
                '            if not is_null_or_none(processed_parms):\n'),
           ),
           '376651bf590c153e1a72ec31011556055f0df8efc7c910174b645bd42e7e3be1'),
    _Patch('pypdf.filters:CCITTFaxDecode._get_parameters', ('filters.py @@ -742,26 +739,44 @@',),
           (737, 789), '832a31754a63b9fde747fbda27ab9b90de81d7c515972d1976abc63e5ee2932f',
           (
               ('        def get_integer(value: Any, key: str) -> int:\n'
                '            if isinstance(value, PdfObject):\n'
                '                value = value.get_object()\n'
                '            if not isinstance(value, int):\n'
                '                raise PdfReadError(f"Expected integer for {key}, got {type(value).__name__}: {value!r}!")\n'
                '            return value\n'
                '\n'
                '        def get_boolean(value: Any, key: str) -> bool:\n'
                '            if not isinstance(value, BooleanObject):\n'
                '                raise PdfReadError(f"Expected boolean for {key}, got {type(value).__name__}: {value!r}!")\n'
                '            return value.value\n'
                '\n'
                '        ccitt_parameters = CCITTParameters(\n'
                '            rows=0 if is_null_or_none(rows) else get_integer(rows, CCITT.ROWS)\n'
                '        )\n'
                '        if parameters:\n'
                '            parameters_unwrapped = parameters.get_object()\n'
                '            if isinstance(parameters_unwrapped, ArrayObject):\n'
                '                decode_parm_list = list(parameters_unwrapped)\n'
                '            else:\n'
                '                decode_parm_list = [parameters_unwrapped]\n'
                '            for decode_parm in decode_parm_list:\n'
                '                if isinstance(decode_parm, PdfObject):\n'
                '                    decode_parm = decode_parm.get_object()\n'
                '                if is_null_or_none(decode_parm):\n'
                '                    continue\n'
                '                if not isinstance(decode_parm, dict):\n'
                '                    logger_warning(\n'
                '                        "Ignoring invalid DecodeParms entry: %(value)s",\n'
                '                        source=__name__, value=decode_parm,\n'
                '                    )\n'
                '                    continue\n'
                '                if CCITT.K in decode_parm:\n'
                '                    ccitt_parameters.K = get_integer(decode_parm[CCITT.K], CCITT.K)\n'
                '                if CCITT.COLUMNS in decode_parm:\n'
                '                    ccitt_parameters.columns = get_integer(decode_parm[CCITT.COLUMNS], CCITT.COLUMNS)\n'
                '                if CCITT.BLACK_IS_1 in decode_parm:\n'
                '                    ccitt_parameters.BlackIs1 = get_boolean(decode_parm[CCITT.BLACK_IS_1], CCITT.BLACK_IS_1)\n'
                '\n'
                '        if ccitt_parameters.columns < 0 or ccitt_parameters.columns > CCITTFaxDecode._MAXIMUM_UNSIGNED_LONG:\n'
                '            raise PdfReadError(\n'
                '                f"Expected valid 32 bit unsigned value for {CCITT.COLUMNS}, got {ccitt_parameters.columns}!"\n'
                '            )\n'
                '        if ccitt_parameters.rows < 0 or ccitt_parameters.rows > CCITTFaxDecode._MAXIMUM_UNSIGNED_LONG:\n'
                '            raise PdfReadError(\n'
                '                f"Expected valid 32 bit unsigned value for {CCITT.ROWS}, got {ccitt_parameters.rows}!"\n'
                '            )\n'
                '        return ccitt_parameters\n',
                '        ccitt_parameters = CCITTParameters(rows=int(rows))\n'
                '        if parameters:\n'
                '            parameters_unwrapped = cast(\n'
                '                Union[ArrayObject, DictionaryObject], parameters.get_object()\n'
                '            )\n'
                '            if isinstance(parameters_unwrapped, ArrayObject):\n'
                '                for decode_parm in parameters_unwrapped:\n'
                '                    if CCITT.K in decode_parm:\n'
                '                        ccitt_parameters.K = decode_parm[CCITT.K].get_object()\n'
                '                    if CCITT.COLUMNS in decode_parm:\n'
                '                        ccitt_parameters.columns = decode_parm[CCITT.COLUMNS].get_object()\n'
                '                    if CCITT.BLACK_IS_1 in decode_parm:\n'
                '                        ccitt_parameters.BlackIs1 = decode_parm[CCITT.BLACK_IS_1].get_object().value\n'
                '            else:\n'
                '                if CCITT.K in parameters_unwrapped:\n'
                '                    ccitt_parameters.K = parameters_unwrapped[CCITT.K].get_object()  # type: ignore[assignment]\n'
                '                if CCITT.COLUMNS in parameters_unwrapped:\n'
                '                    ccitt_parameters.columns = parameters_unwrapped[CCITT.COLUMNS].get_object()  # type: ignore[assignment]\n'
                '                if CCITT.BLACK_IS_1 in parameters_unwrapped:\n'
                '                    ccitt_parameters.BlackIs1 = parameters_unwrapped[CCITT.BLACK_IS_1].get_object().value  # type: ignore[union-attr]\n'
                '\n'
                '        if ccitt_parameters.columns < 0 or ccitt_parameters.columns > CCITTFaxDecode._MAXIMUM_UNSIGNED_LONG:\n'
                '            raise PdfReadError(\n'
                '                f"Expected valid 32 bit unsigned value for {CCITT.COLUMNS}, got {ccitt_parameters.columns}!"\n'
                '            )\n'
                '        if ccitt_parameters.rows < 0 or ccitt_parameters.rows > CCITTFaxDecode._MAXIMUM_UNSIGNED_LONG:\n'
                '            raise PdfReadError(\n'
                '                f"Expected valid 32 bit unsigned value for {CCITT.ROWS}, got {ccitt_parameters.rows}!"\n'
                '            )\n'
                '        return ccitt_parameters\n'),
           ),
           '3c43ef72c137975ca8d6b2fff08cb929b59297b59ab28503da5963b46b11194c'),
    _Patch('pypdf.filters:decode_stream_data', ('filters.py @@ -967,10 +982,17 @@', 'filters.py @@ -988,7 +1010,7 @@'),
           (933, 1034), 'da01f1a497f3f18f5f455d440131470c3c2bb96fedfeb835e825411610549e0a',
           (
               ('        params = params.get_object()\n'
                '        if is_null_or_none(params):\n'
                '            # The decoders are typed for a DictionaryObject; a plain {} is not\n'
                '            # one, so a null /DecodeParms entry would hand them the wrong type.\n'
                '            params = DictionaryObject()\n'
                '        elif not isinstance(params, (dict, list)):\n'
                '            logger_warning(\n'
                '                "Ignoring invalid DecodeParms: %(value)s",\n'
                '                source=__name__, value=params,\n'
                '            )\n'
                '            params = DictionaryObject()\n',
                '        if isinstance(params, NullObject):\n'
                '            # The decoders are typed for a DictionaryObject; a plain {} is not\n'
                '            # one, so a null /DecodeParms entry would hand them the wrong type.\n'
                '            params = DictionaryObject()\n'),
               ('            height = stream.get(ImageAttributes.HEIGHT, 0)\n',
                '            height = stream.get(ImageAttributes.HEIGHT, ())\n'),
           ),
           '581d6148f55f9bb0b664e89ba19194c596a9464f7634d6d6a76d2817c32ce8d0'),
    _Patch('pypdf._page:PageObject._extract_text', ('_page.py @@ -1956,7 +1960,9 @@',),
           (1871, 2034), '59d9347ab51d1b401b4036e5eea264d4d83c3bd91be940615b8d039e2cec4c9b',
           (
               ('            elif operator == b"TD" and len(operands) >= 2:\n'
                '                # a non-numeric ty leaves the leading unchanged, like a non-numeric TL\n'
                '                if isinstance(operands[1], (int, float)):\n'
                '                    extractor.process_operation(b"TL", [-operands[1]])\n',
                '            elif operator == b"TD" and len(operands) >= 2:\n'
                '                extractor.process_operation(b"TL", [-operands[1]])\n'),
           ),
           'e9a7c163eca410d51cc8a7a94b9317fcf809d8e6d47612dd181eb91a7e985a47'),
    # Not a restore: the advisory fix #4265 (CVE-2026-119207) stays, its fixed message and truncated warning included;
    # only its MemoryError is raised as itself, as 6.21.4 raises it everywhere else (the M lines), so the reader names
    # it ("needs more memory") instead of reading a partial dictionary or calling the file damaged.
    _Patch('pypdf.generic._data_structures:DictionaryObject.read_from_stream',
           ('generic/_data_structures.py @@ -675,12 +680,12 @@',),
           (625, 711), '4867dab3632d970bdc7ca59eeb50d6fa01d5fd1eadf8202d36170f8280b1649a',
           (
               ('            except (MemoryError, RecursionError) as exc:\n'
                '                raise PdfReadError("Error reading PDF file.") from exc\n',
                '            except MemoryError:  # #4265 kept, its outcome named: raised as itself, not as a read error\n'
                '                raise\n'
                '            except RecursionError as exc:\n'
                '                raise PdfReadError("Error reading PDF file.") from exc\n'),
           ),
           'aa37af7c1452a6b01899feb9e45c47250229c1745e3ac820ffb60c2674a4e389'),
    # Not a restore: #4269 (CVE-2026-119209) also turned a negative /Index count into 0 before the clamp to the
    # stream's size, which changes the clamp's running total, so the counts after it, and so which entries an update
    # shadows: a small update read a superseded definition's text on 6.21.2 and the current one on 6.21.4 (pypdf-r6
    # F1). The count takes part in the arithmetic as in 6.21.2 and is passed on as 0, so it reads no entry and counts
    # no entry toward #4269's limit, which still bounds every entry read; its warning and strict refusal stay.
    _Patch('pypdf._reader:PdfReader._sanitize_pdf15_xref_stream_index_pairs', ('_reader.py @@ -1343,6 +1366,16 @@',),
           (1344, 1397), '036a6c34089d465e6ddc736d4e477315f6ba85e272f2228f6442cabb885d745f',
           (
               ('                        count=pair_value_int,\n'
                '                    )\n'
                '                    pair_value_int = 0\n',
                '                        count=pair_value_int,\n'
                '                    )\n'),
               ('                total += pair_value_int\n',
                '                total += pair_value_int  # pypdf 6.21.2: a negative count lowers the total\n'
                '                pair_value_int = max(pair_value_int, 0)  # pypdf_compat: no entry read or counted\n'),
           ),
           'dc89932b5e9a009b6a4a878aa20ba50e4c0a6efe29c26f962bc401d14dbf4f49'),
)

# Advisory fixes the reader depends on that no patch replaces: their loaded code is checked against their proven
# source, as each patch target's is (pypdf-r6 FC-2), and nothing in them is changed.
_CHECKED = (
    _Checked('pypdf._reader:PdfReader.__init__', '#4269 (its limit and counter)', (127, 173),
             '1e90b0f398c8165a98acac19304febd0a51607dc16bd680b21ac92b4bb6f2189'),
    _Checked('pypdf._reader:PdfReader._read_xref_tables_and_trailers', '#4269 (the counter reset once per read)',
             (1204, 1257), 'a2891c413587db9347d277f10486af121d23bb2afe5f5adc3935d81544df8505'),
    _Checked('pypdf._reader:PdfReader._read_xref', '#4269 (every /XRefStm naming read; one past the limit logged)',
             (1274, 1301), '2def5dbdfdc44a8cff68b5247e0ff4015e05382612a65224216d58e8f0676ac5'),
    _Checked('pypdf._reader:PdfReader._read_pdf15_xref_stream', '#4269 (the entries counted, the limit raised)',
             (1399, 1451), '4cc029555150139c32bd4cf3798c94985a7dcfd07279eb147c24d56e6cfedf6b'),
    _Checked('pypdf._doc_common:PdfDocCommon._flatten', '#4290 (the page entries allowed)', (1356, 1434),
             '7996c058fd2f29018e4387e22557cce1a721385098a2111b34146fe4059f40b2'),
    _Checked('pypdf._doc_common:PdfDocCommon._flatten_leaf_page', '#4290 (the page entries counted, the limit raised)',
             (1507, 1545), '598daba37c44b00affe7ff9ce7f82d3f17ebfc8e4afc463afb381084ff673d12'),
)

# A name a replacement reads that pypdf 6.21.4's module no longer imports (hunk filters.py @@ -66,9 +66,9 @@):
# (module, name, source module, source name).
_RESTORED_GLOBALS = (('pypdf.filters', 'NullObject', 'pypdf.generic', 'NullObject'),)

# Every module attribute that may hold a replaced function, besides the attribute it is defined as: found by
# scanning sys.modules with every pypdf module and the reader imported (pypdf-r6 design, "bindings").
_BINDINGS = frozenset({
    'pypdf._text_extraction._text_extractor.get_text_operands',  # from . import ... get_text_operands
    'studio.ingest.pdfcontent.get_text_operands',  # the reader measures text as pypdf does (when imported first)
})

# sha256 of every source file of pypdf 6.21.4 as published (its wheel's RECORD agrees), by path in the package.
_MANIFEST = {
    '__init__.py': 'd7786f1b3cb2e52e28b1085f0ea150fa7f029baad252b29af7415c790871f7df',
    '_cmap.py': '8b3edbb61399302e966cbaadd6a863708c2b4de85bdb69813851ee9eea6de926',
    '_codecs/__init__.py': '574b0332eb98897f512be3fafb06e7724b81618c1f03014ca49823e13683dffe',
    '_codecs/_codecs.py': 'ead39a397326cd52a6e0a433e33bbf6cd0cae6e24fb6ab06b93e069c4a764c43',
    '_codecs/adobe_glyphs.py': '69ac4e46ea50409ee46cb0c76e35a280b67aa60f06f7fe5ea832a2349c72923e',
    '_codecs/core_font_metrics.py': 'dbb26cac9a39511246215ed90ce09427259f066e8b0567aaeefdce5b3a05f21f',
    '_codecs/pdfdoc.py': 'c5f4af30562cbf1b9a490d14bbdbd90ca681d16bbce61d6e0a20758bdac07145',
    '_codecs/std.py': '0f240cb84a40184a52f6ecb58d67f87278fe92a4a13ce0228f9b08ed0d580fc1',
    '_codecs/symbol.py': '08fe958d172c72b9bcca6007f74c6977155a7a5c22e8c49bd536f5c0d0e1d359',
    '_codecs/zapfding.py': 'e39a9c635d716c1c2da21ebfb7467fef33631bbfaa238d752d14155d828faf65',
    '_configuration.py': '9d8c16d16023b0612f61ca03109159d8cb6345d91cd35b8d7fce52bebc9efc7f',
    '_crypt_providers/__init__.py': 'c5441b160310bca31a38e4f7454756ddb4bc7d94a147c3c13b3eab7ac7f05855',
    '_crypt_providers/_base.py': '34505711d85bae0f64d353d57cd37f93b94401897606481720e8b9a1f53ff91f',
    '_crypt_providers/_cryptography.py': '33183bb4201aa15e950085a97ee874e2af254be0aaeb9ab0de643d7e93100526',
    '_crypt_providers/_fallback.py': '81772ba3f2bbab82180cbe57195471a059978d75cc6ba4e57830f0c56c828f81',
    '_crypt_providers/_pycryptodome.py': 'bd9102129a13f4ebe9a46ebb74aec456de51e5aa491bd5fce588a3479ed2a6f6',
    '_doc_common.py': 'fdb120c74ef3bd723b0783a9dbe23ba08331532d149ce01ca5aa50b4d571b115',
    '_encryption.py': '342c3ee9fd8cca74bf4be3fe3cb60cc9651aac6025b38f34820321bef85c29fa',
    '_page.py': 'd048e72108dc64e16d12d647eee729362abe3630b897d32f0e40b3985d5a763a',
    '_page_labels.py': '874759c0ee0376c6924b629f553528f21024ac9c14a71987012546907d89115d',
    '_protocols.py': '4e4ea32b83d1f71cc4ec44e7a9a7f6ef5494299913b3a2254672d118f9588ff7',
    '_reader.py': '55bbb1b10a5721a7bad12954a598f6f8beaaacd138d2f771cd97e8b99a1d0514',
    '_text_extraction/__init__.py': '6adc0f09de4efbdd37d61b1681e5263f1d9132cf57e8812254a97fe278e0a8d7',
    '_text_extraction/_layout_mode/__init__.py': '56adb80f37575f9af91995d319579011c9212ed332099acdf207db4a506efecc',
    '_text_extraction/_layout_mode/_fixed_width_page.py': '99734328472c3bdd10cafb4a0caf2fb92b2f61953ba2f63287bfcb5e68994605',
    '_text_extraction/_layout_mode/_text_state_manager.py': '994da1a3d4de7eda11690d80c3744b8e6d396ed6bc05b629527bf760001bd848',
    '_text_extraction/_layout_mode/_text_state_params.py': '5634f0811c865ba97a4d0cc3b12ec8205cb3953fa95d41472768ed930c9d5d8d',
    '_text_extraction/_text_extractor.py': 'baca865ba63ef8bee5e737499fb606901092d5110141ed1a673a146f95fe706a',
    '_utils.py': 'cfaea0f7eadfda43798adaba2bcdf91e804ee11c12c772e11e6591f39be78e50',
    '_version.py': '0d7708d5feb00100c4ccc8d09469a7131dc4d01da831deb95da7e2b29c0fc0ba',
    '_writer.py': '1e95f388a3d6d716fc31045c31a5c9a6f17538325823c4ca4a17431d39163f03',
    'actions/__init__.py': 'd8bdd81ef60846bab097640490991e4b63bd6b521eb0356ed696e24854299518',
    'actions/_actions.py': '9ad300bde70c006ba9484e0d78296103c0dcdafa75038248f3bde6a988cd6c4b',
    'annotations/__init__.py': '7f693ffa3027dfd082076ecac50fdef771a29e7ce40076d49e749e1899758f21',
    'annotations/_base.py': '608453cd3764aa3f035164939b2d1fae47d3af88e87b91d41b344e5287f8a08a',
    'annotations/_markup_annotations.py': 'c210635217f7c5195cae67829cd82a1679ad2767fb07c2289f82b8e88f74a079',
    'annotations/_non_markup_annotations.py': 'fd2cd3ce864ce01dff1bf57a33ff266c9e7b630d2d024f601db347ea5211ab70',
    'constants.py': '579bd3b09defab4b63ac63f7effb4713ade10722c8c7799b8566aa80917c3624',
    'errors.py': '070d56f61c4eb03830ab053a628436974f89894c93aba979423542afe5b81850',
    'filters.py': 'c870b8235de4b0b93b3e01d0ef2c2b490db3dbedaafc0ec47736dd3d40ac5f93',
    'generic/__init__.py': '3bbfbe5ca9a0e6fd1f3f7718960def531794e3c35ceec6b204cb03119eb546b5',
    'generic/_appearance_stream.py': '4f572ec49a2c290b0389ed7b30758ac21855f1c3b8efc71eeb013e29ebfe22b4',
    'generic/_base.py': '8397982fa37b56d52bfdc1c6fc708cb86b8327f64716f0296ff532fb995d8080',
    'generic/_color.py': '2b10852d96453098d4b9b2f437ad85042a552b37038403c1f6719ba29e3c795c',
    'generic/_data_structures.py': 'a2c0ee0c3bac0d584659177263e2e26e4222e5315d7e72838e9f0eb001d7c79f',
    'generic/_files.py': '5a582054cca80cd045b128fdc90ab293ff15d63b75895265302a86f03d277966',
    'generic/_fit.py': '607a2571a31e1c67d84fdb0d1a3dbfd04b52a09619d9a261b4aa9525c03887f9',
    'generic/_font.py': '03628263532c0da3dc56d97166cb1a3d89671ebee88af34692c9758d14dbb462',
    'generic/_image_inline.py': 'a708cc06e98c88b0972a6367e6513282b0fd35599c8429c26ff0573a0058f7cc',
    'generic/_image_xobject.py': '90a667695d1002a18545e554352728a4a125754799e273e7c92fb48969e9bf1c',
    'generic/_link.py': '9fe346b50e3f01fb7dfe6d6fd272af4f2b355526ba5b9e0fc5aede36d3e03ca4',
    'generic/_outline.py': '3c4b924f86fe2a6010203009d05872c4dec036626376c59a4ddc4aa3b862ab78',
    'generic/_rectangle.py': 'ec7ac97ce31ab906ad0368245a17074a4cc1ec5e245a671afba90d03a1d5a3a3',
    'generic/_utils.py': '33c8bde72a42e65d9eef5d74f157aaf74bdb6d4b65427beefbe256fc0b32c793',
    'generic/_viewerpref.py': '24c98e21100d57dc69d797483627cbeec256290ba532015f523038c68d45308d',
    'pagerange.py': '0209c3144e2959cf34d1800cfec3dc1afcb6f747f70f93588abaf6e478753b46',
    'papersizes.py': 'e93cf9b1f34dff724e51aa58f3753e95a928867a57600d2148440d98e54b14bf',
    'types.py': 'b09ef01f393b111fc227b90ffacf2ef5ac459e40979c5a6bf27cdc8f50314dab',
    'xmp.py': '0fb1996e355223d8ad669d289f16eb7e0ad9cd3314e8005cdb4c03defd876fea',
}

_applied: tuple | None = None
_refused: str | None = None


def apply() -> tuple:
    """Apply the layer once per process; return what was applied ((target, hunks, rebound attributes), ...).

    Raises PypdfCompatError, then and on every later call, if it cannot be applied completely."""
    global _applied, _refused
    if _applied is not None:
        return _applied
    if _refused is not None:
        raise PypdfCompatError(_refused)
    try:
        _applied = _apply()
    except PypdfCompatError as exc:
        _refused = str(exc)
        raise
    except MemoryError:  # named by the child as every memory failure is; this process reads nothing more
        _refused = 'memory ran out while applying the layer'
        raise
    except Exception as exc:  # any other failure is a refusal too: nothing reads with a half-applied layer
        _refused = f'unexpected {type(exc).__name__}: {exc}'
        raise PypdfCompatError(_refused) from exc
    return _applied


def applied() -> tuple | None:
    """What apply() applied in this process, or None."""
    return _applied


def _apply() -> tuple:
    import pypdf  # noqa: PLC0415

    if pypdf.__version__ != PYPDF_VERSION:
        raise PypdfCompatError(f'pypdf {pypdf.__version__} is installed; this layer is proven for {PYPDF_VERSION}.')
    root = _check_manifest(pypdf)
    # 1. Check and build everything; nothing is changed yet.
    plans = [_plan(root, patch) for patch in _PATCHES]
    for checked in _CHECKED:
        _check_function(root, checked)
    restored = [(importlib.import_module(module), name, getattr(importlib.import_module(source), source_name))
                for module, name, source, source_name in _RESTORED_GLOBALS]
    for module, name, _ in restored:
        if name in vars(module):
            raise PypdfCompatError(f'{module.__name__}.{name} is already bound.')
    _check_loaded(root)
    _bindings(plans)
    # 2. Patch.
    for module, name, value in restored:
        setattr(module, name, value)
    for plan in plans:
        setattr(plan.owner, plan.name, plan.replacement)
        for module, attribute in plan.bindings:
            setattr(module, attribute, plan.new_func)
    # 3. Verify: every binding holds its replacement, and nothing reaches a replaced function any more.
    report = tuple((plan.patch.target, plan.patch.hunks,
                    tuple(f'{module.__name__}.{attribute}' for module, attribute in plan.bindings)) for plan in plans)
    gone = [(plan.patch.target, weakref.ref(plan.func)) for plan in plans]
    for plan in plans:
        if vars(plan.owner)[plan.name] is not plan.replacement or any(
                vars(module)[attribute] is not plan.new_func for module, attribute in plan.bindings):
            raise PypdfCompatError(f'{plan.patch.target}: a binding does not hold its replacement.')
        plan.raw = plan.func = None
    del plans
    if any(ref() is not None for _, ref in gone):
        gc.collect()  # a replaced function held only by a reference cycle is released here
    alive = [target for target, ref in gone if ref() is not None]
    if alive:
        raise PypdfCompatError(f'still reachable after patching: {", ".join(alive)}.')
    return report


def _check_manifest(pypdf) -> pathlib.Path:
    root = pathlib.Path(pypdf.__file__).parent
    found = {path.relative_to(root).as_posix(): path for path in root.rglob('*.py')}
    if set(found) != set(_MANIFEST):
        raise PypdfCompatError("pypdf's source files are not the proven set.")
    for relative, path in found.items():
        if hashlib.sha256(path.read_bytes()).hexdigest() != _MANIFEST[relative]:
            raise PypdfCompatError(f'pypdf/{relative} is not the proven file.')
    return root


def _check_loaded(root: pathlib.Path) -> None:
    """Every pypdf module loaded is a file of the checked package (no other copy of pypdf shadows it)."""
    prefix = str(root) + os.sep
    for name, module in list(sys.modules.items()):
        if name == 'pypdf' or name.startswith('pypdf.'):
            path = getattr(module, '__file__', None)
            if not path or not path.startswith(prefix) or '..' in path[len(prefix):]:
                raise PypdfCompatError(f'{name} is not loaded from the checked pypdf.')


def _owner(module, qualname: str):
    if '.' not in qualname:
        return module, qualname
    cls, name = qualname.split('.')
    return getattr(module, cls), name


def _function(target: str):
    """(module, owner, name, the attribute as held, the function) for 'module:qualname'."""
    module_name, qualname = target.split(':')
    module = importlib.import_module(module_name)
    owner, name = _owner(module, qualname)
    raw = vars(owner).get(name)
    func = raw.__func__ if isinstance(raw, (staticmethod, classmethod)) else raw
    if not isinstance(func, types.FunctionType):
        raise PypdfCompatError(f'{target} is not a function.')
    return module, owner, name, raw, func


def _source(root: pathlib.Path, module, target: str, lines: tuple, sha256: str) -> str:
    """Lines ``lines`` (first, last) of the module's file: the text inspect.getsource gives for the function there,
    read from the file's bytes, which are hashed again here (the text is the proven file's even if the file changed
    since _check_manifest). Never through inspect, tokenize or linecache: they keep a copy of each whole file they read
    for the life of the process, which the extraction child's address-space limit paid for (pypdf-r6 F3)."""
    path = pathlib.Path(module.__file__)
    try:
        relative = path.relative_to(root).as_posix()
    except ValueError:
        raise PypdfCompatError(f'{module.__name__} is not loaded from the checked pypdf.') from None
    data = path.read_bytes()
    if hashlib.sha256(data).hexdigest() != _MANIFEST.get(relative):
        raise PypdfCompatError(f'pypdf/{relative} is not the proven file.')
    first, last = lines
    if data.count(b'\n') < last or not 0 < first <= last:
        raise PypdfCompatError(f'{target}: its source is not the proven text.')
    start = 0
    for _ in range(first - 1):
        start = data.index(b'\n', start) + 1
    end = start
    for _ in range(last - first + 1):
        end = data.index(b'\n', end) + 1
    text = data[start:end].decode('utf-8')
    if hashlib.sha256(text.encode('utf-8')).hexdigest() != sha256:
        raise PypdfCompatError(f'{target}: its source is not the proven text.')
    return text


def _check_function(root: pathlib.Path, checked: _Checked) -> None:
    """A function the layer keeps as it is: its loaded code must be what its proven source compiles to."""
    module, owner, name, _, func = _function(checked.target)
    source = _source(root, module, checked.target, checked.lines, checked.sha256)
    if not _same_code(func.__code__, _compile(module, owner, name, source, checked.lines[0], func)):
        raise PypdfCompatError(f'{checked.target}: its loaded code is not its source.')


def _plan(root: pathlib.Path, patch: _Patch) -> _Plan:
    module, owner, name, raw, func = _function(patch.target)
    first = patch.lines[0]
    source = _source(root, module, patch.target, patch.lines, patch.original_sha256)
    if not _same_code(func.__code__, _compile(module, owner, name, source, first, func)):
        raise PypdfCompatError(f'{patch.target}: its loaded code is not its source.')
    text = source
    for old, new in patch.edits:
        if text.count(old) != 1:
            raise PypdfCompatError(f'{patch.target}: an edit does not apply exactly once.')
        text = text.replace(old, new, 1)
    if hashlib.sha256(text.encode('utf-8')).hexdigest() != patch.result_sha256:
        raise PypdfCompatError(f'{patch.target}: the replacement is not the proven text.')
    # Its code says where it came from: a traceback names '<pypdf_compat target>' at pypdf's own line numbers (no
    # linecache entry is kept for it; the edited lines are in _PATCHES).
    new_func = _define(module, owner, name, text, first, func, f'<pypdf_compat {patch.target}>')
    if new_func.__code__.co_freevars or func.__code__.co_freevars:
        raise PypdfCompatError(f'{patch.target}: a replaced function must not close over variables.')
    replacement = type(raw)(new_func) if isinstance(raw, (staticmethod, classmethod)) else new_func
    return _Plan(patch, owner, name, raw, func, replacement, new_func)


def _compile(module, owner, name: str, source: str, first: int, original) -> types.CodeType:
    """The code object ``source`` (one function, as inspect.getsource gives it) compiles to where it stands: at its
    proven first line ``first``, inside its class (for name mangling), with the module's own future flags."""
    code = compile(_placed(module, owner, source, first), original.__code__.co_filename, 'exec',
                   flags=original.__code__.co_flags & _FUTURE_ANNOTATIONS, dont_inherit=True)
    found = [const for const in (code.co_consts if owner is module else _class_body(code, owner.__name__).co_consts)
             if isinstance(const, types.CodeType) and const.co_name == name]
    if len(found) != 1:
        raise PypdfCompatError(f'{module.__name__}:{name}: its source does not compile to one function.')
    return found[0]


def _placed(module, owner, source: str, first: int) -> str:
    """``source`` where it stands in its module: at line ``first``, inside its class (name mangling), after a
    never-run line holding the module's own imports (the compiler emits a different call sequence for an attribute
    of an imported module, so the code compares equal only in that context)."""
    if owner is module:
        return _prelude(module) + '\n' * (first - 2) + source
    return _prelude(module) + '\n' * (first - 3) + f'class {owner.__name__}:\n' + source


# The names each touched module binds by import statements at its top level (computed from the proven file).
_IMPORTED = {
    'pypdf._cmap': ('Any', 'ArrayObject', 'BinasciiError', 'BytesIO', 'Callable', 'DecodedStreamObject', 'DictionaryObject', 'LimitReachedError', 'NullObject', 'StreamObject', 'Union', '_FontFileCharacterMap', 'adobe_glyphs', 'cast', 'charset_encoding', 'logger_error', 'logger_warning', 'partial', 'sha256', 'unhexlify'),
    'pypdf._doc_common': ('ABC', 'Any', 'ArrayObject', 'BooleanObject', 'ByteStringObject', 'CA', 'CheckboxRadioButtonAttributes', 'Core', 'DI', 'Destination', 'DictionaryObject', 'EmbeddedFile', 'EncodedStreamObject', 'Encryption', 'FA', 'Field', 'Fit', 'FloatObject', 'GoToActionArguments', 'IndirectObject', 'Iterable', 'Iterator', 'LimitReachedError', 'Mapping', 'NameObject', 'NamedTuple', 'NoReturn', 'NullObject', 'Optional', 'OutlineType', 'PG', 'PageObject', 'PagemodeType', 'PagesAttributes', 'PdfObject', 'PdfReadError', 'PyPdfError', 'Sequence', 'TextStringObject', 'TreeObject', 'Union', 'UserAccessPermissions', 'ViewerPreferences', 'XmpInformation', '_TraversalState', '_VirtualList', '_decompress_with_limit', 'abstractmethod', 'cast', 'create_string_object', 'datetime', 'deprecate_no_replacement', 'deprecation_with_replacement', 'get_configuration', 'index2labels', 'is_null_or_none', 'logger_warning', 'parse_iso8824_date', 'struct'),
    'pypdf._encryption': ('Any', 'ArrayObject', 'BooleanObject', 'ByteStringObject', 'CryptAES', 'CryptBase', 'CryptIdentity', 'CryptRC4', 'DictionaryObject', 'Enum', 'IntEnum', 'NameObject', 'NullObject', 'NumberObject', 'Optional', 'PdfObject', 'PdfReadError', 'StreamObject', 'TextStringObject', 'Union', 'aes_cbc_decrypt', 'aes_cbc_encrypt', 'aes_ecb_decrypt', 'aes_ecb_encrypt', 'create_string_object', 'hashlib', 'logger_warning', 'rc4_decrypt', 'rc4_encrypt', 'secrets', 'stringprep', 'struct', 'unicodedata'),
    'pypdf._page': ('Action', 'AnnotationDictionaryAttributes', 'Any', 'ArrayObject', 'BytesIO', 'Callable', 'CompressedTransformationMatrix', 'ContentStream', 'Decimal', 'DictionaryObject', 'EncodedStreamObject', 'FloatObject', 'Font', 'Image', 'ImageAttributes', 'IndirectObject', 'Iterable', 'Iterator', 'Literal', 'NameObject', 'NullObject', 'NumberObject', 'Optional', 'PG', 'PageSizeNotDefinedError', 'PageTrigger', 'Path', 'PdfCommonDocProtocol', 'PdfObject', 'PdfReadError', 'RES', 'RectangleObject', 'Sequence', 'StreamObject', 'TextExtraction', 'TransformationMatrixType', 'Union', '_INLINE_IMAGE_KEY_MAPPING', '_INLINE_IMAGE_VALUE_MAPPING', '_TraversalState', '_human_readable_bytes', '_layout_mode', 'asdict', 'cast', 'dataclass', 'deepcopy', 'deprecate', 'deprecate_no_replacement', 'deprecate_with_replacement', 'get_configuration', 'is_null_or_none', 'logger_warning', 'math', 'matrix_multiply', 'overload'),
    'pypdf._reader': ('Any', 'ArrayObject', 'ByteStringObject', 'BytesIO', 'Callable', 'Destination', 'DictionaryObject', 'EmptyFileError', 'EncodedStreamObject', 'Encryption', 'FileNotDecryptedError', 'IndirectObject', 'Iterable', 'LimitReachedError', 'NameObject', 'NullObject', 'NumberObject', 'Optional', 'PageObject', 'PasswordType', 'Path', 'PdfDocCommon', 'PdfObject', 'PdfReadError', 'PdfStreamError', 'Self', 'StrByteType', 'StreamObject', 'StreamType', 'TK', 'TYPE_CHECKING', 'TextStringObject', 'TracebackType', 'Union', 'UnsupportedOperation', 'WHITESPACES_AS_BYTES', 'WrongPasswordError', 'XmpInformation', 'apply_legacy_configuration', 'cast', 'convert_to_int', 'get_stream_data', 'get_stream_size', 'is_null_or_none', 'itemgetter', 'logger_warning', 'os', 're', 'read_non_whitespace', 'read_object', 'read_previous_line', 'read_until_whitespace', 'skip_over_comment', 'skip_over_whitespace', 'sys'),
    'pypdf._text_extraction': ('Any', 'Callable', 'DictionaryObject', 'Font', 'Literal', 'Mapping', 'Optional', 'TextStringObject', 'Union', 'encode_pdfdocencoding', 'is_char_neutral', 'is_char_rtl', 'math'),
    'pypdf.filters': ('Any', 'ArrayObject', 'BooleanObject', 'CCITT', 'DependencyError', 'DictionaryObject', 'FT', 'FTA', 'ImageAttributes', 'IndirectObject', 'LZW', 'LimitReachedError', 'NoReturn', 'NumberObject', 'Optional', 'Path', 'PdfObject', 'PdfReadError', 'PdfStreamError', 'StreamAttributes', 'StreamObject', 'TemporaryDirectory', 'Union', 'WHITESPACES_AS_BYTES', '_LzwCodec', 'a85decode', 'binascii', 'cast', 'dataclass', 'deprecate', 'deprecation_with_replacement', 'find_spec', 'get_configuration', 'is_null_or_none', 'logger_warning', 'lru_cache', 'math', 'os', 'shutil', 'struct', 'subprocess', 'zlib'),
    'pypdf.generic._data_structures': ('Any', 'BinaryStreamType', 'BooleanObject', 'ByteStringObject', 'BytesIO', 'Callable', 'CheckboxRadioButtonAttributes', 'FT', 'FieldDictionaryAttributes', 'Fit', 'FloatObject', 'IndirectObject', 'Iterable', 'LimitReachedError', 'NameObject', 'NamedTuple', 'NullObject', 'NumberObject', 'Optional', 'OutlineFontFlag', 'PdfObject', 'PdfReadError', 'PdfReaderProtocol', 'PdfStreamError', 'PdfWriterProtocol', 'STREAM_TRUNCATED_PREMATURELY', 'Self', 'Sequence', 'StreamAttributes', 'StreamParsingBudget', 'StreamType', 'TA', 'TF', 'TextStringObject', 'Union', 'WHITESPACES', 'XmpInformationProtocol', 'cast', 'ceil', 'deprecation_no_replacement', 'extract_inline__ascii85_decode', 'extract_inline__ascii_hex_decode', 'extract_inline__dct_decode', 'extract_inline__run_length_decode', 'extract_inline_default', 'get_configuration', 'is_null_or_none', 'logger_warning', 'logging', 'os', 're', 'read_hex_string_from_stream', 'read_non_whitespace', 'read_string_from_stream', 'read_until_regex', 'read_until_whitespace', 'skip_over_comment', 'skip_over_comments', 'sys'),
    'pypdf.generic._font': ('Any', 'ArrayObject', 'BytesIO', 'ClassVar', 'DefaultTable', 'DictionaryObject', 'FloatObject', 'FontFlags', 'IndirectObject', 'LimitReachedError', 'NameObject', 'NumberObject', 'PdfObject', 'PdfReadError', 'PdfWriter', 'Sequence', 'StreamObject', 'TTFont', 'TYPE_CHECKING', 'TextStringObject', 'adobe_glyphs', 'cast', 'dataclass', 'encoding_dict_from_named_encoding', 'field', 'get_encoding', 'logger_warning', 'table_O_S_2f_2', 'table__h_e_a_d', 'table__p_o_s_t', 'unicodedata'),
}


def _prelude(module) -> str:
    """One line, never run, binding by import every name the module binds by import, so that the compiler knows
    the same imported names as when it compiled the module."""
    return f'if __name__ is None: import {", ".join(_IMPORTED[module.__name__])}\n'


def _define(module, owner, name: str, source: str, first: int, original, filename: str) -> types.FunctionType:
    """The function ``source`` defines, executed where it stands (the module's globals; inside its class for name
    mangling), at line ``first``, with the module's own future flags."""
    namespace: dict = {}
    exec(compile(_placed(module, owner, source, first), filename, 'exec',  # noqa: S102
                 flags=original.__code__.co_flags & _FUTURE_ANNOTATIONS, dont_inherit=True), module.__dict__, namespace)
    value = namespace[name] if owner is module else vars(namespace[owner.__name__])[name]
    if type(value) is not type(vars(owner)[name]):
        raise PypdfCompatError(f'{module.__name__}:{name}: the replacement is not bound as the original is.')
    value = value.__func__ if isinstance(value, (staticmethod, classmethod)) else value
    if not isinstance(value, types.FunctionType) or value.__qualname__ != original.__qualname__:
        raise PypdfCompatError(f'{module.__name__}:{name}: the replacement does not define the same function.')
    return value


def _class_body(code: types.CodeType, cls: str) -> types.CodeType:
    bodies = [const for const in code.co_consts if isinstance(const, types.CodeType) and const.co_name == cls]
    if len(bodies) != 1:
        raise PypdfCompatError(f'class {cls}: no single class body.')
    return bodies[0]


_CODE_FIELDS = ('co_code', 'co_names', 'co_varnames', 'co_freevars', 'co_cellvars', 'co_flags', 'co_argcount',
                'co_posonlyargcount', 'co_kwonlyargcount', 'co_nlocals', 'co_stacksize', 'co_exceptiontable',
                'co_linetable', 'co_firstlineno', 'co_name', 'co_qualname')


def _same_code(a: types.CodeType, b: types.CodeType) -> bool:
    if any(getattr(a, name) != getattr(b, name) for name in _CODE_FIELDS) or len(a.co_consts) != len(b.co_consts):
        return False
    for x, y in zip(a.co_consts, b.co_consts):
        if isinstance(x, types.CodeType) or isinstance(y, types.CodeType):
            if not (isinstance(x, types.CodeType) and isinstance(y, types.CodeType) and _same_code(x, y)):
                return False
        elif type(x) is not type(y) or x != y:
            return False
    return True


def _bindings(plans: list) -> None:
    """Every (module, attribute) other than its definition that holds a replaced function: each must be listed."""
    held = {}
    for plan in plans:
        held[id(plan.func)] = held[id(plan.raw)] = plan
    for module_name, module in list(sys.modules.items()):
        if not isinstance(module, types.ModuleType):
            continue
        for attribute, value in list(vars(module).items()):
            plan = held.get(id(value))
            if plan is None or (value is not plan.func and value is not plan.raw):
                continue
            if module is plan.owner and attribute == plan.name:
                continue
            if f'{module_name}.{attribute}' not in _BINDINGS:
                raise PypdfCompatError(f'{plan.patch.target} is also bound as {module_name}.{attribute}.')
            plan.bindings.append((module, attribute))
