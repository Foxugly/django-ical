# -*- coding: utf-8 -*-
from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.shortcuts import render
from django.urls import path
from mycalendar.forms import MyCalendarForm
from mycalendar.models import MyCalendar
from decorator import check_lang


@check_lang
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
]
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
    urlpatterns += static(settings.STATIC_URL,document_root=settings.STATIC_ROOT)
