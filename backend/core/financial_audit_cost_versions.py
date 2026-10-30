"""Historical project-cost version selection for financial audit detail.

Pure selection logic. No database access, mutations, or statement changes.
All timestamps must be aware and comparable to the supplied cutoff.
"""

from datetime import datetime, time, timedelta, timezone
from zoneinfo import ZoneInfo


def select_project_cost_versions_as_of(records, cutoff_date):
    """Select one eligible approved version per project at cutoff date.

    Future approvals and drafts do not qualify. Results describe a
    historical project-cost position, not monthly expense recognition.
    """
    from datetime import date

    if (
        isinstance(cutoff_date, datetime)
        or not isinstance(cutoff_date, date)
    ):
        raise ValueError("Cutoff must be a calendar date.")

    if cutoff_date.year >= 9999:
        raise ValueError(
            "Reporting cutoff cannot extend beyond year 9998."
        )

    reporting_timezone = ZoneInfo("America/New_York")

    next_local_day = datetime.combine(
        cutoff_date + timedelta(days=1),
        time.min,
        tzinfo=reporting_timezone,
    )

    cutoff_exclusive = next_local_day.astimezone(timezone.utc)

    eligible = {}
    seen_ids = set()
    approval_counts = {}

    for record in records:
        record_id = str(record.pk)

        if record_id in seen_ids:
            raise ValueError("Duplicate cost-record identifier.")

        seen_ids.add(record_id)

        if record.status != "APPROVED":
            continue

        approved_at = record.approved_at

        if (
            not isinstance(approved_at, datetime)
            or approved_at.tzinfo is None
            or approved_at.utcoffset() is None
        ):
            raise ValueError(
                "Approved costs require an aware approval timestamp."
            )

        approved_at_utc = approved_at.astimezone(timezone.utc)

        if approved_at_utc >= cutoff_exclusive:
            continue

        project_id = str(record.project_id)
        approval_counts[project_id] = approval_counts.get(project_id, 0) + 1

        key = (
            record.version,
            approved_at_utc,
            record_id,
        )

        previous = eligible.get(project_id)

        if previous is None or key > previous[0]:
            eligible[project_id] = (key, record)

    selected = [
        eligible[project_id][1]
        for project_id in sorted(eligible)
    ]

    return {
        "cutoff_date": cutoff_date.isoformat(),
        "selection_policy": "HIGHEST_ELIGIBLE_APPROVED_VERSION",
        "selected_record_ids": [str(item.pk) for item in selected],
        "selected_records": selected,
        "approved_version_counts": {
            project_id: approval_counts[project_id]
            for project_id in sorted(approval_counts)
        },
        "financial_statement_reconciled": False,
    }
