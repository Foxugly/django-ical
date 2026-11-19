# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project

Single-purpose Django 4.2 web app that converts an uploaded semicolon-delimited CSV of events into a downloadable `.ics` (iCalendar) file, then exposes share links (Facebook, Twitter, WhatsApp, mail, copy URL).

Stack: Django 4.2, `icalendar` 4.0.6, `django-widget-tweaks`, SQLite, Bootstrap 4 / FontAwesome via CDN. Python virtualenv lives in `.venv/` (also a legacy `venv/`).

## Commands

Activate venv first (Windows bash): `source .venv/Scripts/activate`

- Install deps: `pip install -r requirements.txt`
- Run dev server: `python manage.py runserver`
- Apply migrations: `python manage.py migrate`
- Make migrations after model changes: `python manage.py makemigrations mycalendar`
- Create admin user: `python manage.py createsuperuser`
- Run tests: `python manage.py test` (single app: `python manage.py test mycalendar`; `mycalendar/tests.py` is currently empty)
- Generate translation files: `python manage.py makemessages -l fr -l nl` then `compilemessages` (no `locale/` directory exists yet; create one before running)

## Architecture

The project is intentionally small — most logic lives in two files.

- `django_myical/urls.py` — contains the **home view inline** (not in `mycalendar/views.py`, which is empty). The `home` function handles both GET and POST of the upload form, calls `instance.get_ics()` to generate the calendar after save, and renders `templates/model_form_upload.html` with the 5 most recent `MyCalendar` objects. Also defines `set_lang` for the i18n language cookie switcher.
- `mycalendar/models.py` — `MyCalendar` model owns the CSV→ICS conversion in `get_ics()`. It reads the uploaded `document` FileField (latin-1 encoded), parses each line as `Date;Hour;Subject;detail;Address;`, supports two date formats (`dd/mm/yyyy` or `yyyy-mm-dd`) and two time separators (`.` or `:`), hardcodes timezone `Europe/Brussels`, sets event duration to 1h30, and writes the result via `self.ics.save(..., ContentFile(cal.to_ical()))`. The model also exposes `get_ics_*_link` methods that build social share URLs; `get_ics_full_url` depends on a `settings.WEBSITE` constant that is **not defined** in `settings.py` — that method will raise unless `WEBSITE` is added.
- `templates/model_form_upload.html` — single-page UI: upload form on the left, list of recent calendars with share buttons on the right, CSV format tutorial at the bottom.
- `common_tags.py` — sits at the **repo root** (not inside an app) and is registered as a template library via `TEMPLATES[0]['OPTIONS']['libraries']` in settings. Provides `hash`, `dict`, `verbose_name`, `app_name` filters.
- Uploads land in `media/documents/` (input CSV) and `media/ics/` (generated `.ics`). Both are served by Django in DEBUG mode only.

## Things to know before changing code

- `get_ics()` wraps everything in a bare `try/except` that swallows errors and prints `"error"` to stdout — debugging parse failures requires removing or narrowing that block.
- CSV parsing is positional and unforgiving: `len(vec) >= 3` gates event creation, but the code then unconditionally indexes `vec[3]` (line 52) so rows with exactly 3 fields will crash inside the swallowed try.
- The home view is in `urls.py`, not `views.py`. Don't add a duplicate.
- `SECRET_KEY` and `DEBUG=True` are committed in `settings.py` — treat this as a dev-only project unless deploying with overrides.
- Languages declared: `en`, `fr`, `nl` (Dutch). `LocaleMiddleware` is enabled but no `locale/` directory exists in the repo yet — `makemessages` will need to be run first.
- `STATE` (settings.py) is a custom flag (`INT`/`ACC`/`PROD`) shown as a ribbon in `base.html` when `DEBUG` is true. It is **not** wired to a context processor, so the template tag `{{ STATE }}` only resolves if you pass it through manually.

## Environment

All runtime config is in `.env` (see `.env.example`). Key env vars:
- `SECRET_KEY` (required)
- `DEBUG`, `ALLOWED_HOSTS`, `SITE_DOMAIN`, `CSRF_TRUSTED_ORIGINS`
- `MAX_UPLOAD_BYTES`, `EVENT_DURATION_MINUTES`, `SITE_TIMEZONE`
- `HSTS_SECONDS`, `HSTS_INCLUDE_SUBDOMAINS`, `HSTS_PRELOAD`
- `DJANGO_ENV` (environment ribbon / Sentry env), `SENTRY_DSN` (optional)
- `DB_*` 6-var convention (`DB_ENGINE`/`DB_NAME`/`DB_USER`/`DB_PASSWORD`/`DB_HOST`/`DB_PORT`) — prod = box-local PostgreSQL (OPERATIONS.md §3.13). `DATABASE_URL` is still honoured as an override (used by the `clean_import` tooling/tests); unset → local SQLite.

## Admin 2FA

`/admin/` requires a TOTP second factor for **every** staff account (django-otp 1.7.5 + qrcode 8.2,
app `admin_2fa/`, ported from the fleet reference Poker_server). The public pages (`/`, `/lang/`,
`/health/`) see nothing of it.

- **Wiring**: `"admin_2fa.apps.OTPAdminConfig"` *replaces* `"django.contrib.admin"` (it makes
  `admin.site` an `Admin2FASite`, whose `has_permission` also needs `user.is_verified()`); plus
  `django_otp`, `otp_totp`, `otp_static`, `admin_2fa` in INSTALLED_APPS and
  `django_otp.middleware.OTPMiddleware` right after `AuthenticationMiddleware`. `OTP_TOTP_ISSUER` is
  the label in the authenticator app. A missing piece fails `manage.py check` (`admin_2fa.E001-E004`).
  A custom `AdminSite` subclass must inherit `admin_2fa.sites.Admin2FASite`.
- **Flow**: password on `/admin/login/` -> `/admin/2fa/setup/` (first time: QR code + key, confirm one
  code, 10 single-use backup codes shown **once**) or `/admin/2fa/verify/` (TOTP code or a backup
  code). Server-rendered admin templates, CSRF, `never_cache`, no inline script/style.
- **Brute force**: django-otp throttles each device (1 s, 2 s, 4 s... after each wrong code) and nginx
  puts `/admin/2fa/` in the same `ical_admin_login` zone as the login (10 r/min per IP).
- **Lost phone / locked out** (on the box, as `ical-gunicorn` would run it):

  ```bash
  sudo systemd-run --wait --pipe --quiet --uid=django --gid=www-data \
    -p EnvironmentFile=/run/ical/.env -p WorkingDirectory=/var/www/django_websites/django-ical \
    /var/www/django_websites/django-ical/.venv/bin/python manage.py admin_2fa_reset <username>
  ```

  deletes the user's devices (re-enrolment at the next admin login); `--unlock` only clears the delay.
- **Tests on admin pages**: use `admin_2fa.testing.force_admin_login(client, user)`, not
  `client.force_login` (the admin would redirect to the second factor).
- **Secrets**: never log or send to Sentry the TOTP key, the QR code or a backup code -- the views keep
  them in `Redacted` wrappers and the form field is named `token` (scrubbed by Sentry).
