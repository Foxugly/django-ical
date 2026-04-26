import os

os.environ.setdefault("DJANGO_SECRET_KEY", "test-secret-key-not-for-production")
os.environ.setdefault("DJANGO_DEBUG", "True")
os.environ.setdefault("DJANGO_ALLOWED_HOSTS", "testserver,localhost")
os.environ.setdefault("DJANGO_SITE_DOMAIN", "localhost")
os.environ.setdefault("DJANGO_CSRF_TRUSTED_ORIGINS", "http://localhost")
