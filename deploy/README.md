# Deploy runbook — ical.foxugly.com

Production target: AWS EC2 (Amazon Linux 2023), domain `ical.foxugly.com`, install path `/srv/django-ical`.

## Prerequisites on the EC2 host

- Python 3.12+ installed (`sudo dnf install -y python3.12`).
- nginx installed and running (`sudo dnf install -y nginx && sudo systemctl enable --now nginx`).
- A DNS A record points `ical.foxugly.com` to the EC2 instance's public IP.
- Security group allows inbound 22 (your IP), 80, 443 only.

## First-time deploy (or upgrade from old install)

```bash
# 1) Stop the old service (whatever it is — runserver, old systemd unit, etc.)
sudo systemctl stop nginx   # if needed
# kill any lingering python processes from the old setup

# 2) Move the old install aside (preserves data on disk in case rollback is needed)
sudo mv /path/to/old/django-ical /srv/django-ical.old-$(date +%Y%m%d)

# 3) Clone the upgraded repo
sudo git clone https://github.com/<your-user>/django-ical.git /srv/django-ical
sudo chown -R ec2-user:ec2-user /srv/django-ical
cd /srv/django-ical
git checkout upgrade/django-5   # until merged to master

# 4) Restore prod data
cp /srv/django-ical.old-*/db.sqlite3 /srv/django-ical/db.sqlite3
cp -r /srv/django-ical.old-*/media /srv/django-ical/media

# 5) Set up the venv
python3.12 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt

# 6) Create the production .env
cp .env.example .env
# Generate a fresh SECRET_KEY:
python -c "from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())"
# Edit .env and set:
#   DJANGO_SECRET_KEY=<output of the line above>
#   DJANGO_DEBUG=False
#   DJANGO_ALLOWED_HOSTS=ical.foxugly.com
#   DJANGO_SITE_DOMAIN=ical.foxugly.com
#   DJANGO_STATE=PROD
#   DATABASE_URL=sqlite:////srv/django-ical/db.sqlite3
#   DJANGO_CSRF_TRUSTED_ORIGINS=https://ical.foxugly.com
chmod 600 .env

# 7) Migrate and collect static
python manage.py migrate
python manage.py collectstatic --noinput
python manage.py check --deploy   # should print "0 issues"

# 8) Install systemd unit
sudo cp deploy/django-ical.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now django-ical
sudo systemctl status django-ical   # expect: active (running)

# 9) Install nginx config + Let's Encrypt cert
sudo cp deploy/nginx.conf /etc/nginx/conf.d/django-ical.conf
sudo nginx -t   # syntax check
sudo systemctl reload nginx

# If no cert yet:
sudo dnf install -y certbot python3-certbot-nginx
sudo certbot --nginx -d ical.foxugly.com --redirect --non-interactive --agree-tos -m rvilain@foxugly.com

# 10) Smoke test
curl -I https://ical.foxugly.com/   # expect 200 OK
# Then load in a browser, upload a small CSV, confirm the .ics file generates.

# 11) After 24h of stability, archive the old install
sudo tar -czf /srv/django-ical.old-archive.tar.gz /srv/django-ical.old-*
sudo rm -rf /srv/django-ical.old-*
```

## Updates (subsequent deploys)

```bash
cd /srv/django-ical
git pull
source .venv/bin/activate
pip install -r requirements.txt
python manage.py migrate
python manage.py collectstatic --noinput
sudo systemctl restart django-ical
```

## Rollback

The old install lives at `/srv/django-ical.old-YYYYMMDD`. To roll back:

```bash
sudo systemctl stop django-ical
sudo mv /srv/django-ical /srv/django-ical.failed
sudo mv /srv/django-ical.old-YYYYMMDD /srv/django-ical
# Restart whatever the old service was.
```
