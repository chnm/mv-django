from django.db.models import Count

from mapping_violence.models import Crime


def dashboard_callback(request, context):
    """Populate the Unfold admin dashboard with workflow status summary."""
    status_counts = dict(
        Crime.objects.values_list("status")
        .annotate(count=Count("id"))
        .values_list("status", "count")
    )

    labels = ["Triage", "Assigned", "Needs Review", "Done"]
    keys = ["triage", "assigned", "needs_review", "done"]
    counts = [status_counts.get(k, 0) for k in keys]
    total = sum(counts)

    context.update(
        {
            "status_labels": labels,
            "status_counts": counts,
            "total_crimes": total,
            "kpi": [
                {"title": "Total Records", "value": total},
                {"title": "Triage", "value": status_counts.get("triage", 0)},
                {"title": "Assigned", "value": status_counts.get("assigned", 0)},
                {
                    "title": "Needs Review",
                    "value": status_counts.get("needs_review", 0),
                },
                {"title": "Done", "value": status_counts.get("done", 0)},
            ],
        }
    )
    return context
