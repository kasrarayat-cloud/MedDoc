"""One prospective QuillMD Word milestone installation; inert without a plan.

The old release-specific drivers are not repinned. This adapter uses their
reviewed service, backup, file and ingress primitives, with a new exact source,
migration, static and operation-local preservation contract. No provider request,
authentication submission or historical approval is inferred by installation.
"""
import argparse
import ast
import copy
from contextlib import ExitStack, contextmanager, redirect_stdout
from datetime import datetime, timezone
import gzip
import hashlib
from functools import lru_cache
from io import BytesIO, StringIO
import json
import os
from pathlib import Path, PurePosixPath
import re
import stat
import subprocess
import sys
import tarfile
import time
from types import SimpleNamespace
import uuid
from dotenv import dotenv_values

from . import legacy_model_activation as old
from . import owner_normal_origin as normal

ROOT=Path('/opt/meddoc-pro')
APP=ROOT/'rebuild'
SOURCE=Path(__file__).resolve().parents[2]
RUNTIME=APP/'.runtime'
BASE='4194f58cb37b13e179810db486b54bf2fe7a42a8'
WORD_BASE='09e58cf9c46217321549e7ff59f2d9c217958333'
DECL='docs/foundation/mutations/20261008-quillmd-word-native-delivery.md'
QUALIFIED=True  # Finished-diff fault checks and independent refutation completed 2026-10-08.
MINIMUM_SPACE=28*1024**3
OUTER_SECONDS=1200
MIGRATIONS=('0019_template_preparation','0020_preparation_initial_state',
            '0021_preparation_failure_evidence','0022_wm_output_followup','0023_delivery_campaign')
NEW_TABLES=frozenset({'core_templatepreparation','core_preparationreceipt'})
ADDED_COLUMNS=frozenset({'prepared_path','prepared_sha256','preparation_id'})
CAMPAIGN='word-milestone-delivery-20261008-v1'
CAMPAIGN_SCOPE='fe387adcfb7f9397a7c54c342270063f9fc7f6cdd45b357e6ab16e47d16670c8'
ENV_KEYS=frozenset({'QUILLMD_RELEASE_SHA','QUILLMD_WORD_PREPARATION_ENABLED',
                   'QUILLMD_WORD_PREPARATION_CAMPAIGN','QUILLMD_WORD_PREPARATION_CAMPAIGN_SCOPE_SHA256',
                   'QUILLMD_OWNER_NORMAL_ORIGIN_ENABLED'})
STATIC_INPUTS=frozenset({'app.css','app.js','docx-frame.css','docx-frame.js','template-preparation.js',
    'fonts/dm-sans.ttf','fonts/OFL-DM-Sans.txt','vendor/docx-preview/jszip.min.js',
    'vendor/docx-preview/docx-preview.min.js','vendor/docx-preview/docx-preview.min.js.map',
    'vendor/docx-preview/artifact-lock.json','vendor/docx-preview/LICENSE.jszip',
    'vendor/docx-preview/LICENSE.docx-preview','vendor/docx-preview/THIRD_PARTY_NOTICES.txt',
    'django_otp/css/login.css','otp_totp/css/qrcode.css','otp_totp/js/qrcode.js'})
REPAIR_PATHS=frozenset({'rebuild/core/jobs.py','rebuild/core/preparation.py','rebuild/core/views.py',
    '.github/workflows/test.yml','rebuild/core/template_source.py',
    'rebuild/core/preparation_campaign.py','rebuild/core/answer_constraints.py','rebuild/core/provider_models.py',
    'rebuild/core/tests/test_preparation.py','rebuild/core/tests/test_preparation_campaign.py',
    'rebuild/core/tests/test_preparation_campaign_pg.py','rebuild/core/tests/test_answer_constraints.py',
    'rebuild/core/tests/test_provider_models.py','rebuild/core/tests/test_preparation_constraints.py',
    'rebuild/core/tests/test_preparation_export_layout.py',
    'rebuild/core/tests/test_doctor_pilot_self_service.py',
    'rebuild/documents/engine.py','rebuild/documents/preparation.py','rebuild/documents/test_preparation.py',
    'rebuild/documents/service.py','rebuild/documents/test_export_layout.py','rebuild/documents/layout.py',
    'rebuild/quillmd/settings.py','rebuild/core/migrations/0023_delivery_campaign.py',
    'rebuild/documents/test_preparation_constraints.py',
    'rebuild/static/docx-frame.js','rebuild/static/docx-frame.css','rebuild/static/template-preparation.js',
    'rebuild/templates/docx_preview_frame.html','rebuild/templates/template_preparation.html',
    'rebuild/templates/encounter_detail.html','rebuild/templates/template_detail.html','rebuild/ops/test_docx_preview_browser.cjs',
    'rebuild/ops/word_milestone_delivery.py','rebuild/ops/test_word_milestone_delivery.py',
    'scripts/install-word-milestone.py','scripts/ci/verify-fresh.sh',DECL,
    'docs/foundation/mutations/20261008-quillmd-word-delivery-followup-v1.md'})


# Canonical PostgreSQL definitions from the preserved isolated candidate execution.
# Fixture ownership/ACL is deliberately omitted; actual native defaults bind ACL.
SCHEMA_CONTRACT = {'constraints': {'core_preparationreceipt:core_preparationrece_preparation_id_3735a1ef_fk_core_temp': {'deferrable': True,
                                                                                                       'definition': 'FOREIGN '
                                                                                                                     'KEY '
                                                                                                                     '(preparation_id) '
                                                                                                                     'REFERENCES '
                                                                                                                     'core_templatepreparation(id) '
                                                                                                                     'DEFERRABLE '
                                                                                                                     'INITIALLY '
                                                                                                                     'DEFERRED',
                                                                                                       'initially_deferred': True,
                                                                                                       'type': 'f',
                                                                                                       'validated': True},
                 'core_preparationreceipt:core_preparationreceipt_elapsed_ms_check': {'deferrable': False,
                                                                                      'definition': 'CHECK '
                                                                                                    '((elapsed_ms '
                                                                                                    '>= 0))',
                                                                                      'initially_deferred': False,
                                                                                      'type': 'c',
                                                                                      'validated': True},
                 'core_preparationreceipt:core_preparationreceipt_pkey': {'deferrable': False,
                                                                          'definition': 'PRIMARY KEY (id)',
                                                                          'initially_deferred': False,
                                                                          'type': 'p',
                                                                          'validated': True},
                 'core_preparationreceipt:preparation_cost_nonnegative': {'deferrable': False,
                                                                          'definition': 'CHECK '
                                                                                        '(((computed_cost IS '
                                                                                        'NULL) OR '
                                                                                        '(computed_cost >= '
                                                                                        '(0)::numeric)))',
                                                                          'initially_deferred': False,
                                                                          'type': 'c',
                                                                          'validated': True},
                 'core_preparationreceipt:preparation_receipt_role_cap': {'deferrable': False,
                                                                          'definition': 'CHECK '
                                                                                        '(((quote_maximum >= '
                                                                                        '(0)::numeric) AND '
                                                                                        '(quote_maximum <= '
                                                                                        '0.16) AND '
                                                                                        '((role)::text = ANY '
                                                                                        "((ARRAY['proposer'::character "
                                                                                        'varying, '
                                                                                        "'checker'::character "
                                                                                        'varying])::text[]))))',
                                                                          'initially_deferred': False,
                                                                          'type': 'c',
                                                                          'validated': True},
                 'core_preparationreceipt:preparation_role_once': {'deferrable': False,
                                                                   'definition': 'UNIQUE (preparation_id, '
                                                                                 'role)',
                                                                   'initially_deferred': False,
                                                                   'type': 'u',
                                                                   'validated': True},
                 'core_templatepreparation:core_templateprepara_approved_by_id_b32fc6ce_fk_core_user': {'deferrable': True,
                                                                                                        'definition': 'FOREIGN '
                                                                                                                      'KEY '
                                                                                                                      '(approved_by_id) '
                                                                                                                      'REFERENCES '
                                                                                                                      'core_user(id) '
                                                                                                                      'DEFERRABLE '
                                                                                                                      'INITIALLY '
                                                                                                                      'DEFERRED',
                                                                                                        'initially_deferred': True,
                                                                                                        'type': 'f',
                                                                                                        'validated': True},
                 'core_templatepreparation:core_templateprepara_requested_by_id_1e2e4e8d_fk_core_user': {'deferrable': True,
                                                                                                         'definition': 'FOREIGN '
                                                                                                                       'KEY '
                                                                                                                       '(requested_by_id) '
                                                                                                                       'REFERENCES '
                                                                                                                       'core_user(id) '
                                                                                                                       'DEFERRABLE '
                                                                                                                       'INITIALLY '
                                                                                                                       'DEFERRED',
                                                                                                         'initially_deferred': True,
                                                                                                         'type': 'f',
                                                                                                         'validated': True},
                 'core_templatepreparation:core_templateprepara_template_id_f994e65c_fk_core_temp': {'deferrable': True,
                                                                                                     'definition': 'FOREIGN '
                                                                                                                   'KEY '
                                                                                                                   '(template_id) '
                                                                                                                   'REFERENCES '
                                                                                                                   'core_template(id) '
                                                                                                                   'DEFERRABLE '
                                                                                                                   'INITIALLY '
                                                                                                                   'DEFERRED',
                                                                                                     'initially_deferred': True,
                                                                                                     'type': 'f',
                                                                                                     'validated': True},
                 'core_templatepreparation:core_templatepreparation_pkey': {'deferrable': False,
                                                                            'definition': 'PRIMARY KEY (id)',
                                                                            'initially_deferred': False,
                                                                            'type': 'p',
                                                                            'validated': True},
                 'core_templatepreparation:core_templatepreparation_revision_check': {'deferrable': False,
                                                                                      'definition': 'CHECK '
                                                                                                    '((revision '
                                                                                                    '>= 0))',
                                                                                      'initially_deferred': False,
                                                                                      'type': 'c',
                                                                                      'validated': True},
                 'core_templatepreparation:core_templatepreparation_template_id_key': {'deferrable': False,
                                                                                       'definition': 'UNIQUE '
                                                                                                     '(template_id)',
                                                                                       'initially_deferred': False,
                                                                                       'type': 'u',
                                                                                       'validated': True},
                 'core_templateversion:core_templateversion_preparation_id_cecb82b3_fk_core_temp': {'deferrable': True,
                                                                                                    'definition': 'FOREIGN '
                                                                                                                  'KEY '
                                                                                                                  '(preparation_id) '
                                                                                                                  'REFERENCES '
                                                                                                                  'core_templatepreparation(id) '
                                                                                                                  'DEFERRABLE '
                                                                                                                  'INITIALLY '
                                                                                                                  'DEFERRED',
                                                                                                    'initially_deferred': True,
                                                                                                    'type': 'f',
                                                                                                    'validated': True}},
 'index_supplement_sha256': '04fb345a723dd8b57ce1e84b09b764ab35fc7b6fe9ef1b0dae5ec504c1564491',
 'indexes': {'core_preparationreceipt:core_preparationreceipt_pkey': {'definition': 'CREATE UNIQUE INDEX '
                                                                                    'core_preparationreceipt_pkey '
                                                                                    'ON '
                                                                                    'public.core_preparationreceipt '
                                                                                    'USING btree (id)',
                                                                      'primary': True,
                                                                      'ready': True,
                                                                      'unique': True,
                                                                      'valid': True},
             'core_preparationreceipt:core_preparationreceipt_preparation_id_3735a1ef': {'definition': 'CREATE '
                                                                                                       'INDEX '
                                                                                                       'core_preparationreceipt_preparation_id_3735a1ef '
                                                                                                       'ON '
                                                                                                       'public.core_preparationreceipt '
                                                                                                       'USING '
                                                                                                       'btree '
                                                                                                       '(preparation_id)',
                                                                                         'primary': False,
                                                                                         'ready': True,
                                                                                         'unique': False,
                                                                                         'valid': True},
             'core_preparationreceipt:preparation_role_once': {'definition': 'CREATE UNIQUE INDEX '
                                                                             'preparation_role_once ON '
                                                                             'public.core_preparationreceipt '
                                                                             'USING btree (preparation_id, '
                                                                             'role)',
                                                               'primary': False,
                                                               'ready': True,
                                                               'unique': True,
                                                               'valid': True},
             'core_templatepreparation:core_templatepreparation_approved_by_id_b32fc6ce': {'definition': 'CREATE '
                                                                                                         'INDEX '
                                                                                                         'core_templatepreparation_approved_by_id_b32fc6ce '
                                                                                                         'ON '
                                                                                                         'public.core_templatepreparation '
                                                                                                         'USING '
                                                                                                         'btree '
                                                                                                         '(approved_by_id)',
                                                                                           'primary': False,
                                                                                           'ready': True,
                                                                                           'unique': False,
                                                                                           'valid': True},
             'core_templatepreparation:core_templatepreparation_pkey': {'definition': 'CREATE UNIQUE INDEX '
                                                                                      'core_templatepreparation_pkey '
                                                                                      'ON '
                                                                                      'public.core_templatepreparation '
                                                                                      'USING btree (id)',
                                                                        'primary': True,
                                                                        'ready': True,
                                                                        'unique': True,
                                                                        'valid': True},
             'core_templatepreparation:core_templatepreparation_requested_by_id_1e2e4e8d': {'definition': 'CREATE '
                                                                                                          'INDEX '
                                                                                                          'core_templatepreparation_requested_by_id_1e2e4e8d '
                                                                                                          'ON '
                                                                                                          'public.core_templatepreparation '
                                                                                                          'USING '
                                                                                                          'btree '
                                                                                                          '(requested_by_id)',
                                                                                            'primary': False,
                                                                                            'ready': True,
                                                                                            'unique': False,
                                                                                            'valid': True},
             'core_templatepreparation:core_templatepreparation_template_id_key': {'definition': 'CREATE '
                                                                                                 'UNIQUE '
                                                                                                 'INDEX '
                                                                                                 'core_templatepreparation_template_id_key '
                                                                                                 'ON '
                                                                                                 'public.core_templatepreparation '
                                                                                                 'USING '
                                                                                                 'btree '
                                                                                                 '(template_id)',
                                                                                   'primary': False,
                                                                                   'ready': True,
                                                                                   'unique': True,
                                                                                   'valid': True},
             'core_templatepreparation:preparation_single_running': {'definition': 'CREATE UNIQUE INDEX '
                                                                                   'preparation_single_running '
                                                                                   'ON '
                                                                                   'public.core_templatepreparation '
                                                                                   'USING btree ((1)) WHERE '
                                                                                   '((state)::text = ANY '
                                                                                   "((ARRAY['inventory'::character "
                                                                                   'varying, '
                                                                                   "'proposer'::character "
                                                                                   'varying, '
                                                                                   "'checker'::character "
                                                                                   'varying])::text[]))',
                                                                     'primary': False,
                                                                     'ready': True,
                                                                     'unique': True,
                                                                     'valid': True},
             'core_templateversion:core_templateversion_preparation_id_cecb82b3': {'definition': 'CREATE '
                                                                                                 'INDEX '
                                                                                                 'core_templateversion_preparation_id_cecb82b3 '
                                                                                                 'ON '
                                                                                                 'public.core_templateversion '
                                                                                                 'USING '
                                                                                                 'btree '
                                                                                                 '(preparation_id)',
                                                                                   'primary': False,
                                                                                   'ready': True,
                                                                                   'unique': False,
                                                                                   'valid': True}},
 'migration_sha256': {'rebuild/core/migrations/0019_template_preparation.py': '17e4a60c605ca80db7115beb2e735ad48c7aad3ea4101319c9d1738d3c3e45cd',
                      'rebuild/core/migrations/0020_preparation_initial_state.py': '0604070010a312d9451550d695b43be26478e2bab2a409e77a845bd15cf241ed',
                      'rebuild/core/migrations/0021_preparation_failure_evidence.py': '004efca73837351ab76ca01c5359b517c66cd088925f988af14bea50d871617e',
                      'rebuild/core/migrations/0022_wm_output_followup.py': '048a2b23f4c9d1c5882d01916d50ffa8e2abbfdfdc50d007c3559209fabcf1a7',
                      'rebuild/core/migrations/0023_delivery_campaign.py': '34ec7325a29f69f7c3c5c120fa34048df6f512224b1cd6cd5bd06c8a652fdc46'},
 'postgresql_server_version_num': '160015',
 'provenance_sha256': '43edc9904e6f1e09c527820d051a5f6fc968d883f0d525e23c81d21489f5f3b5'}


class Refusal(RuntimeError):
    """Fixed public label; protected command/provider/database text is not emitted."""


def require(value,label):
    if not value:raise Refusal('word_delivery_'+label)


sha=old.sha
encode=old.encode
protected=old.protected
write_new=old.write_new


def admission_space(phase):
    observed=os.statvfs(ROOT)
    available=observed.f_bavail*observed.f_frsize
    require(available>=MINIMUM_SPACE,'storage_28gib')
    return {'phase':phase,'available_bytes':available,'minimum_available_bytes':MINIMUM_SPACE,
            'filesystem_device':ROOT.stat().st_dev,'available_inodes':observed.f_favail}


def render_environment(original,candidate,*,recovery=False):
    require(type(original) is bytes and original.endswith(b'\n'),'environment_bytes')
    require(re.fullmatch('[a-f0-9]{40}',candidate or ''),'candidate_sha')
    parsed=dotenv_values(stream=StringIO(original.decode()),interpolate=False)
    require(parsed.get('QUILLMD_DATA_MODE','synthetic')=='synthetic'
        and parsed.get('QUILLMD_PREVIEW_AUTH_ENABLED')=='1'
        and parsed.get('QUILLMD_APP_BASE_URL')=='https://app.quillmd.com:9443'
        and parsed.get('QUILLMD_AI_MODE')=='live' and parsed.get('QUILLMD_AI_PROVIDER')=='anthropic',
        'restricted_synthetic_environment')
    values={'QUILLMD_RELEASE_SHA':candidate,'QUILLMD_WORD_PREPARATION_ENABLED':'0' if recovery else '1',
        'QUILLMD_WORD_PREPARATION_CAMPAIGN':'' if recovery else CAMPAIGN,
        'QUILLMD_WORD_PREPARATION_CAMPAIGN_SCOPE_SHA256':'' if recovery else CAMPAIGN_SCOPE,
        'QUILLMD_OWNER_NORMAL_ORIGIN_ENABLED':'0' if recovery else '1'}
    result=[];seen=set();unrelated=[]
    for line in original.splitlines(keepends=True):
        match=old.ASSIGNMENT.match(line);key=match[1].decode() if match else None
        if key in ENV_KEYS:
            require(key not in seen,'duplicate_controlled_setting');seen.add(key)
            result.append((key+'="'+values[key]+'"\n').encode())
        else:result.append(line);unrelated.append(line)
    require('QUILLMD_RELEASE_SHA' in seen,'release_setting_required')
    result.extend((key+'="'+values[key]+'"\n').encode() for key in sorted(ENV_KEYS-seen))
    updated=b''.join(result);after=dotenv_values(stream=StringIO(updated.decode()),interpolate=False)
    require(all(after.get(key)==value for key,value in values.items()),'effective_controlled_settings')
    require({k:v for k,v in parsed.items() if k not in ENV_KEYS}=={k:v for k,v in after.items() if k not in ENV_KEYS},'unrelated_environment_values')
    require([line for line in updated.splitlines(keepends=True) if not
        ((match:=old.ASSIGNMENT.match(line)) and match[1].decode() in ENV_KEYS)]==unrelated,'unrelated_environment_bytes')
    return updated


def source_pins(candidate):
    require(re.fullmatch('[a-f0-9]{40}',candidate or ''),'candidate_sha')
    require(old.git(SOURCE,'rev-parse','HEAD').strip().decode()==candidate,'operator_candidate_head')
    require(not old.git(SOURCE,'status','--porcelain','--untracked-files=no').strip(),'operator_tracked_clean')
    require(old.git(ROOT,'branch','--show-current').strip()==b'main'
        and old.git(ROOT,'rev-parse','HEAD').strip().decode()==BASE
        and not old.git(ROOT,'status','--porcelain','--untracked-files=no').strip(),'shared_exact_clean_main')
    old.git(SOURCE,'merge-base','--is-ancestor',WORD_BASE,candidate)
    require(old.git(SOURCE,'ls-remote','origin','refs/heads/main').split()[0].decode()==candidate,'exact_merged_main')
    changed=set(old.git(SOURCE,'diff','--name-only',WORD_BASE,candidate).decode().splitlines())
    require(changed<=REPAIR_PATHS,'candidate_delta_scope')
    files=old.git(SOURCE,'ls-files','rebuild','scripts/check-citation.sh','scripts/lib/runs-api.sh',
        'scripts/run-ruled-mutation.sh','scripts/lib/declaration.sh','scripts/lib/run-watched.sh',
        'scripts/activate-typed-voice.py','scripts/install-word-milestone.py',DECL).decode().splitlines()
    result={}
    for relative in files:
        path=SOURCE/relative
        require(path.resolve(strict=True)==path and path.is_file() and path.lstat().st_nlink==1,'tracked_source_object')
        raw=old.public_source(path)
        require(raw==old.git(SOURCE,'show',candidate+':'+relative),'tracked_source_bytes')
        result[relative]=sha(raw)
    require(DECL in result,'committed_declaration_required')
    old.command(['bash',str(SOURCE/'scripts/check-citation.sh'),candidate],cwd=SOURCE,timeout=120)
    return result


def validate_plan(plan):
    require(type(plan) is dict and plan.get('format')==1 and plan.get('qualified') is True,'qualified_plan')
    require(plan.get('source_before')==BASE and plan.get('word_base')==WORD_BASE,'plan_source_before')
    require(re.fullmatch('[a-f0-9]{40}',plan.get('candidate','')),'plan_candidate')
    require(plan.get('migration_nodes')==list(MIGRATIONS) and plan.get('minimum_available_bytes')==MINIMUM_SPACE,'plan_migration_storage_scope')
    require(plan.get('provider_calls')==0 and plan.get('authentication_submissions')==0
        and plan.get('historical_deployment_approval_verified') is False
        and plan.get('original_baselines_replaced') is False,'plan_authority_scope')
    require(type(plan.get('source_sha256')) is dict and all(re.fullmatch('[a-f0-9]{64}',s or '') for s in plan['source_sha256'].values()),'plan_source_pins')
    require(set(plan.get('static_source_sha256',{}))==STATIC_INPUTS,'plan_static_population')
    require(plan.get('campaign')==CAMPAIGN and plan.get('campaign_scope_sha256')==CAMPAIGN_SCOPE,'plan_campaign')
    return plan


def projected_population(before,after,*,metadata_sequence_before=None):
    """Old row identities/columns survive schema additions; new metadata is exact."""
    require(set(after['tables'])==set(before['tables'])|NEW_TABLES,'migration_table_population')
    model_contract=migration_model_metadata()
    for name,row in before['tables'].items():
        other=after['tables'][name]
        require(other['old_rows']==row['old_rows'],'old_row_content_'+name)
        require(other['old_columns']==row['old_columns'],'old_column_metadata_'+name)
        require(other['owner_acl']==row['owner_acl'],'old_table_owner_acl_'+name)
        if name not in {'auth_permission','django_content_type','django_migrations'}:
            require(other['rows']==row['rows'],'old_row_count_'+name)
        added=set(other['columns'])-set(row['columns'])
        require(added==(ADDED_COLUMNS if name=='core_templateversion' else set()),'old_column_addition_'+name)
        require([value for value in other['definitions'] if value[0] in row['columns']]==row['definitions'],
            'old_complete_column_metadata_'+name)
        require([value for value in other['definitions'] if value[0] not in row['columns']]==
            model_contract['columns'].get(name,[]),'new_added_column_definition_'+name)
    for name in NEW_TABLES:
        other=after['tables'][name]
        require(other['rows']==0,'new_tables_empty')
        require(other['definitions']==model_contract['columns'][name],'new_table_complete_columns')
        require(other['owner_acl'][0][0]=='quillmd_owner' and other['owner_acl'][0][2] is False and other['owner_acl'][0][3] is False
            and other['owner_acl'][0][4]=='r'
            and other['privileges']==before['expected_new_table_privileges'],'new_table_owner_acl_rls')
    require(after['added_migrations']==[('core',name) for name in MIGRATIONS],'exact_forward_migration_rows')
    require(set(after['added_content_types'])=={('core','templatepreparation'),('core','preparationreceipt')},'exact_added_content_types')
    require(set(after['added_permissions'])=={(model,verb+'_'+model) for model in ('templatepreparation','preparationreceipt')
        for verb in ('add','change','delete','view')},'exact_added_permissions')
    require(after['invariants']==before['invariants'] and not any(after['invariants'].values()),'old_database_invariants')
    require(after['referenced_files']==before['referenced_files'],'old_referenced_files')
    require(after['expected_new_table_privileges']==before['expected_new_table_privileges'],'new_table_default_privileges_preserved')
    schema_preservation(before['schema'],after['schema'],after['expected_functions'],after['expected_triggers'],
        metadata_sequence_before=metadata_sequence_before)
    return True


@lru_cache(maxsize=1)
def migration_model_metadata():
    """Derive full new columns from disk migration state in an isolated no-DB process."""
    require(all(sha(old.public_source(SOURCE/path))==expected for path,expected in SCHEMA_CONTRACT['migration_sha256'].items()),
        'canonical_schema_migration_pins')
    code='''import json
from django.conf import settings
settings.configure(INSTALLED_APPS=['django.contrib.contenttypes','django.contrib.auth','core'],AUTH_USER_MODEL='core.User',DEFAULT_AUTO_FIELD='django.db.models.BigAutoField',DATABASES={'default':{'ENGINE':'django.db.backends.postgresql','NAME':'unused'}})
import django;django.setup()
from django.db.migrations.loader import MigrationLoader
from django.db import connection
loader=MigrationLoader(None);state=loader.project_state([('core','0023_delivery_campaign')])
result={'columns':{}}
for name in ('TemplatePreparation','PreparationReceipt','TemplateVersion'):
 model=state.apps.get_model('core',name);fields=model._meta.local_fields
 if name=='TemplateVersion':fields=[f for f in fields if f.column in ('prepared_path','prepared_sha256','preparation_id')]
 values=[]
 for field in fields:
  datatype=field.db_type(connection).replace('varchar','character varying').replace(', ',',')
  assert not field.has_db_default() and not field.generated
  values.append([field.column,datatype,not field.null,None,'','',True])
 result['columns'][model._meta.db_table]=values
print(json.dumps(result,sort_keys=True))
'''
    # This pure migration-state inspection uses the invoking, dependency-qualified
    # interpreter. The native execution door still pins its installed interpreter.
    result=subprocess.run([sys.executable,'-B','-c',code],cwd=SOURCE/'rebuild',
        env={'PATH':'/usr/bin:/bin','LANG':'C.UTF-8','PYTHONDONTWRITEBYTECODE':'1'},capture_output=True,timeout=30)
    require(result.returncode==0 and len(result.stdout)<=65536,'source_migration_model_contract')
    contract=json.loads(result.stdout)
    require(set(contract['columns'])==set(NEW_TABLES)|{'core_templateversion'}
        and {value[0] for value in contract['columns']['core_templateversion']}==ADDED_COLUMNS,'source_model_contract_population')
    return contract


def original_population(before,observed,*,allow_metadata_consumption=False):
    """A rolled-back transaction is proven from the complete old observation."""
    require(all(observed[key]==before[key] for key in ('tables','invariants','referenced_files','expected_new_table_privileges')),
        'reconciliation_original_database')
    require({k:v for k,v in before['schema'].items() if k!='sequences'}==
        {k:v for k,v in observed['schema'].items() if k!='sequences'},'reconciliation_original_schema')
    # nextval is not transactional. Only the prospective five migration, two
    # content-type and eight permission sequence consumptions can survive a
    # complete transaction rollback. Never reset them or accept other drift.
    limits={'django_migrations_id_seq':5,'django_content_type_id_seq':2,'auth_permission_id_seq':8}
    original=before['schema']['sequences'];current=observed['schema']['sequences'];deltas={}
    require(set(original)==set(current),'reconciliation_sequence_population')
    for name,value in original.items():
        if name not in limits:require(current[name]==value,'reconciliation_unrelated_sequence');continue
        require(len(value)==len(current[name])==1 and len(value[0])==len(current[name][0])==2,
            'reconciliation_metadata_sequence_shape')
        start,called=value[0];end,now_called=current[name][0]
        require(type(start) is int and type(end) is int and type(called) is bool and type(now_called) is bool,
            'reconciliation_metadata_sequence_types')
        consumed=end-start+(1 if not called and now_called else 0)
        require((now_called or (not called and end==start)) and 0<=consumed<=(limits[name] if allow_metadata_consumption else 0),
            'reconciliation_metadata_sequence_consumption')
        deltas[name]={'before':value,'after':current[name],'consumed':consumed,'maximum':limits[name]}
    require(not any(observed.get(key,[]) for key in ('added_migrations','added_content_types','added_permissions')),
        'reconciliation_no_partial_metadata')
    require(observed.get('applied_core_migrations')==before.get('applied_core_migrations'),
        'reconciliation_original_migration_nodes')
    return {'complete_original_database_verified':True,'retained_metadata_sequence_consumption':deltas}


def migration_sql_metadata():
    """Read only the finite, source-pinned forward SQL literals, never reverse SQL."""
    functions={};triggers={}
    for name in MIGRATIONS:
        tree=ast.parse((SOURCE/'rebuild/core/migrations'/(name+'.py')).read_bytes())
        constants={};statements=[]
        for node in tree.body:
            if isinstance(node,ast.Assign) and isinstance(node.value,ast.Constant) and isinstance(node.value.value,str):
                for target in node.targets:
                    if isinstance(target,ast.Name):constants[target.id]=node.value.value
        for label in ('INITIAL','VERSION','CAPS','SQL'):
            if label in constants:statements.append(constants[label])
        for node in ast.walk(tree):
            if (isinstance(node,ast.Call) and isinstance(node.func,ast.Attribute) and node.func.attr=='RunSQL'
                    and node.args and isinstance(node.args[0],ast.Constant) and isinstance(node.args[0].value,str)):
                statements.append(node.args[0].value)
        for statement in statements:
            for key,value in constants.items():statement=statement.replace('@'+key+'@',value)
            for function,arguments,returns,language,body in re.findall(
                    r'CREATE(?:\s+OR\s+REPLACE)?\s+FUNCTION\s+(\w+)\s*\((.*?)\)\s+RETURNS\s+(\w+)\s+LANGUAGE\s+(\w+)\s+AS\s+\$\$(.*?)\$\$',statement,re.I|re.S):
                functions[function]={'body':body,'arguments':', '.join(' '.join(value.split()) for value in arguments.split(',') if value.strip()),
                    'returns':returns.lower(),'language':language.lower(),'owner':'quillmd_owner','acl':None,
                    'configuration':None,'security_definer':False}
            for trigger,timing,events,table,function in re.findall(
                    r'CREATE\s+TRIGGER\s+(\w+)\s+(BEFORE|AFTER)\s+([A-Z\s]+?)\s+ON\s+(\w+)\s+FOR\s+EACH\s+ROW\s+EXECUTE\s+FUNCTION\s+(\w+)\s*\(\s*\)\s*;',statement,re.I|re.S):
                event_names=[name.strip().upper() for name in re.split(r'\s+OR\s+',events)]
                require(set(event_names)<={'INSERT','UPDATE','DELETE','TRUNCATE'},'forward_trigger_event')
                event_bits={'INSERT':4,'DELETE':8,'UPDATE':16,'TRUNCATE':32}
                triggers[table+':'+trigger]={'enabled':'O','type':1+(2 if timing.upper()=='BEFORE' else 0)+sum(event_bits[name] for name in event_names),
                    'function_schema':'public','function':function,'arguments_hex':'','when':None,'columns':'',
                    'constraint':0,'deferrable':False,'initially_deferred':False}
    require(functions and triggers,'forward_sql_metadata_population')
    return functions,triggers


def schema_preservation(before,after,functions,triggers,*,metadata_sequence_before=None):
    """Unrelated schema/ACL/guard changes cannot disappear behind row equality."""
    require(before['policies']==after['policies'] and before['default_acl']==after['default_acl'],'schema_policy_or_default_acl')
    require(before['sequence_metadata']==after['sequence_metadata'],'sequence_definition_or_acl_changed')
    for name,row in before['functions'].items():require(after['functions'].get(name)==row,'old_function_changed')
    require(set(after['functions'])-set(before['functions'])==set(functions),'new_function_population')
    for name,expected in functions.items():
        actual=after['functions'][name]
        require(actual==expected,'new_function_source_or_security')
    for name,row in before['triggers'].items():require(after['triggers'].get(name)==row,'old_trigger_changed')
    require(set(after['triggers'])-set(before['triggers'])==set(triggers),'new_trigger_population')
    for name,expected in triggers.items():
        require({key:value for key,value in after['triggers'][name].items() if key!='definition'}==expected,
            'new_trigger_source_or_enabled_state')
    for kind in ('constraints','indexes'):
        for name,row in before[kind].items():require(after[kind].get(name)==row,'old_'+kind+'_changed')
        additions={name:after[kind][name] for name in set(after[kind])-set(before[kind])}
        require(additions==SCHEMA_CONTRACT[kind],'new_'+kind+'_canonical_population')
    for name,row in before['sequences'].items():
        if name not in {'auth_permission_id_seq','django_content_type_id_seq','django_migrations_id_seq'}:
            require(after['sequences'].get(name)==row,'unrelated_sequence_changed')
    require(set(before['sequences'])==set(after['sequences']),'sequence_population')
    reference=metadata_sequence_before or before['sequences']
    for name,consumption in (('django_migrations_id_seq',5),('django_content_type_id_seq',2),('auth_permission_id_seq',8)):
        require(name in reference and name in after['sequences'],'metadata_sequence_present')
        old_value=reference[name];new_value=after['sequences'][name]
        require(len(old_value)==len(new_value)==1 and len(old_value[0])==len(new_value[0])==2,'metadata_sequence_shape')
        start,called=old_value[0];end,now_called=new_value[0]
        require(type(start) is int and type(end) is int and type(called) is bool and now_called is True,
            'metadata_sequence_identity')
        require(end-start+(0 if called else 1)==consumption,'exact_metadata_sequence_consumption')
    return True


def preservation(before,after,*,ingress=None):
    """Fresh act-local observation; never substitutes for historical approval."""
    for name in ('files','mail','foreign_services'):
        require(after[name]==before[name],'operation_preservation_'+name)
    expected=copy.deepcopy(before['configuration'])
    if ingress is not None:
        require(normal.INGRESS in expected,'declared_ingress_present')
        expected[normal.INGRESS]=ingress
    require(after['configuration']==expected,'operation_preservation_configuration')
    return True


def execute(plan,host):
    validate_plan(plan)
    host.check_plan(plan)
    report={'format':1,'candidate':plan['candidate'],'complete':False,'provider_calls':0,
        'authenticated_https_workflows_verified':False,'historical_deployment_approval_verified':False,
        'original_baselines_replaced':False,'storage':[],'stage':'prepared'}
    stopped=False;advanced=False;schema_complete=False;forward_started=False
    def checkpoint(stage):
        report['stage']=stage;report['storage'].append(host.space(stage));host.record(stage,report)
    try:
        with host.hold():
            before=host.snapshot();report['operation_before']=before
            host.native_admission(before)
            checkpoint('admitted')
            stopped=True
            for unit in old.UNITS[:2]:host.service('stop',unit)
            host.no_pending_work()
            host.service('stop',old.UNITS[2]);host.require_stopped()
            drained=host.snapshot();preservation(before,drained)
            require(drained['database']==before['database'],'drain_database_unchanged')
            report['backup']=host.capture_backup(drained)
            preservation(drained,host.snapshot());checkpoint('encrypted_backup_verified')
            report['static_preparation']=host.prepare_static()
            checkpoint('static_prepared')
            # Every forward node and its post_migrate metadata share one PG
            # transaction. The exact source FF occurs before its commit; an
            # uncertain commit is reconciled from migration/schema observations.
            host.record('forward-attempt',{'candidate':plan['candidate'],'source_before':BASE,'attempts':1,
                'only_unapplied_nodes':list(MIGRATIONS),'metadata_sequence_before':drained['database']['schema']['sequences'],
                'maximum_metadata_sequence_consumption':{'django_migrations_id_seq':5,'django_content_type_id_seq':2,'auth_permission_id_seq':8},
                'provider_calls':0,'migration_replay':False})
            forward_started=True
            host.migrate_and_forward(plan['candidate']);advanced=host.source_revision()==plan['candidate']
            after_migrations=host.snapshot(before=drained['database'])
            projected_population(drained['database'],after_migrations['database']);schema_complete=True
            preservation(drained,after_migrations)
            report['migration_population']=after_migrations['database'];checkpoint('forward_schema_verified')
            host.install_static(report['static_preparation']);host.configure(recovery=False)
            checkpoint('private_configuration_written')
            for unit in (old.UNITS[2],old.UNITS[0],old.UNITS[1]):host.service('start',unit)
            report['native_readiness']=host.readiness(plan['candidate'])
            current=host.snapshot(before=drained['database']);projected_population(drained['database'],current['database']);preservation(drained,current)
            report['ingress_after']=host.publish_ingress()
            current=host.snapshot(before=drained['database']);projected_population(drained['database'],current['database']);preservation(drained,current,ingress=report['ingress_after'])
            report['normal_origin_structure']=host.normal_structure();report['operation_after']=current
            report['complete']=True;checkpoint('installation_complete')
    except BaseException as error:
        report['complete']=False;report['failure_kind']=type(error).__name__
        report['reason']=str(error) if isinstance(error,Refusal) else 'word_delivery_dependency_failure'
        report['stopped']=stopped;report['source_advance_acknowledged']=advanced;report['forward_attempt_started']=forward_started
        # Preserve the original failure before any narrowly scoped recovery.
        try:host.record('first-failure',report)
        except BaseException:report['first_failure_record_write_failed']=True
        if stopped:
            try:
                with host.hold(recovering=True):
                    host.require_stop_for_recovery()
                    actual=host.source_revision()
                    report['observed_source_on_failure']=actual
                    # No rollback to ancestor source or migration replay. A
                    # current new source must have a verified complete schema.
                    if actual==plan['candidate'] and not schema_complete:
                        observed=host.snapshot(before=before['database'])
                        try:projected_population(before['database'],observed['database']);schema_complete=True
                        except Refusal:
                            # Re-execution is allowed only after proving that the
                            # failed transaction left the complete original DB.
                            # A partial/unknown schema cannot enter this path.
                            report['original_database_reconciliation']=original_population(before['database'],observed['database'],allow_metadata_consumption=forward_started)
                            preservation(before,observed)
                            report['forward_reconciliation']=host.reconcile_forward(before,observed)
                            reconciled_sequence_before=observed['database']['schema']['sequences']
                            observed=host.snapshot(before=before['database'])
                            projected_population(before['database'],observed['database'],
                                metadata_sequence_before=reconciled_sequence_before);schema_complete=True
                            preservation(before,observed)
                    if actual==BASE:
                        observed=host.snapshot(before=before['database'])
                        report['original_database_reconciliation']=original_population(before['database'],observed['database'],allow_metadata_consumption=forward_started)
                        preservation(before,observed)
                    require(actual==BASE or (actual==plan['candidate'] and schema_complete),'recovery_source_schema_coherence')
                    report['recovery']=host.recover(report.get('static_preparation'),actual)
            except BaseException as recovery_error:
                report['recovery']={'complete':False,'failure_kind':type(recovery_error).__name__,
                    'reason':str(recovery_error) if isinstance(recovery_error,Refusal) else 'word_delivery_recovery_dependency'}
        try:host.record('failed',report)
        except BaseException:report['failure_record_write_failed']=True
        raise Refusal('word_delivery_installation_failed') from None
    return report


class NativeHost:
    """Trusted fixed target adapter; no caller-selected unit, DB or root path."""
    def __init__(self,plan,directory):
        self.plan=plan;self.directory=Path(directory);self.deadline=time.monotonic()+OUTER_SECONDS
        self.exclusion,self.backup,self.environment,self.managed,self.storage=old.modules()
        self.native=old.Host(self.managed);self.inside=False
        self.original=protected(APP/'.env',65536)
        self.cipher=self.backup.key_at(old.KEY)
        self.ingress_before,self.ingress_metadata=normal.NativeHost.ingress(self)
        self.ingress_candidate=normal.render_ingress(self.ingress_before,(SOURCE/normal.TEMPLATE).read_bytes())
        self.exclusion.bind_runtime(RUNTIME)

    def check_hold(self):
        require(self.inside and time.monotonic()<self.deadline,'same_bounded_exclusion')
        holder=self.exclusion.holder()
        require(holder and holder.get('pid')==os.getpid(),'publication_holder_identity')

    @contextmanager
    def hold(self,recovering=False):
        require(not self.inside,'non_nested_exclusion')
        with old.operation_locks(),self.exclusion.hold('word-milestone-delivery:'+self.plan['candidate'][:12]):
            self.inside=True
            try:self.check_hold();yield
            finally:self.inside=False

    def space(self,phase):return admission_space(phase)
    def record(self,stage,value):write_new(self.directory/(stage+'.json'),encode(value))
    def source_revision(self):return old.git(ROOT,'rev-parse','HEAD').strip().decode()
    def check_plan(self,plan):
        require(QUALIFIED,'finished_diff_qualification_required')
        require(source_pins(plan['candidate'])==plan['source_sha256'],'candidate_source_pin_drift')
        migration_model_metadata()
        require(sha(self.original)==plan['environment_before_sha256']
            and self.ingress_metadata==plan['ingress_before_metadata'],'prospective_inputs_drift')
        require(self.plan['static_source_sha256']=={k:sha(old.public_source(v)) for k,v in self.static_sources().items()},'static_source_pin_drift')
        require((SOURCE/DECL).read_bytes()==old.git(SOURCE,'show',plan['candidate']+':'+DECL),'declaration_source_drift')
        declared=os.environ.get('RULED_MUTATION_DECLARATION','')
        require(Path(declared).name==Path(DECL).name and re.fullmatch('[a-f0-9]{40}',os.environ.get('RULED_MUTATION_DECL_COMMIT','')),'ruled_mutation_door')
        declaration_commit=os.environ['RULED_MUTATION_DECL_COMMIT']
        require(old.git(SOURCE,'show',declaration_commit+':'+DECL)==(SOURCE/DECL).read_bytes(),'committed_declaration_identity')
        write_new(self.directory/'environment-before.fernet',self.cipher.encrypt(self.original))
        write_new(self.directory/'environment-after.fernet',self.cipher.encrypt(render_environment(self.original,plan['candidate'])))
        write_new(self.directory/'ingress-before.fernet',self.cipher.encrypt(self.ingress_before))

    def service(self,action,unit):self.check_hold();self.native.service(action,unit)
    def require_stopped(self):
        require(all(self.native.state(unit).get('ActiveState')=='inactive' and self.native.state(unit).get('MainPID')=='0' for unit in old.UNITS),'three_units_drained')
    def require_stop_for_recovery(self):
        for unit in old.UNITS:self.service('stop',unit)
        self.require_stopped()
    def native_admission(self,before):
        require(self.source_revision()==BASE,'native_release_before')
        require(set(before['database']['tables'])==old.TABLES,'native_original_table_population')
        require(before['database']['postgresql_server_version_num']==SCHEMA_CONTRACT['postgresql_server_version_num'],
            'native_canonical_schema_engine_version')
        require(before['database']['applied_core_migrations'][-1:] == ['0018_servicehealth']
            and not set(before['database']['applied_core_migrations'])&set(MIGRATIONS),'native_original_migration_state')
        require(not any(row[2]=='f' for row in before['database']['schema']['default_acl']),
            'native_source_default_function_acl')
        old.service_boundary(self.native,self.storage,BASE)
        for unit in old.OPERATIONS:
            state=self.native.state(unit)
            require(state.get('ActiveState') in ('inactive','failed') and state.get('MainPID')=='0','operations_not_active')
        self.no_pending_work()

    def database(self,files,before=None):
        import psycopg
        from psycopg import sql
        opts=self.backup.source_options(APP,old.ROLES)
        with psycopg.connect(**opts,autocommit=True) as connection:
            connection.execute("SET timezone='UTC'");connection.execute("SET datestyle='ISO, MDY'")
            connection.execute("SET statement_timeout='90s'")
            connection.execute('BEGIN ISOLATION LEVEL REPEATABLE READ READ ONLY')
            query=lambda statement:connection.execute(statement).fetchall()
            def copied(statement):
                digest=hashlib.sha256()
                with connection.cursor().copy(statement) as stream:
                    for chunk in stream:digest.update(chunk)
                return digest.hexdigest()
            tables={};all_rows=self.backup.fingerprint(query,copied)
            primary=self.backup.table_queries(query)
            for name,fingerprint in all_rows.items():
                columns=query(sql.SQL("SELECT column_name,data_type,is_nullable,column_default,character_maximum_length FROM information_schema.columns WHERE table_schema='public' AND table_name={} ORDER BY ordinal_position").format(sql.Literal(name)).as_string())
                original=before['tables'].get(name) if before else None
                old_columns=original['old_columns'] if original else columns
                names=[row[0] for row in old_columns]
                old_definition=[row for row in columns if row[0] in names]
                statement=sql.SQL('SELECT {} FROM public.{}').format(sql.SQL(',').join(map(sql.Identifier,names)),sql.Identifier(name))
                if original and name in {'auth_permission','django_content_type','django_migrations'}:
                    statement+=sql.SQL(' WHERE id IN ({})').format(sql.SQL(',').join(map(sql.Literal,original['ids']))) if original['ids'] else sql.SQL(' WHERE false')
                statement+=sql.SQL(' ORDER BY {}').format(sql.SQL(',').join(map(sql.Identifier,primary[name])))
                row={'rows':fingerprint['rows'],'sha256':fingerprint['sha256'],'columns':[row[0] for row in columns],
                    'old_columns':old_definition,'old_rows':copied('COPY ('+statement.as_string()+') TO STDOUT'),
                    'owner_acl':query(sql.SQL("SELECT pg_get_userbyid(relowner),relacl::text,relrowsecurity,relforcerowsecurity,relkind FROM pg_class WHERE oid={}::regclass").format(sql.Literal('public.'+name)).as_string())}
                row['definitions']=[list(value) for value in query(sql.SQL("SELECT a.attname,format_type(a.atttypid,a.atttypmod),a.attnotnull,pg_get_expr(d.adbin,d.adrelid),a.attidentity::text,a.attgenerated::text,(a.attcollation=0 OR a.attcollation=t.typcollation) FROM pg_attribute a JOIN pg_class c ON c.oid=a.attrelid JOIN pg_namespace n ON n.oid=c.relnamespace JOIN pg_type t ON t.oid=a.atttypid LEFT JOIN pg_attrdef d ON d.adrelid=a.attrelid AND d.adnum=a.attnum WHERE n.nspname='public' AND c.relname={} AND a.attnum>0 AND NOT a.attisdropped ORDER BY a.attnum").format(sql.Literal(name)).as_string())]
                row['privileges']=query(sql.SQL("SELECT DISTINCT pg_get_userbyid(a.grantor),CASE WHEN a.grantee=0 THEN 'PUBLIC' ELSE pg_get_userbyid(a.grantee) END,a.privilege_type,a.is_grantable FROM pg_class c CROSS JOIN LATERAL aclexplode(COALESCE(c.relacl,acldefault('r',c.relowner))) a WHERE c.oid={}::regclass ORDER BY 1,2,3,4").format(sql.Literal('public.'+name)).as_string())
                if name in {'auth_permission','django_content_type','django_migrations'}:
                    row['ids']=original['ids'] if original else [v[0] for v in query(sql.SQL('SELECT id FROM public.{} ORDER BY id').format(sql.Identifier(name)).as_string())]
                tables[name]=row
            invariants=self.backup.invariant_counts(query)
            references={}
            for _,statement in self.backup.FILE_QUERIES:
                for relative,expected in query(statement):
                    if relative:
                        require(relative in files and (not expected or files[relative]['sha256']==expected),'referenced_file_integrity')
                        references[relative]=files[relative]['sha256']
            old.reaper_admission(query,files)
            self._pending(query)
            result={'tables':tables,'invariants':invariants,'referenced_files':references,
                    'schema':self.schema(query),
                    'postgresql_server_version_num':query('SHOW server_version_num')[0][0],
                    'applied_core_migrations':[name for name, in query("SELECT name FROM django_migrations WHERE app='core' ORDER BY name")]}
            result['expected_new_table_privileges']=query("WITH owner AS (SELECT oid FROM pg_roles WHERE rolname='quillmd_owner'), expected AS (SELECT COALESCE((SELECT defaclacl FROM pg_default_acl d WHERE d.defaclrole=o.oid AND d.defaclnamespace=0 AND d.defaclobjtype='r'),acldefault('r',o.oid)) || COALESCE((SELECT defaclacl FROM pg_default_acl d JOIN pg_namespace n ON n.oid=d.defaclnamespace WHERE d.defaclrole=o.oid AND n.nspname='public' AND d.defaclobjtype='r'),'{}'::aclitem[]) AS acl FROM owner o) SELECT DISTINCT pg_get_userbyid(a.grantor),CASE WHEN a.grantee=0 THEN 'PUBLIC' ELSE pg_get_userbyid(a.grantee) END,a.privilege_type,a.is_grantable FROM expected e CROSS JOIN LATERAL aclexplode(e.acl) a ORDER BY 1,2,3,4")
            if before:
                def added(name,statement):
                    ids=before['tables'][name]['ids']
                    return query(statement+(' AND id NOT IN ('+','.join(str(int(v)) for v in ids)+')' if ids else '')+' ORDER BY id')
                result['added_migrations']=added('django_migrations',"SELECT app,name FROM django_migrations WHERE true")
                result['added_content_types']=added('django_content_type',"SELECT app_label,model FROM django_content_type WHERE true")
                ids=before['tables']['auth_permission']['ids']
                result['added_permissions']=query('SELECT c.model,p.codename FROM auth_permission p JOIN django_content_type c ON c.id=p.content_type_id WHERE '+('p.id NOT IN ('+','.join(str(int(v)) for v in ids)+')' if ids else 'true')+' ORDER BY p.id')
                functions,triggers=migration_sql_metadata()
                result['expected_functions']=functions;result['expected_triggers']=triggers
            connection.execute('COMMIT')
            return result

    def schema(self,query):
        result={}
        functions=query("SELECT p.proname,p.prosrc,pg_get_userbyid(p.proowner),p.proacl::text,p.prosecdef,p.proconfig::text,l.lanname,pg_get_function_identity_arguments(p.oid),pg_get_function_result(p.oid) FROM pg_proc p JOIN pg_namespace n ON n.oid=p.pronamespace JOIN pg_language l ON l.oid=p.prolang WHERE n.nspname='public' AND p.prokind='f' ORDER BY p.proname")
        require(len(functions)==len({row[0] for row in functions}),'unambiguous_function_population')
        result['functions']={name:dict(zip(('body','owner','acl','security_definer','configuration','language','arguments','returns'),values)) for name,*values in functions}
        trigger_rows=query("SELECT c.relname,t.tgname,pg_get_triggerdef(t.oid),t.tgenabled,t.tgtype,pn.nspname,p.proname,encode(t.tgargs,'hex'),pg_get_expr(t.tgqual,t.tgrelid),t.tgattr::text,t.tgconstraint,t.tgdeferrable,t.tginitdeferred FROM pg_trigger t JOIN pg_class c ON c.oid=t.tgrelid JOIN pg_namespace n ON n.oid=c.relnamespace JOIN pg_proc p ON p.oid=t.tgfoid JOIN pg_namespace pn ON pn.oid=p.pronamespace WHERE n.nspname='public' AND NOT t.tgisinternal ORDER BY 1,2")
        result['triggers']={table+':'+name:dict(zip(('definition','enabled','type','function_schema','function','arguments_hex','when','columns','constraint','deferrable','initially_deferred'),values)) for table,name,*values in trigger_rows}
        result['constraints']={table+':'+name:dict(zip(('definition','validated','type','deferrable','initially_deferred'),values)) for table,name,*values in query("SELECT c.conrelid::regclass::text,c.conname,pg_get_constraintdef(c.oid),c.convalidated,c.contype,c.condeferrable,c.condeferred FROM pg_constraint c JOIN pg_namespace n ON n.oid=c.connamespace WHERE n.nspname='public' ORDER BY 1,2")}
        result['indexes']={table+':'+name:dict(zip(('definition','unique','primary','valid','ready'),values)) for table,name,*values in query("SELECT c.relname,i.relname,pg_get_indexdef(x.indexrelid),x.indisunique,x.indisprimary,x.indisvalid,x.indisready FROM pg_index x JOIN pg_class c ON c.oid=x.indrelid JOIN pg_class i ON i.oid=x.indexrelid JOIN pg_namespace n ON n.oid=c.relnamespace WHERE n.nspname='public' ORDER BY 1,2")}
        result['policies']=query("SELECT * FROM pg_policies WHERE schemaname='public' ORDER BY tablename,policyname")
        result['default_acl']=query("SELECT pg_get_userbyid(d.defaclrole),COALESCE(n.nspname,''),d.defaclobjtype,d.defaclacl::text FROM pg_default_acl d LEFT JOIN pg_namespace n ON n.oid=d.defaclnamespace WHERE d.defaclnamespace=0 OR n.nspname='public' ORDER BY 1,2,3")
        result['sequence_metadata']=query("SELECT s.sequencename,s.sequenceowner,s.data_type,s.start_value,s.min_value,s.max_value,s.increment_by,s.cycle,s.cache_size,c.relacl::text FROM pg_sequences s JOIN pg_class c ON c.relname=s.sequencename JOIN pg_namespace n ON n.oid=c.relnamespace AND n.nspname=s.schemaname WHERE s.schemaname='public' ORDER BY s.sequencename")
        from psycopg import sql
        result['sequences']={}
        for name, in query("SELECT sequencename FROM pg_sequences WHERE schemaname='public' ORDER BY sequencename"):
            result['sequences'][name]=query(sql.SQL('SELECT last_value,is_called FROM public.{}').format(sql.Identifier(name)).as_string())
        return result

    def _pending(self,query):
        require(query("SELECT count(*) FROM core_job WHERE state IN ('queued','running','reconciliation')")[0][0]==0
            and query("SELECT count(*) FROM core_reservation WHERE state='held'")[0][0]==0,'native_pending_or_unknown_work')
        tables={row[0] for row in query("SELECT tablename FROM pg_tables WHERE schemaname='public'")}
        if 'core_templatepreparation' in tables:
            require(query("SELECT count(*) FROM core_templatepreparation WHERE state IN ('queued','inventory','proposer','checker')")[0][0]==0,'native_pending_preparation')
            require(query("SELECT count(*) FROM core_preparationreceipt WHERE state IN ('reserved','sending','unknown')")[0][0]==0,'native_unknown_preparation_receipt')
    def no_pending_work(self):self.database(self.storage.inventory(Path('/var/lib/quillmd/files')))

    def snapshot(self,before=None):
        self.check_hold();files=self.storage.inventory(Path('/var/lib/quillmd/files'))
        configuration=self.native.configuration()
        foreign=[Path(name).name for name,row in configuration.items() if name.startswith('/etc/systemd/system/')
            and name.endswith('.service') and 'sha256' in row and not Path(name).name.startswith('quillmd-')]
        require(len(foreign)<=128 and len(foreign)==len(set(foreign)),'bounded_foreign_service_population')
        states={}
        for unit in sorted(foreign):
            raw=old.command(['systemctl','show',unit,'--property=ActiveState,SubState,MainPID,InvocationID,FragmentPath,DropInPaths,UnitFileState,WorkingDirectory,ExecMainStartTimestampMonotonic'],timeout=10)
            states[unit]=dict(line.split('=',1) for line in raw.decode().splitlines() if '=' in line)
        result={'files':files,'mail':self.storage.inventory(Path('/var/lib/quillmd/mail')),
                'configuration':configuration,'foreign_services':states,'database':self.database(files,before)}
        self.check_hold();return result

    def capture_backup(self,before):
        destination=ROOT/'backups/quillmd-word-native-delivery-20261008'
        self.backup.private_dir(destination,create=True)
        retained=old.inventory(destination)
        write_new(self.directory/'fresh-backup-attempt.json',encode({'attempts':1,'provider_calls':0,'before_sha256':sha(encode(before))}))
        output=StringIO()
        with redirect_stdout(output):self.backup.backup(SimpleNamespace(source=APP,output=destination,key_file=old.KEY,database_credentials=old.ROLES))
        receipt=json.loads(output.getvalue());require(receipt.get('complete') is True,'fresh_backup_complete')
        path=Path(receipt['backup_directory']);require(path.parent==destination and re.fullmatch(r'[0-9]{8}T[0-9]{6}Z-[a-f0-9]{8}',path.name),'fresh_backup_destination')
        loaded,manifest=self.backup.load_backup(path,self.cipher)
        require(loaded==path and manifest.get('run_id')==path.name
            and receipt.get('run_id')==path.name
            and sha(protected(path/'manifest.json.fernet',8*1024**2))==receipt.get('manifest_cipher_sha256'),
            'fresh_backup_manifest_identity')
        container=self.backup.inspect_container('quillmd-fresh-postgres')
        require(container.get('Id')==manifest.get('container_id') and container.get('Image')==manifest.get('image_id')
            and container.get('State',{}).get('Running') is True
            and container.get('HostConfig',{}).get('PortBindings')=={'5432/tcp':[{'HostIp':'127.0.0.1','HostPort':'55438'}]},
            'fresh_backup_live_database_identity')
        require(manifest['source_commit']==BASE and manifest['database']=='quillmd_fresh'
            and manifest['tables']=={name:{'rows':row['rows'],'sha256':row['sha256']} for name,row in before['database']['tables'].items()}
            and manifest['invariants']==before['database']['invariants'],'fresh_backup_population')
        require({item['path']:item['sha256'] for item in manifest['files']}==before['database']['referenced_files'],'fresh_backup_references')
        self.backup.decrypt_checked(path/'database.dump.fernet',manifest['dump'],self.cipher)
        for item in manifest['files']:
            require(before['files'][item['path']]['sha256']==item['sha256'] and before['files'][item['path']]['size']==item['size'],
                'fresh_backup_reference_size')
            self.backup.decrypt_checked(path/item['object'],item,self.cipher)
        current=old.inventory(destination);require(all(current.get(name)==row for name,row in retained.items()),'previous_backup_preservation')
        require(sha(protected(old.RESTORE))==old.RESTORE_SHA,'independent_restore_evidence')
        receipt.update(authenticated_dump_and_objects=True,provider_calls=0);return receipt

    def static_sources(self):
        result=old.static_sources()
        result.update({name:SOURCE/'rebuild/static'/name for name in STATIC_INPUTS-set(result)})
        return result

    def static_expected(self,inputs):
        expected={name:old.public_source(path) for name,path in inputs.items()}
        font='fonts/dm-sans.'+hashlib.md5(expected['fonts/dm-sans.ttf']).hexdigest()[:12]+'.ttf'
        expected['app.css']=expected['app.css'].replace(b'fonts/dm-sans.ttf',font.encode())
        source='vendor/docx-preview/docx-preview.min.js.map'
        compiled=str(PurePosixPath(source).with_suffix(''))+'.'+hashlib.md5(expected[source]).hexdigest()[:12]+'.map'
        expected['vendor/docx-preview/docx-preview.min.js']=expected['vendor/docx-preview/docx-preview.min.js'].replace(b'sourceMappingURL=docx-preview.min.js.map',('sourceMappingURL='+PurePosixPath(compiled).name).encode())
        return expected

    def validate_static(self,stage):
        primitives=old.static_primitives();rows=primitives.static_inventory(stage);inputs=self.static_sources()
        require({name:sha(old.public_source(path)) for name,path in inputs.items()}==self.plan['static_source_sha256'],'static_source_pins')
        manifest=json.loads((stage/'staticfiles.json').read_bytes())
        require(set(manifest)=={'paths','version','hash'} and manifest['version']=='1.1'
            and set(manifest['paths'])==STATIC_INPUTS,'finite_static_manifest')
        require(manifest['hash']==hashlib.md5(json.dumps(sorted(manifest['paths'].items())).encode()).hexdigest()[:12],'static_manifest_hash')
        expected=self.static_expected(inputs);allowed={'staticfiles.json'};directories={'.'}
        for name,path in inputs.items():
            raw=old.public_source(path);compiled_bytes=expected[name]
            original=PurePosixPath(name);compiled=str(original.with_suffix(''))+'.'+hashlib.md5(compiled_bytes).hexdigest()[:12]+original.suffix
            require(manifest['paths'][name]==compiled and (stage/name).read_bytes()==raw
                and (stage/compiled).read_bytes()==compiled_bytes,'static_compilation_bytes')
            for filename,content in ((name,raw),(compiled,compiled_bytes)):
                allowed.update((filename,filename+'.gz',filename+'.br'));directories.update(str(p) for p in PurePosixPath(filename).parents)
                if filename+'.gz' in rows:require(gzip.decompress((stage/(filename+'.gz')).read_bytes())==content,'static_gzip_bytes')
                if filename+'.br' in rows:
                    import brotli
                    require(brotli.decompress((stage/(filename+'.br')).read_bytes())==content,'static_brotli_bytes')
        require(all(name in (directories if row['kind']=='directory' else allowed) for name,row in rows.items()),'undeclared_static_output')
        return rows

    def prepare_static(self):
        primitives=old.static_primitives();before=primitives.static_inventory(APP/'staticfiles')
        require(sha(encode(before))==self.plan['static_before_inventory_sha256'],'static_original_drift')
        stage=self.directory/'static-stage';primitives.create_static_stage(stage)
        code=('from django.conf import settings;settings.configure(SECRET_KEY="public-static-only",'
            'INSTALLED_APPS=["django.contrib.staticfiles","django_otp","django_otp.plugins.otp_totp"],STATIC_URL="/static/",'
            'STATIC_ROOT='+repr(str(stage))+',STATICFILES_DIRS=['+repr(str(SOURCE/'rebuild/static'))+'],'
            'STORAGES={"staticfiles":{"BACKEND":"quillmd.static_storage.PublicCompressedManifestStaticFilesStorage",'
            '"OPTIONS":{"file_permissions_mode":420,"directory_permissions_mode":493}}});'
            'import django;django.setup();from django.core.management import call_command;call_command("collectstatic",interactive=False,verbosity=0)')
        result=subprocess.run([str(APP/'.venv/bin/python'),'-B','-c',code],cwd=SOURCE/'rebuild',
            env={'PATH':'/usr/bin:/bin','LANG':'C.UTF-8','PYTHONDONTWRITEBYTECODE':'1'},capture_output=True,timeout=120)
        require(result.returncode==0,'isolated_static_collection')
        staged=self.validate_static(stage);primitives.retain_static(APP/'staticfiles',self.directory/'public-assets-before.tar',before)
        return {'before':before,'staged':staged,'stage':str(stage),'archive_sha256':sha(protected(self.directory/'public-assets-before.tar',64*1024**2))}

    def install_static(self,preparation,reconciling=False):
        primitives=old.static_primitives();root=APP/'staticfiles';stage=Path(preparation['stage'])
        current=primitives.static_inventory(root)
        require(self.validate_static(stage)==preparation['staged'],'static_stage_install_race')
        before=preparation['before'];staged=preparation['staged'];aliases=set(STATIC_INPUTS)|{'staticfiles.json'}
        aliases|={name+suffix for name in STATIC_INPUTS for suffix in ('.gz','.br')}
        if not reconciling:require(current==before,'static_install_race')
        else:
            require(set(before)<=set(current)<=set(before)|set(staged),'static_reconciliation_population')
            for name,row in current.items():
                if name in before and name not in aliases:require(row==before[name],'static_reconciliation_immutable_drift')
                elif row['kind']=='file':
                    require(any(all(row.get(key)==known.get(key) for key in ('kind','mode','size','sha256'))
                        for known in (before.get(name,{}),staged.get(name,{}))),'static_reconciliation_unknown_bytes')
        directories=[name for name,row in staged.items() if row['kind']=='directory' and name not in current]
        for name in sorted(directories,key=lambda p:len(PurePosixPath(p).parts)):primitives.create_static_stage(root/name)
        for name,row in sorted(staged.items(),key=lambda item:(item[0]=='staticfiles.json',item[0])):
            if row['kind']=='directory':continue
            prior=current.get(name)
            if prior and all(prior.get(k)==row.get(k) for k in ('kind','mode','size','sha256')):continue
            require(not prior or name in aliases,'immutable_static_replacement')
            target=root/name;require(target.parent.resolve(strict=True)==target.parent,'static_parent_identity')
            raw=(stage/name).read_bytes();require(sha(raw)==row['sha256'],'static_staged_bytes')
            temporary=target.with_name('.word-delivery-'+uuid.uuid4().hex)
            fd=os.open(temporary,os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW,0o644)
            try:
                with os.fdopen(fd,'wb') as stream:os.fchmod(stream.fileno(),0o644);stream.write(raw);stream.flush();os.fsync(stream.fileno())
                if prior:
                    require(primitives.static_inventory(root)[name]==prior,'static_target_race');os.replace(temporary,target)
                else:os.link(temporary,target,follow_symlinks=False);temporary.unlink()
            finally:
                if temporary.exists():temporary.unlink()
        after=primitives.static_inventory(root)
        require(set(after)==set(before)|set(staged),'static_output_population')
        require(all(after[name]==row for name,row in before.items() if name not in aliases),'old_immutable_static_preservation')
        require(all(all(after[name].get(key)==row.get(key) for key in ('kind','mode','size','sha256'))
            for name,row in staged.items() if row['kind']=='file'),'complete_candidate_static_bytes')
        return after

    def migrate_and_forward(self,candidate,*,source_already_forward=False):
        self.check_hold();roles=json.loads(protected(old.ROLES,16384))
        require(roles['database']=='quillmd_fresh' and roles['container_id']==self.backup.inspect_container('quillmd-fresh-postgres')['Id'],'retained_migrator_database_identity')
        role=roles['roles']['migrator'];values=dotenv_values(stream=StringIO(self.original.decode()),interpolate=False)
        environment={k:v for k,v in values.items() if isinstance(v,str)}
        environment.update(PATH='/usr/bin:/bin',LANG='C.UTF-8',PYTHONDONTWRITEBYTECODE='1',QUILLMD_ENV_MANAGED='1',
            QUILLMD_DB_NAME='quillmd_fresh',QUILLMD_DB_USER=role['name'],QUILLMD_DB_PASSWORD=role['password'],
            QUILLMD_DB_HOST='127.0.0.1',QUILLMD_DB_PORT='55438',PGOPTIONS='-c role=quillmd_owner')
        code='''import os,sys,subprocess
os.environ['DJANGO_SETTINGS_MODULE']='quillmd.settings'
import django;django.setup()
from django.db import connection,transaction
from django.db.migrations.executor import MigrationExecutor
from django.core.management.sql import emit_post_migrate_signal
candidate=CANDIDATE;allowed=ALLOWED;forwarded=FORWARDED
expected_source=candidate if forwarded else BASE_SOURCE
assert subprocess.check_output(['/usr/bin/git','-C','/opt/meddoc-pro','rev-parse','HEAD']).strip().decode()==expected_source
assert subprocess.check_output(['/usr/bin/git','-C','/opt/meddoc-pro','branch','--show-current']).strip()==b'main'
assert not subprocess.check_output(['/usr/bin/git','-C','/opt/meddoc-pro','status','--porcelain','--untracked-files=no']).strip()
executor=MigrationExecutor(connection)
target=[('core',allowed[-1])]
plan=executor.migration_plan(target)
assert [(m.app_label,m.name,backwards) for m,backwards in plan]==[('core',name,False) for name in allowed]
with transaction.atomic():
 executor.migrate(target)
 emit_post_migrate_signal(0,False,'default',apps=executor.loader.project_state(target).apps)
 if not forwarded:
  result=subprocess.run(['/usr/bin/git','-C','/opt/meddoc-pro','merge','--ff-only',candidate],capture_output=True,timeout=45,umask=0o022)
  assert result.returncode==0
 assert subprocess.check_output(['/usr/bin/git','-C','/opt/meddoc-pro','rev-parse','HEAD']).strip().decode()==candidate
print('forward_transaction_committed')
'''.replace('CANDIDATE',repr(candidate)).replace('ALLOWED',repr(list(MIGRATIONS))).replace('FORWARDED',repr(source_already_forward)).replace('BASE_SOURCE',repr(BASE))
        result=subprocess.run([str(APP/'.venv/bin/python'),'-B','-c',code],cwd=SOURCE/'rebuild',env=environment,capture_output=True,timeout=240)
        require(result.returncode==0 and result.stdout.strip()==b'forward_transaction_committed','forward_transaction_result')
        from .private_availability_recovery import source_readability
        source_readability(ROOT)
        require(self.source_revision()==candidate,'forward_source_identity')

    def reconcile_forward(self,before,observed):
        """One forward completion after an observed full DB rollback, never replay."""
        self.check_hold();original_proof=original_population(before['database'],observed['database'],allow_metadata_consumption=True)
        attempted=json.loads(protected(self.directory/'forward-attempt.json',4*1024**2))
        require(attempted.get('candidate')==self.plan['candidate'] and attempted.get('source_before')==BASE
            and attempted.get('attempts')==1 and attempted.get('only_unapplied_nodes')==list(MIGRATIONS)
            and attempted.get('metadata_sequence_before')==json.loads(encode(before['database']['schema']['sequences'])),
            'reconciliation_prior_forward_attempt')
        require(self.source_revision()==self.plan['candidate'],'reconciliation_exact_candidate_source')
        require(old.git(ROOT,'branch','--show-current').strip()==b'main'
            and not old.git(ROOT,'status','--porcelain','--untracked-files=no').strip(),'reconciliation_clean_main')
        for relative,expected in self.plan['source_sha256'].items():
            require(sha(old.public_source(ROOT/relative))==expected,'reconciliation_current_source_pins')
        write_new(self.directory/'forward-reconciliation-attempt.json',encode({'attempts':1,
            'source':self.plan['candidate'],'observed_original_database_sha256':sha(encode(observed['database'])),
            'original_database_proof':original_proof,
            'only_unapplied_nodes':list(MIGRATIONS),'provider_calls':0,'migration_replay':False}))
        self.migrate_and_forward(self.plan['candidate'],source_already_forward=True)
        return {'complete':True,'attempts':1,'only_observed_unapplied_nodes':list(MIGRATIONS),
            'retained_original_database_proof':original_proof,
            'migration_replay':False,'source_reset':False,'provider_calls':0}

    def configure(self,recovery=False):
        current=protected(APP/'.env',65536)
        allowed={self.original,render_environment(self.original,self.plan['candidate'])}
        require(current in allowed,'environment_current_known_state')
        self.environment.replace_environment(APP/'.env',current,render_environment(self.original,self.plan['candidate'],recovery=recovery))

    def readiness(self,candidate):
        self.check_hold();units=old.await_service_boundary(self.native,self.storage,candidate)
        import httpx
        health=[]
        for port,surface in ((9130,'doctor'),(9131,'admin')):
            r=httpx.get('http://127.0.0.1:'+str(port)+'/health/',timeout=5);require(r.status_code==200,'native_health_http')
            data=r.json();require(data.get('release')==candidate and data.get('surface')==surface and data.get('data_mode')=='synthetic-only','native_health_contract');health.append(data)
        return {'units':units,'health':health,'actual_provider_model_verified':False}

    def publish_ingress(self):
        self.check_hold()
        # Reuse the unchanged fixed-file root primitive, without constructing or
        # invoking its old release/approval controller. Its helper failure receipt
        # is redirected only to this new operation's protected evidence directory.
        original_managed=self.managed
        class BoundManaged:
            IMAGE=self.managed.IMAGE
            def run_helper(_,argv,**kwargs):
                kwargs['failure_directory']=self.directory
                return original_managed.run_helper(argv,**kwargs)
        self.managed=BoundManaged()
        try:return normal.NativeHost.replace_ingress(self,self.ingress_before,self.ingress_candidate,self.ingress_metadata)
        finally:self.managed=original_managed

    def normal_structure(self):
        self.check_hold();raw,metadata=normal.NativeHost.ingress(self)
        require(raw==self.ingress_candidate and metadata['sha256']==sha(raw),'normal_ingress_installed_bytes')
        # Network/authentication probing is separate: owner/session writes must
        # not masquerade as preservation evidence inside the install interval.
        return {'origin':'https://app.quillmd.com','restricted_grants_only':True,'ingress_sha256':sha(raw),
                'authenticated_doctor_admin_acceptance_required':True,'private_origin_unchanged':'https://app.quillmd.com:9443'}

    def recover(self,preparation,actual):
        self.check_hold()
        if actual==BASE:
            require(protected(APP/'.env',65536)==self.original,'original_environment_preserved')
        else:self.configure(recovery=True)
        raw,metadata=normal.NativeHost.ingress(self)
        if raw!=self.ingress_before:
            require(raw==self.ingress_candidate,'recovery_ingress_known_candidate')
            current_managed=self.managed
            class BoundManaged:
                IMAGE=self.managed.IMAGE
                def run_helper(_,argv,**kwargs):kwargs['failure_directory']=self.directory;return current_managed.run_helper(argv,**kwargs)
            self.managed=BoundManaged()
            try:normal.NativeHost.replace_ingress(self,raw,self.ingress_before,metadata)
            finally:self.managed=current_managed
        if actual==BASE:
            if preparation:self.restore_static(preparation)
        else:
            require(preparation is not None,'recovery_candidate_static_stage_required')
            self.install_static(preparation,reconciling=True)
        for unit in (old.UNITS[2],old.UNITS[0],old.UNITS[1]):self.service('start',unit)
        ready=self.readiness(actual)
        return {'complete':True,'served_revision':actual,'feature_campaign_normal_origin_off':actual!=BASE,'readiness':ready,
                'database_reversed':False,'source_reset':False,'historical_approval_inferred':False}

    def restore_static(self,preparation):
        primitives=old.static_primitives();root=APP/'staticfiles';current=primitives.static_inventory(root)
        archive=protected(self.directory/'public-assets-before.tar',64*1024**2)
        require(sha(archive)==preparation['archive_sha256'],'static_rollback_archive_identity')
        payload={}
        with tarfile.open(fileobj=BytesIO(archive),mode='r:') as source:
            for member in source:
                require(member.name in preparation['before'] and member.isfile() and member.name not in payload,'static_rollback_archive_population')
                data=source.extractfile(member).read(member.size+1)
                require(sha(data)==preparation['before'][member.name]['sha256'],'static_rollback_archive_bytes');payload[member.name]=data
        aliases={'staticfiles.json'}|set(STATIC_INPUTS)|{name+suffix for name in STATIC_INPUTS for suffix in ('.gz','.br')}
        for name,raw in sorted(payload.items(),key=lambda item:(item[0]=='staticfiles.json',item[0])):
            if name not in aliases:require(current[name]==preparation['before'][name],'static_rollback_immutable_drift');continue
            if current[name]['sha256']==sha(raw):continue
            candidate=preparation['staged'].get(name)
            require(candidate and current[name]['sha256']==candidate['sha256'],'static_rollback_alias_known_state')
            target=root/name;temporary=target.with_name('.word-delivery-rollback-'+uuid.uuid4().hex)
            fd=os.open(temporary,os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW,0o644)
            with os.fdopen(fd,'wb') as output:os.fchmod(output.fileno(),0o644);output.write(raw);output.flush();os.fsync(output.fileno())
            require(primitives.static_inventory(root)[name]==current[name],'static_rollback_write_race');os.replace(temporary,target)
        after=primitives.static_inventory(root)
        require(set(after)==set(current),'static_rollback_no_deletions')
        return {'original_manifest_aliases_restored':True,'published_immutable_assets_retained':True}


def prepare_plan(candidate,destination):
    require(QUALIFIED,'finished_diff_qualification_required')
    pins=source_pins(candidate);admission_space('prospective_preflight')
    directory=Path(destination)
    require(directory.is_absolute() and directory.parent==RUNTIME/'ai-word-preparation-20261008'
        and directory.parent.resolve(strict=True)==directory.parent,'new_protected_plan_destination')
    directory.mkdir(mode=0o700)
    provisional={'candidate':candidate}
    host=NativeHost(provisional,directory)
    require(dotenv_values(stream=StringIO(host.original.decode()),interpolate=False).get('QUILLMD_RELEASE_SHA')==BASE,'native_environment_before')
    primitives=old.static_primitives()
    plan={'format':1,'qualified':True,'created_at':datetime.now(timezone.utc).isoformat(),
        'source_before':BASE,'word_base':WORD_BASE,'candidate':candidate,'source_sha256':pins,
        'migration_nodes':list(MIGRATIONS),'environment_before_sha256':sha(host.original),
        'ingress_before_metadata':host.ingress_metadata,'static_before_inventory_sha256':sha(encode(primitives.static_inventory(APP/'staticfiles'))),
        'static_source_sha256':{name:sha(old.public_source(path)) for name,path in host.static_sources().items()},
        'minimum_available_bytes':MINIMUM_SPACE,'campaign':CAMPAIGN,'campaign_scope_sha256':CAMPAIGN_SCOPE,
        'provider_calls':0,'authentication_submissions':0,'historical_deployment_approval_verified':False,'original_baselines_replaced':False}
    validate_plan(plan);write_new(directory/'prospective-plan.json',encode(plan));return plan


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    modes=parser.add_mutually_exclusive_group();modes.add_argument('--prepare',action='store_true');modes.add_argument('--execute',action='store_true')
    parser.add_argument('--candidate');parser.add_argument('--directory');args=parser.parse_args(argv)
    if not(args.prepare or args.execute):
        print(json.dumps({'qualified':QUALIFIED,'installed_state_accessed':False,'execution_performed':False,
            'minimum_available_bytes':MINIMUM_SPACE,'provider_calls':0,'historical_approval_inferred':False}));return 0
    require(QUALIFIED,'finished_diff_qualification_required')
    require(os.getuid()==os.geteuid()==1000,'native_operator_identity')
    if args.prepare:
        plan=prepare_plan(args.candidate,args.directory);print(json.dumps({'prepared':True,'candidate':plan['candidate'],'directory':args.directory,'provider_calls':0}));return 0
    directory=Path(args.directory)
    require(directory.parent==RUNTIME/'ai-word-preparation-20261008'
        and directory.resolve(strict=True)==directory and stat.S_IMODE(directory.stat().st_mode)==0o700,'execution_directory')
    plan=validate_plan(json.loads(protected(directory/'prospective-plan.json',4*1024**2)))
    require(args.candidate in (None,plan['candidate']),'execute_candidate_argument')
    require(source_pins(plan['candidate'])==plan['source_sha256'],'before_installed_access_candidate_pins')
    require(not os.path.lexists(directory/'execution-attempt.json'),'single_execution_attempt')
    write_new(directory/'execution-attempt.json',encode({'plan_sha256':sha(protected(directory/'prospective-plan.json',4*1024**2)),'candidate':plan['candidate'],'attempt':1}))
    result=execute(plan,NativeHost(plan,directory));print(json.dumps({'complete':result['complete'],'candidate':plan['candidate'],'directory':str(directory),'provider_calls':0}));return 0
