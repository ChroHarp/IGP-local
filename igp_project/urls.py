from django.contrib import admin
from django.http import HttpResponse
from django.urls import include, path

from accounts.views import program_document_download


def health_check(request):
    return HttpResponse("ok", content_type="text/plain")


urlpatterns = [
    path("admin/", admin.site.urls),
    path("accounts/", include("allauth.urls")),
    path("documents/<uuid:public_id>/download/", program_document_download, name="program-document-download"),
    path("health/", health_check, name="health"),
]
