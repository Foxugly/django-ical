import hashlib
from datetime import datetime, timedelta
from urllib.parse import quote_plus

import pytz
from django.core.files import File
from django.db import models
from django.utils.translation import gettext as _
from icalendar import Calendar, Event, vText


class MyCalendar(models.Model):
    name = models.CharField(max_length=100, verbose_name=_("Name"), )
    document = models.FileField(upload_to='documents/')
    ics = models.FileField(upload_to='ics/', blank=True, null=True)
    uploaded_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.name

    def get_ics(self):
        ret = True
        try:
            cal = Calendar()
            calname = '%s' % (self.name)
            cal.add('prodid', '-// %s //' % (calname))
            cal.add('version', '2.0')
            cal.add('X-WR-CALNAME', '%s' % calname)
            fichier = open(self.document.path, 'r')
            for line in fichier.readlines():
                vec = line.split(';')
                if len(vec) >= 3:
                    date = vec[0].split('/')
                    if '.' in vec[1]:
                        date += vec[1].split('.')
                    elif ':' in vec[1]:
                        date += vec[1].split(':')
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
                        if len(adr) > 5:
                            event['location'] = vText(adr)
                    event['uid'] = hashlib.sha224(("%s%s" % (vec[0], match)).encode('utf-8')).hexdigest()
                    cal.add_component(event)
                path_ics = '%s.ics' % calname.replace(' ', '_')
                f = open(path_ics, 'wb')
                f.write(cal.to_ical())
                f.close()
                f = open(path_ics, 'r')
                self.ics.save(path_ics, File(f))
                f.close()
        except:
            print("error")
            ret = False
        return ret

    def get_ics_facebook_link(self):
        url = "https://www.facebook.com/sharer/sharer.php?u=%s" % quote_plus(self.ics.url)
        return url

    def get_ics_twitter_link(self):
        url = "https://twitter.com/intent/tweet?text=%s&url=h%s&via=rapid_api" % (self.name, quote_plus(self.ics.url))
        return url

    def get_ics_mail_link(self):
        url = "mailto:?subject=Calendar %s&body=Link to the calendar : %s " % (self.name, quote_plus(self.ics.url))
