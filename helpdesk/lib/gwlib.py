from __future__ import annotations

import os
import time
from typing import Any
from urllib.parse import quote

import requests
from django.conf import settings


class GroupWiseError(RuntimeError):
    """Raised when the GroupWise Admin REST API returns an error."""


class gw:
    def __init__(self, gwHost, gwPort, gwAdmin, gwPass):
        self.baseUrl = f"https://{gwHost}:{gwPort}"
        self.gwAdmin = gwAdmin
        self.timeout = getattr(settings, "GW_REQUEST_TIMEOUT", 10)
        self.session = requests.Session()
        self.session.auth = (gwAdmin, os.environ.get("GW_ADMIN_PASSWORD", gwPass))
        self.session.verify = getattr(settings, "GW_VERIFY_TLS", True)
        self.session.headers.update({"Accept": "application/json"})

    def _request(self, method: str, path: str, **kwargs):
        url = path if path.startswith("http") else f"{self.baseUrl}{path}"
        kwargs.setdefault("timeout", self.timeout)
        response = self.session.request(method, url, **kwargs)
        if response.status_code >= 400:
            detail = response.text.strip() or response.reason
            raise GroupWiseError(f"GroupWise API {response.status_code}: {detail}")
        return response

    @staticmethod
    def checkResponse(response):
        if not response.content:
            return None
        payload = response.json()
        return payload.get("object", payload)

    def _json(self, method: str, path: str, **kwargs):
        return self.checkResponse(self._request(method, path, **kwargs))

    def whoami(self):
        try:
            return self._json("GET", "/gwadmin-service/system/whoami") or {}
        except requests.RequestException:
            return 1

    def objectCount(self, gwtype):
        response = self._request("GET", f"/gwadmin-service/list/{gwtype}").json()
        return response.get("resultInfo", {}).get("outOf", 0)

    def _paged(self, object_type: str, next_id=0, count=8):
        params = {"count": count}
        try:
            next_id = int(next_id or 0)
        except (TypeError, ValueError):
            next_id = 0
        if next_id > 1:
            params["nextId"] = next_id
        payload = self._request(
            "GET", f"/gwadmin-service/list/{object_type}", params=params
        ).json()
        return payload.get("object", []), payload.get("resultInfo", {}).get("nextId", 1)

    def pageUsers(self, nextId):
        users, next_id = self._paged("user", nextId)
        return {"userList": users, "nextId": next_id or 1}

    def allUsers(self):
        users = []
        next_id = 0
        while True:
            page, next_id = self._paged("user", next_id, 1000)
            users.extend(page)
            if not next_id or int(next_id) <= 1:
                return users

    def pageGroups(self, nextId):
        groups, next_id = self._paged("group", nextId)
        for group in groups:
            group["url"] = group.get("@url", "")
        return {"groupList": groups, "nextId": next_id or 1}

    def getAllGroups(self):
        groups, _ = self._paged("group", 0, 10000)
        for group in groups:
            group["url"] = group.get("@url", "")
        return groups

    def getGroups(self):
        return self.getAllGroups()

    def getUserCount(self):
        info = self._json("GET", "/gwadmin-service/system/info") or {}
        return info.get("userCount", 0) + info.get("externalUserCount", 0)

    def getGroupCount(self):
        info = self._json("GET", "/gwadmin-service/system/info") or {}
        return info.get("groupCount", 0) + info.get("externalGroupCount", 0)

    def getObject(self, object_id):
        return self._json("GET", f"/gwadmin-service/object/{quote(str(object_id), safe='.')}")

    def getObjectByUrl(self, userurl):
        return self._json("GET", userurl)

    def getGroup(self, object_id):
        return self.getObject(object_id)

    def userSearch(self, userid):
        return self._search(userid, "USER")

    def groupSearch(self, groupid):
        return self._search(groupid, "GROUP")

    def _search(self, text, object_prefix):
        payload = self._request(
            "GET", "/gwadmin-service/system/search", params={"text": text}
        ).json()
        results = []
        for item in payload.get("object", []):
            if object_prefix not in item.get("id", ""):
                continue
            details = self.getObject(item["id"])
            details["pendingOp"] = "true" if "pendingOp" in item else "false"
            if object_prefix == "USER":
                details["ldap"] = "true" if details.get("ldapDn") else "false"
            results.append(details)
        return results

    def getPolist(self):
        payload = self._request("GET", "/gwadmin-service/list/post_office").json()
        return [self._post_office(item) for item in payload.get("object", [])]

    def getExtPolist(self):
        payload = self._request(
            "GET", "/gwadmin-service/list/post_office", params={"externalRecord": "true"}
        ).json()
        return [self._post_office(item) for item in payload.get("object", [])]

    @staticmethod
    def _post_office(item):
        return {
            "name": item.get("name", ""),
            "url": item.get("@url", ""),
            "@url": item.get("@url", ""),
            "id": item.get("id", ""),
            "ldap": "LDAP" in item.get("securitySettings", []),
            "external": bool(item.get("externalRecord")),
        }

    def getDomlist(self):
        payload = self._request("GET", "/gwadmin-service/list/domain").json()
        return [
            {
                "name": item.get("name", ""),
                "url": item.get("@url", ""),
                "external": bool(item.get("externalRecord")),
            }
            for item in payload.get("object", [])
        ]

    def checkPoLdap(self, postoffice):
        payload = self._request(
            "GET", "/gwadmin-service/list/post_office", params={"name": postoffice}
        ).json()
        objects = payload.get("object", [])
        return int(bool(objects and "LDAP" in objects[0].get("securitySettings", [])))

    def addrFormats(self):
        return ["HOST", "USER", "LAST_FIRST", "FIRST_LAST", "FLAST"]

    def iDomains(self):
        payload = self._request("GET", "/gwadmin-service/system/internetdomains").json()
        return [item["name"] for item in payload.get("object", []) if "name" in item]

    def defIdom(self):
        return (self._json("GET", "/gwadmin-service/system") or {}).get(
            "internetDomainName"
        )

    def userFormats(self, object_id):
        return self.getObject(object_id).get("allowedAddressFormats", {})

    def userAddresses(self, userurl):
        payload = self._json("GET", f"{userurl}/emailaddresses")
        if isinstance(payload, dict) and isinstance(payload.get("allowed"), list):
            return "\n".join(payload["allowed"])
        return payload

    def getpic(self, url):
        return self._request(
            "GET", url, headers={"Accept": "application/octet-stream"}
        ).content

    def addUser(self, pourl, data):
        response = self._request("POST", f"{pourl}/users", json=data)
        return dict(response.headers)

    addExtUser = addUser

    def updateUser(self, object_id, data):
        obj = self.getObject(object_id)
        self._request("PUT", obj["@url"], json=data)
        return self.getObject(object_id)

    def changePass(self, object_id, password):
        obj = self.getObject(object_id)
        response = self._request(
            "PUT", f"{obj['@url']}/clientoptions", json={"userPassword": {"value": password}}
        )
        return response.status_code

    def delUser(self, object_id):
        obj = self.getObject(object_id)
        self._request("DELETE", obj["@url"])
        for _ in range(9):
            try:
                data = self.getObject(object_id)
            except GroupWiseError:
                return 0
            if not data.get("pendingOp"):
                return 0
            time.sleep(2)
        return 1

    def dissociate(self, object_id):
        obj = self.getObject(object_id)
        return self._request("DELETE", f"{obj['@url']}/directorylink").text

    def addGroup(self, gwdata, pourl):
        response = self._request("POST", f"{pourl}/groups", json=gwdata)
        return dict(response.headers)

    def updateGroup(self, object_id, data, operation_type="u"):
        obj = self.getObject(object_id)
        if operation_type == "m":
            path = f"{obj['@url']}/members"
            method = "POST"
        else:
            path = obj["@url"]
            method = "PUT"
        return self._request(method, path, json=data).status_code

    def deleteGroup(self, object_id):
        obj = self.getObject(object_id)
        self._request("DELETE", obj["@url"])
        return 0

    def getGroupMembers(self, url):
        payload = self._request("GET", f"{url}/members").json()
        return payload.get("object", [])

    def addUserToGroup(self, grpdata):
        response = self._request(
            "POST", f"{grpdata['url']}/members", json={"id": grpdata["id"]}
        )
        return response.status_code

    def delFromGroup(self, url, userid):
        return self._request("DELETE", f"{url}/members/{userid}").status_code

    def userGroupMembership(self, object_id):
        user = self.getObject(object_id)
        payload = self._request("GET", f"{user['@url']}/groupmemberships").json()
        return [
            [item.get("name"), item.get("participation"), item.get("id")]
            for item in payload.get("object", [])
        ]

    def addUserToGroups(self, groups, userid):
        user = self.getObject(userid)
        for group_id in groups:
            self._request(
                "PUT", f"{user['@url']}/groupmemberships", json={"add": {"id": group_id}}
            )

    def updateGroupMembership(self, name, userid, groupid, participation):
        user = self.getObject(userid)
        data = {"update": [{"id": groupid, "participation": participation, "name": name}]}
        return self._request("PUT", f"{user['@url']}/groupmemberships", json=data).status_code

    def removeFromGroup(self, userid, grpid):
        user = self.getObject(userid)
        return self._request("DELETE", f"{user['@url']}/groupmemberships/{grpid}").status_code

    def renameUser(self, object_id, newid):
        user = self.getObject(object_id)
        return self._request(
            "POST", f"{user['@url']}/rename", json={"objectId": object_id, "newObjectId": newid, "createNickname": False}
        ).status_code

    def moveUser(self, userid, poid):
        response = self._request(
            "POST", "/gwadmin-service/system/moverequests", json={"sources": [{"id": userid}], "postOfficeId": poid, "directoryUser": False}
        )
        return "Succeeded" if response.status_code < 300 else response.text

    def getExtUsers(self):
        payload = self._request(
            "GET", "/gwadmin-service/list/user", params={"externalRecord": "true"}
        ).json()
        return payload.get("object", [])

    def resources(self, object_id):
        user = self.getObject(object_id)
        payload = self._request("GET", f"{user['@url']}/resources").json()
        return [
            [item.get("name"), item.get("@url"), item.get("id"), item.get("postOfficeName"), item.get("domainName")]
            for item in payload.get("object", [])
        ]

    def addResource(self, name, po, domain, owner):
        response = self._request(
            "POST", f"/gwadmin-service/domains/{domain}/postoffices/{po}/resources", json={"name": name, "domainName": domain, "postOfficeName": po, "owner": owner}
        )
        return 0 if "location" in response.headers else 1

    def delResource(self, url):
        return self._request("DELETE", url).text

    def nicknames(self, object_id):
        user = self.getObject(object_id)
        payload = self._request("GET", f"{user['@url']}/nicknames").json()
        return payload.get("object", [])

    def addNickname(self, **data):
        response = self._request(
            "POST", f"/gwadmin-service/domains/{data['domainName']}/postoffices/{data['postOfficeName']}/nicknames", json=data
        )
        return 0 if "location" in response.headers else 1

    def delNickname(self, url):
        return 0 if not self._request("DELETE", url).text else 1

    def gwcheck(self, action, object_id, options):
        user = self.getObject(object_id)
        payload: dict[str, Any] = dict(options)
        payload.setdefault("action", action)
        response = self._request("POST", f"{user['@url']}/gwcheck", json=payload)
        return response.text or 0
