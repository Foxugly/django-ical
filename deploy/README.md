# Deploy runbook — ical.foxugly.com

Target: fresh AWS EC2 (Ubuntu 24.04 LTS), domain `ical.foxugly.com`, install path `/var/www/django_websites/django-ical/`, user `www-data`.

## Pre-requisites

- Old server: data already snapshotted to `import/` locally and filtered with `scripts/clean_import.py` to produce `import-clean/`.
- Tarball: `tar czf import-clean.tar.gz import-clean/` produced locally.
- DNS A record `ical.foxugly.com` will be cut over to the new server's IP at the swap step (or use `/etc/hosts` override on your laptop to validate before DNS swap).

## On the new EC2 (one-time setup)

```bash
# 1) System packages
sudo apt update
sudo apt install -y python3.12 python3.12-venv git nginx certbot python3-certbot-nginx

# 2) Code
sudo mkdir -p /var/www/django_websites
sudo chown www-data:www-data /var/www/django_websites
cd /var/www/django_websites
sudo -u www-data git clone <REPO_URL> django-ical
cd django-ical
sudo -u www-data git checkout upgrade/django-5

# 3) venv + deps
sudo -u www-data python3.12 -m venv .venv
sudo -u www-data .venv/bin/pip install --upgrade pip
sudo -u www-data .venv/bin/pip install -r requirements.txt

# 4) Restore data from the local tarball
# (from your laptop): scp import-clean.tar.gz ubuntu@<NEW_EC2_IP>:/tmp/
# then on the EC2:
cd /tmp && tar xzf import-clean.tar.gz
sudo mv /tmp/import-clean/db.sqlite3 /var/www/django_websites/django-ical/db.sqlite3
sudo mv /tmp/import-clean/media /var/www/django_websites/django-ical/media
sudo chown -R www-data:www-data /var/www/django_websites/django-ical/db.sqlite3 /var/www/django_websites/django-ical/media

# 5) Production .env
cd /var/www/django_websites/django-ical
sudo -u www-data cp .env.example .env
sudo -u www-data .venv/bin/python -c "from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())"
# Edit .env (sudo -u www-data nano .env):
#   DJANGO_SECRET_KEY=<output above>
#   DJANGO_DEBUG=False
#   DJANGO_ALLOWED_HOSTS=ical.foxugly.com
#   DJANGO_SITE_DOMAIN=ical.foxugly.com
#   DJANGO_STATE=PROD
#   DATABASE_URL=sqlite:////var/www/django_websites/django-ical/db.sqlite3
#   DJANGO_CSRF_TRUSTED_ORIGINS=https://ical.foxugly.com
sudo chmod 600 .env

# 6) Migrate + collectstatic
sudo -u www-data .venv/bin/python manage.py migrate
sudo -u www-data .venv/bin/python manage.py collectstatic --noinput
sudo -u www-data .venv/bin/python manage.py check --deploy

# 7) systemd unit
sudo cp deploy/django-ical.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now django-ical
sudo systemctl status django-ical   # expect: active (running)

# 8) nginx + Let's Encrypt
sudo cp deploy/nginx.conf /etc/nginx/sites-available/django-ical
sudo ln -sf /etc/nginx/sites-available/django-ical /etc/nginx/sites-enabled/
sudo rm -f /etc/nginx/sites-enabled/default
sudo nginx -t && sudo systemctl reload nginx

# 9) Cert (DNS must point to this server first, OR use --webroot challenge)
sudo certbot --nginx -d ical.foxugly.com --redirect --non-interactive --agree-tos -m <YOUR_EMAIL>

# 10) Smoke test
curl -I https://ical.foxugly.com/   # expect 200 OK
```

## DNS cutover

Update the A record `ical.foxugly.com` → new EC2 public IP. TTL ≤ 5 min recommended for fast rollback.

## Updates (subsequent deploys)

```bash
cd /var/www/django_websites/django-ical
sudo -u www-data git pull
sudo -u www-data .venv/bin/pip install -r requirements.txt
sudo -u www-data .venv/bin/python manage.py migrate
sudo -u www-data .venv/bin/python manage.py collectstatic --noinput
sudo systemctl restart django-ical
```

## Rollback

DNS-level: revert the A record to the old server. Effective in <5 min if TTL was low.
