"""The admin 2FA (admin_2fa/) must not change anything outside /admin/, staff included."""
from pathlib import Path

import pytest
from django.contrib.auth import get_user_model
from django.urls import reverse
from django_otp.plugins.otp_totp.models import TOTPDevice

NGINX_CONF = Path(__file__).resolve().parents[2] / "deploy" / "nginx" / "ical.foxugly.com.conf"


@pytest.mark.django_db
@pytest.mark.parametrize("enrolled", [False, True])
def test_staff_logged_in_with_a_password_only_sees_the_public_site(client, enrolled):
    user = get_user_model().objects.create_user(username="ops", password="sup3rSecret!")
    user.is_staff = True
    user.save()
    if enrolled:
        TOTPDevice.objects.create(user=user, name="admin-2fa", confirmed=True)
    client.force_login(user)

    assert client.get(reverse("home")).status_code == 200
    assert client.get(reverse("health")).status_code == 200
    lang = client.get(reverse("lang"), {"lang": "fr", "next": "/"})
    assert lang.status_code == 302
    assert lang["Location"] == "/"


@pytest.mark.django_db
def test_public_pages_stay_anonymous(client):
    assert client.get(reverse("home")).status_code == 200
    assert client.get(reverse("health")).status_code == 200


def _block(opening):
    text = NGINX_CONF.read_text(encoding="utf-8")
    start = text.index(opening)
    return text[start : text.index("}", start)]


def test_admin_2fa_steps_share_the_login_limit():
    assert "limit_req zone=ical_admin_login" in _block("location = /admin/login/")
    assert "limit_req zone=ical_admin_login" in _block("location ^~ /admin/2fa/")
