# GWHelpdesk

GWHelpdesk provides a role-oriented web interface for common GroupWise user and group administration tasks. It communicates with the GroupWise Admin REST API and does not modify GroupWise databases directly.

This branch is the Python 3 modernization of the original Django 1.10 application.

## Supported runtime

- Python 3.10 or newer
- Django 5.2 LTS
- A GroupWise system exposing the HTTPS Admin REST service
- SQLite for local application configuration and administrator records
- Gunicorn and a reverse proxy such as nginx for production

The current code must be validated against the exact GroupWise release used in production. Automated tests mock or avoid the GroupWise API and do not replace testing against a non-production GroupWise system.

## Quick start

```bash
python3 gwhelpdesk_install.py
source .venv/bin/activate
python manage.py setup
python manage.py runserver 0.0.0.0:8000
```

The installer creates a virtual environment, installs `requirements.txt`, runs database migrations, and executes Django's configuration checks. It does not install OS packages or make changes under `/etc`.

A manual installation is equivalent:

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
python manage.py migrate
python manage.py setup
python manage.py check
```

## Configuration

Set these values in systemd, Docker Compose, or the service environment:

- `DJANGO_SECRET_KEY`: required for production.
- `DJANGO_ALLOWED_HOSTS`: comma-separated hostnames or IP addresses.
- `DJANGO_CSRF_TRUSTED_ORIGINS`: comma-separated HTTPS origins.
- `DJANGO_COOKIE_SECURE=true`: use when the site is published over HTTPS.
- `GW_VERIFY_TLS=true`: verifies the GroupWise Admin service certificate.
- `REQUESTS_CA_BUNDLE`: internal CA bundle when GroupWise uses a private CA.
- `GW_ADMIN_PASSWORD`: optional service environment override for the password stored in SQLite.

Disabling GroupWise TLS verification should be limited to temporary testing:

```bash
export GW_VERIFY_TLS=false
```

## Production example

```bash
source .venv/bin/activate
python manage.py migrate
python manage.py collectstatic --noinput
python manage.py check --deploy
gunicorn --workers 3 --bind 127.0.0.1:8000 gwhelp.wsgi:application
```

The original SysV init and SLES 12 package automation are deliberately no longer part of `manage.py setup`. Service configuration belongs in a systemd unit or container deployment.

## Validation

```bash
python -m compileall -q .
python manage.py check
python manage.py makemigrations --check --dry-run
python manage.py test
```

GitHub Actions runs these checks on Python 3.10, 3.12, and 3.13.

## Upgrade notes

- Existing local administrator password hashes created by the old fixed-salt method may need to be reset with `python manage.py setup`; newly created passwords use Django's current password hasher.
- Retain the existing SQLite database and run `python manage.py migrate`.
- Legacy templates using `{% load staticfiles %}` are supported by a temporary compatibility template-tag module.
- GroupWise credentials should ultimately be moved from SQLite to a secrets manager or service environment.
