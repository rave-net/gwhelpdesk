from __future__ import annotations

import logging

from django import forms
from django.db import OperationalError, ProgrammingError
from django.forms import Form, ModelForm

from .lib import gwlib
from .models import Admin, GWSettings

logger = logging.getLogger(__name__)

VISIBILITY_CHOICES = [
    ("SYSTEM", "System"),
    ("DOMAIN", "Domain"),
    ("POST_OFFICE", "Post Office"),
    ("NONE", "None"),
]

ADDRESS_FORMAT_CHOICES = [
    ("HOST", "Username.PostOffice@InternetDomain"),
    ("USER", "Username@InternetDomain"),
    ("FIRST_LAST", "First.Last@InternetDomain"),
    ("LAST_FIRST", "Last.First@InternetDomain"),
    ("FLAST", "FirstInitialLastName@InternetDomain"),
]


def gwInit():
    """Return a configured GroupWise client without querying at import time."""
    try:
        config = GWSettings.objects.first()
    except (OperationalError, ProgrammingError):
        return None
    if config is None:
        return None
    return gwlib.gw(config.gwHost, config.gwPort, config.gwAdmin, config.gwPass)


def _safe_choices(loader, value_key="name", label_key="name"):
    client = gwInit()
    if client is None:
        return []
    try:
        return [
            (item[value_key], item[label_key])
            for item in loader(client)
            if value_key in item and label_key in item
        ]
    except Exception:
        logger.exception("Unable to populate GroupWise form choices")
        return []


class AddExtUser(forms.Form):
    name = forms.CharField(max_length=64)
    postOfficeName = forms.ChoiceField(choices=(), required=True)
    givenName = forms.CharField(max_length=64, required=False)
    surname = forms.CharField(max_length=64, required=False)
    prefemail = forms.CharField(max_length=128, required=False)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["postOfficeName"].choices = _safe_choices(
            lambda client: client.getExtPolist()
        )


class AddUser(forms.Form):
    name = forms.CharField(max_length=64)
    postOfficeName = forms.ChoiceField(choices=(), required=True)
    givenName = forms.CharField(max_length=64, required=False)
    surname = forms.CharField(max_length=64, required=False)
    password = forms.CharField(
        max_length=64, required=False, widget=forms.PasswordInput(render_value=True)
    )
    password2 = forms.CharField(
        max_length=64, required=False, widget=forms.PasswordInput(render_value=True)
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["postOfficeName"].choices = _safe_choices(
            lambda client: client.getPolist()
        )

    def clean(self):
        data = super().clean()
        if data.get("password") != data.get("password2"):
            self.add_error("password2", "Passwords do not match")
        return data


class AdminForm(ModelForm):
    class Meta:
        model = Admin
        fields = "__all__"
        widgets = {
            "password": forms.PasswordInput(render_value=True),
            "password2": forms.PasswordInput(render_value=True),
        }

    def clean(self):
        data = super().clean()
        if data.get("password") != data.get("password2"):
            self.add_error("password2", "Passwords do not match")
        return data


class changePassword(Form):
    password = forms.CharField(max_length=64, widget=forms.PasswordInput)
    password2 = forms.CharField(max_length=64, widget=forms.PasswordInput)
    id = forms.CharField(max_length=128)
    name = forms.CharField(max_length=64)

    def clean(self):
        data = super().clean()
        if data.get("password") != data.get("password2"):
            self.add_error("password2", "Passwords do not match")
        return data


class GWConfig(ModelForm):
    class Meta:
        model = GWSettings
        fields = "__all__"
        widgets = {"gwPass": forms.PasswordInput(render_value=True)}


class Groups(forms.Form):
    groups = forms.MultipleChoiceField(choices=(), required=False)
    participation = forms.CharField(max_length=64, required=False)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["groups"].choices = _safe_choices(
            lambda client: client.getGroups(), value_key="id", label_key="name"
        )


class GroupSearch(forms.Form):
    groupname = forms.CharField(max_length=128)


class AddGroup(forms.Form):
    name = forms.CharField(max_length=64)
    pourl = forms.ChoiceField(choices=(), required=True)
    visibility = forms.ChoiceField(choices=VISIBILITY_CHOICES)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["pourl"].choices = _safe_choices(
            lambda client: client.getPolist(), value_key="url", label_key="name"
        )


class LoginForm(Form):
    username = forms.CharField(max_length=128)
    password = forms.CharField(max_length=128, widget=forms.PasswordInput)


class Maintenence(forms.Form):
    actions = [
        ("analyze", "Analyze/Fix Database"),
        ("expire", "Expire/Reduce"),
        ("rebuild", "Structural Rebuild"),
        ("reset", "Reset Client Options"),
    ]
    action = forms.ChoiceField(choices=actions)


class Move(forms.Form):
    id = forms.CharField(max_length=128)
    postoffice = forms.CharField(max_length=128)


class Rename(forms.Form):
    newid = forms.CharField(max_length=64)
    id = forms.CharField(max_length=128)
    name = forms.CharField(max_length=64)


class Resources(forms.Form):
    resourcename = forms.CharField(max_length=64, required=False)
    resourceid = forms.CharField(max_length=128, required=False)
    resourceurl = forms.CharField(max_length=256, required=False)
    ownerid = forms.CharField(max_length=128, required=False)


class Addresource(forms.Form):
    resourcename = forms.CharField(max_length=64)
    ownername = forms.CharField(max_length=32)
    ownerid = forms.CharField(max_length=128)
    visibility = forms.ChoiceField(choices=VISIBILITY_CHOICES)


class Search(forms.Form):
    userid = forms.CharField(max_length=64)


class SearchResults(forms.Form):
    id = forms.CharField(max_length=128)
    name = forms.CharField(max_length=64)


class InternetDomainChoicesMixin:
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if "iDomainValue" in self.fields:
            client = gwInit()
            choices = []
            if client is not None:
                try:
                    choices = [(domain, domain) for domain in client.iDomains()]
                except Exception:
                    logger.exception("Unable to load GroupWise internet domains")
            self.fields["iDomainValue"].choices = choices


class UserDetails(InternetDomainChoicesMixin, forms.Form):
    name = forms.CharField(max_length=64)
    givenName = forms.CharField(max_length=64, required=False)
    surname = forms.CharField(max_length=64, required=False)
    middleInitial = forms.CharField(max_length=12, required=False)
    suffix = forms.CharField(max_length=64, required=False)
    title = forms.CharField(max_length=64, required=False)
    company = forms.CharField(max_length=61, required=False)
    department = forms.CharField(max_length=64, required=False)
    fileId = forms.CharField(max_length=3, required=False)
    description = forms.CharField(max_length=256, required=False)
    telephoneNumber = forms.CharField(max_length=24, required=False)
    mobilePhoneNumber = forms.CharField(max_length=24, required=False)
    homePhoneNumber = forms.CharField(max_length=24, required=False)
    otherPhoneNumber = forms.CharField(max_length=24, required=False)
    faxNumber = forms.CharField(max_length=24, required=False)
    pagerNumber = forms.CharField(max_length=24, required=False)
    streetAddress = forms.CharField(max_length=128, required=False)
    postOfficeBox = forms.CharField(max_length=24, required=False)
    city = forms.CharField(max_length=64, required=False)
    stateProvince = forms.CharField(max_length=64, required=False)
    postalZipCode = forms.CharField(max_length=16, required=False)
    visibility = forms.ChoiceField(choices=VISIBILITY_CHOICES)
    location = forms.CharField(max_length=64, required=False)
    loginDisabled = forms.BooleanField(required=False)
    forceInactive = forms.BooleanField(required=False)
    allowedOverride = forms.BooleanField(required=False)
    HOST = forms.BooleanField(required=False)
    USER = forms.BooleanField(required=False)
    FIRST_LAST = forms.BooleanField(required=False)
    LAST_FIRST = forms.BooleanField(required=False)
    FLAST = forms.BooleanField(required=False)
    preferredAddressFormatValue = forms.ChoiceField(
        choices=ADDRESS_FORMAT_CHOICES, required=False
    )
    preferredAddressFormatInherited = forms.BooleanField(required=False)
    preferredEmailId = forms.CharField(max_length=128, required=False)
    internetDomainNameOverride = forms.BooleanField(required=False)
    iDomainValue = forms.ChoiceField(choices=(), required=False)
    iDomainExclusive = forms.BooleanField(required=False)


class ExtUserDetails(UserDetails):
    loginDisabled = None
    forceInactive = None


class GroupDetails(InternetDomainChoicesMixin, forms.Form):
    name = forms.CharField(max_length=64)
    description = forms.CharField(max_length=256, required=False)
    visibility = forms.ChoiceField(choices=VISIBILITY_CHOICES)
    allowedOverride = forms.BooleanField(required=False)
    HOST = forms.BooleanField(required=False)
    USER = forms.BooleanField(required=False)
    FIRST_LAST = forms.BooleanField(required=False)
    LAST_FIRST = forms.BooleanField(required=False)
    FLAST = forms.BooleanField(required=False)
    preferredAddressFormatValue = forms.ChoiceField(
        choices=ADDRESS_FORMAT_CHOICES, required=False
    )
    preferredAddressFormatInherited = forms.BooleanField(required=False)
    preferredEmailId = forms.CharField(max_length=128, required=False)
    internetDomainNameOverride = forms.BooleanField(required=False)
    iDomainValue = forms.ChoiceField(choices=(), required=False)
    iDomainExclusive = forms.BooleanField(required=False)
    replication = forms.ChoiceField(choices=(), required=False)


class GroupInet(GroupDetails):
    id = forms.CharField(max_length=128)


class GroupList(forms.Form):
    name = forms.CharField(max_length=64)
    id = forms.CharField(max_length=128)
    domain = forms.CharField(max_length=64, required=False)
    visiblity = forms.CharField(max_length=16, required=False)
    postOfficeName = forms.CharField(max_length=64, required=False)


class UserGroups(forms.Form):
    group = forms.CharField(max_length=64, required=False)
    participation = forms.CharField(max_length=64, required=False)
    grpid = forms.CharField(max_length=256, required=False)


class UserList(forms.Form):
    name = forms.CharField(max_length=64)
    id = forms.CharField(max_length=128)
    givenName = forms.CharField(max_length=64, required=False)
    surname = forms.CharField(max_length=64, required=False)
    postOfficeName = forms.CharField(max_length=64)


class Nicknames(forms.Form):
    nickname = forms.CharField(max_length=64)
    postOfficeName = forms.ChoiceField(choices=(), required=True)
    visibility = forms.ChoiceField(choices=VISIBILITY_CHOICES)
    surname = forms.CharField(max_length=64, required=False)
    givenName = forms.CharField(max_length=64, required=False)
    referreduser = forms.CharField(max_length=128)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["postOfficeName"].choices = _safe_choices(
            lambda client: client.getPolist(), value_key="id", label_key="name"
        )
