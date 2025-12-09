import debug_toolbar
from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import include, path
from django.views.generic.base import TemplateView
from wagtail import urls as wagtail_urls
from wagtail.admin import urls as wagtailadmin_urls
from wagtail.documents import urls as wagtaildocs_urls

from locations.views import locations_geojson, map_view
from mapping_violence.views import crime_detail, crime_list, index

urlpatterns = [
    path("", index, name="index"),
    path("map/", map_view, name="map"),
    path("data/", crime_list, name="crime_list"),
    path("api/locations.geojson", locations_geojson, name="locations_geojson"),
    path("crime/<int:crime_id>/", crime_detail, name="crime_detail"),
    path("admin/", admin.site.urls),
    path("cms/", include(wagtailadmin_urls)),
    path("documents/", include(wagtaildocs_urls)),
    # allauth
    path("accounts/", include("allauth.urls")),
    path("accounts/profile/", TemplateView.as_view(template_name="profile.html")),
    path("schema-viewer/", include("schema_viewer.urls")),
    # Wagtail pages - must be last to act as catch-all
    path("", include(wagtail_urls)),
] + static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)

if settings.DEBUG:
    urlpatterns = [path("__debug__/", include(debug_toolbar.urls))] + urlpatterns
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)
