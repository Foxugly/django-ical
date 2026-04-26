# Deploy — ical.foxugly.com

## On your laptop

```bash
# 1) Filter prod data (one-time, after pulling the prod backup into ./import/)
python scripts/clean_import.py --src-dir import --dst-dir import-clean

# 2) Build the deploy bundle
bash scripts/build_bundle.sh
# Produces django-ical-deploy.tar.gz at the repo root.
```

## On the new EC2 (Ubuntu)

**Prerequisite — `django` user must exist before running install.sh.**
The service runs as `django:www-data`. If the user is absent, install.sh aborts with a clear message.
Create it once on a fresh host:

```bash
sudo useradd --system --no-create-home --shell /usr/sbin/nologin django
sudo usermod -aG www-data django
```

```bash
# 1) Copy the bundle
scp django-ical-deploy.tar.gz ubuntu@<NEW_EC2_IP>:/tmp/

# 2) Extract + install
ssh ubuntu@<NEW_EC2_IP>
sudo mkdir -p /var/www/django_websites/django-ical
sudo tar xzf /tmp/django-ical-deploy.tar.gz -C /var/www/django_websites/django-ical
sudo bash /var/www/django_websites/django-ical/deploy/install.sh

# 3) Point DNS A record ical.foxugly.com → <NEW_EC2_IP>

# 4) Issue HTTPS cert (after DNS propagates)
sudo certbot --nginx -d ical.foxugly.com --redirect --non-interactive --agree-tos -m <YOUR_EMAIL>

# 5) Verify
curl -I https://ical.foxugly.com/
```

## Update an existing install

If you bring up a new bundle later (after code changes), the install script is idempotent. Just extract over the same path and re-run:

```bash
sudo systemctl stop django-ical
sudo tar xzf /tmp/django-ical-deploy.tar.gz -C /var/www/django_websites/django-ical
sudo bash /var/www/django_websites/django-ical/deploy/install.sh
```

The install script will skip the venv recreate if it already exists (just `pip install -r requirements.txt` to pick up new deps), preserve the existing `.env`, and re-run `migrate` + `collectstatic`.

## Rollback

DNS-level: revert the A record `ical.foxugly.com` to the old server. Effective in ≤ TTL minutes.
