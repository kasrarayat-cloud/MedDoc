"""Make an existing, verified, MFA-enrolled account an administrator, under a committed declaration approved by
a second administrator, through the ruled-mutation door. See core.admin_authority."""
from core import admin_authority
from ._admin_change import AdminChangeCommand


class Command(AdminChangeCommand):
    help = __doc__
    operation = admin_authority.ELEVATE
