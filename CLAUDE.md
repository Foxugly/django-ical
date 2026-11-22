# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project

Single-purpose Django web app (**ical.foxugly.com**) that converts an uploaded semicolon-delimited CSV
of events into a downloadable `.ics` (iCalendar) file, then exposes share links (Facebook, Twitter,
WhatsApp, mail, copy URL).

Stack: Python 3.12+, **Django 6.1**, `icalendar` 7, `django-widget-tweaks`, `django-environ`,
WhiteNoise, gunicorn, `psycopg`, `sentry-sdk`, django-otp (admin 2FA). Bootstrap 5.3 + FontAwesome 5
via jsDelivr (SRI). PostgreSQL in prod, SQLite in dev. Virtualenv in `.venv/`.

## Commands

Activate venv first (Windows bash): `source .venv/Scripts/activate`

- Install deps (two steps — `requirements.txt` is hash-pinned, and one hashed line puts a whole pip run in hash-checking mode):
  `pip install --require-hashes -r requirements.txt` then `pip install -r requirements-dev.txt`
- Change a dependency: edit `requirements.in` (runtime ranges) or `requirements-dev.in`, then regenerate the locks (`--universal`: Linux prod + Windows dev, Python 3.12+):
  `uv pip compile requirements.in --generate-hashes --universal --python-version 3.12 -o requirements.txt`
  and `uv pip compile requirements-dev.in --universal --python-version 3.12 -o requirements-dev.txt`.
  The deploy installs exactly the lock (`--require-hashes --no-deps` + `pip check`).
- Lint: `ruff check .` (config `ruff.toml`; CI gate)
- Tests: `pytest` (pytest-django; tests in `mycalendar/tests/`; `conftest.py` sets dev env defaults).
  CI runs them against PostgreSQL 16.
- Run dev server: `python manage.py runserver`
- Migrations: `python manage.py migrate` / `python manage.py makemigrations mycalendar`
- Translations (`locale/fr`, `locale/nl` exist): `python manage.py makemessages -l fr -l nl` then `compilemessages`

## Architecture

- `mycalendar/views.py` — `home` (GET/HEAD/POST): upload form, calls `instance.get_ics()` after save,
  renders `templates/model_form_upload.html` with the 5 most recent `MyCalendar` objects.
- `django_myical/urls.py` — routes `/`, `/health/` (`django_myical/health.py`), `/admin/`, `/lang/`.
  `set_lang` (language cookie) lives here; `next` only redirects same-site (`_safe_next_url`) and the
  cookie value is taken from `settings.LANGUAGES`, never the raw query string.
- `mycalendar/services/ics.py` — pure CSV→ICS conversion (no Django, no IO): rows
  `Date;Hour;Subject;detail;Address;`, dates `dd/mm/yyyy` or `yyyy-mm-dd`, times `hh:mm` or `hh.mm`.
- `mycalendar/models.py` — `MyCalendar.get_ics()` decodes the upload (UTF-8, `errors="replace"`), calls
  the service with `SITE_TIMEZONE` / `EVENT_DURATION_MINUTES`, logs failures (`logger.exception`) and
  returns `False` instead of raising. `get_ics_*_link` build share URLs from `SITE_DOMAIN`.
- `mycalendar/validators.py` — upload checks: extension `.csv`/`.txt`, size (`MAX_UPLOAD_BYTES`),
  content type, no binary content.
- `django_myical/context_processors.site_state` exposes `DEBUG` / `STATE` (environment ribbon in `base.html`).
- `common_tags.py` sits at the **repo root** and is registered as a template library in settings.
- Uploads land in `media/documents/` (CSV) and `media/ics/` (generated `.ics`); Django serves them only in DEBUG.
- `scripts/clean_import.py` + `deploy/import-data.sh` — one-time import of the historical data (done).

## Deploy

Push to `main` → `.github/workflows/ci.yml` (test, pip-audit, then OIDC → SSM deploy). The root steps
install units / nginx from root's bare mirror, then `deploy/ssm-deploy.sh` runs as `django` (pip from
the lock, migrate, collectstatic, restart `ical-gunicorn`). Never `git pull` on the box.
Units: `ical-env-fetch` (SSM `/ical/prod` → `/run/ical/.env`) + `ical-gunicorn` (`127.0.0.1:8002`).
Sentry project: `ical-backend-frontend`.

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
