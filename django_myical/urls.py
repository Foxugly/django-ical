# -*- coding: utf-8 -*-
from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.shortcuts import render, HttpResponseRedirect
from django.urls import path, reverse
from django.utils import translation
from django.utils.translation import check_for_language, get_language

from mycalendar.forms import MyCalendarForm
from mycalendar.models import MyCalendar


def set_lang(request):
    response = None
    if 'lang' in request.GET and check_for_language(request.GET.get('lang')):
        user_language = request.GET.get('lang')
        translation.activate(user_language)
        if 'next' in request.GET:
            response = HttpResponseRedirect(request.GET.get('next'))
        else:
            response = HttpResponseRedirect(reverse('home'))
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


def home(request):
    c = {}
    if request.method == 'POST':
        form = MyCalendarForm(request.POST, request.FILES)
        if form.is_valid():
            instance = form.save()
            instance.save()
            instance.get_ics()
        c['form'] = MyCalendarForm()
    else:
        c['form'] = MyCalendarForm()
    c['object_list'] = MyCalendar.objects.all().order_by('-pk')[:5]
    return render(request, "model_form_upload.html", c)


urlpatterns = [
    path('', home, name='home'),
    path('admin/', admin.site.urls),
    path('lang/', set_lang, name='lang'),
]
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)
