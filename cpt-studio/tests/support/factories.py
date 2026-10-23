"""Shared test factories. Synthetic data only.

Every helper creates the minimum valid rows and returns them, so a test reads
as the scenario it checks.
"""
import hashlib
import itertools

from django.utils import timezone

from studio import models
from studio.gi.profiles import CATEGORY_NAME, CATEGORY_SLUG, PROFILES_VERSION
from studio.types import ExtractionResult, PageSpan

_counter = itertools.count(1)


def category():
    obj, _ = models.Category.objects.get_or_create(
        slug=CATEGORY_SLUG, defaults={'name': CATEGORY_NAME, 'profiles_version': PROFILES_VERSION})
    return obj


def workspace(name='Gastroenterology'):
    return models.Workspace.objects.create(name=name, category=category())


def user(username=None, *, actor_kind=models.User.HUMAN, password='synthetic-pass-123!'):
    username = username or f'user{next(_counter)}'
    obj = models.User.objects.create_user(username=username, password=password, actor_kind=actor_kind,
                                          display_name=username.title())
    return obj


def member(ws, usr=None, role=models.Membership.REVIEWER):
    usr = usr or user()
    models.Membership.objects.create(user=usr, workspace=ws, role=role)
    return usr


def encounter(ws, usr, title='Synthetic GI note'):
    return models.Encounter.objects.create(workspace=ws, title=title, created_by=usr)


def pasted_revision(enc, usr, text, *, number=None, parent=None, extract=True):
    """A PASTE revision; with extract=True its extraction is recorded as 'ok'."""
    number = number or (enc.revisions.count() + 1)
    rev = models.SourceRevision.objects.create(
        encounter=enc, number=number, kind=models.SourceRevision.PASTE, pasted_text=text, parent=parent,
        synthetic_attested_by=usr, synthetic_attested_at=timezone.now(), created_by=usr)
    if extract:
        record(rev, ExtractionResult(status='ok', method='paste', text=text,
                                     pages=(PageSpan(page=1, start=0, end=len(text)),)))
        rev.refresh_from_db()
    enc.current_revision = rev
    enc.save(update_fields=['current_revision', 'updated_at'])
    return rev


def record(rev, result: ExtractionResult):
    models.SourceRevision.record_extraction(
        rev.pk, extraction_status=result.status, extraction_method=result.method, text=result.text,
        text_sha256=hashlib.sha256(result.text.encode('utf-8')).hexdigest(),
        pages=[{'page': p.page, 'start': p.start, 'end': p.end} for p in result.pages],
        messages=list(result.messages), ocr_pages=list(result.ocr_pages), engine=dict(result.engine),
        extracted_at=timezone.now())
