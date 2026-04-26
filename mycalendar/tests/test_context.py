import pytest
from django.urls import reverse


@pytest.mark.django_db
def test_state_ribbon_renders_when_debug(client, settings):
    settings.DEBUG = True
    settings.STATE = "INT"
    response = client.get(reverse("home"))
    assert b"INT" in response.content
