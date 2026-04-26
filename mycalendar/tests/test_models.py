from io import BytesIO

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile

from mycalendar.models import MyCalendar


CSV_BYTES = (
    "31/12/2021;21.30;RBP;SCC;Av Des Vaillants 2;\n"
    "2022-01-15;09:00;Solo;;;\n"
).encode("utf-8")


@pytest.mark.django_db
def test_get_ics_creates_ics_file():
    instance = MyCalendar.objects.create(
        name="My Cal",
        document=SimpleUploadedFile("cal.csv", CSV_BYTES, content_type="text/csv"),
    )
    assert instance.get_ics() is True
    assert instance.ics.name.endswith(".ics")
    instance.ics.open("rb")
    try:
        content = instance.ics.read()
    finally:
        instance.ics.close()
    assert b"BEGIN:VCALENDAR" in content
    assert b"RBP-SCC" in content


@pytest.mark.django_db
def test_get_ics_returns_false_on_bad_csv(caplog):
    instance = MyCalendar.objects.create(
        name="Bad",
        document=SimpleUploadedFile("bad.csv", b"not;a;valid;date;line;", content_type="text/csv"),
    )
    assert instance.get_ics() is False
    assert any("failed to build ICS" in rec.message for rec in caplog.records)
