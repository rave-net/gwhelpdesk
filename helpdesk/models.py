from django.db import models


class GWSettings(models.Model):
    gwHost = models.CharField(max_length=120)
    gwPort = models.PositiveSmallIntegerField()
    gwAdmin = models.CharField(max_length=64)
    gwPass = models.CharField(max_length=256)

    class Meta:
        verbose_name_plural = "GroupWise settings"

    def __str__(self):
        return f"{self.gwHost}:{self.gwPort}"


class Admin(models.Model):
    ADMIN = "AD"
    HELPDESK = "HD"
    HELPDESKLITE = "HL"
    PASSWORD = "PW"
    ADDRBOOK = "AB"

    roleChoices = (
        (ADMIN, "Administrator"),
        (HELPDESK, "Helpdesk"),
        (HELPDESKLITE, "Helpdesk Lite"),
        (ADDRBOOK, "Address Book"),
        (PASSWORD, "Password"),
    )

    username = models.CharField(max_length=128, null=True)
    first_name = models.CharField(max_length=64, null=True, blank=True)
    last_name = models.CharField(max_length=64, null=True, blank=True)
    password = models.CharField(max_length=256, null=True)
    password2 = models.CharField(max_length=256, null=True, blank=True)
    role = models.CharField(max_length=4, choices=roleChoices, default=HELPDESK)

    def __str__(self):
        return self.username or f"Admin {self.pk}"
