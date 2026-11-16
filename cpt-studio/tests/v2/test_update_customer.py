"""Step 3c of design v2 (FINAL-V2 4.8, 4.12; amendment 1, DECISIONS D208): studio/customer_api.py's customer texts -
amendment 1's texts of the automatic update as constants (sections 1.4, 2.5, 3.9, 5.1-5.4, 6.2, 7.1-7.2), with 7.1's
case-C, no-restore and check forms; the refusal, template and blocker tables; the appraise step's words; the held facts'
fixed sentences; FINAL-V2 4.12's confidentiality net (FORBIDDEN); and the customer scan over all of them. Text-only and
synthetic: no database, no network. The functions that read an update's state for the page are step 5d's.

What is proved here:
- every amendment text is present verbatim where the amendment gives it (each found in AMENDMENT-1.md);
- each derived form equals 7.1's rule applied to its base text, computed here independently, and update_text chooses
  the form by update.kind and update.restorable (only True offers a restore);
- no case-C, no-restore or check text offers a restore; no check text names a change of the member's;
- every refusal is a customer sentence (KNOWN_ERRORS, KNOWN_TEMPLATES) and UPDATE_BLOCKER reads its customer words;
- FORBIDDEN matches the joined and underscored forms (gemini_unknown) and not clinical words that begin with a name
  (corticosteroid), and plain() refuses and passes them accordingly;
- no customer string here names a provider or model or carries a held fact's cause, and a v2 proposal whose support
  carries held facts and their causes shows none of them;
- D225 (repair r3c; 3c P2, P3, P10): each fixed saved-changes line has its updating form and its form for every state
  in which nothing runs, chosen by state; BLOCKER_EXACT holds 5.3's two customer texts and their check forms under an
  internal blocker per update state and kind; an A21 clearing says the document was read again (D225Texts); and
  (refute-r3c-r1 P5) the check line's form for when nothing runs is true after the update's reading has run;
- D246 (repair r3c; customer_api.py needs no change): the new id SYNTHETIC_ACT's fact key reads its own fixed customer
  sentence, as every D246 form's does, never a cause; and every sentence a D246 form or id makes passes the customer
  guard unchanged (plain, FORBIDDEN, the denylist's hard patterns, the held-fact causes) - D246CustomerTexts;
- D254, D257, D258, D253 QX (ii) (repair r3c of round w8r; customer_api.py needs no change): every sentence the totalized
  builders make over every combination of present and absent slots passes the customer guard as written, and the two
  new ids' fact keys read their own fixed sentences - D254CustomerTexts;
- D267 (repair r3c of round w9r; refute-r3c-r1 F4, F7): held_fact_words words 'conflict:other' (and any kind no kind
  names) as 'another act', every named kind by the item's own label; a procedure-keyed held fact by the item's message
  (each procedure-keyed message id's sentence, by the message and by its value) and, with no message - or a message of
  another key - v1's pinned sentence; every held fact with every message passes the customer guard - D267HeldFactWords.
"""
from pathlib import Path
from types import SimpleNamespace

from django.test import SimpleTestCase

from studio import answers, customer_api as c, jobs, progress
from studio.interpretation import wording
from studio.interpretation.contract.types import Kind
from studio.interpretation.engine import requirements
from studio.interpretation.engine.types import ItemKind
from studio.models import Decision, Proposal
from studio.validation import questions
from tests.v2.test_wording import HARD

ROOT = Path(__file__).resolve().parents[2]


def flat(path):
    return ' '.join((ROOT / 'docs' / 'gemini-migration' / path).read_text(encoding='utf-8').split())


AMENDMENT = flat('AMENDMENT-1.md')
FINAL = flat('FINAL-V2.md')

# Every text amendment 1 gives verbatim, as the constant states it (a template filled the way the amendment shows it)
VERBATIM = {
    'UPDATE_TITLE': c.UPDATE_TITLE,
    'UPDATE_TITLE_CHECK': c.UPDATE_TITLE_CHECK,
    'STATE_LABELS[updating]': c.STATE_LABELS['updating'],
    'CHANGE_SERVICE_DATE': c.CHANGE_SERVICE_DATE.format(date='10 November 2026'),
    'CHANGE_SERVICE_DATE_REMOVED': c.CHANGE_SERVICE_DATE_REMOVED,
    'CHANGE_SETTING': c.CHANGE_SETTING.format(value=answers.CHOICE_LABELS['setting']['hospital_outpatient']),
    'CHANGE_PATIENT_STATUS': c.CHANGE_PATIENT_STATUS.format(value=answers.CHOICE_LABELS['patient_status']['new']),
    'CHANGE_BILLING_CONTEXT': c.CHANGE_BILLING_CONTEXT.format(value=answers.CHOICE_LABELS['billing_context']['facility']),
    'CHANGE_DOCUMENTATION': c.CHANGE_DOCUMENTATION.format(n=2),
    'CHANGE_SAVED_BY': c.CHANGE_SAVED_BY.format(member='<member>', time='<time>'),
    'SAVED_CHANGES_UNFINISHED': c.SAVED_CHANGES_UNFINISHED,
    'SAVED_CHANGES_SAME_DETAILS': c.SAVED_CHANGES_SAME_DETAILS,
    'SAVED_CHANGES_CHECK': c.SAVED_CHANGES_CHECK,
    'EARLIER_CODES_HEADING': c.EARLIER_CODES_HEADING,
    'EARLIER_CODES_MADE': c.EARLIER_CODES_MADE.format(time='<time>', date='<date>'),
    'ANSWER_AFTER_UPDATE': c.ANSWER_AFTER_UPDATE,
    'UPDATE_EXPORT_NOTE[updating]': c.UPDATE_EXPORT_NOTE['updating'],
    'UPDATE_EXPORT_NOTE[other]': c.UPDATE_EXPORT_NOTE['other'],
    'RESULTS_UPDATING': c.RESULTS_UPDATING,
    'RESULTS_NOT_UPDATED': c.RESULTS_NOT_UPDATED,
    'RESULTS_EARLIER_SHOWN': c.RESULTS_EARLIER_SHOWN,
    'RESULTS_NO_EARLIER_CODE': c.RESULTS_NO_EARLIER_CODE,
    'TALLY_BEFORE': f'"{c.TALLY_BEFORE}"',
    'TALLY_NO_EARLIER_CODE': c.TALLY_NO_EARLIER_CODE,
    'RESTORED_TOAST': c.RESTORED_TOAST,
    'UPDATE_DECISION': c.UPDATE_DECISION,
    'UPDATE_EXPORT': c.UPDATE_EXPORT,
    'UPDATE_ANSWER_WITHDRAW': c.UPDATE_ANSWER_WITHDRAW,
    'UPDATE_BLOCKER': c.UPDATE_BLOCKER,
    'UPDATE_BLOCKER_WORDS[updating]': c.UPDATE_BLOCKER_WORDS[('updating', 'details')],
    'UPDATE_BLOCKER_WORDS[other]': c.UPDATE_BLOCKER_WORDS[('other', 'details')],
    'UPDATE_BLOCKER_WORDS[updating, check]': c.UPDATE_BLOCKER_WORDS[('updating', 'check')],
    'SAVE_TOO_LONG': c.SAVE_TOO_LONG,
    'SAVE_UNPREPARED': c.SAVE_UNPREPARED,
    'ADDENDUM_TOO_LONG': c.ADDENDUM_TOO_LONG,
    'ADDENDUM_UNPREPARED': c.ADDENDUM_UNPREPARED,
    'ADDENDUM_DOCUMENT_TOO_LONG': c.ADDENDUM_DOCUMENT_TOO_LONG,
    'ADDENDUM_DOCUMENT_UNPREPARED': c.ADDENDUM_DOCUMENT_UNPREPARED,
    'ADDENDUM_DUPLICATE': c.ADDENDUM_DUPLICATE,
    'RESTORE_REFUSED': c.RESTORE_REFUSED,
    'RETRY_UPDATE_NOTHING': c.RETRY_UPDATE_NOTHING,
    'RETRY_UPDATE_HELD': c.RETRY_UPDATE_HELD,
    'RETRY_UPDATE_READING': c.RETRY_UPDATE_READING,
    'RETRY_UPDATE_REFUSED_BEFORE': c.RETRY_UPDATE_REFUSED_BEFORE,
    'UPDATE_ACTION_LABELS[retry_reading]': f'"{c.UPDATE_ACTION_LABELS["retry_reading"]}"',
    'UPDATE_ACTION_LABELS[retry_update]': f'"{c.UPDATE_ACTION_LABELS["retry_update"]}"',
    'PROVIDER_PAUSED': c.PROVIDER_PAUSED,
    'WHAT_CHANGED_COMPARED': c.WHAT_CHANGED_COMPARED,
    'WHAT_CHANGED_SINCE': c.WHAT_CHANGED_SINCE,
    'WHAT_CHANGED_NOT_DOCUMENTED': f'"{c.WHAT_CHANGED_NOT_DOCUMENTED}" for none',
    'WHAT_CHANGED_TWO_DATES': f'"{c.WHAT_CHANGED_TWO_DATES}" for a conflict',
    'WHAT_CHANGED_DOCUMENTATION': c.WHAT_CHANGED_DOCUMENTATION,
    'WHAT_CHANGED_READ_AGAIN': c.WHAT_CHANGED_READ_AGAIN,
    'WHAT_CHANGED_ADDED': c.WHAT_CHANGED_ADDED,
    'WHAT_CHANGED_REMOVED': c.WHAT_CHANGED_REMOVED,
    'WHAT_CHANGED_ALTERNATIVE': c.WHAT_CHANGED_ALTERNATIVE,
    'WHAT_CHANGED_NOT_SUGGESTED': c.WHAT_CHANGED_NOT_SUGGESTED.format(reason='…'),
    'WHAT_CHANGED_STATUS_CHANGED': c.WHAT_CHANGED_STATUS_CHANGED,
    'WHAT_CHANGED_UNITS': c.WHAT_CHANGED_UNITS,
    'WHAT_CHANGED_ITEM': c.WHAT_CHANGED_ITEM,
    'WHAT_CHANGED_UNCHANGED': c.WHAT_CHANGED_UNCHANGED,
    'WHAT_CHANGED_KEPT': c.WHAT_CHANGED_KEPT,
    'WHAT_CHANGED_KEPT_THEN_CLEARED': c.WHAT_CHANGED_KEPT_THEN_CLEARED,
    'WHAT_CHANGED_KEPT_THEN_CHANGED': c.WHAT_CHANGED_KEPT_THEN_CHANGED,
    'WHAT_CHANGED_ANSWERS': c.WHAT_CHANGED_ANSWERS,
    'CLEARED_BY_REVISION': c.CLEARED_BY_REVISION,
    'CLEARED_NEW_READING': c.CLEARED_NEW_READING,
    'CLEARED_SAME_DETAILS': c.CLEARED_SAME_DETAILS,
    'CLEARED_DETAILS_CHANGED': c.CLEARED_DETAILS_CHANGED,
    'EARLIER_DOWNLOAD': c.EARLIER_DOWNLOAD,
    **{f'WHAT_CHANGED_STATUS[{key}]': f'"{value}"' for key, value in c.WHAT_CHANGED_STATUS.items()},
    **{f'WHAT_CHANGED_DECISION_NOUNS[{key}]': value for key, value in c.WHAT_CHANGED_DECISION_NOUNS.items()},
    **{f'WHAT_CHANGED_DETAIL_LABELS[{key}]': f'`{value}: ' for key, value in c.WHAT_CHANGED_DETAIL_LABELS.items()},
    **{f'UPDATE_TEXTS[{situation}].details': row.details for situation, row in c.UPDATE_TEXTS.items()
       if situation not in ('appraisal_failed', 'worker_paused')},
}
# 7.1's row of each situation: (phase, action)
ROWS = {
    'reading_failed': ('failed', 'retry_reading'), 'appraisal_failed': ('failed', 'retry_reading'),
    'too_long': ('failed', 'none'), 'review_failed': ('failed', 'retry_update'),
    'review_not_sent': ('failed', 'retry_update'), 'review_held': ('paused', 'resume'),
    'review_refused_before': ('failed', 'none'), 'review_unbuilt': ('failed', 'none'),
    'processing_failed': ('failed', 'retry_update'), 'interpreter_paused': ('paused', 'resume'),
    'review_disabled': ('paused', 'resume'), 'being_confirmed': ('being_confirmed', 'none'),
    'stopped_by_member': ('stopped', 'resume'), 'stopped_by_system': ('stopped', 'resume'),
    'worker_paused': ('paused', 'none'),
}
UPLOAD_AGAIN = ' Upload the document again, shorter or split, to have it read.'
SHORTEN = ' Shorten the document and upload it again.'
TOO_LONG_RESTORE = ' Restore the earlier details to use them again, or shorten the document and upload it again.'


def swap(text, old, new):
    """``text`` with ``old`` replaced by ``new`` where it occurs (counted by the caller's own asserts on the result)."""
    return text.replace(old, new)


def no_restore(situation, text):
    """7.1, no restore where A19 refuses one: every restore clause dropped; the too-long text ends SHORTEN."""
    if situation == 'too_long':
        assert text.count(TOO_LONG_RESTORE) == 1, text
        return swap(text, TOO_LONG_RESTORE, SHORTEN)
    text = swap(swap(text, 'Resume to finish it, or restore the earlier details.', 'Resume to finish it.'),
                'Resume once it is available, or restore the earlier details.', 'Resume once it is available.')
    return swap(swap(text, ' You can restore the earlier details to use them again.', ''),
                ' Restore the earlier details to use them again.', '')


def case_c(situation, text):
    """7.1, case C: no restore clause; "from before the documentation was added"; the too-long and the could-not-be-
    prepared texts end UPLOAD_AGAIN."""
    if situation == 'too_long':
        text = swap(text, TOO_LONG_RESTORE, UPLOAD_AGAIN)
    elif situation == 'review_unbuilt':
        assert text.count(' Restore the earlier details to use them again.') == 1, text
        text = swap(text, ' Restore the earlier details to use them again.', UPLOAD_AGAIN)
    else:
        text = no_restore(situation, text)
    return swap(text, 'from before your change', 'from before the documentation was added')


def check(situation, text):
    """7.1, check texts (A21): no "Your change is saved"; "from before this update"; no restore clause."""
    text = no_restore(situation, text)
    text = swap(swap(text, 'Your change is saved, but the codes', 'The codes'), 'Your change is saved. ', '')
    text = swap(swap(text, 'Your change is saved and the codes', 'The codes'), ' after your change', '')
    return swap(swap(text, 'from before your latest change', 'from before this update'), 'from before your change',
                'from before this update')


def customer_strings():
    """Every customer string step 3c adds to customer_api (and the update texts' progress twin the amendment words),
    each with its name."""
    names = [name for name in vars(c) if name.isupper() and (
        name.startswith(('UPDATE', 'CHANGE', 'SAVED_CHANGES', 'EARLIER', 'ANSWER_AFTER', 'RESULTS', 'TALLY', 'RESTORE',
                         'SAVE_', 'ADDENDUM', 'RETRY_UPDATE', 'PROVIDER_PAUSED', 'WHAT_CHANGED', 'CLEARED', 'APPRAISE')))]
    out = []

    def walk(name, value):
        if isinstance(value, str):
            out.append((name, value))
        elif isinstance(value, dict):
            for key, item in value.items():
                walk(f'{name}[{key}]', item)
        elif isinstance(value, (tuple, list)):
            for index, item in enumerate(value):
                walk(f'{name}[{index}]', item)
        elif isinstance(value, c.UpdateText):
            for field in ('details', 'no_restore', 'documentation', 'check'):
                walk(f'{name}.{field}', getattr(value, field))
    for name in names:
        walk(name, getattr(c, name))
    out.append(('STATE_LABELS[updating]', c.STATE_LABELS['updating']))
    out += [(f'held_fact_words({fact})', c.held_fact_words(fact)) for fact in held_fact_keys()]
    # D267 (repair r3c of round w9r): each held fact worded by every item message too (a procedure-keyed one names what
    # its item asks; any other message leaves the key's sentence)
    out += [(f'held_fact_words({fact}, {message.value})', c.held_fact_words(fact, message)) for fact in held_fact_keys()
            for message in wording.Message]
    out.append(('WAITING_FOR_EARLIER (5.2, step 5b)', 'Your change is saved. A step started before it is finishing '
                'first; its result is used only where it still applies.'))
    return out


def held_fact_keys():
    keys = [fact.value for fact in requirements.FactKey if fact is not requirements.FactKey.CONFLICT]
    return keys + [f'conflict:{kind.value}' for kind in Kind]


class AmendmentTexts(SimpleTestCase):
    """Done when: every amendment text is present verbatim where the amendment gives it."""

    def test_every_verbatim_text_is_in_the_amendment(self):
        missing = [name for name, text in VERBATIM.items() if ' '.join(text.split()) not in AMENDMENT]
        self.assertEqual(missing, [])
        self.assertEqual(c.STATE_LABELS['updating'], 'Updating codes')
        self.assertIn('\u2014', c.UPDATE_TITLE)  # the em dash of "Changes saved—updating codes"

    def test_the_appraise_step_and_the_derived_row_take_the_designs_words(self):
        self.assertIn(f'pass 2 "{c.APPRAISE_DETAIL}"', FINAL)
        self.assertIn(f'"{c.APPRAISE_DETAIL}"', AMENDMENT)
        self.assertIn('"checking the reading against the document could not be completed"', AMENDMENT)
        self.assertEqual(c.UPDATE_TEXTS['appraisal_failed'].details, c.UPDATE_TEXTS['reading_failed'].details.replace(
            'reading the documented procedures could not be completed',
            'checking the reading against the document could not be completed'))
        self.assertEqual(c.UPDATE_TEXTS['worker_paused'].details, progress.MESSAGES['paused'])
        self.assertTrue(c.APPRAISE_SLOW.startswith(c.APPRAISE_DETAIL))

    def test_the_v1_state_labels_are_unchanged(self):
        self.assertEqual({key: value for key, value in c.STATE_LABELS.items() if key != 'updating'}, {
            'processing': 'Processing', 'action_needed': 'Action needed', 'awaiting_detail': 'A few details needed',
            'ready': 'Ready for review', 'reviewed': 'Reviewed', 'no_codes': 'No codes suggested', 'stopped': 'Stopped',
            'failed': 'Could not finish', 'being_confirmed': 'Being confirmed'})


class UpdateForms(SimpleTestCase):
    """7.1's forms: case C, no restore and check, each 7.1's rule applied to the base text."""

    def test_each_rows_forms_follow_the_rules(self):
        self.assertEqual(set(c.UPDATE_TEXTS), set(ROWS))
        for situation, row in c.UPDATE_TEXTS.items():
            with self.subTest(situation=situation):
                self.assertEqual(row.no_restore, no_restore(situation, row.details))
                self.assertEqual(row.documentation, case_c(situation, row.details))
                self.assertEqual(row.check, check(situation, row.details))
                self.assertEqual((row.phase, row.action), ROWS[situation])

    def test_no_case_c_no_restore_or_check_text_offers_a_restore_and_no_check_text_names_the_members_change(self):
        for situation, row in c.UPDATE_TEXTS.items():
            with self.subTest(situation=situation):
                for form in (row.no_restore, row.documentation, row.check):
                    self.assertNotIn('restore', form.lower())
                self.assertNotIn('your change', row.check.lower())
                self.assertNotIn('your latest change', row.check.lower())
                self.assertNotIn('from before your change', row.documentation)
        restoring = {situation for situation, row in c.UPDATE_TEXTS.items() if 'restore' in row.details.lower()}
        self.assertEqual(restoring, {'too_long', 'review_held', 'review_refused_before', 'review_unbuilt',
                                     'interpreter_paused', 'review_disabled', 'stopped_by_member'})

    def test_update_text_chooses_by_kind_and_restorable(self):
        for situation, row in c.UPDATE_TEXTS.items():
            self.assertEqual(c.update_text(situation, 'details', True), row.details)
            for restorable in (False, None, 1, 'yes'):
                self.assertEqual(c.update_text(situation, 'details', restorable), row.no_restore)
            for restorable in (True, False):
                self.assertEqual(c.update_text(situation, 'documentation', restorable), row.documentation)
                self.assertEqual(c.update_text(situation, 'check', restorable), row.check)
        with self.assertRaises(KeyError):
            c.update_text('reading_failed', 'save', True)
        with self.assertRaises(KeyError):
            c.update_text('unknown_situation', 'details', True)

    def test_the_51_and_53_texts_check_forms_follow_the_rule(self):
        pairs = ((c.UPDATE_DECISION, c.UPDATE_DECISION_CHECK), (c.UPDATE_EXPORT, c.UPDATE_EXPORT_CHECK),
                 (c.EARLIER_CODES_HEADING, c.EARLIER_CODES_HEADING_CHECK), (c.EARLIER_CODES_MADE, c.EARLIER_CODES_MADE_CHECK),
                 (c.UPDATE_EXPORT_NOTE['updating'], c.UPDATE_EXPORT_NOTE_CHECK['updating']),
                 (c.UPDATE_EXPORT_NOTE['other'], c.UPDATE_EXPORT_NOTE_CHECK['other']),
                 (c.RESULTS_UPDATING, c.RESULTS_UPDATING_CHECK), (c.RESULTS_NOT_UPDATED, c.RESULTS_NOT_UPDATED_CHECK),
                 (c.RESULTS_EARLIER_SHOWN, c.RESULTS_EARLIER_SHOWN_CHECK),
                 (c.UPDATE_BLOCKER_WORDS[('updating', 'details')], c.UPDATE_BLOCKER_WORDS[('updating', 'check')]),
                 (c.UPDATE_BLOCKER_WORDS[('other', 'details')], c.UPDATE_BLOCKER_WORDS[('other', 'check')]))
        for base, form in pairs:
            with self.subTest(base=base):
                self.assertEqual(form, check('', base))
                self.assertNotIn('your', form.lower().replace('your answers', ''))
        # the three 7.1's literal rules do not reach (recorded as a question): "before your change" reads "before this
        # update", by the rule that no check text names a change of the member's
        for base, form in ((c.RESULTS_NO_EARLIER_CODE, c.RESULTS_NO_EARLIER_CODE_CHECK), (c.TALLY_BEFORE, c.TALLY_BEFORE_CHECK),
                           (c.TALLY_NO_EARLIER_CODE, c.TALLY_NO_EARLIER_CODE_CHECK)):
            self.assertEqual(form, base.replace('before your change', 'before this update').replace(
                'Before your change', 'Before this update'))
        self.assertEqual(c.UPDATE_TITLE_CHECK, c.STATE_LABELS['updating'])


class Tables(SimpleTestCase):
    """Every refusal reaches the member as written (KNOWN_ERRORS, KNOWN_TEMPLATES); UPDATE_BLOCKER reads its words."""

    REFUSALS = ('UPDATE_DECISION', 'UPDATE_DECISION_CHECK', 'UPDATE_EXPORT', 'UPDATE_EXPORT_CHECK', 'UPDATE_ANSWER_WITHDRAW',
                'SAVE_TOO_LONG', 'SAVE_UNPREPARED', 'ADDENDUM_TOO_LONG', 'ADDENDUM_UNPREPARED', 'ADDENDUM_DOCUMENT_TOO_LONG',
                'ADDENDUM_DOCUMENT_UNPREPARED', 'RESTORE_REFUSED', 'RETRY_UPDATE_NOTHING', 'RETRY_UPDATE_HELD',
                'RETRY_UPDATE_READING', 'RETRY_UPDATE_REFUSED_BEFORE')

    def test_every_refusal_is_a_known_customer_sentence(self):
        for name in self.REFUSALS:
            text = getattr(c, name)
            with self.subTest(name=name):
                self.assertIn(text, c.KNOWN_ERRORS)
                self.assertIsNone(c.KNOWN_ERRORS[text])
                self.assertEqual(c.customer_error(text), text)
                self.assertEqual(c.customer_error(text + ' '), c.GENERIC_ERROR)
        # retry_update's unchanged refusals are already known (7.2)
        for text in (jobs.RETRY_BUSY, jobs.RETRY_UNKNOWN):
            self.assertEqual(c.customer_error(text), text)

    def test_the_duplicate_addendum_template_takes_a_revision_number_only(self):
        for number in (1, 2, 17, 100000):
            self.assertEqual(c.customer_error(c.ADDENDUM_DUPLICATE.format(n=number)), c.ADDENDUM_DUPLICATE.format(n=number))
        for text in ('This documentation was already added as revision 0.',
                     'This documentation was already added as revision two.',
                     'This documentation was already added as revision 2',
                     'This documentation was already added as revision 2. ',
                     'This documentation was already added as revision 1234567.'):
            self.assertEqual(c.customer_error(text), c.GENERIC_ERROR, text)

    def test_the_update_blocker_reads_its_true_in_every_state_and_kind_form(self):
        self.assertEqual(c.customer_blocker(c.UPDATE_BLOCKER), 'The codes have not been updated yet.')
        self.assertNotIn('being updated', c.BLOCKER_EXACT[c.UPDATE_BLOCKER])
        self.assertNotIn('your change', c.BLOCKER_EXACT[c.UPDATE_BLOCKER])
        self.assertEqual(set(c.UPDATE_BLOCKER_WORDS), {(state, kind) for state in ('updating', 'other')
                                                       for kind in ('details', 'check')})

    def test_the_new_facts_reach_the_open_clarification_blocker(self):
        for fact, words in list(wording.MISSING.items())[7:]:
            self.assertEqual(c.customer_blocker(f'Open clarification: {fact}'), f'A detail is needed: {words}.')

    def test_the_fixed_lines_and_their_keys(self):
        self.assertEqual(set(c.SAVED_CHANGES_EMPTY), {'unfinished', 'same_details', 'check'})
        self.assertEqual(set(c.UPDATE_EXPORT_NOTE), set(c.UPDATE_EXPORT_NOTE_CHECK))
        self.assertEqual(set(c.WHAT_CHANGED_DECISION_NOUNS), {Decision.APPROVE, Decision.REJECT, Decision.REINSTATE,
                                                              Decision.CONFIRM})
        self.assertEqual(c.WHAT_CHANGED_STATUS['ready'], c.STATUS_LABELS['ready'])
        self.assertEqual(c.WHAT_CHANGED_STATUS['excluded'], c.CHECK_EXCLUDED_SUB_LABEL)
        self.assertEqual(c.WHAT_CHANGED_UNCHANGED.format(n=2), '2 codes unchanged')


class Confidentiality(SimpleTestCase):
    """FINAL-V2 4.12 [R:MO-2]: both nets see joined forms; no customer string names a provider or model or a cause."""

    MATCH = ('gemini_unknown', 'reading_gemini_x', 'Gemini', 'GEMINI', 'gemini-4-argon', 'gemini-4-carbon', 'Corti',
             'corti_x', 'x_astra', 'Fable', 'openai', 'Anthropic', 'claude', 'Google', 'held: gemini_unknown.',
             'GeminiTimeout', 'readingGemini', 'OpenAIError')
    PASS = ('corticosteroid', 'cortical', 'Corticosteroid', 'CORTICAL', 'hydrocortisone', 'astral', 'fabled', 'googled',
            'claudette', 'Cortisol', 'A corticosteroid injection was given.', 'No carbon-particle tattoo was placed.',
            'carbon dioxide insufflation')

    def test_forbidden_matches_the_joined_forms_and_not_clinical_words(self):
        for text in self.MATCH:
            with self.subTest(text=text):
                self.assertIsNotNone(c.FORBIDDEN.search(text))
                self.assertEqual(c.plain(text), '')
        for text in self.PASS:
            with self.subTest(text=text):
                self.assertIsNone(c.FORBIDDEN.search(text))
                self.assertEqual(c.plain(text), text)

    def test_the_rest_of_the_net_is_unchanged(self):
        for text in ('gpt-4', 'claude-sonnet', 'gemini-2', '@cptstudio-1', 'cpt-studio:events', 'a' * 32 + '0',
                     'the participants', 'peer review', 'vendor', 'tokens', 'credit', 'trace', 'sha256', 'tool call',
                     'request id', 'replay', 'provider', 'routing', 'reader', 'cue', 'own passages', 'gemini-events@2'):
            self.assertIsNotNone(c.FORBIDDEN.search(text), text)

    def test_no_customer_string_names_a_provider_or_model_or_carries_a_cause(self):
        strings = customer_strings()
        self.assertGreater(len(strings), 150)
        for name, text in strings:
            with self.subTest(name=name):
                self.assertTrue(text.strip(), name)
                self.assertIsNone(c.FORBIDDEN.search(text), text)
                self.assertEqual([pattern.pattern for pattern in HARD if pattern.search(text)], [], text)
                self.assertFalse([cause for cause in c.HELD_FACT_CAUSES if cause in text], text)

    def test_a_held_fact_reads_its_fixed_sentence_never_its_cause(self):
        for fact in held_fact_keys():
            with self.subTest(fact=fact):
                words = c.held_fact_words(fact)
                self.assertNotIn('a detail of the encounter', words)  # every RANK key has its own words
                self.assertNotIn('_', words)
                self.assertTrue(words.startswith('A detail is needed: ') and words.endswith('.'))
        for cause in ('reading_unknown', 'reading_contradicted', 'unestablished:source_too_long', 'appraisal:contradicts',
                      'relation:contradiction', 'unlisted', 'coding_rule:route_b', 'context_missing', 'date_unknown',
                      'gemini_unknown', 'conflict:gemini_unknown', None, 7):
            with self.subTest(cause=cause):
                words = c.held_fact_words(cause)
                self.assertFalse([item for item in c.HELD_FACT_CAUSES if item in words], words)
                self.assertIsNone(c.FORBIDDEN.search(words), words)

    def test_a_v2_proposals_held_facts_and_causes_reach_no_customer_string(self):
        held = [{'fact': 'event_entry', 'cause': 'reading_unknown', 'rank': 5},
                {'fact': 'act_yield', 'cause': 'gemini_unknown', 'rank': 15},
                {'fact': 'conflict:stone_extraction', 'cause': 'appraisal:contradicts', 'rank': 1}]
        proposal = SimpleNamespace(
            support={'held_facts': held, 'family': 'gi.ercp', 'state': 'uncertain', 'reason': 'held',
                     'acts': [{'label': 'stone removal', 'kind': 'stone_extraction'}]},
            family='gi.ercp', bucket=Proposal.SELECTED, checks=[], status=Proposal.NEEDS_CLARIFICATION, code='43264')
        view = SimpleNamespace(questions=[{'fact': 'act_yield'}, {'fact': 'event_entry'}], withheld_by='',
                               same_day_held=False, reason='', blocker='', stale=False, modifier_review=None, checks=[],
                               status=Proposal.NEEDS_CLARIFICATION, summary='', answer='')
        shown = c._qualifications(proposal, 'needs_detail', view, '43264') + [c._summary(proposal),
                                                                             c.code_summary(proposal, view)]
        shown += [c.held_fact_words(item['fact']) for item in held]
        for text in shown:
            with self.subTest(text=text):
                self.assertFalse([cause for cause in c.HELD_FACT_CAUSES + ('gemini',) if cause in text.lower()], text)
                self.assertIsNone(c.FORBIDDEN.search(text), text)


class D225Texts(SimpleTestCase):
    """D225 (repair r3c; 3c P2, P3, P10): every customer sentence is true for its state."""

    OTHER = {
        'unfinished': 'The codes from before your change were not finished, and they have not been finished for these '
                      'details yet.',
        'same_details': 'These are the details of the codes from before your change; the codes need to be made again '
                        'because your answers, or an earlier check, changed since those codes were made, and they have '
                        'not been made again yet.',
        'check': 'An earlier check was settled, so the codes need to be updated with the current reading; they have '
                 'not been updated yet.',
    }
    BLOCKERS = {
        ('updating', 'details'): 'The codes are from before the latest change; the update is running',
        ('other', 'details'): 'The codes are from before the latest change; the update is not running',
        ('updating', 'check'): 'The codes are from before this update; the update is running',
        ('other', 'check'): 'The codes are from before this update; the update is not running',
    }
    NOTHING_RUNS = ('failed', 'stopped', 'paused', 'being_confirmed')

    # 3c P2: the three fixed lines
    def test_each_fixed_line_has_an_updating_form_and_a_form_for_when_nothing_runs(self):
        self.assertEqual((c.SAVED_CHANGES_UNFINISHED_OTHER, c.SAVED_CHANGES_SAME_DETAILS_OTHER,
                          c.SAVED_CHANGES_CHECK_OTHER), (self.OTHER['unfinished'], self.OTHER['same_details'],
                                                         self.OTHER['check']))
        self.assertEqual(set(c.SAVED_CHANGES_LINES), set(c.SAVED_CHANGES_EMPTY))
        for reason, forms in c.SAVED_CHANGES_LINES.items():
            with self.subTest(reason=reason):
                self.assertEqual(set(forms), set(c.UPDATE_EXPORT_NOTE))  # 'updating' and 'other', as the export note
                self.assertEqual(forms['updating'], c.SAVED_CHANGES_EMPTY[reason])  # the amendment's text, unchanged
                self.assertEqual(forms['other'], self.OTHER[reason])

    def test_saved_changes_line_chooses_the_form_by_state(self):
        self.assertEqual(c.UPDATE_STATES, ('updating',) + self.NOTHING_RUNS)
        self.assertIn('"state": "updating" | "failed" | "stopped" | "paused" | "being_confirmed"', AMENDMENT)
        for reason in c.SAVED_CHANGES_EMPTY:
            with self.subTest(reason=reason):
                self.assertEqual(c.saved_changes_line(reason, 'updating'), c.SAVED_CHANGES_EMPTY[reason])
                for state in self.NOTHING_RUNS:
                    self.assertEqual(c.saved_changes_line(reason, state), self.OTHER[reason])
        for state in c.UPDATE_STATES:
            self.assertEqual(c.update_state_form(state), 'updating' if state == 'updating' else 'other')
        for reason, state in (('unfinished', 'running'), ('unfinished', None), ('unfinished', 'Updating'),
                              ('check', ''), ('nothing', 'updating'), ('unfinished', ('updating',)), ('check', 1)):
            with self.subTest(reason=reason, state=state), self.assertRaises(KeyError):
                c.saved_changes_line(reason, state)

    def test_no_form_for_when_nothing_runs_says_work_is_under_way(self):
        """5.1 [R:truth-T4] and U21: "being updated" appears only in 'updating'. Each other form keeps its line's
        why."""
        for reason, text in self.OTHER.items():
            with self.subTest(reason=reason):
                for running in ('being ', 'are made again', 'is being', 'are being'):
                    self.assertNotIn(running, text.lower())
        self.assertNotIn('your', c.SAVED_CHANGES_CHECK_OTHER.lower())  # A21: no change of the member's
        self.assertTrue(c.SAVED_CHANGES_UNFINISHED_OTHER.startswith('The codes from before your change were not '
                                                                    'finished'))
        self.assertIn('because your answers, or an earlier check, changed since those codes were made',
                      c.SAVED_CHANGES_SAME_DETAILS_OTHER)
        self.assertTrue(c.SAVED_CHANGES_CHECK_OTHER.startswith('An earlier check was settled'))

    def test_the_check_form_is_true_after_the_reading_has_run(self):
        """refute-r3c-r1 P5: an A21 update (kind check) fails, stops, pauses or waits on a confirmation at its document
        review too, after its reading ran (amendment 7.4); its form for every such state says what is owed - the codes
        - and never that the document still needs to be read, beside the panel's own text for each situation."""
        line = c.saved_changes_line('check', 'failed')
        self.assertEqual(line, 'An earlier check was settled, so the codes need to be updated with the current '
                               'reading; they have not been updated yet.')
        self.assertNotIn('read', line.replace('reading', ''))  # no "read again", "needs to be read", "being read"
        self.assertNotIn('document', line)
        for situation in ('review_failed', 'review_not_sent', 'processing_failed', 'stopped_by_member',
                          'being_confirmed'):
            state = c.UPDATE_TEXTS[situation].phase
            with self.subTest(situation=situation):
                self.assertIn(state, self.NOTHING_RUNS)
                self.assertEqual(c.saved_changes_line('check', state), line)
                self.assertNotIn('Your change', c.update_text(situation, 'check', False))  # the panel's A21 form
        self.assertEqual(c.saved_changes_line('check', 'updating'), 'An earlier check was settled, so the document is '
                                                                     'being read again with the current reading.')

    # 3c P3: BLOCKER_EXACT holds 5.3's two customer texts and their check forms
    def test_blocker_exact_holds_the_two_texts_and_their_check_forms(self):
        self.assertEqual(c.UPDATE_BLOCKERS, self.BLOCKERS)
        self.assertEqual(set(c.UPDATE_BLOCKERS), set(c.UPDATE_BLOCKER_WORDS))
        self.assertEqual(len(set(c.UPDATE_BLOCKERS.values()) | {c.UPDATE_BLOCKER}), 5)  # five distinct internal keys
        for key, internal in c.UPDATE_BLOCKERS.items():
            with self.subTest(key=key):
                self.assertEqual(c.BLOCKER_EXACT[internal], c.UPDATE_BLOCKER_WORDS[key])
                self.assertEqual(c.customer_blocker(internal), c.UPDATE_BLOCKER_WORDS[key])
        for text in ('The codes are being updated after your change.',
                     'The codes have not been updated after your change yet.'):  # 5.3, verbatim
            self.assertIn(f'"{text}"', AMENDMENT)
        self.assertEqual(sorted(c.BLOCKER_EXACT[internal] for internal in c.UPDATE_BLOCKERS.values()),
                         sorted(['The codes are being updated after your change.',
                                 'The codes have not been updated after your change yet.',
                                 'The codes are being updated.', 'The codes have not been updated yet.']))
        self.assertEqual(c.BLOCKER_EXACT[c.UPDATE_BLOCKER], 'The codes have not been updated yet.')  # unchanged

    def test_update_blocker_chooses_by_state_and_kind(self):
        for state in c.UPDATE_STATES:
            form = 'updating' if state == 'updating' else 'other'
            for kind, words in (('details', 'details'), ('documentation', 'details'), ('check', 'check')):
                with self.subTest(state=state, kind=kind):
                    self.assertEqual(c.update_blocker(state, kind), self.BLOCKERS[(form, words)])
                    said = c.customer_blocker(c.update_blocker(state, kind))
                    self.assertEqual('being updated' in said, state == 'updating')
                    self.assertEqual('your change' in said, kind != 'check')
        for state, kind in (('running', 'details'), ('updating', 'save'), (None, 'check'), ('updating', None)):
            with self.subTest(state=state, kind=kind), self.assertRaises(KeyError):
                c.update_blocker(state, kind)

    # 3c P10: an A21 clearing
    def test_an_a21_clearing_says_the_document_was_read_again(self):
        self.assertEqual(c.CLEARED_READ_AGAIN, 'Cleared when the document was read again with the current reading: the '
                                               'code it was made on changed.')
        self.assertNotIn('detail', c.CLEARED_READ_AGAIN)
        for sentence in (c.CLEARED_SAME_DETAILS, c.CLEARED_DETAILS_CHANGED, c.CLEARED_READ_AGAIN):  # 5.4's form
            self.assertTrue(sentence.startswith('Cleared when ') and sentence.endswith(': the code it was made on '
                                                                                       'changed.'), sentence)
        self.assertIn('read again with the current reading', c.WHAT_CHANGED_READ_AGAIN)  # 6.2's words for it
        self.assertEqual(len({c.CLEARED_BY_REVISION, c.CLEARED_NEW_READING, c.CLEARED_SAME_DETAILS,
                              c.CLEARED_DETAILS_CHANGED, c.CLEARED_READ_AGAIN}), 5)

    def test_the_new_texts_are_in_the_customer_scan(self):
        names = {name for name, _ in customer_strings()}
        for name in ('SAVED_CHANGES_UNFINISHED_OTHER', 'SAVED_CHANGES_SAME_DETAILS_OTHER', 'SAVED_CHANGES_CHECK_OTHER',
                     'SAVED_CHANGES_LINES[check][other]', 'CLEARED_READ_AGAIN'):
            self.assertIn(name, names)
        self.assertEqual(len([name for name in names if name.startswith('UPDATE_BLOCKERS[')]), 4)


class D246CustomerTexts(SimpleTestCase):
    """D246 (repair r3c): the synthetic act's item, and every item a D246 form words, reads the customer's fixed sentence
    of its fact key (held_fact_words), never a cause; every sentence a D246 form or id makes passes the customer guard as
    written - customer_api's net needs no new entry for them."""

    D246_IDS = ('base_included', 'separate_em', 'doubt', 'same_duct', 'statement_scope', 'synthetic_act')

    def test_each_d246_items_fact_reads_its_own_fixed_sentence(self):
        spec = wording.MESSAGES[wording.Message.SYNTHETIC_ACT]
        self.assertEqual((spec.fact, spec.rank), ('performed_status', 2))
        self.assertEqual(c.held_fact_words(spec.fact), 'A detail is needed: whether the service was performed.')
        self.assertEqual(c.QUESTION_WORDS[spec.fact], 'CPT Studio could not confirm from the document that this was '
                                                      'done on the date of service.')
        for message in self.D246_IDS:
            fact = wording.MESSAGES[wording.Message(message)].fact
            with self.subTest(message=message, fact=fact):
                self.assertIn(fact, c.FACT_WORDS)
                words = c.held_fact_words(fact)
                self.assertEqual(words, f'A detail is needed: {c.FACT_WORDS[fact]}.')
                self.assertFalse([cause for cause in c.HELD_FACT_CAUSES if cause in words], words)
                self.assertIsNone(c.FORBIDDEN.search(words), words)

    def test_every_d246_sentence_passes_the_customer_guard_as_written(self):
        from tests.v2.test_wording import d246_sentences
        sentences = d246_sentences()
        self.assertGreater(len(sentences), 700)
        for label, text in sentences:
            with self.subTest(label=label):
                self.assertEqual(c.plain(text), ' '.join(text.split()), text)  # shown, never replaced
                self.assertIsNone(c.FORBIDDEN.search(text), text)
                self.assertEqual([pattern.pattern for pattern in HARD if pattern.search(text)], [], text)
                self.assertFalse([cause for cause in c.HELD_FACT_CAUSES if cause in text], text)


class D254CustomerTexts(SimpleTestCase):
    """DECISIONS D254, D257, D258, D253 QX (ii) (repair r3c of round w8r; customer_api.py needs no change): every sentence
    the totalized builders make - each message, every combination of present and absent slots its builder reads
    (tests/v2/test_wording.py's D254Total) - passes the customer guard as written, and the two new ids' fact keys read
    their own fixed customer sentences, never a cause."""

    def test_the_new_ids_facts_read_their_fixed_sentences(self):
        for message, fact, words in ((wording.Message.UNLISTED_SCOPE, 'performed_status',
                                      'A detail is needed: whether the service was performed.'),
                                     (wording.Message.ENTEROSCOPY_THROUGH, 'procedure',
                                      'A detail is needed: in which procedure the act was done.')):
            with self.subTest(message=message):
                spec = wording.MESSAGES[message]
                self.assertEqual(spec.fact, fact)
                self.assertIn(fact, c.FACT_WORDS)
                self.assertEqual(c.held_fact_words(fact), words)
                self.assertFalse([cause for cause in c.HELD_FACT_CAUSES if cause in words], words)
        self.assertEqual(c.QUESTION_WORDS['performed_status'], 'CPT Studio could not confirm from the document that this '
                                                               'was done on the date of service.')

    def test_every_d254_sentence_passes_the_customer_guard_as_written(self):
        from tests.v2.test_wording import d254_sentences
        sentences = d254_sentences()
        self.assertGreater(len(sentences), 7000)
        for label, text in sentences:
            with self.subTest(label=label):
                self.assertEqual(c.plain(text), ' '.join(text.split()), text)  # shown, never replaced
                self.assertIsNone(c.FORBIDDEN.search(text), text)
                self.assertEqual([pattern.pattern for pattern in HARD if pattern.search(text)], [], text)
                self.assertFalse([cause for cause in c.HELD_FACT_CAUSES if cause in text], text)
                for name in ('Gemini', 'Corti', 'Astra', 'Fable', 'model', 'provider'):
                    self.assertNotIn(name, text)


class D267HeldFactWords(SimpleTestCase):
    """DECISIONS D267 (repair r3c of round w9r; refute-r3c-r1 F4, F7 = r3c Q10; TRIAGE G1-06, G2-17): held_fact_words
    words 'conflict:other' with D254 rule 2's one label, 'another act' (never "the other"), every named kind by the item's
    own label (wording.kind_words); and a procedure-keyed held fact by the item's message - which step 5b records with
    it - naming what its item asks (the route, the anatomy passed through, the tract), never "in which procedure the act
    was done" where the procedure is known; v1's pinned sentence stands when no message is given."""

    PROCEDURE = 'A detail is needed: in which procedure the act was done.'  # v1's MISSING['procedure'], pinned
    ASKS = {
        'procedure': PROCEDURE,
        # D284, G1-08 (step f3w; build list B8): the three explanations state an established route or tract and ask
        # whether the class the code describes was performed - restated from "which part of the digestive tract ..." and
        # "the route of ...", phrases of the attribute each states
        'another_tract': 'A detail is needed: whether the endoscopic ultrasound this code describes was performed.',
        'enteroscopy_route': 'A detail is needed: the route of the enteroscopy.',
        'enteroscopy_approach': 'A detail is needed: whether the enteroscopy this code describes was performed.',
        'examination_route': 'A detail is needed: the route of the endoscopic ultrasound.',
        'examination_approach': 'A detail is needed: whether the endoscopic ultrasound this code describes was performed.',
        'enteroscopy_through': 'A detail is needed: the altered anatomy the enteroscopy was passed through.',
    }
    EXPLANATIONS = ('another_tract', 'enteroscopy_approach', 'examination_approach')

    def test_conflict_other_reads_another_act(self):
        """F4's input: held_fact_words('conflict:other') said "which statement about the other is right for this date";
        the same item's act is "another act" (wording.fact_key gives conflict:other for it)."""
        self.assertEqual(c.held_fact_words('conflict:other'),
                         'A detail is needed: which statement about another act is right for this date.')
        self.assertEqual(wording.fact_key(wording.Message.CONFLICT, wording.Slots(act=Kind.OTHER)), 'conflict:other')
        item = wording.build(wording.Message.CONFLICT, wording.Slots(act=Kind.OTHER), '')
        self.assertIn('another act', item.question)  # one label: the item and its held fact
        for key in ('conflict:other', 'conflict:', 'conflict:not_a_kind', 'conflict:Snare'):  # no kind names the act
            with self.subTest(key=key):
                words = c.held_fact_words(key)
                self.assertIn('which statement about another act is right for this date', words)
                self.assertNotIn('the other', words)
                self.assertNotIn('the another act', words)
                self.assertNotRegex(words, r'\bthe act\b')

    def test_every_named_kind_reads_the_items_own_label(self):
        for kind in Kind:
            if kind is Kind.OTHER:
                continue
            with self.subTest(kind=kind):
                label = wording.kind_words(kind)
                words = c.held_fact_words(f'conflict:{kind.value}')
                self.assertEqual(words, f'A detail is needed: {questions.missing("conflict:", label)}.')
                self.assertEqual(words, f'A detail is needed: which statement about the {label} is right for this '
                                        'date.')
                item = wording.build(wording.Message.CONFLICT, wording.Slots(act=kind), '')
                self.assertEqual(item.fact, f'conflict:{kind.value}')
                self.assertIn(f'the {label} ', item.question)  # the item names the act by the same label
                self.assertNotIn('_', words)
        self.assertEqual(c.held_fact_words('conflict:em_prolonged'),  # never the enumeration's value ("em prolonged")
                         'A detail is needed: which statement about the prolonged visit time is right for this date.')
        self.assertEqual(c.held_fact_words('conflict:snare'),  # every label the reconciliation table holds is unchanged
                         'A detail is needed: which statement about the snare removal is right for this date.')

    def test_each_procedure_keyed_message_names_what_its_item_asks(self):
        keyed = {message.value for message, spec in wording.MESSAGES.items() if spec.fact == 'procedure'}
        self.assertEqual(set(self.ASKS), keyed)  # every procedure-keyed message id has its sentence here
        self.assertEqual(set(c.HELD_FACT_ASKS), keyed - {'procedure'})
        for value, words in self.ASKS.items():
            with self.subTest(message=value):
                self.assertEqual(c.held_fact_words('procedure', value), words)  # as step 5b records it (its value)
                self.assertEqual(c.held_fact_words('procedure', wording.Message(value)), words)
                if value != 'procedure':  # the procedure is known: never v1's procedure sentence
                    self.assertNotIn('in which procedure', words)
        phrases = {phrase.format(session=session) for phrase in wording.ATTRIBUTE_PHRASES.values()
                   if '{act}' not in phrase for session in ('enteroscopy', 'endoscopic ultrasound')}
        for value, words in c.HELD_FACT_ASKS.items():
            with self.subTest(message=value):
                spec = wording.MESSAGES[wording.Message(value)]
                if value in self.EXPLANATIONS:  # D284 G1-08 (B8): the class phrase, no phrase of the attribute stated
                    self.assertEqual(spec.kind, ItemKind.EXPLANATION)
                    self.assertRegex(words, r'^whether the (?:enteroscopy|endoscopic ultrasound) this code describes was '
                                            r'performed$')
                    self.assertNotIn(words, phrases)
                    for stated in ('route', 'tract', 'passed through'):
                        self.assertNotIn(stated, words)
                else:  # a question: wording's own phrase, said of the session by its service
                    self.assertEqual(spec.kind, ItemKind.QUESTION)
                    self.assertIn(words, phrases, value)

    def test_no_message_keeps_v1s_sentence(self):
        self.assertEqual(c.held_fact_words('procedure'), self.PROCEDURE)
        self.assertEqual(c.held_fact_words('procedure', None), self.PROCEDURE)
        self.assertEqual(f'A detail is needed: {wording.MISSING["procedure"]}.', self.PROCEDURE)
        for message in ('doubt', 'not_a_message', '', 7, Kind.SNARE, b'enteroscopy_route'):  # no procedure message
            with self.subTest(message=message):
                self.assertEqual(c.held_fact_words('procedure', message), self.PROCEDURE)
        # a message never words another key's held fact: each key's own sentence, with every message
        for fact in held_fact_keys() + ['not_a_key', '']:
            for message in wording.Message:
                if wording.MESSAGES[message].fact != fact:
                    self.assertEqual(c.held_fact_words(fact, message), c.held_fact_words(fact), (fact, message))
        self.assertEqual(c.held_fact_words('performed_status', 'enteroscopy_route'),
                         'A detail is needed: whether the service was performed.')

    def test_every_held_fact_sentence_with_its_message_passes_the_customer_guard(self):
        shown = 0
        for fact in held_fact_keys():
            for message in (None, *wording.Message):
                words = c.held_fact_words(fact, message)
                shown += 1
                self.assertTrue(words.startswith('A detail is needed: ') and words.endswith('.'), words)
                self.assertNotIn('a detail of the encounter', words)
                self.assertNotIn('_', words)
                self.assertIsNone(c.FORBIDDEN.search(words), words)
                self.assertEqual([pattern.pattern for pattern in HARD if pattern.search(words)], [], words)
                self.assertFalse([cause for cause in c.HELD_FACT_CAUSES if cause in words], words)
                self.assertEqual(c.plain(words), words)
        self.assertGreater(shown, 3000)


class D284AddonWords(SimpleTestCase):
    """DECISIONS D284 (G3-15; build list B7), customer_api's half: an add-on its ADDON row holds reads a fixed sentence
    chosen by the item's MESSAGE (wording.Message.ADDON's value), never by its key - never QUESTION_WORDS'
    performed_status sentence ("could not confirm ... done", untrue of an add-on whose act is established) and never
    STALE_WORDS - in the three states a view shows it: a stored question (its row id; the record's item, step 5b's
    support['item'], is ADDON), a question read time words live (its own ``message``), and a reinstated add-on the row
    withholds (``withheld_by`` overlay.ADDON_CHECK)."""

    @staticmethod
    def proposal(item_message):
        support = {'held_facts': [{'fact': 'performed_status', 'cause': 'coding_rule:ADDON', 'rank': 4}],
                   'family': 'gi.em', 'state': 'uncertain', 'reason': 'held'}
        if item_message is not None:
            support['item'] = {'message': item_message, 'fact': 'performed_status'}
        return SimpleNamespace(support=support, family='gi.em', bucket=Proposal.SELECTED, checks=[],
                               status=Proposal.NEEDS_CLARIFICATION, code='99417')

    @staticmethod
    def view(questions=(), withheld_by=''):
        return SimpleNamespace(questions=list(questions), withheld_by=withheld_by, same_day_held=False, reason='',
                               blocker='', stale=(), modifier_review=None, checks=[],
                               status=Proposal.NEEDS_CLARIFICATION, summary='', answer='')

    def test_the_three_states(self):
        stored = {'id': 7, 'fact': 'performed_status', 'scope': 'proposal'}
        live = {'fact': 'performed_status', 'message': wording.Message.ADDON.value}
        for name, proposal, view, words in (
                ('stored', self.proposal('addon'), self.view([stored]), c.ADDON_WORDS),
                ('live', self.proposal(None), self.view([live]), c.ADDON_WORDS),
                ('live, beside a stored item of another message', self.proposal('status'), self.view([live]),
                 c.ADDON_WORDS),
                ('reinstated, withheld', self.proposal('addon'), self.view(withheld_by=c.ADDON_CHECK),
                 c.WITHHELD_WORDS[c.ADDON_CHECK])):
            with self.subTest(state=name):
                shown = c._qualifications(proposal, 'needs_detail', view, '99417')
                self.assertIn(words, shown)
                self.assertNotIn(c.QUESTION_WORDS['performed_status'], shown)
                self.assertNotIn(c.STALE_WORDS, shown)

    def test_the_message_chooses_never_the_key(self):
        """The same key with any other message (or none) keeps QUESTION_WORDS' sentence: a live question of another
        message, a stored one whose record's item is another message or of another fact, one with no row id."""
        for name, proposal, question in (
                ('live, status', self.proposal('addon'), {'fact': 'performed_status', 'message': 'status'}),
                ('stored, status item', self.proposal('status'), {'id': 7, 'fact': 'performed_status'}),
                ('stored, no item', self.proposal(None), {'id': 7, 'fact': 'performed_status'}),
                ('no row id', self.proposal('addon'), {'fact': 'performed_status'})):
            with self.subTest(case=name):
                shown = c._qualifications(proposal, 'needs_detail', self.view([question]), '99417')
                self.assertIn(c.QUESTION_WORDS['performed_status'], shown)
                self.assertNotIn(c.ADDON_WORDS, shown)
        proposal = self.proposal('addon')
        proposal.support['item']['fact'] = 'event_entry'
        shown = c._qualifications(proposal, 'needs_detail', self.view([{'id': 7, 'fact': 'performed_status'}]), '99417')
        self.assertNotIn(c.ADDON_WORDS, shown)

    def test_the_sentences_pass_the_customer_guard(self):
        self.assertEqual(c.ADDON_CHECK, 'coding_rule:ADDON')
        for text in (c.ADDON_WORDS, c.WITHHELD_WORDS[c.ADDON_CHECK]):
            with self.subTest(text=text):
                self.assertEqual(c.plain(text), text)
                self.assertIsNone(c.FORBIDDEN.search(text), text)
                self.assertEqual([pattern.pattern for pattern in HARD if pattern.search(text)], [], text)
                self.assertFalse([cause for cause in c.HELD_FACT_CAUSES if cause in text], text)
                self.assertNotIn('could not confirm', text)
                self.assertNotIn('ADDON', text)
