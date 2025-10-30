from wagtail.models import Page


def navigation(request):
    """
    Add navigation menu items to template context from Wagtail pages.
    Includes child pages for dropdown functionality.
    """
    try:
        # Get the root page (usually the home page)
        root_page = Page.objects.filter(depth=2).first()
        if root_page:
            # Get all live pages that are direct children of root
            nav_pages = root_page.get_children().live().in_menu()

            # Build navigation data with child pages
            nav_data = []
            for page in nav_pages:
                children = page.get_children().live().in_menu()
                nav_data.append(
                    {
                        "page": page,
                        "children": children,
                        "has_children": children.exists(),
                    }
                )
        else:
            nav_data = []
    except Exception:
        nav_data = []

    return {
        "nav_pages": nav_pages if "nav_pages" in locals() else Page.objects.none(),
        "nav_data": nav_data,
    }
