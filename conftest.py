import os

os.environ.setdefault("SECRET_KEY", "test-secret-key-not-for-production")
os.environ.setdefault("DEBUG", "True")
os.environ.setdefault("ALLOWED_HOSTS", "testserver,localhost")
os.environ.setdefault("SITE_DOMAIN", "localhost")
os.environ.setdefault("CSRF_TRUSTED_ORIGINS", "http://localhost")
