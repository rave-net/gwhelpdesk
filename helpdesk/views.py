from __future__ import annotations

import logging
from pathlib import Path

from django.conf import settings
from django.contrib import messages
from django.contrib.auth.hashers import check_password, make_password
from django.http import HttpResponseRedirect
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views.decorators.http import require_http_methods
from ipware import get_client_ip

from .forms import (
    AddExtUser,
    AddGroup,
    AddUser,
    Addresource,
    AdminForm,
    ExtUserDetails,
    GroupDetails,
    GroupSearch,
    GWConfig,
    LoginForm,
    Maintenence,
    Move,
    Nicknames,
    Rename,
    Resources,
    Search,
    SearchResults,
    UserDetails,
    UserGroups,
    changePassword,
)
from .lib.gwlib import GroupWiseError, gw
from .models import Admin, GWSettings

logger = logging.getLogger("helpdesk")
LOG_FILE = Path(settings.BASE_DIR) / "logs" / "helpdesk.log"
LOG_FILE.parent.mkdir(parents=True, exist_ok=True)


def _title(request, value):
    request.session["header"] = value


def _require_login(request):
    if "adminname" not in request.session:
        return redirect("login")
    return None


def _client():
    config = GWSettings.objects.first()
    if config is None:
        raise GroupWiseError("GroupWise Admin service has not been configured")
    return gw(config.gwHost, config.gwPort, config.gwAdmin, config.gwPass)


def _audit(request, message):
    username = request.session.get("adminname", "unknown")
    logger.info("[%s] - %s", username, message)


def _gw_error(request, exc):
    logger.exception("GroupWise operation failed")
    messages.error(request, str(exc))


def _decorate_user(client, user):
    if not user:
        return user
    user["ldap"] = "true" if user.get("ldapDn") else "false"
    user["url"] = user.get("@url", user.get("url", ""))
    return user


def _user_context(client, user, form_class=UserDetails):
    return {
        "form": form_class(initial=user),
        "user": _decorate_user(client, user),
        "addressFormats": client.addrFormats(),
        "emailAddrs": client.userAddresses(user["@url"]),
        "idomains": [(domain, domain) for domain in client.iDomains()],
    }


def index(request):
    response = _require_login(request)
    return response or render(request, "helpdesk/index.html")


@require_http_methods(["GET", "POST"])
def login(request):
    form = LoginForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        username = form.cleaned_data["username"]
        try:
            admin = Admin.objects.get(username=username)
        except Admin.DoesNotExist:
            messages.error(request, f"{username} login id not found.")
        else:
            if check_password(form.cleaned_data["password"], admin.password or ""):
                request.session.update(
                    {
                        "adminname": username,
                        "role": admin.role,
                        "surname": admin.last_name,
                        "givenName": admin.first_name,
                    }
                )
                client_ip, _ = get_client_ip(request)
                _audit(request, f"Logged in from IP {client_ip or 'unknown'}")
                return redirect("index")
            messages.error(request, f"Incorrect password for {username}.")
    if not Admin.objects.exists():
        messages.error(request, "There are no administrators defined. Run manage.py setup.")
    return render(request, "helpdesk/login.html", {"form": form})


def logout(request):
    if "adminname" in request.session:
        _audit(request, "Logged out")
    request.session.flush()
    return redirect("login")


def admins(request):
    response = _require_login(request)
    if response:
        return response
    form = AdminForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        data = form.cleaned_data
        admin = get_object_or_404(Admin, username=data["username"])
        if "delete" in request.POST:
            admin.delete()
            _audit(request, f"Administrator {data['username']} deleted")
        elif "chpwd" in request.POST:
            request.session["adminname_to_change"] = admin.username
            return render(request, "helpdesk/changeadminpassword.html", {"form": form, "admin": admin})
        else:
            admin.first_name = data.get("first_name")
            admin.last_name = data.get("last_name")
            admin.role = data.get("role")
            admin.save(update_fields=["first_name", "last_name", "role"])
            _audit(request, f"Administrator {admin.username} modified")
        return redirect("admins")
    return render(request, "helpdesk/admins.html", {"form": form, "admins": Admin.objects.all()})


def addadmin(request):
    response = _require_login(request)
    if response:
        return response
    form = AdminForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        admin = form.save(commit=False)
        admin.password = make_password(form.cleaned_data["password"])
        admin.password2 = ""
        admin.save()
        _audit(request, f"Administrator {admin.username} added")
        return redirect("admins")
    return render(request, "helpdesk/addadmin.html", {"form": form})


def changeadminpassword(request):
    response = _require_login(request)
    if response:
        return response
    username = request.session.get("adminname_to_change", request.session["adminname"])
    admin = get_object_or_404(Admin, username=username)
    form = AdminForm(request.POST or None, instance=admin)
    if request.method == "POST" and form.is_valid():
        admin.password = make_password(form.cleaned_data["password"])
        admin.password2 = ""
        admin.save(update_fields=["password", "password2"])
        _audit(request, f"Password changed for administrator {username}")
        return redirect("admins")
    return render(request, "helpdesk/changeadminpassword.html", {"form": form, "admin": admin})


def gwconfig(request):
    response = _require_login(request)
    if response:
        return response
    instance = GWSettings.objects.first()
    form = GWConfig(request.POST or None, instance=instance)
    if request.method == "POST" and form.is_valid():
        record = form.save()
        try:
            result = gw(record.gwHost, record.gwPort, record.gwAdmin, record.gwPass).whoami()
            if result == 1 or "SYSTEM_RECORD" not in result.get("roles", []):
                messages.warning(request, "Settings saved, but GroupWise administrator validation failed.")
            else:
                messages.success(request, "GroupWise connection verified.")
        except Exception as exc:
            _gw_error(request, exc)
        return redirect("gwconfig")
    return render(request, "helpdesk/gwconfig.html", {"form": form, "gwconfig": instance})


def search(request):
    response = _require_login(request)
    if response:
        return response
    _title(request, "GroupWise User Search")
    return render(request, "helpdesk/search.html", {"form": Search()})


def searchresults(request):
    response = _require_login(request)
    if response:
        return response
    form = Search(request.POST or None)
    if request.method == "POST" and form.is_valid():
        try:
            client = _client()
            query = form.cleaned_data["userid"]
            users = client.allUsers() if query == "*" else client.userSearch(query)
            for user in users:
                _decorate_user(client, user)
            _audit(request, f"Performed user search for {query}")
            return render(request, "helpdesk/searchresults.html", {"users": users, "searchstring": query})
        except Exception as exc:
            _gw_error(request, exc)
    return render(request, "helpdesk/search.html", {"form": form})


def userlist(request):
    response = _require_login(request)
    if response:
        return response
    try:
        client = _client()
        if request.method == "POST" and "userform" in request.POST:
            user = client.getObject(request.POST["id"])
            request.session["id"] = user["id"]
            request.session["name"] = user["name"]
            return render(request, "helpdesk/userdata.html", _user_context(client, user))
        next_id = request.POST.get("nextid", 0)
        page = client.pageUsers(next_id)
        for user in page["userList"]:
            _decorate_user(client, user)
        return render(
            request,
            "helpdesk/userlist.html",
            {
                "users": page["userList"],
                "nextid": page["nextId"],
                "firstset": int(page["nextId"] or 1) > 1,
                "usercount": client.getUserCount(),
            },
        )
    except Exception as exc:
        _gw_error(request, exc)
        return render(request, "helpdesk/userlist.html", {"users": []})


def extuserlist(request):
    response = _require_login(request)
    if response:
        return response
    try:
        users = _client().getExtUsers()
    except Exception as exc:
        _gw_error(request, exc)
        users = []
    return render(request, "helpdesk/userlist.html", {"users": users, "usercount": len(users)})


def adduser(request):
    return _add_user(request, external=False)


def addextuser(request):
    return _add_user(request, external=True)


def _add_user(request, external):
    response = _require_login(request)
    if response:
        return response
    form_class = AddExtUser if external else AddUser
    form = form_class(request.POST or None)
    try:
        client = _client()
        offices = client.getExtPolist() if external else client.getPolist()
        if request.method == "POST" and form.is_valid():
            office = next(item for item in offices if item["name"] == form.cleaned_data["postOfficeName"])
            payload = {
                "name": form.cleaned_data["name"],
                "givenName": form.cleaned_data.get("givenName", ""),
                "surname": form.cleaned_data.get("surname", ""),
            }
            if not external and not office["external"] and form.cleaned_data.get("password"):
                payload["password"] = form.cleaned_data["password"]
            headers = client.addUser(office["url"], payload)
            location = headers.get("location") or headers.get("Location")
            if location:
                user = client.getObjectByUrl(location)
                request.session["id"] = user["id"]
                request.session["name"] = user["name"]
                _audit(request, f"GroupWise user {user['name']} added")
                return render(request, "helpdesk/userdata.html", _user_context(client, user, ExtUserDetails if external else UserDetails))
            messages.error(request, "GroupWise did not return the new user location.")
    except Exception as exc:
        _gw_error(request, exc)
        offices = []
    template = "helpdesk/addextuser.html" if external else "helpdesk/adduser.html"
    return render(request, template, {"form": form, "polist": offices})


def userdata(request):
    return _userdata(request, external=False)


def extuserdata(request):
    return _userdata(request, external=True)


def _userdata(request, external):
    response = _require_login(request)
    if response:
        return response
    try:
        client = _client()
        form_class = ExtUserDetails if external else UserDetails
        if request.method == "POST" and "edit" in request.POST:
            user = client.getObject(request.POST["id"])
            request.session["id"] = user["id"]
            request.session["name"] = user["name"]
            return render(request, "helpdesk/extuserdata.html" if external else "helpdesk/userdata.html", _user_context(client, user, form_class))
        if request.method == "POST" and "delete" in request.POST:
            client.delUser(request.POST["id"])
            _audit(request, f"Deleted GroupWise user {request.POST['id']}")
            return render(request, "helpdesk/deluser.html")
        if request.method == "POST" and "changepwd" in request.POST:
            form = changePassword(initial={"id": request.POST["id"], "name": request.POST["name"]})
            return render(request, "helpdesk/changepassword.html", {"form": form, "id": request.POST["id"], "name": request.POST["name"]})
        if request.method == "POST" and "update" in request.POST:
            form = form_class(request.POST)
            if form.is_valid():
                user = client.updateUser(request.session["id"], _clean_update_data(form.cleaned_data))
                _audit(request, f"Updated GroupWise user {user['name']}")
                return render(request, "helpdesk/extuserdata.html" if external else "helpdesk/userdata.html", _user_context(client, user, form_class))
        object_id = request.session.get("id")
        if object_id:
            user = client.getObject(object_id)
            return render(request, "helpdesk/extuserdata.html" if external else "helpdesk/userdata.html", _user_context(client, user, form_class))
    except Exception as exc:
        _gw_error(request, exc)
    return render(request, "helpdesk/extuserdata.html" if external else "helpdesk/userdata.html")


def _clean_update_data(data):
    ignored = {"password2", "allowedOverride", "HOST", "USER", "FIRST_LAST", "LAST_FIRST", "FLAST", "preferredAddressFormatInherited", "internetDomainNameOverride", "iDomainValue", "iDomainExclusive"}
    return {key: value for key, value in data.items() if key not in ignored and value not in (None, "")}


def changepassword(request):
    response = _require_login(request)
    if response:
        return response
    form = changePassword(request.POST or None)
    if request.method == "POST" and form.is_valid():
        try:
            _client().changePass(form.cleaned_data["id"], form.cleaned_data["password"])
            _audit(request, f"Changed GroupWise password for {form.cleaned_data['name']}")
            messages.success(request, "Password changed.")
        except Exception as exc:
            _gw_error(request, exc)
    return render(request, "helpdesk/changepassword.html", {"form": form})


def deluser(request):
    response = _require_login(request)
    if response:
        return response
    try:
        object_id = request.session["id"]
        _client().delUser(object_id)
        _audit(request, f"Deleted GroupWise user {object_id}")
    except Exception as exc:
        _gw_error(request, exc)
    return render(request, "helpdesk/deluser.html")


def dissociate(request):
    response = _require_login(request)
    if response:
        return response
    try:
        client = _client()
        object_id = request.session["id"]
        client.dissociate(object_id)
        user = client.getObject(object_id)
        _audit(request, f"Dissociated {user['name']} from directory")
        return render(request, "helpdesk/userdata.html", _user_context(client, user))
    except Exception as exc:
        _gw_error(request, exc)
        return redirect("userdata")


def grouplist(request):
    response = _require_login(request)
    if response:
        return response
    try:
        client = _client()
        page = client.pageGroups(request.POST.get("nextid", 0))
        return render(request, "helpdesk/grouplist.html", {"groups": page["groupList"], "nextid": page["nextId"], "count": client.getGroupCount()})
    except Exception as exc:
        _gw_error(request, exc)
        return render(request, "helpdesk/grouplist.html", {"groups": []})


def addgroup(request):
    response = _require_login(request)
    if response:
        return response
    form = AddGroup(request.POST or None)
    try:
        client = _client()
        offices = client.getPolist()
        if request.method == "POST" and form.is_valid():
            headers = client.addGroup({"name": form.cleaned_data["name"], "visibility": form.cleaned_data["visibility"]}, form.cleaned_data["pourl"])
            location = headers.get("location") or headers.get("Location")
            if location:
                group = client.getObjectByUrl(location)
                _audit(request, f"GroupWise group {group['name']} added")
                return render(request, "helpdesk/groupdetails.html", {"form": GroupDetails(initial=group), "group": group, "members": []})
            return redirect("grouplist")
    except Exception as exc:
        _gw_error(request, exc)
        offices = []
    return render(request, "helpdesk/addgroup.html", {"form": form, "polist": offices})


def groupsearch(request):
    response = _require_login(request)
    if response:
        return response
    return render(request, "helpdesk/groupsearch.html", {"form": GroupSearch()})


def groupsearchresults(request):
    response = _require_login(request)
    if response:
        return response
    form = GroupSearch(request.POST or None)
    if request.method == "POST" and form.is_valid():
        try:
            groups = _client().groupSearch(form.cleaned_data["groupname"])
            return render(request, "helpdesk/groupsearchresults.html", {"groups": groups, "searchstring": form.cleaned_data["groupname"]})
        except Exception as exc:
            _gw_error(request, exc)
    return render(request, "helpdesk/groupsearch.html", {"form": form})


def groupdetails(request):
    response = _require_login(request)
    if response:
        return response
    try:
        client = _client()
        object_id = request.POST.get("id") or request.session.get("id")
        if not object_id:
            return redirect("grouplist")
        group = client.getGroup(object_id)
        request.session["id"] = object_id
        request.session["name"] = group.get("name")
        if request.method == "POST" and "deletegroup" in request.POST:
            client.deleteGroup(object_id)
            _audit(request, f"Deleted GroupWise group {group.get('name')}")
            return redirect("grouplist")
        if request.method == "POST" and "deletemember" in request.POST:
            client.delFromGroup(group["@url"], request.POST["memberid"])
        if request.method == "POST" and "general" in request.POST:
            client.updateGroup(object_id, {"description": request.POST.get("description", ""), "visibility": request.POST.get("visibility", "SYSTEM")})
            group = client.getGroup(object_id)
        members = client.getGroupMembers(group["@url"])
        return render(request, "helpdesk/groupdetails.html", {"form": GroupDetails(initial=group), "group": group, "members": members, "addressFormats": client.addrFormats(), "emailAddrs": client.userAddresses(group["@url"]), "idomains": [(item, item) for item in client.iDomains()]})
    except Exception as exc:
        _gw_error(request, exc)
        return redirect("grouplist")


def addgrpmember(request):
    response = _require_login(request)
    if response:
        return response
    try:
        client = _client()
        if request.method == "POST" and "add" in request.POST:
            client.addUserToGroup({"id": request.POST["id"], "url": client.getGroup(request.POST["grpid"])["@url"]})
            return redirect("groupdetails")
        page = client.pageUsers(request.POST.get("nextid", 0))
        return render(request, "helpdesk/addgrpmember.html", {"users": page["userList"], "nextid": page["nextId"], "usercount": client.getUserCount()})
    except Exception as exc:
        _gw_error(request, exc)
        return render(request, "helpdesk/addgrpmember.html", {"users": []})


def groups(request):
    response = _require_login(request)
    if response:
        return response
    try:
        client = _client()
        object_id = request.session["id"]
        form = UserGroups(request.POST or None)
        if request.method == "POST" and form.is_valid():
            if "remove" in request.POST:
                client.removeFromGroup(object_id, form.cleaned_data["grpid"])
            elif "edit" in request.POST:
                client.updateGroupMembership(request.session.get("name", ""), object_id, form.cleaned_data["grpid"], form.cleaned_data["participation"])
            elif "add" in request.POST:
                client.addUserToGroups(request.POST.getlist("groups"), object_id)
        return render(request, "helpdesk/groups.html", {"form": form, "groupList": client.userGroupMembership(object_id)})
    except Exception as exc:
        _gw_error(request, exc)
        return render(request, "helpdesk/groups.html", {"form": UserGroups(), "groupList": []})


def addtogroups(request):
    response = _require_login(request)
    if response:
        return response
    try:
        client = _client()
        if request.method == "POST":
            client.addUserToGroup({"id": request.session["id"], "url": request.POST["url"]})
            return redirect("grouplist")
        return render(request, "helpdesk/addtogroups.html", {"groups": client.getAllGroups()})
    except Exception as exc:
        _gw_error(request, exc)
        return render(request, "helpdesk/addtogroups.html", {"groups": []})


def move(request):
    response = _require_login(request)
    if response:
        return response
    form = Move(request.POST or None)
    try:
        client = _client()
        if request.method == "POST" and form.is_valid():
            client.moveUser(form.cleaned_data["id"], form.cleaned_data["postoffice"])
            messages.success(request, "Move request submitted.")
        return render(request, "helpdesk/move.html", {"form": form, "polist": client.getPolist()})
    except Exception as exc:
        _gw_error(request, exc)
        return render(request, "helpdesk/move.html", {"form": form, "polist": []})


def rename(request):
    response = _require_login(request)
    if response:
        return response
    form = Rename(request.POST or None)
    if request.method == "POST" and form.is_valid():
        try:
            _client().renameUser(form.cleaned_data["id"], form.cleaned_data["newid"])
            messages.success(request, "Rename request submitted.")
        except Exception as exc:
            _gw_error(request, exc)
    return render(request, "helpdesk/rename.html", {"form": form})


def maintenance(request):
    response = _require_login(request)
    if response:
        return response
    form = Maintenence(request.POST or None)
    if request.method == "POST" and form.is_valid():
        try:
            action = form.cleaned_data["action"].upper()
            _client().gwcheck(action, request.POST["id"], dict(request.POST.items()))
            messages.success(request, "Maintenance request submitted.")
        except Exception as exc:
            _gw_error(request, exc)
    return render(request, "helpdesk/maintenance.html", {"form": form})


def resources(request):
    response = _require_login(request)
    if response:
        return response
    try:
        client = _client()
        object_id = request.session["id"]
        if request.method == "POST" and "delete" in request.POST:
            client.delResource(request.POST["resourceurl"])
        return render(request, "helpdesk/resources.html", {"form": Resources(), "resources": client.resources(object_id)})
    except Exception as exc:
        _gw_error(request, exc)
        return render(request, "helpdesk/resources.html", {"resources": []})


def addresource(request):
    response = _require_login(request)
    if response:
        return response
    form = Addresource(request.POST or None)
    try:
        client = _client()
        if request.method == "POST" and form.is_valid():
            owner = form.cleaned_data["ownerid"].split(".")
            client.addResource(form.cleaned_data["resourcename"], owner[2], owner[1], form.cleaned_data["ownername"])
            return redirect("resources")
        return render(request, "helpdesk/addresource.html", {"form": form, "polist": client.getPolist()})
    except Exception as exc:
        _gw_error(request, exc)
        return render(request, "helpdesk/addresource.html", {"form": form, "polist": []})


def nicknames(request):
    response = _require_login(request)
    if response:
        return response
    try:
        client = _client()
        object_id = request.session["id"]
        if request.method == "POST" and "delete" in request.POST:
            client.delNickname(request.POST["url"])
        return render(request, "helpdesk/nicknames.html", {"nicknames": client.nicknames(object_id)})
    except Exception as exc:
        _gw_error(request, exc)
        return render(request, "helpdesk/nicknames.html", {"nicknames": []})


def addnickname(request):
    response = _require_login(request)
    if response:
        return response
    form = Nicknames(request.POST or None)
    try:
        client = _client()
        if request.method == "POST" and form.is_valid():
            po_parts = form.cleaned_data["postOfficeName"].split(".")
            user_parts = form.cleaned_data["referreduser"].split(".")
            client.addNickname(
                name=form.cleaned_data["nickname"],
                domainName=po_parts[1],
                postOfficeName=po_parts[2],
                visibility=form.cleaned_data["visibility"],
                givenName=form.cleaned_data.get("givenName", ""),
                surname=form.cleaned_data.get("surname", ""),
                referredUserName=form.cleaned_data["referreduser"],
                userName=user_parts[3],
                userPostOfficeName=user_parts[2],
                userDomainName=user_parts[1],
            )
            return redirect("nicknames")
        return render(request, "helpdesk/addnickname.html", {"form": form, "polist": client.getPolist()})
    except Exception as exc:
        _gw_error(request, exc)
        return render(request, "helpdesk/addnickname.html", {"form": form, "polist": []})


def viewlog(request):
    response = _require_login(request)
    if response:
        return response
    content = LOG_FILE.read_text(encoding="utf-8", errors="replace") if LOG_FILE.exists() else ""
    return render(request, "helpdesk/viewlog.html", {"log": content})
