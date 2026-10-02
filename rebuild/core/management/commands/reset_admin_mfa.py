"""Remove an administrator's authenticators and sign them out everywhere, under a committed declaration approved by
a second administrator, through the ruled-mutation door. Creates no new key: the administrator enrols one at their
next password sign-in on the administration surface, within the re-enrolment window. See core.admin_authority."""
from core import admin_authority
from ._admin_change import AdminChangeCommand


class Command(AdminChangeCommand):
    help = __doc__
    operation = admin_authority.RESET
