"""Descriptive VERIDIAN access catalog.

This module defines possible permissions; it grants none.
Existing backend authorization remains authoritative until
a separately tested and approved integration is introduced.
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class PermissionDefinition:
    code: str
    label: str
    category: str
    action: str
    project_scoped: bool = False
    sensitive: bool = False
    independent_approval: bool = False


def permission(code, label, category, action, *,
               project_scoped=False, sensitive=False,
               independent_approval=False):
    return PermissionDefinition(
        code=code,
        label=label,
        category=category,
        action=action,
        project_scoped=project_scoped,
        sensitive=sensitive,
        independent_approval=independent_approval,
    )


PERMISSIONS = (
    permission("dashboard.view", "View Project Status Dashboard",
               "dashboard", "view", project_scoped=True),

    permission("customers.view", "View customer directory",
               "customers", "view", project_scoped=True),
    permission("customers.manage", "Manage customer records",
               "customers", "manage", project_scoped=True),

    permission("documents.sow.view", "View signed Project SOW Agreement",
               "documents", "view", project_scoped=True),
    permission("documents.completion_financed.view",
               "View signed financed completion certificate",
               "documents", "view", project_scoped=True),
    permission("documents.completion_non_financed.view",
               "View signed non-financed completion certificate",
               "documents", "view", project_scoped=True),
    permission("documents.invoice.view", "View signed invoice",
               "documents", "view", project_scoped=True),
    permission("documents.satisfaction_survey.view",
               "View Customer Satisfaction Survey",
               "documents", "view", project_scoped=True),

    permission("marketing_reports.view", "View marketing reports",
               "marketing", "view", sensitive=True),

    permission("technician_assignments.view",
               "View technician assignment directory",
               "technicians", "view", project_scoped=True),
    permission("technician_assignments.create",
               "Create technician assignments",
               "technicians", "create", project_scoped=True,
               sensitive=True, independent_approval=True),
    permission("technician_assignments.end",
               "End technician assignments",
               "technicians", "end", project_scoped=True,
               sensitive=True, independent_approval=True),

    permission("compensation.own.view",
               "View own payroll or contractor compensation by period",
               "compensation", "view", sensitive=True),
    permission("compensation.all.view",
               "View all payroll or contractor compensation by period",
               "compensation", "view", sensitive=True,
               independent_approval=True),

    permission("payroll_payments.approve",
               "Approve payroll payments",
               "payroll", "approve", sensitive=True,
               independent_approval=True),

    permission("financials.operations.view",
               "View Statement of Operations",
               "financials", "view", sensitive=True,
               independent_approval=True),
    permission("financials.cashflow.view",
               "View Cashflow Statement",
               "financials", "view", sensitive=True,
               independent_approval=True),
    permission("financials.balance_sheet.view",
               "View Balance Sheet",
               "financials", "view", sensitive=True,
               independent_approval=True),

    permission("users.manage", "Manage user accounts",
               "administration", "manage", sensitive=True,
               independent_approval=True),
    permission("positions.manage",
               "Manage positions and permission templates",
               "administration", "manage", sensitive=True,
               independent_approval=True),
)

PERMISSION_BY_CODE = {item.code: item for item in PERMISSIONS}

if len(PERMISSION_BY_CODE) != len(PERMISSIONS):
    raise RuntimeError("Duplicate VERIDIAN permission codes.")


def describe_permission(code):
    """Return metadata only; never an authorization decision."""
    return PERMISSION_BY_CODE.get(code)


def has_permission(user, code, *, project=None):
    """Fail closed until explicit authorization integration is approved."""
    return False
