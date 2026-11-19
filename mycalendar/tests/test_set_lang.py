import pytest
from django.urls import reverse


@pytest.mark.parametrize(
    "next_url",
    [
        "https://example.org/",
        "//example.org/",
        "http://example.org/path",
        "javascript:alert(1)",
        "/\example.org",
    ],
)
def test_set_lang_rejects_external_next(client, next_url):
    response = client.get(reverse("lang"), {"lang": "fr", "next": next_url})
    assert response.status_code == 302
    assert response["Location"] == reverse("home")


def test_set_lang_keeps_local_next(client):
    response = client.get(reverse("lang"), {"lang": "fr", "next": "/admin/"})
    assert response.status_code == 302
    assert response["Location"] == "/admin/"


def test_set_lang_without_next_goes_home(client):
    response = client.get(reverse("lang"), {"lang": "nl"})
    assert response.status_code == 302
    assert response["Location"] == reverse("home")
    assert response.cookies["django_language"].value == "nl"
