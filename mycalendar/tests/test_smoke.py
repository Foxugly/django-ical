import pytest
from django.urls import reverse


@pytest.mark.django_db
def test_home_renders(client):
    response = client.get(reverse("home"))
    assert response.status_code == 200
    assert b"Generate ical" in response.content
