import os
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'quillmd.settings')
import django
django.setup()
from django.core.management import call_command
from django.test import override_settings
with override_settings(STORAGES={'default':{'BACKEND':'django.core.files.storage.FileSystemStorage'},
                                  'staticfiles':{'BACKEND':'django.contrib.staticfiles.storage.StaticFilesStorage'}}):
    call_command('test', 'core.tests.test_production_operations_status',
                 'core.tests.test_publication_exclusion',
                 'core.tests.test_admin_console.PublishedOperationsStatus',
                 'core.tests.test_admin_console.PublishedOperationsCarryTheirStaleness',
                 interactive=False, verbosity=1)
