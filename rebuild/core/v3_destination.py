"""Literal source/destination scope guards; these never establish clinical meaning."""
import re
import unicodedata


_SIDE = re.compile(r'\b(?:left(?!\s+(?:blank|empty|unchanged)\b)|right(?!\s+for\b)|lt|rt|bilateral|bil)\b'
                   r'|\(([LR])\)', re.I)


def sides(text):
    """Only the explicit side vocabulary already recognized on printed forms.

    The same compatibility-normalized reading is used for source and destination.
    A recognized token can withhold an answer; it never grants anatomical identity.
    """
    found = set()
    for match in _SIDE.finditer(unicodedata.normalize('NFKC', str(text or ''))):
        token = (match[1] or match[0]).casefold()
        found.update({'left', 'right'} if token in ('bilateral', 'bil') else
                     {'left' if token in ('left', 'lt', 'l') else 'right'})
    return found


def side_warnings(field, selected):
    """Keep unknown/mixed/opposite source scope held for a side-specific field.

    Full original context matters even when the short label is only 'Findings'.
    No source sentence is shortened to rescue an answer containing another side.
    """
    required = sides(str(field.get('context') or '') + ' ' + str(field.get('label') or ''))
    if not required:
        return []
    return [unit for unit in selected if len(required) != 1 or sides(unit['quote']) != required]
