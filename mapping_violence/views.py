from django.shortcuts import get_object_or_404, render
from django_tables2 import RequestConfig

from content.models import HomePageContent, ProjectPerson
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
            "address", "address__city", "weapon", "connected_event"
        ).prefetch_related("victim", "perpetrator", "witnesses"),
        pk=crime_id,
    )

    context = {
        "crime": crime,
    }

    return render(request, "crimes/detail.html", context)


def crime_list(request):
    """Display a data table of all crimes with filtering"""
    crimes = (
        Crime.objects.select_related("address", "address__city")
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

    return render(request, "crimes/list.html", context)
