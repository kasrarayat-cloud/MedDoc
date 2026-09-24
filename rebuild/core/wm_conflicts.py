"""The qualified Word form's statement/answer conflicts, named for the clinician.

The Word adapter already reports every wording/answer conflict as a fixed string carrying a claim key
(`documents/sdk_word/Adapter/WmVariants.cs` `ApplyVariants`, `WmAdapter.cs` `TemplateConflicts`), and the
page used to discard them for one general sentence that named no statement. This module NAMES what the
adapter found; it never decides a conflict, and a string it does not know keeps the general sentence.

⚠️ A TRANSCRIPTION, PINNED. Which answers each rule compares is copied from the adapter, and
`ADAPTER_SOURCES` pins both C# files by sha256 (a test fails the moment either changes), so a changed rule
cannot leave this naming the wrong answers. Involved answers are taken from the answers the adapter was
actually SENT (`wm_review.sdk_answers`: missing means empty text) and the wordings from the variants sent,
never recomputed from defaults.

⚠️ PAGE ONLY. These rows name findings (fixed option texts). They are rendered server-side on the document
page and never put in a flash message, which Django stores in a signed but readable cookie.
"""
from decimal import Decimal, InvalidOperation
import re

from django.core.exceptions import ValidationError

ADAPTER_SOURCES = {
    'documents/sdk_word/Adapter/WmVariants.cs': '75dbfbfd7bb27919eab99aa28743b1abc3626723f35b4a761081233989456f11',
    'documents/sdk_word/Adapter/WmAdapter.cs': 'd78942a652fbc522499c71e693888250d2e1bd4cdf9c93f05c1d85046c086f20',
}
GENERAL = ('The chosen prewritten statement wordings conflict with the answers. Each conflict is listed on the '
           'document page; correct the answers or the wordings before review and export.')

ASYMPTOMATIC = 'sdt_2005853103'
SYMPTOMS = ('sdt_-1124008635', 'sdt_269290727', 'sdt_722175654', 'sdt_-49312682')
PREVIOUS_TREATMENT = 'sdt_-770853925'
REFLUX_FINDING = {'claim_32': 'sdt_-213273323', 'claim_36': 'sdt_605543147'}
SAME_VEIN = {'claim_23': ('claim_30', ('sdt_-1287346867', 'sdt_1706206184', 'sdt_-892962961', 'sdt_-213273323')),
             'claim_27': ('claim_34', ('sdt_1093284141', 'sdt_-1268837810', 'sdt_2001841928', 'sdt_605543147'))}
SIDE_ROWS = {'claim_30': (1, 13), 'claim_32': (1, 13), 'claim_34': (15, 27), 'claim_36': (15, 27)}

#: The adapter's exact strings. Prefixed ones follow `claim_<n>: `.
PREFIXED = {
    'selected statement needs a documented answer for every required control.': 'required',
    'selected statement cannot omit an answered control.': 'omitted',
    'positive selected reflux requires the reviewed positive statement.': 'reflux_positive',
    'the same documented vein cannot be absent and reflux-positive.': 'same_vein',
    'a non-assessed side cannot contain documented measurements or locations.': 'side_not_assessed',
    'reflux measurements contradict a non-assessed reflux statement.': 'reflux_not_assessed',
    "a recorded reflux duration exceeds this template's explicit 500 ms positive criterion.": 'reflux_over_500',
}
WHOLE = {
    'Asymptomatic selection conflicts with required symptom selections in other unchanged slots.': 'asymptomatic',
    'Clinical indication reports previous treatment while both reviewed leg statements deny it.': 'previous_treatment',
}
EXPLAIN = {
    'required': 'The chosen wording needs an answer that is not given.',
    'omitted': 'The chosen wording leaves out answers that are given.',
    'reflux_positive': 'The answer records positive reflux, so this statement needs its positive-reflux wording.',
    'same_vein': 'The same vein is recorded as absent after treatment and as reflux positive.',
    'side_not_assessed': 'This side is worded as not assessed, but it has measurements or locations.',
    'reflux_not_assessed': 'Reflux is worded as not assessed, but this side has reflux times.',
    'reflux_over_500': 'A reflux time on this side is over 500 ms, above the form’s own positive criterion, so the '
                       'no-reflux wording cannot be used.',
    'asymptomatic': '“Asymptomatic” is chosen while a symptom is also chosen.',
    'previous_treatment': 'The clinical indication records previous vein treatment, but both leg statements say '
                          'there was none.',
}
CLAIM = re.compile(r'(claim_\d+): (.+)\Z', re.S)


class WmConflicts(ValidationError):
    """The adapter's conflicts, named. Its message stays GENERAL: it may reach a flash message."""

    def __init__(self, rows):
        super().__init__(GENERAL)
        self.rows = rows


def _side(fields, claim, unit=None):
    first, last = SIDE_ROWS[claim]
    return [field['key'] for field in fields
            if isinstance((field.get('locator') or {}).get('row'), int) and first <= field['locator']['row'] <= last
            and (unit is None or (field.get('kind') == 'measurement' and field['locator'].get('unit') == unit))]


def over_500(text):
    if not text.endswith(' ms'):
        return False
    try:
        return Decimal(text[:-len(' ms')]) > 500
    except InvalidOperation:
        return False


def describe(conflicts, version, sent, variants):
    """Rows of {statements: [(label, wording)], answers: [(label, shown value or '')], explanation} or a
    general row for any string this does not know."""
    fields = version.fields
    labels = {field['key']: field['label'] for field in fields}
    kinds = {field['key']: field.get('kind') for field in fields}
    requirements = {row['key']: row for row in version.review_requirements}

    def given(key):
        return bool((sent.get(key) or {}).get('text'))

    def statement(claim):
        row = requirements.get(claim)
        if not row:
            return None
        chosen = variants.get(claim)
        wording = next((variant['label'] for variant in row.get('variants', []) if variant['id'] == chosen), chosen or '')
        return row['label'], wording

    def answer(key):
        # Only a fixed choice is shown as text; a measurement or free text is named, not quoted.
        shown = (sent.get(key) or {}).get('text', '') if kinds.get(key) == 'choice' else ''
        return labels.get(key, key), shown

    rows = []
    for text in conflicts:
        matched = CLAIM.match(text)
        rule = WHOLE.get(text) or (PREFIXED.get(matched.group(2)) if matched else None)
        claim = matched.group(1) if matched else None
        statements, keys = [], []
        if rule in ('required', 'omitted') and claim in requirements:
            variant = next((v for v in requirements[claim].get('variants', []) if v['id'] == variants.get(claim)), {})
            wanted = variant.get('required_control_keys' if rule == 'required' else 'empty_control_keys') or []
            keys = [key for key in wanted if given(key) == (rule == 'omitted')]
            statements = [claim]
        elif rule == 'reflux_positive' and claim in REFLUX_FINDING:
            statements, keys = [claim], [REFLUX_FINDING[claim]]
        elif rule == 'same_vein' and claim in SAME_VEIN:
            impression, involved = SAME_VEIN[claim]
            # Two empty vein answers compare equal in the adapter; that is not "the same documented vein".
            if given(involved[0]) or given(involved[2]):
                statements, keys = [claim, impression], list(involved)
        elif rule == 'side_not_assessed' and claim in SIDE_ROWS:
            statements, keys = [claim], [key for key in _side(fields, claim) if given(key)]
        elif rule == 'reflux_not_assessed' and claim in SIDE_ROWS:
            statements, keys = [claim], [key for key in _side(fields, claim, 'ms') if given(key)]
        elif rule == 'reflux_over_500' and claim in SIDE_ROWS:
            # Only the times the adapter found over 500 ms (its MeasurementValue: the value before " ms").
            # The number chooses which answer to NAME; it is never quoted.
            statements, keys = [claim], [key for key in _side(fields, claim, 'ms') if over_500((sent.get(key) or {}).get('text', ''))]
        elif rule == 'asymptomatic':
            keys = [ASYMPTOMATIC] + [key for key in SYMPTOMS if given(key)]
        elif rule == 'previous_treatment':
            statements, keys = ['claim_23', 'claim_27'], [PREVIOUS_TREATMENT]
        named = [row for row in (statement(key) for key in statements) if row]
        if not rule or (not keys and rule not in ('previous_treatment',)) or len(named) != len(statements):
            rows.append({'statements': [], 'answers': [], 'explanation': GENERAL, 'statement_keys': [], 'answer_keys': []})
            continue
        rows.append({'statements': named, 'answers': [answer(key) for key in keys], 'explanation': EXPLAIN[rule],
                     'statement_keys': statements, 'answer_keys': keys})
    return rows
