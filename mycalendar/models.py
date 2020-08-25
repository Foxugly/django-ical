from django.db import models
from django.utils.translation import gettext as _
from urllib.parse import quote_plus


class MyCalendar(models.Model):
    name = models.CharField(max_length=100, verbose_name=_("Name"), )
    document = models.FileField(upload_to='documents/')
    ics = models.FileField(upload_to='ics/', blank=True, null=True)
    uploaded_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.name

    def get_ics_facebook_link(self):
        url = "https://www.facebook.com/sharer/sharer.php?u=%s" % quote_plus(self.ics.url)
        return url

    def get_ics_twitter_link(self):
        url= "https://twitter.com/intent/tweet?text=%s&url=h%s&via=rapid_api" % (self.name, quote_plus(self.ics.url))
        return url

    def get_ics_mail_link(self):
        url="mailto:?subject=Calendar %s&body=Link to the calendar : %s " % (self.name, quote_plus(self.ics.url))
