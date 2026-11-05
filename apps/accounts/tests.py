from django.contrib.auth import get_user_model
from django.test import Client, TestCase
from django.urls import reverse
from rest_framework.authtoken.models import Token
from rest_framework.test import APIClient


class AuthenticationTests(TestCase):
    def setUp(self):
        self.username = "farm-admin"
        self.password = "SafeTestPassword-42"
        self.user = get_user_model().objects.create_user(
            username=self.username,
            password=self.password,
        )
        self.token = Token.objects.create(user=self.user)
        self.api_client = APIClient()

    def test_web_login_accepts_valid_credentials(self):
        response = self.client.post(
            reverse("accounts:login"),
            {"username": self.username, "password": self.password},
        )

        self.assertRedirects(response, "/")
        self.assertTrue(response.wsgi_request.user.is_authenticated)

    def test_web_login_rejects_incorrect_password(self):
        response = self.client.post(
            reverse("accounts:login"),
            {"username": self.username, "password": "incorrect"},
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Nom d’utilisateur ou mot de passe incorrect.")
        self.assertFalse(response.wsgi_request.user.is_authenticated)

    def test_web_logout_ends_the_session(self):
        csrf_client = Client(enforce_csrf_checks=True)
        csrf_client.force_login(self.user)
        page = csrf_client.get("/")
        csrf_token = csrf_client.cookies["csrftoken"].value

        rejected = csrf_client.post(reverse("accounts:logout"))
        response = csrf_client.post(
            reverse("accounts:logout"),
            {"csrfmiddlewaretoken": csrf_token},
        )

        self.assertEqual(page.status_code, 200)
        self.assertEqual(rejected.status_code, 403)
        self.assertRedirects(response, reverse("accounts:login"))
        self.assertNotIn("_auth_user_id", csrf_client.session)

    def test_home_page_redirects_anonymous_user_to_login(self):
        response = self.client.get("/")

        self.assertRedirects(response, f"{reverse('accounts:login')}?next=/")

    def test_api_profile_requires_a_token_and_returns_json_error(self):
        response = self.api_client.get(reverse("accounts:current-user"))

        self.assertEqual(response.status_code, 401)
        self.assertEqual(response["Content-Type"], "application/json")
        self.assertIn("detail", response.json())

    def test_valid_token_authorizes_protected_api_route(self):
        self.api_client.credentials(HTTP_AUTHORIZATION=f"Token {self.token.key}")

        response = self.api_client.get(reverse("accounts:current-user"))

        self.assertEqual(response.status_code, 200)

    def test_profile_returns_identity_without_token_or_password(self):
        self.api_client.credentials(HTTP_AUTHORIZATION=f"Token {self.token.key}")

        response = self.api_client.get(reverse("accounts:current-user"))

        self.assertEqual(response.json(), {"id": self.user.pk, "username": self.username})
        self.assertNotIn("token", response.json())
        self.assertNotIn("password", response.json())

    def test_token_revocation_invalidates_the_presented_token(self):
        self.api_client.credentials(HTTP_AUTHORIZATION=f"Token {self.token.key}")

        revoke_response = self.api_client.post(reverse("accounts:token-revoke"))
        protected_response = self.api_client.get(reverse("accounts:current-user"))

        self.assertEqual(revoke_response.status_code, 200)
        self.assertEqual(revoke_response.json(), {"detail": "Token revoked."})
        self.assertEqual(protected_response.status_code, 401)

    def test_token_endpoint_issues_token_for_valid_credentials(self):
        response = self.api_client.post(
            reverse("accounts:token-create"),
            {"username": self.username, "password": self.password},
            format="json",
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["token"], self.token.key)

    def test_login_form_requires_csrf_token(self):
        csrf_client = Client(enforce_csrf_checks=True)
        login_url = reverse("accounts:login")
        page = csrf_client.get(login_url)
        csrf_token = csrf_client.cookies["csrftoken"].value

        rejected = csrf_client.post(
            login_url,
            {"username": self.username, "password": self.password},
        )
        accepted = csrf_client.post(
            login_url,
            {
                "username": self.username,
                "password": self.password,
                "csrfmiddlewaretoken": csrf_token,
            },
        )

        self.assertEqual(page.status_code, 200)
        self.assertEqual(rejected.status_code, 403)
        self.assertRedirects(accepted, "/")

    def test_unknown_api_route_returns_json_404(self):
        response = self.api_client.get("/api/v1/not-a-real-endpoint/")
        self.assertEqual(response.status_code, 404)
        self.assertEqual(response["Content-Type"], "application/json")
        self.assertIn("detail", response.json())
