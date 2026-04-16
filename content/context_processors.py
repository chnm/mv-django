from wagtail.models import Page


def _build_nav_tree(page, max_depth=3):
    """
    Recursively build navigation data for a page and its children.
    max_depth limits how many levels deep to traverse (1 = just this level's children).
    """
    children_pages = page.get_children().live().in_menu()
    children = []
    if max_depth > 0:
        for child in children_pages:
            children.append(_build_nav_tree(child, max_depth - 1))
    return {
        "page": page,
        "children": children,
        "has_children": len(children) > 0,
    }


def navigation(request):
    """
    Add navigation menu items to template context from Wagtail pages.
    Supports nested child pages up to 3 levels deep.
    """
    try:
        root_page = Page.objects.filter(depth=2).first()
        if root_page:
            nav_pages = root_page.get_children().live().in_menu()
            nav_data = [_build_nav_tree(page, max_depth=2) for page in nav_pages]
        else:
            nav_data = []
    except Exception:
        nav_data = []

    return {
        "nav_pages": nav_pages if "nav_pages" in locals() else Page.objects.none(),
        "nav_data": nav_data,
    }
