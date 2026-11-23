"""Read-only, company-wide customer and project duplicate awareness.

This endpoint reports company-wide matches while returning project
details only from the actor's existing authorized project scope.
It never creates, approves, or modifies a record.
"""
from django.db.models import Q
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.response import Response

from .models import Customer, Project, User, Role


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def lookup(request):
    actor = User.objects.get(pk=request.user.pk)

    if not actor.is_active or actor.role not in (
        Role.SALES_ASSOCIATE,
        Role.SALES_MANAGER,
        Role.COMPTROLLER,
    ):
        raise PermissionDenied(
            "Customer duplicate lookup requires an active commercial user."
        )

    name = request.query_params.get("name", "").strip()

    if not 2 <= len(name) <= 200:
        raise ValidationError({
            "name": "Enter a customer name of 2 to 200 characters."
        })

    # Do not limit this search to projects owned by the current
    # Sales Associate. Include archived customer records as well.
    matching_customers = Customer.objects.filter(
        legal_name__iexact=name
    )

    all_projects = Project.objects.filter(
        customer__in=matching_customers
    )

    # Reuse the existing authorization rules for returned project
    # details. Other associates' project details are not exposed.
    from .api import project_scope

    visible_projects = project_scope(actor).filter(
        customer__in=matching_customers
    )

    visible_count = visible_projects.count()
    company_count = all_projects.count()

    project_rows = list(
        visible_projects.order_by("-created_at", "-id")
        .values("id", "code", "location", "state")[:50]
    )

    return Response({
        "name": name,
        "possible_customer_match": matching_customers.exists(),
        "company_project_match": company_count > 0,
        "restricted_projects_exist": company_count > visible_count,
        "visible_project_count": visible_count,
        "visible_projects": [
            {
                "id": str(row["id"]),
                "code": row["code"],
                "location": row["location"],
                "state": row["state"],
            }
            for row in project_rows
        ],
        "more_visible_projects": visible_count > len(project_rows),
    })
