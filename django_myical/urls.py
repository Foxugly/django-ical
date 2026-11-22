from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.http import HttpResponseRedirect
from django.urls import path, reverse
from django.utils import translation
from django.utils.http import url_has_allowed_host_and_scheme
from django.utils.translation import check_for_language

from django_myical.health import health
from mycalendar.views import home


def _safe_next_url(request):
    """`next` only when it points back to this site, else the home page.

    An external `next` would turn /lang/ into an open redirect. Positive guard
    (return inside the `if`) so CodeQL sees the sanitizer (py/url-redirection).
    """
    candidate = request.GET.get("next")
    if candidate and url_has_allowed_host_and_scheme(
        candidate,
        allowed_hosts={request.get_host()},
        require_https=request.is_secure(),
    ):
        return candidate
    return reverse("home")


def _supported_language(code):
    """The settings.LANGUAGES code equal to `code`, or None.

    The cookie gets the value from settings, never the raw query string
    (py/cookie-injection); check_for_language also needs the locale installed.
    """
    for lang_code, _name in settings.LANGUAGES:
        if code == lang_code and check_for_language(lang_code):
            return lang_code
    return None


def set_lang(request):
    user_language = _supported_language(request.GET.get("lang"))
    if user_language is None:
        return HttpResponseRedirect(reverse("home"))
    translation.activate(user_language)
    response = HttpResponseRedirect(_safe_next_url(request))
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
    path("health/", health, name="health"),
    path("admin/", admin.site.urls),
    path("lang/", set_lang, name="lang"),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
