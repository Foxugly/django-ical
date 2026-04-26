# Deploy — ical.foxugly.com

Target: Ubuntu, install path `/var/www/django_websites/django-ical/`, user `django:www-data`, stack nginx + gunicorn + systemd + Let's Encrypt.

Prerequisite: the `django` user exists on the host:
```bash
sudo useradd --system --no-create-home --shell /usr/sbin/nologin django
sudo usermod -aG www-data django
```

## Fresh install

```bash
# 1) Code
sudo mkdir -p /var/www/django_websites
sudo chown django:www-data /var/www/django_websites
sudo -u django git clone -b master https://github.com/Foxugly/django-ical.git /var/www/django_websites/django-ical

# 2) Setup (apt deps, venv, .env, migrate, collectstatic, systemd, nginx)
sudo bash /var/www/django_websites/django-ical/deploy/install.sh

# 3) HTTPS (after DNS A record points to this server)
sudo certbot --nginx -d ical.foxugly.com --redirect --non-interactive --agree-tos -m <YOUR_EMAIL>

# 4) Verify
curl -i https://ical.foxugly.com/
```

## Update

```bash
cd /var/www/django_websites/django-ical
sudo -u django git pull
sudo bash deploy/install.sh   # idempotent: re-pip, re-migrate, re-collectstatic, restart
```

## Import prod data (one-time)

The historical prod data (db.sqlite3 + media/) is filtered locally to remove webshell uploads, packaged into a tarball, then imported on the server.

```bash
# On your laptop (one-time)
python scripts/clean_import.py --src-dir <path-to-old-prod-backup> --dst-dir import-clean
tar czf import-clean.tar.gz -C import-clean .

# Copy to the EC2
scp import-clean.tar.gz ubuntu@<EC2_IP>:/tmp/

# On the EC2 — install the data (stops/restarts service, backs up existing db)
sudo bash /var/www/django_websites/django-ical/deploy/import-data.sh /tmp/import-clean.tar.gz
```

## Rollback

DNS-level: revert the A record `ical.foxugly.com` to the old server IP. Effective in ≤ TTL minutes.

DB-level: `import-data.sh` saves the previous `db.sqlite3` as `db.sqlite3.before-import-YYYYMMDD-HHMMSS` before overwriting. Restore with `mv` + `systemctl restart django-ical`.
