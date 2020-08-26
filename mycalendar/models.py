import hashlib
from datetime import datetime, timedelta
from urllib.parse import quote_plus

import pytz
#from django.core.files import File, ContentFile
from django.core.files.base import ContentFile
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
                    if '/' in vec[0]:
                        date = vec[0].split('/')
                        day = date[0]
                        month = date[1]
                        year = date[2]
                    elif "-" in vec[0]:
                        date = vec[0].split(':')
                        day = date[2]
                        month = date[1]
                        year = date[0]
                    else:
                        print("error date")
                    if '.' in vec[1]:
                        hour, minute = vec[1].split('.')
                    elif ':' in vec[1]:
                        hour, minute = vec[1].split(':')
                    event = Event()
                    match = ('%s' % vec[2]) if len(vec[3]) < 2 else ('%s-%s' % (vec[2], vec[3]))
                    event.add('summary', match)
                    date_start = datetime(int(year), int(month), int(day), int(hour), int(minute), 0,
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
            #f = open(path_ics, 'wb')
            #f.write(cal.to_ical())
            #f.close()
            #f = open(path_ics, 'r')
            #self.ics.save(path_ics, File(f))
            #f.close()
            self.ics.save(path_ics, ContentFile(cal.to_ical()))
        except:
            print("error")
            ret = False
        return ret

    def get_ics_facebook_link(self):
        url = "https://www.facebook.com/sharer/sharer.php?u=%s" % quote_plus(self.ics.url)
        return url

    # <button class="btn btn-social-icon btn-facebook" type="button" onclick="dpisocial_share_this('https://www.facebook.com/sharer/sharer.php?u=https%3A%2F%2Fwww.lesoir.be%2F321090%2Farticle%2F2020-08-26%2Fen-aout-une-personne-contaminee-sur-5-avait-voyage-selon-le-centre-de-crise', 'facebook', 321090);"><i class="fa fa-facebook icon icon-facebook"></i></button>

    def get_ics_twitter_link(self):
        url = "https://twitter.com/intent/tweet?text=%s&url=h%s&via=rapid_api" % (self.name, quote_plus(self.ics.url))
        return url

    def get_ics_mail_link(self):
        url = "mailto:?subject=Calendar %s&body=Link to the calendar : %s " % (self.name, quote_plus(self.ics.url))
        return url

    # <button onclick="location.href='mailto:?subject=Un%20article%20int%C3%A9ressant%20%C3%A0%20lire%20sur%20Le%20Soir%20Plus&amp;body=Un%20article%20int%C3%A9ressant%20%C3%A0%20lire%20https%3A%2F%2Fwww.lesoir.be%2F321090%2Farticle%2F2020-08-26%2Fen-aout-une-personne-contaminee-sur-5-avait-voyage-selon-le-centre-de-crise'" class="btn btn-social-icon btn-mail" type="button"><i class="fa fa-envelope-o"></i><span class="label"></span></button>

    def get_ics_whatsapp_link(self):
        url = "https://api.whatsapp.com/send?text=Link to the calendar '%s' : %s " % (
        self.name, quote_plus(self.ics.url))
        return url

    # <button class="btn btn-social-icon btn-whatsapp" type="button" onclick="dpisocial_share_this('https://api.whatsapp.com/send?text=Voici un article intéressant - https://www.lesoir.be/321090/article/2020-08-26/en-aout-une-personne-contaminee-sur-5-avait-voyage-selon-le-centre-de-crise', 'whatsapp', 321090);"><i class="fa fa-whatsapp icon icon-whatsapp"></i></button>

    def get_ics_messenger_link(self):
        return None
    # <button class="btn btn-social-icon btn-messenger" type="button" onclick="dpisocial_share_messenger('https://www.lesoir.be/321090/article/2020-08-26/en-aout-une-personne-contaminee-sur-5-avait-voyage-selon-le-centre-de-crise', 'facebook', '321090');"><i class="fa fa-facebook icon icon-messenger"></i></button>
