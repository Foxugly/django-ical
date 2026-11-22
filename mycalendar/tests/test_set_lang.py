import pytest
from django.urls import reverse


@pytest.mark.parametrize(
    "next_url",
    [
        "https://example.org/",
        "//example.org/",
        "http://example.org/path",
        "javascript:alert(1)",
        r"/\example.org",
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


@pytest.mark.parametrize("lang", ["xx", "", "fr;evil=1", "../../etc"])
def test_set_lang_rejects_unknown_language(client, lang):
    response = client.get(reverse("lang"), {"lang": lang, "next": "/admin/"})
    assert response.status_code == 302
    assert response["Location"] == reverse("home")
    assert "django_language" not in response.cookies


@pytest.mark.django_db
def test_header_lang_links_urlencode_next(client):
    response = client.get("/?a=1&b=2")
    assert b"next=/%3Fa%3D1%26b%3D2" in response.content
