import csv

from django.db.models import Q
from django.http import StreamingHttpResponse
from django.shortcuts import get_object_or_404, render
from django_tables2 import RequestConfig

from content.models import HomePageContent, ProjectPerson
from mapping_violence.context_helpers import get_filter_context
from mapping_violence.filters import CrimeFilter
from mapping_violence.models import Crime
from mapping_violence.tables import CrimeTable


def index(request):
    # Get active home page content
    home_content = HomePageContent.objects.filter(is_active=True).first()

    # Get project team and advisory board members
    project_team = ProjectPerson.objects.filter(
        is_active=True, team_type="project_team"
    ).order_by("display_order", "name")

    advisory_board = ProjectPerson.objects.filter(
        is_active=True, team_type="advisory_board"
    ).order_by("display_order", "name")

    context = {
        "home_content": home_content,
        "project_team": project_team,
        "advisory_board": advisory_board,
    }

    return render(request, "index.html", context)


def crime_detail(request, crime_id):
    """Display detailed information about a specific crime"""
    crime = get_object_or_404(
        Crime.objects.select_related(
            "address", "address__city", "weapon", "connected_event", "judge"
        ).prefetch_related("victim", "perpetrator", "witnesses"),
        pk=crime_id,
    )

    # Find cases sharing a victim or perpetrator with this crime
    person_pks = set(
        list(crime.victim.values_list("pk", flat=True))
        + list(crime.perpetrator.values_list("pk", flat=True))
    )
    if person_pks:
        related_qs = (
            Crime.objects.filter(
                Q(victim__in=person_pks) | Q(perpetrator__in=person_pks)
            )
            .exclude(pk=crime.pk)
            .select_related("address", "address__city")
            .prefetch_related("victim", "perpetrator")
            .distinct()
            .order_by("-date", "-year")[:10]
        )
        related_crimes = []
        for rel in related_qs:
            shared = []
            seen_pks = set()
            for v in rel.victim.all():
                if v.pk in person_pks and v.pk not in seen_pks:
                    shared.append(str(v))
                    seen_pks.add(v.pk)
            for p in rel.perpetrator.all():
                if p.pk in person_pks and p.pk not in seen_pks:
                    shared.append(str(p))
                    seen_pks.add(p.pk)
            related_crimes.append({"crime": rel, "shared": shared})
    else:
        related_crimes = []

    context = {
        "crime": crime,
        "related_crimes": related_crimes,
    }

    return render(request, "crimes/detail.html", context)


def crime_list(request):
    """Display a data table of all crimes with filtering"""
    crimes = (
        Crime.objects.select_related("address", "address__city", "weapon")
        .prefetch_related("victim", "perpetrator")
        .order_by("-date", "-year")
    )

    # Apply filters
    crime_filter = CrimeFilter(request.GET, queryset=crimes)

    # Create table
    table = CrimeTable(crime_filter.qs)
    RequestConfig(request, paginate={"per_page": 50}).configure(table)

    context = {
        "table": table,
        "filter": crime_filter,
    }
    context.update(get_filter_context())

    return render(request, "crimes/list.html", context)


class Echo:
    """Pseudo-buffer for StreamingHttpResponse with csv.writer."""

    def write(self, value):
        return value


def crime_export_csv(request):
    """Export filtered crimes as a CSV download."""
    crimes = (
        Crime.objects.select_related(
            "address", "address__city", "weapon", "connected_event"
        )
        .prefetch_related("victim", "perpetrator")
        .order_by("-date", "-year")
    )
    crime_filter = CrimeFilter(request.GET, queryset=crimes)
    queryset = crime_filter.qs

    columns = [
        ("Case Number", lambda c: c.number),
        ("Crime", lambda c: c.crime),
        ("Date", lambda c: str(c.date) if c.date else ""),
        ("Year", lambda c: c.year),
        ("Month", lambda c: c.month),
        ("Day", lambda c: c.day),
        ("City", lambda c: c.address.city.name if c.address and c.address.city else ""),
        ("Location", lambda c: c.address.name if c.address else ""),
        ("Victim(s)", lambda c: "; ".join(str(v) for v in c.victim.all())),
        (
            "Victim Gender",
            lambda c: "; ".join(v.gender for v in c.victim.all() if v.gender),
        ),
        ("Perpetrator(s)", lambda c: "; ".join(str(p) for p in c.perpetrator.all())),
        (
            "Perpetrator Gender",
            lambda c: "; ".join(p.gender for p in c.perpetrator.all() if p.gender),
        ),
        ("Weapon", lambda c: str(c.weapon) if c.weapon else ""),
        ("Motive", lambda c: c.motive),
        ("Fatality", lambda c: "Y" if c.fatality else "N"),
        (
            "Convicted",
            lambda c: "Y" if c.convicted else "N" if c.convicted is False else "",
        ),
        ("Sentence", lambda c: c.sentence),
        ("Description", lambda c: c.description_of_case),
        (
            "Connected Event",
            lambda c: str(c.connected_event) if c.connected_event else "",
        ),
        ("Archival Location", lambda c: c.archival_location),
        ("Reference", lambda c: c.reference),
    ]

    def rows():
        yield [col[0] for col in columns]
        for crime in queryset.iterator(chunk_size=500):
            yield [col[1](crime) for col in columns]

    pseudo_buffer = Echo()
    writer = csv.writer(pseudo_buffer)
    response = StreamingHttpResponse(
        (writer.writerow(row) for row in rows()),
        content_type="text/csv",
    )
    response["Content-Disposition"] = 'attachment; filename="mapping_violence_data.csv"'
    return response
