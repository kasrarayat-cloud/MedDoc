"""Run selected Django tests with core.billing imported from a scratch copy only."""
import importlib.abc
import importlib.util
from pathlib import Path
import os
import sys

scratch=Path(__file__).resolve().parent
sys.path.insert(0,str(Path.cwd()))
class BillingCopy(importlib.abc.MetaPathFinder):
    def find_spec(self,fullname,path=None,target=None):
        if fullname=='core.billing':
            return importlib.util.spec_from_file_location(fullname,scratch/'billing-copy.py')
sys.meta_path.insert(0,BillingCopy())
os.environ.setdefault('DJANGO_SETTINGS_MODULE','quillmd.settings')
import django
django.setup()
from core import billing
assert Path(billing.__file__).resolve()==scratch/'billing-copy.py'
from django.core.management import call_command
call_command('test',*sys.argv[1:],interactive=False,verbosity=1)
