from django.utils import translation
from django.conf import settings


def check_lang(function):
    def wrap(request, *args, **kwargs):
        if request.user.is_authenticated:
            if translation.LANGUAGE_SESSION_KEY in request.session:
                del request.session[translation.LANGUAGE_SESSION_KEY]
                translation.activate(request.user.language)
                request.session[translation.LANGUAGE_SESSION_KEY] = request.user.language
        elif translation.LANGUAGE_SESSION_KEY not in request.session:
            translation.activate(settings.LANGUAGE_CODE)
            request.session[translation.LANGUAGE_SESSION_KEY] = settings.LANGUAGE_CODE
        return function(request, *args, **kwargs)

    wrap.__doc__ = function.__doc__
    wrap.__name__ = function.__name__
    return wrap
