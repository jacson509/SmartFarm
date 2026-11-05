from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.test import TestCase
from django.urls import reverse
from rest_framework.authtoken.models import Token
from rest_framework.test import APIClient

from apps.facilities.models import Building, Space
from apps.actuators.models import Actuator, ActuatorCommand


class ActuatorTests(TestCase):
    def setUp(self):
        user = get_user_model().objects.create_user(username="actuator-user", password="SafeTestPassword-42")
        self.token = Token.objects.create(user=user)
        self.api = APIClient()
        self.building = Building.objects.create(name="Bâtiment actionneurs")
        self.space = Space.objects.create(building=self.building, name="Espace actif")

    def authorize(self):
        self.api.credentials(HTTP_AUTHORIZATION=f"Token {self.token.key}")

    def actuator_payload(self, **overrides):
        data = {
            "name": "Ventilateur principal",
            "actuator_type": "FAN",
            "space": self.space.pk,
            "description": "Ventilation du bâtiment",
            "is_active": True,
        }
        data.update(overrides)
        return data

    def make_actuator(self, **overrides):
        return Actuator.objects.create(
            name=overrides.pop("name", "Ventilateur enregistré"),
            actuator_type=overrides.pop("actuator_type", Actuator.ActuatorType.FAN),
            space=overrides.pop("space", self.space),
            **overrides,
        )

    def make_command(self, actuator=None, value="ON", **overrides):
        return ActuatorCommand.objects.create(
            actuator=actuator or self.make_actuator(), value=value, **overrides
        )

    def test_api_actuator_create(self):
        self.authorize()
        response = self.api.post(reverse("actuator-list"), self.actuator_payload(), format="json")
        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.json()["name"], "Ventilateur principal")

    def test_api_actuator_list(self):
        self.authorize()
        self.make_actuator()
        self.assertEqual(self.api.get(reverse("actuator-list")).status_code, 200)

    def test_api_actuator_detail(self):
        self.authorize()
        actuator = self.make_actuator()
        self.assertEqual(self.api.get(reverse("actuator-detail", args=(actuator.pk,))).status_code, 200)

    def test_api_actuator_update(self):
        self.authorize()
        actuator = self.make_actuator()
        response = self.api.patch(reverse("actuator-detail", args=(actuator.pk,)), {"name": "Pompe"}, format="json")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["name"], "Pompe")

    def test_api_actuator_deactivate_and_reactivate(self):
        self.authorize()
        actuator = self.make_actuator()
        url = reverse("actuator-detail", args=(actuator.pk,))
        self.assertEqual(self.api.patch(url, {"is_active": False}, format="json").status_code, 200)
        self.assertFalse(Actuator.objects.get(pk=actuator.pk).is_active)
        self.assertEqual(self.api.patch(url, {"is_active": True}, format="json").status_code, 200)

    def test_invalid_actuator_type_is_rejected(self):
        self.authorize()
        response = self.api.post(reverse("actuator-list"), self.actuator_payload(actuator_type="BOGUS"), format="json")
        self.assertEqual(response.status_code, 400)

    def test_missing_actuator_name_is_rejected(self):
        self.authorize()
        response = self.api.post(reverse("actuator-list"), self.actuator_payload(name="  "), format="json")
        self.assertEqual(response.status_code, 400)

    def test_too_long_actuator_name_is_rejected(self):
        self.authorize()
        response = self.api.post(reverse("actuator-list"), self.actuator_payload(name="x" * 151), format="json")
        self.assertEqual(response.status_code, 400)

    def test_nonexistent_space_is_rejected(self):
        self.authorize()
        response = self.api.post(reverse("actuator-list"), self.actuator_payload(space=99999), format="json")
        self.assertEqual(response.status_code, 400)

    def test_inactive_space_is_rejected(self):
        self.authorize()
        self.space.is_active = False
        self.space.save()
        response = self.api.post(reverse("actuator-list"), self.actuator_payload(), format="json")
        self.assertEqual(response.status_code, 400)

    def test_api_requires_authentication_and_returns_json(self):
        response = self.api.get(reverse("actuator-list"))
        self.assertEqual(response.status_code, 401)
        self.assertEqual(response["Content-Type"], "application/json")

    def test_api_accepts_valid_token(self):
        self.authorize()
        self.assertEqual(self.api.get(reverse("actuator-list")).status_code, 200)

    def test_actuator_filters_by_building_space_type_and_active(self):
        self.authorize()
        active = self.make_actuator()
        inactive = self.make_actuator(name="Lampe", actuator_type=Actuator.ActuatorType.LIGHTING, is_active=False)
        url = reverse("actuator-list")
        for params, expected_ids in (
            ({"building": self.building.pk}, {active.pk, inactive.pk}),
            ({"space": self.space.pk}, {active.pk, inactive.pk}),
            ({"actuator_type": "FAN"}, {active.pk}),
            ({"is_active": "true"}, {active.pk}),
        ):
            response = self.api.get(url, params)
            self.assertEqual(response.status_code, 200)
            self.assertEqual({item["id"] for item in response.json()}, expected_ids)

    def test_invalid_actuator_filter_is_rejected(self):
        self.authorize()
        response = self.api.get(reverse("actuator-list"), {"is_active": "sometimes"})
        self.assertEqual(response.status_code, 400)

    def test_command_on_and_off_are_recorded_pending(self):
        self.authorize()
        actuator = self.make_actuator()
        for value in ("ON", "OFF"):
            response = self.api.post(reverse("actuator-command-list"), {"actuator": actuator.pk, "value": value}, format="json")
            self.assertEqual(response.status_code, 201)
            command = ActuatorCommand.objects.get(pk=response.json()["id"])
            self.assertEqual(command.status, ActuatorCommand.Status.PENDING)
            self.assertIsNone(command.executed_at)

    def test_command_type_must_be_supported(self):
        self.authorize()
        actuator = self.make_actuator()
        response = self.api.post(reverse("actuator-command-list"), {"actuator": actuator.pk, "command_type": "RESET", "value": "ON"}, format="json")
        self.assertEqual(response.status_code, 400)

    def test_command_value_must_be_on_or_off(self):
        self.authorize()
        actuator = self.make_actuator()
        response = self.api.post(reverse("actuator-command-list"), {"actuator": actuator.pk, "value": "MAYBE"}, format="json")
        self.assertEqual(response.status_code, 400)

    def test_client_cannot_set_command_status_or_timestamps(self):
        self.authorize()
        actuator = self.make_actuator()
        response = self.api.post(reverse("actuator-command-list"), {
            "actuator": actuator.pk, "value": "ON", "status": "EXECUTED", "executed_at": "2026-01-01T00:00:00Z"
        }, format="json")
        self.assertEqual(response.status_code, 400)

    def test_inactive_actuator_cannot_receive_command(self):
        self.authorize()
        actuator = self.make_actuator(is_active=False)
        response = self.api.post(reverse("actuator-command-list"), {"actuator": actuator.pk, "value": "ON"}, format="json")
        self.assertEqual(response.status_code, 400)

    def test_inactive_space_or_building_cannot_receive_command(self):
        self.authorize()
        actuator = self.make_actuator()
        self.space.is_active = False
        self.space.save()
        response = self.api.post(reverse("actuator-command-list"), {"actuator": actuator.pk, "value": "ON"}, format="json")
        self.assertEqual(response.status_code, 400)
        self.space.is_active = True
        self.space.save()
        self.building.is_active = False
        self.building.save()
        response = self.api.post(reverse("actuator-command-list"), {"actuator": actuator.pk, "value": "ON"}, format="json")
        self.assertEqual(response.status_code, 400)

    def test_command_list_detail_filters_and_pagination(self):
        self.authorize()
        actuator = self.make_actuator()
        on_command = self.make_command(actuator=actuator, value="ON")
        off_command = self.make_command(actuator=actuator, value="OFF")
        list_url = reverse("actuator-command-list")
        self.assertEqual(self.api.get(list_url).status_code, 200)
        self.assertEqual(self.api.get(reverse("actuator-command-detail", args=(on_command.pk,))).status_code, 200)
        response = self.api.get(list_url, {"actuator": actuator.pk, "status": "PENDING", "command_type": "POWER_STATE"})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["count"], 2)
        self.assertEqual(self.api.get(list_url, {"actuator": "not-an-id"}).status_code, 400)
        self.assertEqual(self.api.get(list_url, {"status": "UNKNOWN"}).status_code, 400)
        self.assertEqual(self.api.get(list_url, {"command_type": "UNKNOWN"}).status_code, 400)
        self.assertEqual(ActuatorCommand.objects.filter(pk__in=(on_command.pk, off_command.pk)).count(), 2)

    def test_command_api_has_no_update_or_delete_and_preserves_history(self):
        self.authorize()
        command = self.make_command()
        url = reverse("actuator-command-detail", args=(command.pk,))
        self.assertEqual(self.api.delete(url).status_code, 405)
        self.assertEqual(self.api.patch(url, {"value": "OFF"}, format="json").status_code, 405)
        self.assertTrue(ActuatorCommand.objects.filter(pk=command.pk).exists())

    def test_api_delete_archives_actuator_with_command_history(self):
        self.authorize()
        actuator = self.make_actuator()
        command = self.make_command(actuator=actuator)
        response = self.api.delete(reverse("actuator-detail", args=(actuator.pk,)))
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()["archived"])
        actuator.refresh_from_db()
        self.assertFalse(actuator.is_active)
        self.assertTrue(ActuatorCommand.objects.filter(pk=command.pk).exists())

    def test_command_api_paginates_at_default_measurement_page_size(self):
        self.authorize()
        actuator = self.make_actuator()
        for number in range(25):
            self.make_command(actuator=actuator, value="ON" if number % 2 else "OFF")
        response = self.api.get(reverse("actuator-command-list"))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["count"], 25)
        self.assertEqual(len(response.json()["results"]), 20)

    def test_command_model_rejects_executed_without_timestamp(self):
        command = ActuatorCommand(actuator=self.make_actuator(), value="ON", status="EXECUTED")
        with self.assertRaises(ValidationError):
            command.save()

    def test_html_actuator_pages_require_login_and_render_for_authenticated_user(self):
        actuator = self.make_actuator()
        for url in (reverse("actuators:actuator-list"), reverse("actuators:actuator-detail", args=(actuator.pk,))):
            self.assertEqual(self.client.get(url).status_code, 302)
        self.client.login(username="actuator-user", password="SafeTestPassword-42")
        self.assertEqual(self.client.get(reverse("actuators:actuator-list")).status_code, 200)
        self.assertEqual(self.client.get(reverse("actuators:actuator-detail", args=(actuator.pk,))).status_code, 200)

    def test_html_command_creation_and_history(self):
        self.client.login(username="actuator-user", password="SafeTestPassword-42")
        actuator = self.make_actuator()
        response = self.client.post(reverse("actuators:command-create", args=(actuator.pk,)), {"value": "ON"})
        self.assertEqual(response.status_code, 302)
        self.assertEqual(actuator.commands.count(), 1)
        self.assertEqual(self.client.get(reverse("actuators:command-list", args=(actuator.pk,))).status_code, 200)

    def test_html_deletion_requires_confirmation_and_archives_with_history(self):
        self.client.login(username="actuator-user", password="SafeTestPassword-42")
        actuator = self.make_actuator()
        command = self.make_command(actuator=actuator)
        url = reverse("actuators:actuator-delete", args=(actuator.pk,))
        self.assertEqual(self.client.post(url, {}).status_code, 302)
        actuator.refresh_from_db()
        self.assertTrue(actuator.is_active)
        self.assertEqual(self.client.post(url, {"confirmed": "1"}).status_code, 302)
        actuator.refresh_from_db()
        self.assertFalse(actuator.is_active)
        self.assertTrue(ActuatorCommand.objects.filter(pk=command.pk).exists())

