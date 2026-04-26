# Django-iCal — Full Tech & Security Upgrade — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Modernize the django-ical project (Django 4.2 → 5.2 LTS, Python 3.12+, `icalendar` 6.x, `zoneinfo`), fix latent bugs (CSV parsing, encoding, swallowed exceptions, missing settings), secure file uploads, and deploy hardened settings on AWS EC2 at `ical.foxugly.com` while preserving existing prod data.

**Architecture:** Keep the project shape (single Django app, SQLite, `MyCalendar` model, single home view). Move the inline view from `urls.py` to `mycalendar/views.py`. Add a thin `services/ics.py` module to isolate CSV→ICS logic from the model so it becomes testable. Replace `pytz` with `zoneinfo`. Replace bare `try/except` with structured logging. Add upload validators (size, extension, MIME, content). Pull all secrets and per-environment settings from environment variables via `django-environ`. Serve static files with WhiteNoise; run under gunicorn behind nginx with Let's Encrypt TLS.

**Tech Stack:** Python 3.12, Django 5.2 LTS, `icalendar` 6.x, `django-widget-tweaks` (latest), `django-environ`, `whitenoise`, `gunicorn`, `pytest-django`, `ruff`, AWS EC2 + nginx + certbot.

---

## Pre-flight: backup production

These steps run on the EC2 instance and are irreversible-on-rollback safety nets. Execute manually.

- [ ] **Step P1: SSH into prod EC2 and snapshot the database**

```bash
ssh ec2-user@ical.foxugly.com   # adjust user as needed
cd /path/to/django-ical
cp db.sqlite3 db.sqlite3.backup-$(date +%Y%m%d-%H%M%S)
```

- [ ] **Step P2: Snapshot the media folder (uploaded CSVs and generated ICS)**

```bash
tar -czf media-backup-$(date +%Y%m%d-%H%M%S).tar.gz media/
```

- [ ] **Step P3: Pull both backups to local machine**

```bash
# from local
scp ec2-user@ical.foxugly.com:/path/to/django-ical/db.sqlite3.backup-* ./backups/
scp ec2-user@ical.foxugly.com:/path/to/django-ical/media-backup-*.tar.gz ./backups/
```

- [ ] **Step P4: Capture the prod Python version and pip freeze**

```bash
ssh ec2-user@ical.foxugly.com 'python --version && cd /path/to/django-ical && pip freeze' > backups/prod-env.txt
```

- [ ] **Step P5: Note current EC2 instance metadata**

Capture: instance ID, AMI, security groups, Elastic IP, current nginx config path. Save as `backups/prod-infra.md`. This is reference material for the redeploy.

---

## Phase 1: Local environment + baseline tests

### Task 1: Set up clean Python 3.12 venv with current versions, lock baseline

**Files:**
- Modify: `requirements.txt`
- Create: `requirements.in`
- Create: `requirements-dev.in`
- Create: `.python-version`

- [ ] **Step 1.1: Confirm Python 3.12 available**

```bash
py -3.12 --version
```

Expected: `Python 3.12.x`. If not installed, install from python.org first.

- [ ] **Step 1.2: Create fresh venv and pin Python version**

```bash
rm -rf .venv venv
py -3.12 -m venv .venv
source .venv/Scripts/activate
python -m pip install --upgrade pip pip-tools
echo "3.12" > .python-version
```

- [ ] **Step 1.3: Create `requirements.in` (runtime deps, unpinned)**

```
Django>=5.2,<5.3
icalendar>=6.0,<7.0
django-widget-tweaks>=1.5
django-environ>=0.11
whitenoise>=6.6
gunicorn>=22.0
```

- [ ] **Step 1.4: Create `requirements-dev.in`**

```
-r requirements.in
pytest>=8.0
pytest-django>=4.8
ruff>=0.5
```

- [ ] **Step 1.5: Compile and install**

```bash
pip-compile requirements.in -o requirements.txt
pip-compile requirements-dev.in -o requirements-dev.txt
pip install -r requirements-dev.txt
```

Expected: no errors. `requirements.txt` is now fully pinned.

- [ ] **Step 1.6: Verify Django boots**

```bash
python manage.py check
```

Expected: `System check identified no issues`. May surface deprecation warnings — that's fine, we'll fix them in subsequent tasks.

- [ ] **Step 1.7: Commit**

```bash
git add requirements.in requirements-dev.in requirements.txt requirements-dev.txt .python-version
git commit -m "chore: pin Python 3.12 and upgrade core deps to Django 5.2 LTS"
```

---

### Task 2: Configure pytest, add a smoke test

**Files:**
- Create: `pytest.ini`
- Create: `conftest.py`
- Create: `mycalendar/tests/__init__.py`
- Create: `mycalendar/tests/test_smoke.py`
- Delete: `mycalendar/tests.py` (replaced by tests package)

- [ ] **Step 2.1: Write `pytest.ini`**

```ini
[pytest]
DJANGO_SETTINGS_MODULE = django_myical.settings
python_files = test_*.py
addopts = -ra
```

- [ ] **Step 2.2: Write `conftest.py` (empty placeholder for fixtures)**

```python
# Project-level pytest fixtures live here.
```

- [ ] **Step 2.3: Delete the empty `mycalendar/tests.py` and create the tests package**

```bash
rm mycalendar/tests.py
mkdir mycalendar/tests
touch mycalendar/tests/__init__.py
```

- [ ] **Step 2.4: Write the failing smoke test in `mycalendar/tests/test_smoke.py`**

```python
import pytest
from django.urls import reverse


@pytest.mark.django_db
def test_home_renders(client):
    response = client.get(reverse("home"))
    assert response.status_code == 200
    assert b"Generate ical" in response.content
```

- [ ] **Step 2.5: Run smoke test**

```bash
pytest mycalendar/tests/test_smoke.py -v
```

Expected: PASS. If it fails, fix before moving on — this is the baseline behaviour we preserve through the upgrade.

- [ ] **Step 2.6: Commit**

```bash
git add pytest.ini conftest.py mycalendar/tests/
git rm mycalendar/tests.py
git commit -m "test: add pytest config and smoke test for home view"
```

---

## Phase 2: Code modernization & bug fixes

### Task 3: Extract CSV→ICS into a pure service module

The current `MyCalendar.get_ics()` mixes file IO, parsing, ICS building, encoding choice, timezone, and exception swallowing. Pull pure logic out so we can unit-test it without the ORM.

**Files:**
- Create: `mycalendar/services/__init__.py`
- Create: `mycalendar/services/ics.py`
- Create: `mycalendar/tests/test_ics_service.py`

- [ ] **Step 3.1: Create the package**

```bash
mkdir mycalendar/services
touch mycalendar/services/__init__.py
```

- [ ] **Step 3.2: Write the failing test for happy-path parsing**

`mycalendar/tests/test_ics_service.py`:

```python
from datetime import datetime
from zoneinfo import ZoneInfo

import pytest
from icalendar import Calendar

from mycalendar.services.ics import build_calendar, parse_row


BRUSSELS = ZoneInfo("Europe/Brussels")


def test_parse_row_dd_mm_yyyy_with_dot_time():
    row = "31/12/2021;21.30;RBP;SCC;Avenue Des Vaillants 2 1200 Woluwé-St-Lambert;"
    event = parse_row(row, tz=BRUSSELS)
    assert event.summary == "RBP-SCC"
    assert event.start == datetime(2021, 12, 31, 21, 30, tzinfo=BRUSSELS)
    assert event.location == "Avenue Des Vaillants 2 1200 Woluwé-St-Lambert"


def test_parse_row_iso_date_with_colon_time():
    row = "2021-12-31;21:30;RBP;;;"
    event = parse_row(row, tz=BRUSSELS)
    assert event.summary == "RBP"
    assert event.start == datetime(2021, 12, 31, 21, 30, tzinfo=BRUSSELS)
    assert event.location is None


def test_parse_row_too_few_fields_returns_none():
    assert parse_row("only;two", tz=BRUSSELS) is None


def test_parse_row_bad_date_raises():
    with pytest.raises(ValueError):
        parse_row("bogus;21:30;A;B;;", tz=BRUSSELS)


def test_build_calendar_produces_valid_ics():
    csv_text = (
        "31/12/2021;21.30;RBP;SCC;Av Des Vaillants 2;\n"
        "2022-01-15;09:00;Solo;;;\n"
    )
    ics_bytes = build_calendar(csv_text, name="My Cal", tz=BRUSSELS)
    cal = Calendar.from_ical(ics_bytes)
    events = [c for c in cal.walk("vevent")]
    assert len(events) == 2
    assert str(events[0]["summary"]) == "RBP-SCC"
    assert str(events[1]["summary"]) == "Solo"
```

- [ ] **Step 3.3: Run tests to verify they fail**

```bash
pytest mycalendar/tests/test_ics_service.py -v
```

Expected: FAIL with `ImportError: cannot import name 'build_calendar'`.

- [ ] **Step 3.4: Implement `mycalendar/services/ics.py`**

```python
"""Pure CSV→ICS conversion. No Django, no IO."""
from __future__ import annotations

import hashlib
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Optional
from zoneinfo import ZoneInfo

from icalendar import Calendar, Event, vText


EVENT_DURATION = timedelta(hours=1, minutes=30)


@dataclass(frozen=True)
class ParsedEvent:
    summary: str
    start: datetime
    location: Optional[str]
    uid: str

    def end(self) -> datetime:
        return self.start + EVENT_DURATION


def _parse_date(token: str) -> tuple[int, int, int]:
    if "/" in token:
        day, month, year = token.split("/")
    elif "-" in token:
        year, month, day = token.split("-")
    else:
        raise ValueError(f"unrecognized date format: {token!r}")
    return int(year), int(month), int(day)


def _parse_time(token: str) -> tuple[int, int]:
    sep = "." if "." in token else ":" if ":" in token else None
    if sep is None:
        raise ValueError(f"unrecognized time format: {token!r}")
    hour, minute = token.split(sep)
    return int(hour), int(minute)


def parse_row(row: str, *, tz: ZoneInfo) -> Optional[ParsedEvent]:
    fields = [f.strip() for f in row.rstrip("\n").split(";")]
    if len(fields) < 3:
        return None

    year, month, day = _parse_date(fields[0])
    hour, minute = _parse_time(fields[1])
    start = datetime(year, month, day, hour, minute, tzinfo=tz)

    home = fields[2]
    away = fields[3] if len(fields) > 3 else ""
    summary = f"{home}-{away}" if len(away) >= 2 else home

    location: Optional[str] = None
    if len(fields) > 4 and len(fields[4]) > 5:
        location = fields[4]

    uid = hashlib.sha224(f"{fields[0]}{summary}".encode("utf-8")).hexdigest()
    return ParsedEvent(summary=summary, start=start, location=location, uid=uid)


def build_calendar(csv_text: str, *, name: str, tz: ZoneInfo) -> bytes:
    cal = Calendar()
    cal.add("prodid", f"-// {name} //")
    cal.add("version", "2.0")
    cal.add("X-WR-CALNAME", name)

    now = datetime.now(tz=tz)
    for row in csv_text.splitlines():
        if not row.strip():
            continue
        parsed = parse_row(row, tz=tz)
        if parsed is None:
            continue
        event = Event()
        event.add("summary", parsed.summary)
        event.add("dtstart", parsed.start)
        event.add("dtend", parsed.end())
        event.add("dtstamp", now)
        if parsed.location:
            event["location"] = vText(parsed.location)
        event["uid"] = parsed.uid
        cal.add_component(event)

    return cal.to_ical()
```

- [ ] **Step 3.5: Run tests to verify they pass**

```bash
pytest mycalendar/tests/test_ics_service.py -v
```

Expected: PASS (5/5).

- [ ] **Step 3.6: Commit**

```bash
git add mycalendar/services mycalendar/tests/test_ics_service.py
git commit -m "feat(mycalendar): extract pure CSV→ICS service with zoneinfo and tests"
```

---

### Task 4: Wire the model to the new service, drop pytz, log instead of swallow

**Files:**
- Modify: `mycalendar/models.py`
- Create: `mycalendar/tests/test_models.py`

- [ ] **Step 4.1: Write failing test for the model integration**

`mycalendar/tests/test_models.py`:

```python
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
```

- [ ] **Step 4.2: Run tests to verify they fail**

```bash
pytest mycalendar/tests/test_models.py -v
```

Expected: FAIL (the current model uses latin-1 and swallows exceptions silently).

- [ ] **Step 4.3: Rewrite `mycalendar/models.py`**

```python
import logging
from urllib.parse import quote_plus
from zoneinfo import ZoneInfo

from django.conf import settings
from django.core.files.base import ContentFile
from django.db import models
from django.utils.translation import gettext_lazy as _

from mycalendar.services.ics import build_calendar


logger = logging.getLogger(__name__)
TZ = ZoneInfo("Europe/Brussels")


class MyCalendar(models.Model):
    name = models.CharField(max_length=100, verbose_name=_("Name"))
    document = models.FileField(upload_to="documents/")
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
```

Note: `WEBSITE` is renamed to `SITE_DOMAIN` for clarity, scheme is forced to `https`, all URL params now go through `quote_plus`.

- [ ] **Step 4.4: Run tests to verify they pass**

```bash
pytest mycalendar/tests/ -v
```

Expected: all tests PASS. (`SITE_DOMAIN` will need to exist in settings — temporarily add `SITE_DOMAIN = "localhost"` in `django_myical/settings.py` to keep tests green; we'll move it to env in Task 8.)

- [ ] **Step 4.5: Add temp `SITE_DOMAIN` placeholder to `django_myical/settings.py`**

Append:
```python
SITE_DOMAIN = "localhost"  # overridden in Task 8
```

- [ ] **Step 4.6: Re-run full test suite**

```bash
pytest -v
```

Expected: all PASS.

- [ ] **Step 4.7: Commit**

```bash
git add mycalendar/models.py mycalendar/tests/test_models.py django_myical/settings.py
git commit -m "refactor(mycalendar): use ICS service, zoneinfo, structured logging; rename WEBSITE→SITE_DOMAIN"
```

---

### Task 5: Move home view to views.py, add CSRF and method tests

**Files:**
- Modify: `mycalendar/views.py`
- Modify: `django_myical/urls.py`
- Modify: `mycalendar/tests/test_smoke.py`

- [ ] **Step 5.1: Write failing tests in `mycalendar/tests/test_smoke.py`**

Replace contents with:

```python
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
```

- [ ] **Step 5.2: Run test to verify failure**

```bash
pytest mycalendar/tests/test_smoke.py -v
```

Expected: at least the POST test fails or passes accidentally — depending on the current view. Confirm both run before refactor.

- [ ] **Step 5.3: Move home view to `mycalendar/views.py`**

```python
from django.shortcuts import render
from django.views.decorators.http import require_http_methods

from mycalendar.forms import MyCalendarForm
from mycalendar.models import MyCalendar


@require_http_methods(["GET", "POST"])
def home(request):
    if request.method == "POST":
        form = MyCalendarForm(request.POST, request.FILES)
        if form.is_valid():
            instance = form.save()
            instance.get_ics()
            form = MyCalendarForm()
    else:
        form = MyCalendarForm()

    context = {
        "form": form,
        "object_list": MyCalendar.objects.order_by("-pk")[:5],
    }
    return render(request, "model_form_upload.html", context)
```

- [ ] **Step 5.4: Strip the home view + duplicate save from `django_myical/urls.py`**

New contents:

```python
from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.shortcuts import HttpResponseRedirect
from django.urls import path, reverse
from django.utils import translation
from django.utils.translation import check_for_language

from mycalendar.views import home


def set_lang(request):
    if "lang" not in request.GET or not check_for_language(request.GET["lang"]):
        return HttpResponseRedirect(reverse("home"))
    user_language = request.GET["lang"]
    translation.activate(user_language)
    next_url = request.GET.get("next") or reverse("home")
    response = HttpResponseRedirect(next_url)
    response.set_cookie(
        settings.LANGUAGE_COOKIE_NAME,
        user_language,
        max_age=settings.LANGUAGE_COOKIE_AGE,
        path=settings.LANGUAGE_COOKIE_PATH,
        domain=settings.LANGUAGE_COOKIE_DOMAIN,
        secure=settings.LANGUAGE_COOKIE_SECURE,
        httponly=settings.LANGUAGE_COOKIE_HTTPONLY,
        samesite=settings.LANGUAGE_COOKIE_SAMESITE,
    )
    return response


urlpatterns = [
    path("", home, name="home"),
    path("admin/", admin.site.urls),
    path("lang/", set_lang, name="lang"),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
```

(Static-files block dropped: WhiteNoise will handle them; Django dev server handles them automatically when `DEBUG=True`.)

- [ ] **Step 5.5: Run full test suite**

```bash
pytest -v
```

Expected: all PASS.

- [ ] **Step 5.6: Commit**

```bash
git add mycalendar/views.py django_myical/urls.py mycalendar/tests/test_smoke.py
git commit -m "refactor: move home view to views.py, harden set_lang, drop duplicate save()"
```

---

### Task 6: Secure file upload (size, extension, MIME, content sanity)

**Files:**
- Create: `mycalendar/validators.py`
- Modify: `mycalendar/models.py`
- Modify: `mycalendar/forms.py`
- Create: `mycalendar/tests/test_validators.py`

- [ ] **Step 6.1: Write failing validator tests**

`mycalendar/tests/test_validators.py`:

```python
import pytest
from django.core.exceptions import ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile

from mycalendar.validators import validate_csv_upload


def _f(name, data, ct="text/csv"):
    return SimpleUploadedFile(name, data, content_type=ct)


def test_accepts_small_csv():
    validate_csv_upload(_f("ok.csv", b"31/12/2021;21.30;A;B;;\n"))


def test_rejects_wrong_extension():
    with pytest.raises(ValidationError, match="extension"):
        validate_csv_upload(_f("evil.exe", b"data"))


def test_rejects_oversized():
    big = b"a" * (1024 * 1024 + 1)  # 1 MiB + 1 byte
    with pytest.raises(ValidationError, match="size"):
        validate_csv_upload(_f("big.csv", big))


def test_rejects_wrong_content_type():
    with pytest.raises(ValidationError, match="content type"):
        validate_csv_upload(_f("ok.csv", b"data", ct="application/x-msdownload"))


def test_rejects_non_text_bytes():
    with pytest.raises(ValidationError, match="binary"):
        validate_csv_upload(_f("nul.csv", b"\x00\x01\x02\xff", ct="text/csv"))
```

- [ ] **Step 6.2: Run to verify failure**

```bash
pytest mycalendar/tests/test_validators.py -v
```

Expected: FAIL (`ImportError`).

- [ ] **Step 6.3: Implement `mycalendar/validators.py`**

```python
from django.core.exceptions import ValidationError

MAX_UPLOAD_BYTES = 1024 * 1024  # 1 MiB
ALLOWED_EXTENSIONS = {".csv", ".txt"}
ALLOWED_CONTENT_TYPES = {"text/csv", "text/plain", "application/csv", "application/vnd.ms-excel"}


def validate_csv_upload(uploaded_file) -> None:
    name = uploaded_file.name.lower()
    if not any(name.endswith(ext) for ext in ALLOWED_EXTENSIONS):
        raise ValidationError("unsupported file extension; expected .csv or .txt")

    if uploaded_file.size > MAX_UPLOAD_BYTES:
        raise ValidationError(f"file size exceeds {MAX_UPLOAD_BYTES} bytes")

    ct = (uploaded_file.content_type or "").lower()
    if ct and ct not in ALLOWED_CONTENT_TYPES:
        raise ValidationError(f"unsupported content type: {ct}")

    head = uploaded_file.read(4096)
    uploaded_file.seek(0)
    if b"\x00" in head:
        raise ValidationError("file appears to be binary, not text")
    try:
        head.decode("utf-8")
    except UnicodeDecodeError:
        try:
            head.decode("latin-1")
        except UnicodeDecodeError as exc:
            raise ValidationError("file is not valid UTF-8 or Latin-1 text") from exc
```

- [ ] **Step 6.4: Run validator tests, verify pass**

```bash
pytest mycalendar/tests/test_validators.py -v
```

Expected: PASS (5/5).

- [ ] **Step 6.5: Wire validator into the model**

Edit `mycalendar/models.py`, change the `document` field:

```python
from mycalendar.validators import validate_csv_upload

# inside class MyCalendar:
document = models.FileField(upload_to="documents/", validators=[validate_csv_upload])
```

- [ ] **Step 6.6: Make migration for the validator change**

```bash
python manage.py makemigrations mycalendar
```

Expected: a `0004_*.py` migration is created.

- [ ] **Step 6.7: Run full test suite**

```bash
pytest -v
```

Expected: all PASS. The form inherits the validator automatically via ModelForm.

- [ ] **Step 6.8: Commit**

```bash
git add mycalendar/validators.py mycalendar/models.py mycalendar/migrations/0004_*.py mycalendar/tests/test_validators.py
git commit -m "feat(security): validate CSV uploads (size, ext, content-type, binary check)"
```

---

### Task 7: Inject DEBUG and STATE into template context

The `STATE` ribbon in `base.html` currently never resolves. Either remove it or wire a context processor.

**Files:**
- Create: `django_myical/context_processors.py`
- Modify: `django_myical/settings.py`
- Create: `mycalendar/tests/test_context.py`

- [ ] **Step 7.1: Failing test**

`mycalendar/tests/test_context.py`:

```python
import pytest
from django.urls import reverse


@pytest.mark.django_db
def test_state_ribbon_renders_when_debug(client, settings):
    settings.DEBUG = True
    settings.STATE = "INT"
    response = client.get(reverse("home"))
    assert b"INT" in response.content
```

- [ ] **Step 7.2: Run to verify failure**

```bash
pytest mycalendar/tests/test_context.py -v
```

Expected: FAIL.

- [ ] **Step 7.3: Add context processor**

`django_myical/context_processors.py`:

```python
from django.conf import settings


def site_state(request):
    return {"DEBUG": settings.DEBUG, "STATE": getattr(settings, "STATE", "")}
```

- [ ] **Step 7.4: Register it in `django_myical/settings.py`**

In the `TEMPLATES[0]["OPTIONS"]["context_processors"]` list, append:

```python
"django_myical.context_processors.site_state",
```

- [ ] **Step 7.5: Run test, verify pass**

```bash
pytest mycalendar/tests/test_context.py -v
```

Expected: PASS.

- [ ] **Step 7.6: Commit**

```bash
git add django_myical/context_processors.py django_myical/settings.py mycalendar/tests/test_context.py
git commit -m "fix: inject DEBUG/STATE into template context so the dev ribbon actually shows"
```

---

## Phase 3: Settings hardening

### Task 8: Move secrets and per-env settings to environment via django-environ

**Files:**
- Modify: `django_myical/settings.py`
- Create: `.env.example`
- Modify: `.gitignore`

- [ ] **Step 8.1: Append `.env` patterns to `.gitignore`**

```
.env
.env.*
!.env.example
```

- [ ] **Step 8.2: Create `.env.example`**

```
DJANGO_SECRET_KEY=replace-me-with-django-utils-crypto-get_random_secret_key
DJANGO_DEBUG=False
DJANGO_ALLOWED_HOSTS=ical.foxugly.com
DJANGO_SITE_DOMAIN=ical.foxugly.com
DJANGO_STATE=PROD
DATABASE_URL=sqlite:///db.sqlite3
DJANGO_CSRF_TRUSTED_ORIGINS=https://ical.foxugly.com
```

- [ ] **Step 8.3: Rewrite `django_myical/settings.py`** (key sections only — keep the rest unchanged)

Top of file:

```python
from pathlib import Path

import environ
from django.utils.translation import gettext_lazy as _

BASE_DIR = Path(__file__).resolve().parent.parent

env = environ.Env(
    DJANGO_DEBUG=(bool, False),
    DJANGO_ALLOWED_HOSTS=(list, []),
    DJANGO_CSRF_TRUSTED_ORIGINS=(list, []),
)
environ.Env.read_env(BASE_DIR / ".env")

SECRET_KEY = env("DJANGO_SECRET_KEY")
DEBUG = env("DJANGO_DEBUG")
ALLOWED_HOSTS = env("DJANGO_ALLOWED_HOSTS")
SITE_DOMAIN = env("DJANGO_SITE_DOMAIN", default="localhost")
STATE = env("DJANGO_STATE", default="DEV")
CSRF_TRUSTED_ORIGINS = env("DJANGO_CSRF_TRUSTED_ORIGINS")

DATABASES = {"default": env.db("DATABASE_URL", default=f"sqlite:///{BASE_DIR / 'db.sqlite3'}")}
```

Replace the existing `SECRET_KEY`, `DEBUG`, `STATE`, `ALLOWED_HOSTS`, `DATABASES`, and the bottom `SITE_DOMAIN = "localhost"` placeholder added in Task 4.

Append below existing settings:

```python
# Security headers — only enforce HTTPS-related ones outside DEBUG.
if not DEBUG:
    SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
    SECURE_SSL_REDIRECT = True
    SECURE_HSTS_SECONDS = 60 * 60 * 24 * 30  # 30 days; bump to 1 year once stable
    SECURE_HSTS_INCLUDE_SUBDOMAINS = False
    SECURE_HSTS_PRELOAD = False
    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SECURE = True
    SECURE_CONTENT_TYPE_NOSNIFF = True
    SECURE_REFERRER_POLICY = "same-origin"
    X_FRAME_OPTIONS = "DENY"

# WhiteNoise for static files.
STATIC_URL = "/static/"
STATIC_ROOT = BASE_DIR / "staticfiles"
STATICFILES_DIRS = [BASE_DIR / "static"]
STORAGES = {
    "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
    "staticfiles": {"BACKEND": "whitenoise.storage.CompressedManifestStaticFilesStorage"},
}

# Logging — surface ICS build failures in prod logs.
LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "handlers": {
        "console": {"class": "logging.StreamHandler"},
    },
    "root": {"handlers": ["console"], "level": "INFO"},
    "loggers": {
        "mycalendar": {"handlers": ["console"], "level": "INFO", "propagate": False},
    },
}

# File upload limits.
DATA_UPLOAD_MAX_MEMORY_SIZE = 1024 * 1024  # 1 MiB
FILE_UPLOAD_MAX_MEMORY_SIZE = 1024 * 1024
```

- [ ] **Step 8.4: Add WhiteNoise middleware** (in `django_myical/settings.py` MIDDLEWARE list, right after SecurityMiddleware):

```python
"whitenoise.middleware.WhiteNoiseMiddleware",
```

- [ ] **Step 8.5: Create local `.env` for development**

```bash
cp .env.example .env
python -c "from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())"
# paste the output into DJANGO_SECRET_KEY in .env
# set DJANGO_DEBUG=True for local dev
# set DJANGO_ALLOWED_HOSTS=127.0.0.1,localhost
# set DJANGO_SITE_DOMAIN=localhost:8000
```

- [ ] **Step 8.6: Run full test suite**

```bash
pytest -v
```

Expected: all PASS. If a test breaks because settings are missing, set them via `pytest.ini` `env` plugin or in `conftest.py`.

If failures, add to `conftest.py`:

```python
import os

os.environ.setdefault("DJANGO_SECRET_KEY", "test-secret-key-not-for-production")
os.environ.setdefault("DJANGO_DEBUG", "True")
os.environ.setdefault("DJANGO_ALLOWED_HOSTS", "testserver,localhost")
os.environ.setdefault("DJANGO_SITE_DOMAIN", "localhost")
```

- [ ] **Step 8.7: Verify dev server boots**

```bash
python manage.py check --deploy
python manage.py runserver
```

Expected: server starts, no warnings related to SECRET_KEY/DEBUG/ALLOWED_HOSTS leaking. The `--deploy` check may flag HSTS settings — those only apply when `DEBUG=False`, so toggle and re-check.

- [ ] **Step 8.8: Commit**

```bash
git add django_myical/settings.py .env.example .gitignore conftest.py
git commit -m "feat(security): externalize settings to env, harden HTTPS/cookie/HSTS, add WhiteNoise"
```

- [ ] **Step 8.9: Rotate the leaked SECRET_KEY (manual)**

The old `SECRET_KEY` lived in git history. Generate a new one (already done in Step 8.5). When deploying, set `DJANGO_SECRET_KEY` to a fresh value via the production `.env` so old sessions/CSRF tokens become invalid (acceptable per "downtime ok").

---

### Task 9: Make migrations and verify against backed-up prod DB locally

**Files:**
- (no new files — just verifying)

- [ ] **Step 9.1: Restore the prod backup into a local copy**

```bash
cp backups/db.sqlite3.backup-* db.sqlite3.prodcopy
DJANGO_DATABASE_URL=sqlite:///db.sqlite3.prodcopy python manage.py migrate --plan
```

Expected: migrations 0001–0004 (or whatever number was generated in Task 6) listed as pending. The `0003` migration that was untracked in git is now committed via Task 1's diff.

- [ ] **Step 9.2: Apply migrations to the prod copy**

```bash
DATABASE_URL=sqlite:///db.sqlite3.prodcopy python manage.py migrate
```

Expected: all migrations apply cleanly. No data loss.

- [ ] **Step 9.3: Smoke-check existing rows still work**

```bash
DATABASE_URL=sqlite:///db.sqlite3.prodcopy python manage.py shell -c "
from mycalendar.models import MyCalendar
print('count:', MyCalendar.objects.count())
for obj in MyCalendar.objects.all()[:3]:
    print(obj.pk, obj.name, bool(obj.ics))
"
```

Expected: same count as in prod, no errors.

- [ ] **Step 9.4: Re-run a regeneration on one row**

```bash
DATABASE_URL=sqlite:///db.sqlite3.prodcopy python manage.py shell -c "
from mycalendar.models import MyCalendar
obj = MyCalendar.objects.first()
print('regen:', obj.get_ics())
"
```

Expected: returns `True` and updates `obj.ics`. If `False`, check logs — most likely a CSV that legitimately fails the new validators (e.g. odd encoding); in which case the original `media/` file is still on disk untouched.

- [ ] **Step 9.5: Cleanup**

```bash
rm db.sqlite3.prodcopy
```

(No commit — verification only.)

---

## Phase 4: Production deployment

### Task 10: Add gunicorn config and a systemd unit

**Files:**
- Create: `deploy/gunicorn.conf.py`
- Create: `deploy/django-ical.service`
- Create: `deploy/nginx.conf`
- Create: `deploy/README.md`

- [ ] **Step 10.1: Write `deploy/gunicorn.conf.py`**

```python
bind = "127.0.0.1:8000"
workers = 3
worker_class = "sync"
timeout = 30
accesslog = "-"
errorlog = "-"
```

- [ ] **Step 10.2: Write `deploy/django-ical.service`**

```ini
[Unit]
Description=django-ical gunicorn
After=network.target

[Service]
User=ec2-user
Group=ec2-user
WorkingDirectory=/srv/django-ical
EnvironmentFile=/srv/django-ical/.env
ExecStart=/srv/django-ical/.venv/bin/gunicorn django_myical.wsgi:application -c deploy/gunicorn.conf.py
Restart=on-failure
RestartSec=3

[Install]
WantedBy=multi-user.target
```

- [ ] **Step 10.3: Write `deploy/nginx.conf`** (server block to drop into `/etc/nginx/conf.d/`)

```
server {
    listen 80;
    server_name ical.foxugly.com;
    return 301 https://$host$request_uri;
}

server {
    listen 443 ssl http2;
    server_name ical.foxugly.com;

    ssl_certificate     /etc/letsencrypt/live/ical.foxugly.com/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/ical.foxugly.com/privkey.pem;

    client_max_body_size 2M;

    location /media/ {
        alias /srv/django-ical/media/;
    }

    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    }
}
```

(WhiteNoise serves `/static/` directly from gunicorn — no nginx alias needed for it.)

- [ ] **Step 10.4: Write `deploy/README.md`** with the manual deploy steps (see Task 11).

- [ ] **Step 10.5: Commit**

```bash
git add deploy/
git commit -m "chore(deploy): gunicorn + systemd + nginx configs"
```

---

### Task 11: Cut the new prod release

These steps run on the EC2 box. Done manually with rollback points.

- [ ] **Step 11.1: Stop the old service**

Whatever it is today (`sudo systemctl stop nginx`, kill the runserver process, etc). This is when prod goes dark.

- [ ] **Step 11.2: Move the old install aside**

```bash
sudo mv /path/to/old/django-ical /srv/django-ical.old-$(date +%Y%m%d)
```

- [ ] **Step 11.3: Clone the upgraded repo**

```bash
sudo git clone https://github.com/<user>/django-ical.git /srv/django-ical
sudo chown -R ec2-user:ec2-user /srv/django-ical
cd /srv/django-ical
```

- [ ] **Step 11.4: Restore prod data into the new tree**

```bash
cp /srv/django-ical.old-*/db.sqlite3 /srv/django-ical/db.sqlite3
cp -r /srv/django-ical.old-*/media /srv/django-ical/media
```

- [ ] **Step 11.5: Install Python 3.12 if missing, create venv, install deps**

```bash
# Amazon Linux 2023:
sudo dnf install -y python3.12
python3.12 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
```

- [ ] **Step 11.6: Create `/srv/django-ical/.env`**

```bash
cp .env.example .env
# edit .env:
#   DJANGO_SECRET_KEY=<output of get_random_secret_key>
#   DJANGO_DEBUG=False
#   DJANGO_ALLOWED_HOSTS=ical.foxugly.com
#   DJANGO_SITE_DOMAIN=ical.foxugly.com
#   DJANGO_STATE=PROD
#   DJANGO_CSRF_TRUSTED_ORIGINS=https://ical.foxugly.com
chmod 600 .env
```

- [ ] **Step 11.7: Run migrations and collectstatic**

```bash
python manage.py migrate
python manage.py collectstatic --noinput
python manage.py check --deploy
```

Expected: migrate applies cleanly (idempotent on prod data); collectstatic populates `staticfiles/`; `check --deploy` reports no security warnings.

- [ ] **Step 11.8: Install systemd unit and start service**

```bash
sudo cp deploy/django-ical.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now django-ical
sudo systemctl status django-ical
```

Expected: `active (running)`.

- [ ] **Step 11.9: Install nginx config and certbot cert**

```bash
sudo cp deploy/nginx.conf /etc/nginx/conf.d/django-ical.conf
sudo nginx -t
sudo systemctl reload nginx

# If no cert yet:
sudo dnf install -y certbot python3-certbot-nginx
sudo certbot --nginx -d ical.foxugly.com --redirect --non-interactive --agree-tos -m <your-email>
```

Expected: nginx reloads cleanly; certbot returns a valid cert; HTTPS works at `https://ical.foxugly.com`.

- [ ] **Step 11.10: Smoke test in browser**

Visit `https://ical.foxugly.com`, upload a small test CSV, confirm the `.ics` file generates and the Facebook/Twitter/WhatsApp/mail/copy buttons all produce the right URLs (now under `https://ical.foxugly.com/media/ics/...`).

- [ ] **Step 11.11: Verify EC2 security group**

Ensure inbound is only 22 (your IP), 80, 443. No 8000 exposed (gunicorn binds to 127.0.0.1 anyway, but defense in depth).

- [ ] **Step 11.12: After 24h, archive the old install**

```bash
sudo tar -czf /srv/django-ical.old-archive.tar.gz /srv/django-ical.old-*
sudo rm -rf /srv/django-ical.old-*
```

---

## Phase 5: Bonus hardening (optional, do after prod is stable)

### Task 12: Add CI (GitHub Actions)

**Files:**
- Create: `.github/workflows/ci.yml`

- [ ] **Step 12.1: Write workflow**

```yaml
name: CI

on:
  push:
    branches: [master]
  pull_request:

jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: "3.12"
      - run: pip install -r requirements-dev.txt
      - run: cp .env.example .env && sed -i 's/replace-me.*/test-key/' .env
      - run: ruff check .
      - run: pytest -v
```

- [ ] **Step 12.2: Commit and push**

```bash
git add .github/workflows/ci.yml
git commit -m "ci: run ruff and pytest on push and PR"
git push
```

---

### Task 13: Generate translation files

The project declares `en`, `fr`, `nl` but ships no `locale/` directory.

- [ ] **Step 13.1: Generate**

```bash
mkdir locale
python manage.py makemessages -l fr -l nl
# edit the generated .po files in locale/fr/LC_MESSAGES and locale/nl/LC_MESSAGES
python manage.py compilemessages
```

- [ ] **Step 13.2: Commit**

```bash
git add locale/
git commit -m "i18n: generate fr and nl translation catalogs"
```

---

## Self-review checklist

- [x] **SECRET_KEY** rotated and externalized — Task 8
- [x] **DEBUG** off in prod via env — Task 8
- [x] **ALLOWED_HOSTS** scoped to `ical.foxugly.com` — Task 8
- [x] **HTTPS / HSTS / cookie flags** — Task 8
- [x] **CSRF_TRUSTED_ORIGINS** — Task 8
- [x] **File upload validators** (size, ext, MIME, binary) — Task 6
- [x] **CSV parsing fix** (out-of-range index, encoding) — Task 3 (uses UTF-8 with replace, accepts both date/time formats)
- [x] **Bare try/except** replaced with logging — Task 4
- [x] **`settings.WEBSITE`** missing → renamed to `SITE_DOMAIN`, defined — Tasks 4, 8
- [x] **`STATE` not in template context** — Task 7
- [x] **Home view in `urls.py`** — moved in Task 5
- [x] **Duplicate `instance.save()`** in `urls.py` — dropped in Task 5
- [x] **pytz → zoneinfo** — Tasks 3, 4
- [x] **Django 4.2 → 5.2** — Task 1
- [x] **Static files in prod** (WhiteNoise) — Task 8
- [x] **Prod data preserved** — pre-flight P1–P3 + Task 11 step 11.4
- [x] **Migrations apply cleanly to prod data** — Task 9 verifies locally first
- [x] **Tests for every behavior change** — Tasks 3, 4, 5, 6, 7

Tradeoffs/assumptions documented:
- SQLite kept (low volume per user). Migration to Postgres can be added later.
- Bootstrap 4 / FontAwesome via CDN kept (no SRI added) — out of scope for this plan; flagged as a future hardening item.
- jQuery 3.3.1 kept (used by `file-upload.js` and the copy-to-clipboard handler) — replacing with vanilla JS is out of scope.
- No CSP header added — out of scope; nginx `add_header Content-Security-Policy` is a one-line follow-up if desired.
- `STATE` left in template context to preserve the existing dev ribbon behavior, now correctly wired.
