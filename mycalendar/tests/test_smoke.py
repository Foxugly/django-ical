import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from django.urls import reverse


@pytest.mark.django_db
def test_home_get(client):
    response = client.get(reverse("home"))
    assert response.status_code == 200
    assert b"Generate ical" in response.content


@pytest.mark.django_db
def test_home_post_creates_calendar_and_ics(client):
    csv = b"31/12/2021;21.30;RBP;SCC;Av Des Vaillants 2;\n"
    response = client.post(
        reverse("home"),
        data={"name": "Test", "document": SimpleUploadedFile("c.csv", csv, content_type="text/csv")},
    )
    assert response.status_code == 200
    from mycalendar.models import MyCalendar
    obj = MyCalendar.objects.get(name="Test")
    assert obj.ics.name.endswith(".ics")
