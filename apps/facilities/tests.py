from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from rest_framework.authtoken.models import Token
from rest_framework.test import APIClient

from apps.facilities.models import Building, Space


class FacilitiesTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(
            username="facilities-admin",
            password="SafeTestPassword-42",
        )
        self.token = Token.objects.create(user=self.user)
        self.api = APIClient()

    def authorize_api(self):
        self.api.credentials(HTTP_AUTHORIZATION=f"Token {self.token.key}")

    def test_building_creation_and_list(self):
        self.authorize_api()
        created = self.api.post(
            reverse("building-list"),
            {"name": "Poulailler Nord", "location": "Ferme principale"},
            format="json",
        )

        listing = self.api.get(reverse("building-list"))

        self.assertEqual(created.status_code, 201)
        self.assertEqual(created.json()["name"], "Poulailler Nord")
        self.assertEqual(listing.status_code, 200)
        self.assertEqual(len(listing.json()), 1)

    def test_building_can_be_consulted_and_modified(self):
        self.authorize_api()
        building = Building.objects.create(name="Bâtiment A")

        detail = self.api.get(reverse("building-detail", args=[building.pk]))
        updated = self.api.patch(
            reverse("building-detail", args=[building.pk]),
            {"name": "Bâtiment rénové", "location": "Secteur Est"},
            format="json",
        )

        self.assertEqual(detail.status_code, 200)
        self.assertEqual(detail.json()["id"], building.pk)
        self.assertEqual(updated.status_code, 200)
        self.assertEqual(updated.json()["name"], "Bâtiment rénové")

    def test_building_can_be_deactivated(self):
        self.authorize_api()
        building = Building.objects.create(name="Bâtiment actif")

        response = self.api.patch(
            reverse("building-detail", args=[building.pk]),
            {"is_active": False},
            format="json",
        )

        building.refresh_from_db()
        self.assertEqual(response.status_code, 200)
        self.assertFalse(building.is_active)

    def test_space_creation_and_building_association(self):
        self.authorize_api()
        building = Building.objects.create(name="Poulailler")

        response = self.api.post(
            reverse("space-list"),
            {"building": building.pk, "name": "Zone de ponte"},
            format="json",
        )

        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.json()["building"], building.pk)
        self.assertEqual(Space.objects.get(pk=response.json()["id"]).building, building)

    def test_space_rejects_missing_or_nonexistent_building(self):
        self.authorize_api()

        missing = self.api.post(
            reverse("space-list"), {"name": "Sans bâtiment"}, format="json"
        )
        nonexistent = self.api.post(
            reverse("space-list"),
            {"building": 999999, "name": "Bâtiment absent"},
            format="json",
        )

        self.assertEqual(missing.status_code, 400)
        self.assertIn("building", missing.json())
        self.assertEqual(nonexistent.status_code, 400)
        self.assertIn("building", nonexistent.json())

    def test_space_can_be_modified_and_filtered_by_building(self):
        self.authorize_api()
        first_building = Building.objects.create(name="Étable A")
        second_building = Building.objects.create(name="Étable B")
        first_space = Space.objects.create(building=first_building, name="Espace initial")
        Space.objects.create(building=second_building, name="Autre espace")

        updated = self.api.patch(
            reverse("space-detail", args=[first_space.pk]),
            {"name": "Espace modifié"},
            format="json",
        )
        filtered = self.api.get(reverse("space-list"), {"building": first_building.pk})
        invalid_filter = self.api.get(reverse("space-list"), {"building": "invalide"})

        self.assertEqual(updated.status_code, 200)
        self.assertEqual(updated.json()["name"], "Espace modifié")
        self.assertEqual(filtered.status_code, 200)
        self.assertEqual([item["id"] for item in filtered.json()], [first_space.pk])
        self.assertEqual(invalid_filter.status_code, 400)

    def test_api_requires_token_and_returns_json(self):
        response = self.api.get(reverse("building-list"))

        self.assertEqual(response.status_code, 401)
        self.assertEqual(response["Content-Type"], "application/json")
        self.assertIn("detail", response.json())

    def test_token_authorizes_api_access(self):
        self.authorize_api()

        response = self.api.get(reverse("building-list"))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response["Content-Type"], "application/json")

    def test_validation_errors_and_missing_objects_use_json_status_codes(self):
        self.authorize_api()

        invalid = self.api.post(
            reverse("building-list"), {"name": "   "}, format="json"
        )
        missing = self.api.get(reverse("building-detail", args=[999999]))

        self.assertEqual(invalid.status_code, 400)
        self.assertEqual(invalid["Content-Type"], "application/json")
        self.assertIn("name", invalid.json())
        self.assertEqual(missing.status_code, 404)
        self.assertEqual(missing["Content-Type"], "application/json")

    def test_delete_archives_building_and_preserves_its_space(self):
        self.authorize_api()
        building = Building.objects.create(name="Bâtiment avec espace")
        space = Space.objects.create(building=building, name="Espace conservé")

        response = self.api.delete(reverse("building-detail", args=[building.pk]))

        building.refresh_from_db()
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()["archived"])
        self.assertFalse(building.is_active)
        self.assertTrue(Space.objects.filter(pk=space.pk).exists())

    def test_delete_unreferenced_space_removes_it_after_api_request(self):
        self.authorize_api()
        building = Building.objects.create(name="Bâtiment")
        space = Space.objects.create(building=building, name="Espace supprimable")

        response = self.api.delete(reverse("space-detail", args=[space.pk]))

        self.assertEqual(response.status_code, 204)
        self.assertFalse(Space.objects.filter(pk=space.pk).exists())

    def test_html_facility_pages_require_login(self):
        response = self.client.get(reverse("facilities:building-list"))

        self.assertRedirects(
            response,
            f"{reverse('accounts:login')}?next={reverse('facilities:building-list')}",
        )

    def test_html_list_detail_create_update_and_delete_pages_render(self):
        self.client.force_login(self.user)
        building = Building.objects.create(name="Bâtiment pages")
        space = Space.objects.create(building=building, name="Espace pages")
        urls = (
            reverse("facilities:building-list"),
            reverse("facilities:building-create"),
            reverse("facilities:building-detail", args=[building.pk]),
            reverse("facilities:building-update", args=[building.pk]),
            reverse("facilities:building-delete", args=[building.pk]),
            reverse("facilities:space-list"),
            reverse("facilities:space-create"),
            reverse("facilities:space-detail", args=[space.pk]),
            reverse("facilities:space-update", args=[space.pk]),
            reverse("facilities:space-delete", args=[space.pk]),
        )

        responses = [self.client.get(url) for url in urls]

        self.assertEqual([response.status_code for response in responses], [200] * len(urls))
        self.assertContains(responses[1], 'maxlength="150"')
        self.assertContains(responses[1], "data-trim-required=")

    def test_html_building_form_creates_record_and_confirmation_page_is_protected(self):
        self.client.force_login(self.user)
        form_response = self.client.post(
            reverse("facilities:building-create"),
            {"name": "Bâtiment formulaire", "location": "Nord", "is_active": "on"},
        )
        building = Building.objects.get(name="Bâtiment formulaire")
        confirmation = self.client.get(reverse("facilities:building-delete", args=[building.pk]))

        self.assertRedirects(form_response, reverse("facilities:building-detail", args=[building.pk]))
        self.assertEqual(confirmation.status_code, 200)
        self.assertContains(confirmation, "Confirmer la suppression")

    def test_html_space_form_creates_and_confirmation_post_deletes_with_csrf(self):
        self.client.force_login(self.user)
        building = Building.objects.create(name="Bâtiment HTML")
        response = self.client.post(
            reverse("facilities:space-create"),
            {"building": building.pk, "name": "Espace HTML", "is_active": "on"},
        )
        space = Space.objects.get(name="Espace HTML")
        self.assertRedirects(response, reverse("facilities:space-detail", args=[space.pk]))
        deleted = self.client.post(
            reverse("facilities:space-delete", args=[space.pk]),
            {"confirmed": "1"},
        )

        self.assertRedirects(deleted, reverse("facilities:space-list"))
        self.assertFalse(Space.objects.filter(pk=space.pk).exists())
