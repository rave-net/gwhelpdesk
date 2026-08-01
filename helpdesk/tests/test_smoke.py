from django.contrib.auth.hashers import make_password
from django.test import Client, TestCase
from django.urls import reverse

from helpdesk.forms import AddUser
from helpdesk.models import Admin


class SmokeTests(TestCase):
    def setUp(self):
        self.admin = Admin.objects.create(
            username="admin",
            first_name="Test",
            last_name="Admin",
            password=make_password("test-password"),
            password2="",
            role=Admin.ADMIN,
        )
        self.client = Client()

    def test_login_page_loads(self):
        response = self.client.get(reverse("login"))
        self.assertEqual(response.status_code, 200)

    def test_login_accepts_django_password_hash(self):
        response = self.client.post(
            reverse("login"),
            {"username": "admin", "password": "test-password"},
        )
        self.assertRedirects(response, reverse("index"))

    def test_add_user_form_does_not_contact_groupwise_at_import(self):
        form = AddUser()
        self.assertIn("postOfficeName", form.fields)

    def test_protected_index_redirects_to_login(self):
        response = self.client.get(reverse("index"))
        self.assertRedirects(response, reverse("login"))
