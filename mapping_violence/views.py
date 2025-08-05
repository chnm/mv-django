from django.shortcuts import render

from content.models import HomePageContent, ProjectPerson


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
