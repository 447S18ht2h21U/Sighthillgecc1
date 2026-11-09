"""Unregistered, default-deny VERIDIAN tax-entry role boundary."""
from rest_framework.exceptions import PermissionDenied
from .models import Role, User

def require_tax_entry_preparer(actor):
    identifier = getattr(actor, "pk", None)
    if identifier is None:
        raise PermissionDenied("An active Comptroller account is required.")
    current = User.objects.filter(pk=identifier, is_active=True).first()
    if current is None or current.role != Role.COMPTROLLER:
        raise PermissionDenied("Only an active Comptroller may prepare a tax draft.")
    return current

def require_tax_entry_action(actor, action):
    if action != "PREPARE_DRAFT":
        raise PermissionDenied("Tax verification and operational actions are disabled.")
    return require_tax_entry_preparer(actor)
