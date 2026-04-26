from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.shortcuts import HttpResponseRedirect
from django.urls import path, reverse
from django.utils import translation
from django.utils.translation import check_for_language

from mycalendar.views import home


def set_lang(request):
    if "lang" not in request.GET or not check_for_language(request.GET["lang"]):
        return HttpResponseRedirect(reverse("home"))
    user_language = request.GET["lang"]
    translation.activate(user_language)
    next_url = request.GET.get("next") or reverse("home")
    response = HttpResponseRedirect(next_url)
    response.set_cookie(
        settings.LANGUAGE_COOKIE_NAME,
        user_language,
        max_age=settings.LANGUAGE_COOKIE_AGE,
        path=settings.LANGUAGE_COOKIE_PATH,
        domain=settings.LANGUAGE_COOKIE_DOMAIN,
        secure=settings.LANGUAGE_COOKIE_SECURE,
        httponly=settings.LANGUAGE_COOKIE_HTTPONLY,
        samesite=settings.LANGUAGE_COOKIE_SAMESITE,
    )
    return response


urlpatterns = [
    path("", home, name="home"),
    path("admin/", admin.site.urls),
    path("lang/", set_lang, name="lang"),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
