import logging
from urllib.parse import quote_plus
from zoneinfo import ZoneInfo

from django.conf import settings
from django.core.files.base import ContentFile
from django.db import models
from django.utils.translation import gettext_lazy as _

from mycalendar.services.ics import build_calendar
from mycalendar.validators import validate_csv_upload


logger = logging.getLogger(__name__)
TZ = ZoneInfo("Europe/Brussels")


class MyCalendar(models.Model):
    name = models.CharField(max_length=100, verbose_name=_("Name"))
    document = models.FileField(upload_to="documents/", validators=[validate_csv_upload])
    ics = models.FileField(upload_to="ics/", blank=True, null=True)
    uploaded_at = models.DateTimeField(auto_now_add=True)

    def __str__(self) -> str:
        return self.name

    def get_ics(self) -> bool:
        try:
            with self.document.open("rb") as fh:
                csv_text = fh.read().decode("utf-8", errors="replace")
            ics_bytes = build_calendar(csv_text, name=self.name, tz=TZ)
        except Exception:
            logger.exception("failed to build ICS for MyCalendar id=%s", self.pk)
            return False

        filename = f"{self.name.replace(' ', '_')}.ics"
        self.ics.save(filename, ContentFile(ics_bytes))
        return True

    def get_ics_full_url(self) -> str:
        return f"https://{settings.SITE_DOMAIN}{self.ics.url}"

    def get_ics_facebook_link(self) -> str:
        return f"https://www.facebook.com/sharer/sharer.php?u={quote_plus(self.get_ics_full_url())}"

    def get_ics_twitter_link(self) -> str:
        return (
            f"https://twitter.com/intent/tweet"
            f"?text={quote_plus(self.name)}&url={quote_plus(self.get_ics_full_url())}"
        )

    def get_ics_mail_link(self) -> str:
        return (
            f"mailto:?subject={quote_plus(f'Calendar {self.name}')}"
            f"&body={quote_plus(f'Link to the calendar: {self.get_ics_full_url()}')}"
        )

    def get_ics_whatsapp_link(self) -> str:
        return (
            f"https://api.whatsapp.com/send?text="
            f"{quote_plus(f'Link to the calendar {self.name}: {self.get_ics_full_url()}')}"
        )
