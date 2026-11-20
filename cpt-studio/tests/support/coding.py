"""Synthetic factories for the coding path's tests (studio.fable, studio.jobs, studio.state). Synthetic text only; no
real document, no network."""
from __future__ import annotations

import itertools
import json

from django.utils import timezone

from studio import models
from studio.fable import client as fable_client
from studio.fable import prompts
from studio.storage import store_original

_counter = itertools.count(1)
PDF_BYTES = b'%PDF-1.7\n% synthetic test bytes, never parsed by the coding step\n%%EOF\n'
NOTE = ('SYNTHETIC PROCEDURE NOTE\nProcedure: colonoscopy to the cecum.\nFindings: one 6 mm polyp in the sigmoid '
        'colon, removed by cold snare.\nPlan: follow up per pathology.')


def workspace(name='Synthetic practice'):
    category, _ = models.Category.objects.get_or_create(
        slug='synthetic-coding', defaults={'name': 'Synthetic coding', 'profiles_version': 'synthetic@1'})
    return models.Workspace.objects.create(name=name, category=category)


def user(username=None):
    username = username or f'coder{next(_counter)}'
    return models.User.objects.create_user(username=username, password='synthetic-pass-123!',
                                           display_name=username.title())


def member(ws, role=models.Membership.REVIEWER):
    usr = user()
    models.Membership.objects.create(user=usr, workspace=ws, role=role)
    return usr


def encounter(ws, by, *, service_date=None, insurance=None, title='Synthetic note'):
    values = {key: value for key, value in (('service_date', service_date), ('insurance', insurance)) if value}
    return models.Encounter.objects.create(workspace=ws, title=title, created_by=by, user_values=values)


def _revision(enc, by, **fields):
    number = enc.revisions.count() + 1
    rev = models.SourceRevision.objects.create(encounter=enc, number=number, synthetic_attested_by=by,
                                               synthetic_attested_at=timezone.now(), created_by=by, **fields)
    enc.current_revision = rev
    enc.save(update_fields=['current_revision', 'updated_at'])
    return rev


def paste(enc, by, text=NOTE):
    return _revision(enc, by, kind=models.SourceRevision.PASTE, pasted_text=text)


def upload(enc, by, data=PDF_BYTES, filename='synthetic-note.pdf', media_type='application/pdf'):
    storage_name, digest, size = store_original(enc.workspace_id, data, filename)
    source = models.SourceFile.objects.create(encounter=enc, original_name=filename, media_type=media_type,
                                              size=size, sha256=digest, storage_name=storage_name, uploaded_by=by)
    return _revision(enc, by, kind=models.SourceRevision.UPLOAD, source_file=source)


def text_block(text, citations=None):
    return {'type': 'text', 'text': text, 'citations': list(citations) if citations is not None else None}


def page_cite(quote, page):
    return {'type': 'page_location', 'cited_text': quote, 'document_index': 0, 'document_title': 'synthetic-note.pdf',
            'start_page_number': page, 'end_page_number': page + 1}


def char_cite(quote, start=0):
    return {'type': 'char_location', 'cited_text': quote, 'document_index': 0, 'document_title': 'Pasted text',
            'start_char_index': start, 'end_char_index': start + len(quote)}


def usage(input_tokens=12_000, output_tokens=3_000, **extra):
    return {'input_tokens': input_tokens, 'output_tokens': output_tokens, 'cache_creation_input_tokens': 0,
            'cache_read_input_tokens': 0, **extra}


def message(blocks, *, stop='end_turn', used=None, model='claude-fable-5-2', **extra):
    return {'id': f'msg_synthetic{next(_counter)}', 'type': 'message', 'role': 'assistant', 'model': model,
            'content': list(blocks), 'stop_reason': stop, 'stop_sequence': None,
            'usage': used if used is not None else usage(), **extra}


def fenced(result):
    return f'\n\n```json\n{json.dumps(result, indent=1)}\n```\n'


def reader_result(codes, *, questions=(), problems=()):
    return {'document_kind': 'synthetic colonoscopy report', 'services_found': ['colonoscopy with polypectomy'],
            'codes': list(codes), 'documentation_problems': list(problems), 'questions': list(questions)}


def code(code='45385', status='ready', *, units=1, modifiers=(), reason='The note documents it.', question=None):
    return {'code': code, 'units': units, 'modifiers': list(modifiers), 'status': status, 'reason': reason,
            'evidence': [{'quote': 'removed by cold snare', 'page': 1}], 'question': question}


def review(code='45385', verdict='agree', *, reason='Supported as listed.', status='ready', question=None):
    return {'code': code, 'verdict': verdict, 'correct_code': code, 'correct_units': 1, 'correct_modifiers': [],
            'correct_status': status, 'reason': reason, 'evidence': [{'quote': 'cold snare', 'page': 1}],
            'question': question}


def checker_result(reviews, *, missed=(), questions=()):
    return {'reviews': list(reviews), 'missed_codes': list(missed), 'questions': list(questions)}


def reader_message(result, *, used=None, stop='end_turn'):
    """A reader answer with one CODE section per code, each cited, and the final JSON."""
    blocks = [text_block('I read the whole note.\n')]
    for item in result.get('codes', []):
        blocks.append(text_block(f"CODE {item['code']}\n"))
        blocks.append(text_block('The polyp was removed by snare.', [page_cite('removed by cold snare', 1)]))
    blocks.append(text_block(fenced(result)))
    return message(blocks, used=used, stop=stop)


def checker_message(result, *, used=None, stop='end_turn'):
    blocks = [text_block('I read the whole note first.\n')]
    for item in result.get('reviews', []) + result.get('missed_codes', []):
        blocks.append(text_block(f"REVIEW {item['code']}\n"))
        blocks.append(text_block('The snare removal is documented.', [page_cite('cold snare', 2)]))
    blocks.append(text_block(fenced(result)))
    return message(blocks, used=used, stop=stop)


def succeeded(msg):
    return fable_client.message_outcome(msg, sent=True, latency_ms=1234.5, request_id='req_synthetic')


COUNTED = 4_000  # a FakeCoder's free token count of any request, unless it is given another


class FakeCoder:
    """Stands in for the live coder: ``reader`` and ``checker`` are Outcomes, or callables of the request returning
    one. Records every call as (role, request). Like the live coder it counts a request's input tokens before the send
    (``counted``: the count, None for a count that failed, or an exception the count raises); records every request it
    counted in ``counts``."""
    mode, endpoint = 'test', fable_client.ENDPOINT

    def __init__(self, reader=None, checker=None, counted=COUNTED):
        self.answers = {'reader': reader, 'checker': checker}
        self.calls, self.counted, self.counts = [], counted, []

    def count_input_tokens(self, request):
        self.counts.append(request)
        if isinstance(self.counted, BaseException):
            raise self.counted
        return self.counted

    def send(self, request):
        role = 'reader' if request.stored['system'] == prompts.READER_SYSTEM else 'checker'
        self.calls.append((role, request))
        answer = self.answers[role]
        if answer is None:
            raise AssertionError(f'the {role} was not expected to be sent')
        return answer(request) if callable(answer) else answer

    def roles(self):
        return [role for role, _ in self.calls]
