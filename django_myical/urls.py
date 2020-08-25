# -*- coding: utf-8 -*-
from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.shortcuts import render
from django.urls import path
from mycalendar.forms import MyCalendarForm
from mycalendar.models import MyCalendar
from decorator import check_lang
import pytz
from datetime import datetime, timedelta
from icalendar import Calendar, Event, vCalAddress, vText
import os
import hashlib
from django.core.files import File
from time import sleep


def get_ics(object):
    sleep(2)
    print("#2")
    ret = True
    #try:
    cal = Calendar()
    calname = '%s' % (object.name)
    cal.add('prodid', '-// %s //' % (calname))
    cal.add('version', '2.0')
    cal.add('X-WR-CALNAME', '%s' % calname)
    print("#3")
    print(object.__dict__)
    fichier = open(object.document.path, 'r')
    for line in fichier.readlines():
        vec = line.split(';')
        print(vec)
        if len(vec) >= 3:
            date = vec[0].split('/')
            date += vec[1].split('.')
            event = Event()
            match = ('%s' % vec[2]) if len(vec[3]) < 2 else ('%s-%s' % (vec[2], vec[3]))
            event.add('summary', match)
            date_start = datetime(int(date[2]), int(date[1]), int(date[0]), int(date[3]), int(date[4]), 0,
                                  tzinfo=pytz.timezone('Europe/Brussels'))
            event.add('dtstart', date_start)
            event.add('dtend', date_start + timedelta(hours=2))
            event.add('dtstamp', datetime.now())
            if len(vec) > 4:
                adr = vec[4][:-1]
                print(adr)
                if len(adr) > 5:
                    event['location'] = vText(adr)

            event['uid'] = hashlib.sha224(("%s%s" % (vec[0], match)).encode('utf-8')).hexdigest()
            print(event)
            cal.add_component(event)
        path_ics = '%s.ics' % calname.replace(' ', '_')
        f = open(path_ics, 'wb')
        f.write(cal.to_ical())
        f.close()
        f = open(path_ics, 'r')
        object.ics.save(path_ics, File(f))
        f.close()
    #except:
    #    print("error")
    #    ret = False
    return ret




@check_lang
def home(request):
    c = {}
    if request.method == 'POST':
        form = MyCalendarForm(request.POST, request.FILES)
        if form.is_valid():
            instance = form.save()
            instance.save()
            sleep(2)
            print("#1")
            get_ics(instance)
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
