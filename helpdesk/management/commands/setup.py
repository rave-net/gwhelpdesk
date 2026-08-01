from __future__ import annotations

from getpass import getpass

from django.contrib.auth.hashers import make_password
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from helpdesk.lib import gwlib
from helpdesk.models import Admin, GWSettings


class Command(BaseCommand):
    help = "Configure the GroupWise Admin service and create a site administrator."

    def add_arguments(self, parser):
        parser.add_argument(
            "--skip-gw-check",
            action="store_true",
            help="Save GroupWise settings without validating the connection.",
        )

    @transaction.atomic
    def handle(self, *args, **options):
        self.stdout.write("GroupWise Admin Service Configuration")
        config = GWSettings.objects.first()

        if config is None or self._yes_no("Configure GroupWise connection", default=True):
            config = self._configure_groupwise(config, options["skip_gw_check"])
        else:
            self.stdout.write(f"Using existing GroupWise server {config.gwHost}:{config.gwPort}")

        admin = Admin.objects.first()
        if admin is None:
            self._create_admin()
        elif self._yes_no(
            f"Replace existing site administrator {admin.username}", default=False
        ):
            admin.delete()
            self._create_admin()

        self.stdout.write(self.style.SUCCESS("gwhelpdesk setup completed."))
        self.stdout.write(
            "Run 'python manage.py runserver' for testing or deploy with Gunicorn/systemd."
        )

    def _configure_groupwise(self, existing, skip_check):
        host = input(f"GroupWise Admin host [{getattr(existing, 'gwHost', '')}]: ").strip()
        host = host or (existing.gwHost if existing else "")
        if not host:
            raise CommandError("A GroupWise Admin host is required")

        default_port = str(existing.gwPort if existing else 9710)
        port_text = input(f"GroupWise Admin port [{default_port}]: ").strip() or default_port
        try:
            port = int(port_text)
        except ValueError as exc:
            raise CommandError("The GroupWise Admin port must be numeric") from exc

        username = input(
            f"GroupWise system administrator [{getattr(existing, 'gwAdmin', '')}]: "
        ).strip()
        username = username or (existing.gwAdmin if existing else "")
        if not username:
            raise CommandError("A GroupWise administrator is required")

        password = getpass("GroupWise administrator password: ")
        if not password and existing:
            password = existing.gwPass
        if not password:
            raise CommandError("A GroupWise administrator password is required")

        if not skip_check:
            result = gwlib.gw(host, port, username, password).whoami()
            if result == 1:
                raise CommandError("Unable to connect to the GroupWise Admin service")
            if "SYSTEM_RECORD" not in result.get("roles", []):
                raise CommandError(f"{username} is not a GroupWise system administrator")
            self.stdout.write(self.style.SUCCESS("GroupWise connection verified."))

        config = existing or GWSettings()
        config.gwHost = host
        config.gwPort = port
        config.gwAdmin = username
        config.gwPass = password
        config.save()
        return config

    def _create_admin(self):
        username = input("Site administrator username: ").strip()
        if not username:
            raise CommandError("A site administrator username is required")
        first_name = input("First name: ").strip()
        last_name = input("Last name: ").strip()
        password = getpass("Site administrator password: ")
        password2 = getpass("Confirm site administrator password: ")
        if password != password2:
            raise CommandError("Passwords do not match")
        if not password:
            raise CommandError("A site administrator password is required")
        Admin.objects.create(
            username=username,
            first_name=first_name,
            last_name=last_name,
            password=make_password(password),
            password2="",
            role=Admin.ADMIN,
        )
        self.stdout.write(self.style.SUCCESS(f"Administrator {username} created."))

    @staticmethod
    def _yes_no(prompt, default=False):
        suffix = " [Y/n]: " if default else " [y/N]: "
        answer = input(prompt + suffix).strip().lower()
        if not answer:
            return default
        return answer in {"y", "yes"}
