import debug_toolbar
from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import include, path
from django.views.generic.base import TemplateView

from mapping_violence.views import index

urlpatterns = [
    path("", index, name="index"),
    path("admin/", admin.site.urls),
    # allauth
    path("accounts/", include("allauth.urls")),
    path("accounts/profile/", TemplateView.as_view(template_name="profile.html")),
] + static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)

if settings.DEBUG:
    urlpatterns = [path("__debug__/", include(debug_toolbar.urls))] + urlpatterns
