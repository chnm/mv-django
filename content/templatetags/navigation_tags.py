from django import template
from wagtail.models import Page

register = template.Library()


@register.inclusion_tag("includes/navigation.html", takes_context=True)
def main_navigation(context):
    """
    Returns navigation menu items from Wagtail pages.
    Finds all live pages that are children of the root page.
    """
    request = context.get("request")

    # Get the root page (usually the home page)
    try:
        root_page = Page.objects.filter(depth=2).first()
        if root_page:
            # Get all live pages that are direct children of root
            nav_pages = root_page.get_children().live().in_menu()
        else:
            nav_pages = Page.objects.none()
    except Exception:
        nav_pages = Page.objects.none()

    return {
        "nav_pages": nav_pages,
        "request": request,
    }


@register.inclusion_tag("includes/mobile_navigation.html", takes_context=True)
def mobile_navigation(context):
    """
    Returns mobile navigation menu items from Wagtail pages.
    """
    request = context.get("request")

    # Get the root page (usually the home page)
    try:
        root_page = Page.objects.filter(depth=2).first()
        if root_page:
            # Get all live pages that are direct children of root
            nav_pages = root_page.get_children().live().in_menu()
        else:
            nav_pages = Page.objects.none()
    except Exception:
        nav_pages = Page.objects.none()

    return {
        "nav_pages": nav_pages,
        "request": request,
    }
