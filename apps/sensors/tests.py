from decimal import Decimal
from datetime import datetime, time, timedelta

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone
from rest_framework.authtoken.models import Token
from rest_framework.test import APIClient

from apps.facilities.models import Building, Space
from apps.sensors.models import Measurement, Sensor


class SensorTests(TestCase):
    def setUp(self):
        user = get_user_model().objects.create_user(
            username="sensor-admin",
            password="SafeTestPassword-42",
        )
        self.token = Token.objects.create(user=user)
        self.api = APIClient()
        self.building = Building.objects.create(name="Bâtiment capteurs")
        self.space = Space.objects.create(building=self.building, name="Espace actif")

    def authorize_api(self):
        self.api.credentials(HTTP_AUTHORIZATION=f"Token {self.token.key}")

    def payload(self, **overrides):
        data = {
            "name": "Capteur de test",
            "sensor_type": Sensor.SensorType.TEMPERATURE,
            "space": self.space.pk,
            "minimum_threshold": "10.00",
            "maximum_threshold": "30.00",
            "description": "Capteur de démonstration",
            "is_active": True,
        }
        data.update(overrides)
        return data

    def create_sensor(self, **overrides):
        return Sensor.objects.create(
            name=overrides.pop("name", "Capteur enregistré"),
            sensor_type=overrides.pop("sensor_type", Sensor.SensorType.TEMPERATURE),
            space=overrides.pop("space", self.space),
            minimum_threshold=overrides.pop("minimum_threshold", Decimal("10.00")),
            maximum_threshold=overrides.pop("maximum_threshold", Decimal("30.00")),
            **overrides,
        )

    def test_create_temperature_sensor_assigns_celsius(self):
        self.authorize_api()
        response = self.api.post(
            reverse("sensor-list"),
            self.payload(sensor_type="TEMPERATURE", minimum_threshold="-10", maximum_threshold="35"),
            format="json",
        )

        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.json()["sensor_type"], "TEMPERATURE")
        self.assertEqual(response.json()["unit"], "°C")

    def test_create_humidity_sensor_assigns_percent(self):
        self.authorize_api()
        response = self.api.post(
            reverse("sensor-list"),
            self.payload(sensor_type="HUMIDITY", minimum_threshold="25", maximum_threshold="75"),
            format="json",
        )

        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.json()["unit"], "%")

    def test_unit_is_automatic_even_if_client_sends_inconsistent_unit(self):
        self.authorize_api()
        response = self.api.post(
            reverse("sensor-list"),
            self.payload(
                sensor_type="HUMIDITY",
                minimum_threshold="20",
                maximum_threshold="80",
                unit="°C",
            ),
            format="json",
        )

        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.json()["unit"], "%")
        self.assertEqual(Sensor.objects.get(pk=response.json()["id"]).unit, "%")

    def test_unit_is_recalculated_for_model_partial_update(self):
        sensor = self.create_sensor()
        sensor.sensor_type = Sensor.SensorType.HUMIDITY
        sensor.minimum_threshold = Decimal("20")
        sensor.maximum_threshold = Decimal("80")

        sensor.save(update_fields=("sensor_type", "minimum_threshold", "maximum_threshold"))
        sensor.refresh_from_db()

        self.assertEqual(sensor.unit, "%")

    def test_invalid_sensor_type_is_rejected_by_api(self):
        self.authorize_api()
        response = self.api.post(
            reverse("sensor-list"), self.payload(sensor_type="CO2"), format="json"
        )

        self.assertEqual(response.status_code, 400)
        self.assertIn("sensor_type", response.json())

    def test_name_longer_than_150_characters_is_rejected(self):
        self.authorize_api()
        response = self.api.post(
            reverse("sensor-list"), self.payload(name="x" * 151), format="json"
        )

        self.assertEqual(response.status_code, 400)
        self.assertIn("name", response.json())

    def test_nonexistent_space_is_rejected(self):
        self.authorize_api()
        response = self.api.post(
            reverse("sensor-list"), self.payload(space=999999), format="json"
        )

        self.assertEqual(response.status_code, 400)
        self.assertIn("space", response.json())

    def test_inactive_space_is_rejected_by_api_and_model(self):
        self.authorize_api()
        inactive_space = Space.objects.create(
            building=self.building,
            name="Espace inactif",
            is_active=False,
        )
        response = self.api.post(
            reverse("sensor-list"), self.payload(space=inactive_space.pk), format="json"
        )
        sensor = Sensor(
            name="Capteur refusé",
            sensor_type=Sensor.SensorType.TEMPERATURE,
            space=inactive_space,
            minimum_threshold=Decimal("10"),
            maximum_threshold=Decimal("30"),
        )

        self.assertEqual(response.status_code, 400)
        self.assertIn("space", response.json())
        with self.assertRaises(ValidationError):
            sensor.full_clean()

    def test_temperature_minimum_below_technical_limit_is_rejected(self):
        self.authorize_api()
        response = self.api.post(
            reverse("sensor-list"),
            self.payload(minimum_threshold="-50.01", maximum_threshold="20"),
            format="json",
        )

        self.assertEqual(response.status_code, 400)
        self.assertIn("minimum_threshold", response.json())

    def test_temperature_maximum_above_technical_limit_is_rejected(self):
        self.authorize_api()
        response = self.api.post(
            reverse("sensor-list"),
            self.payload(minimum_threshold="20", maximum_threshold="80.01"),
            format="json",
        )

        self.assertEqual(response.status_code, 400)
        self.assertIn("maximum_threshold", response.json())

    def test_humidity_thresholds_obey_zero_to_one_hundred_limits(self):
        self.authorize_api()
        below = self.api.post(
            reverse("sensor-list"),
            self.payload(sensor_type="HUMIDITY", minimum_threshold="-0.01", maximum_threshold="50"),
            format="json",
        )
        above = self.api.post(
            reverse("sensor-list"),
            self.payload(sensor_type="HUMIDITY", minimum_threshold="50", maximum_threshold="100.01"),
            format="json",
        )

        self.assertEqual(below.status_code, 400)
        self.assertIn("minimum_threshold", below.json())
        self.assertEqual(above.status_code, 400)
        self.assertIn("maximum_threshold", above.json())

    def test_minimum_must_be_strictly_less_than_maximum(self):
        self.authorize_api()
        equal = self.api.post(
            reverse("sensor-list"),
            self.payload(minimum_threshold="20", maximum_threshold="20"),
            format="json",
        )
        reversed_order = self.api.post(
            reverse("sensor-list"),
            self.payload(minimum_threshold="25", maximum_threshold="20"),
            format="json",
        )

        self.assertEqual(equal.status_code, 400)
        self.assertEqual(reversed_order.status_code, 400)
        self.assertIn("maximum_threshold", equal.json())

    def test_technical_boundary_values_are_accepted(self):
        temperature = self.create_sensor(
            name="Température limites",
            minimum_threshold=Decimal("-50.00"),
            maximum_threshold=Decimal("80.00"),
        )
        humidity = self.create_sensor(
            name="Humidité limites",
            sensor_type=Sensor.SensorType.HUMIDITY,
            minimum_threshold=Decimal("0.00"),
            maximum_threshold=Decimal("100.00"),
        )

        self.assertEqual(temperature.unit, "°C")
        self.assertEqual(humidity.unit, "%")

    def test_sensor_can_be_updated_and_unit_changes_with_type(self):
        self.authorize_api()
        sensor = self.create_sensor()

        response = self.api.patch(
            reverse("sensor-detail", args=[sensor.pk]),
            {
                "name": "Capteur humidité modifié",
                "sensor_type": "HUMIDITY",
                "minimum_threshold": "15",
                "maximum_threshold": "85",
            },
            format="json",
        )

        sensor.refresh_from_db()
        self.assertEqual(response.status_code, 200)
        self.assertEqual(sensor.name, "Capteur humidité modifié")
        self.assertEqual(sensor.sensor_type, Sensor.SensorType.HUMIDITY)
        self.assertEqual(sensor.unit, "%")

    def test_sensor_can_be_deactivated(self):
        self.authorize_api()
        sensor = self.create_sensor()

        response = self.api.patch(
            reverse("sensor-detail", args=[sensor.pk]), {"is_active": False}, format="json"
        )

        sensor.refresh_from_db()
        self.assertEqual(response.status_code, 200)
        self.assertFalse(sensor.is_active)

    def test_sensor_detail_and_delete_endpoints(self):
        self.authorize_api()
        sensor = self.create_sensor()

        detail = self.api.get(reverse("sensor-detail", args=[sensor.pk]))
        deleted = self.api.delete(reverse("sensor-detail", args=[sensor.pk]))

        self.assertEqual(detail.status_code, 200)
        self.assertEqual(detail.json()["id"], sensor.pk)
        self.assertEqual(deleted.status_code, 204)
        self.assertFalse(Sensor.objects.filter(pk=sensor.pk).exists())

    def test_filtering_by_sensor_type(self):
        self.authorize_api()
        temperature = self.create_sensor(name="Température")
        humidity = self.create_sensor(
            name="Humidité",
            sensor_type=Sensor.SensorType.HUMIDITY,
            minimum_threshold=Decimal("20"),
            maximum_threshold=Decimal("80"),
        )

        response = self.api.get(reverse("sensor-list"), {"sensor_type": "HUMIDITY"})

        self.assertEqual(response.status_code, 200)
        self.assertEqual([item["id"] for item in response.json()], [humidity.pk])
        self.assertNotIn(temperature.pk, [item["id"] for item in response.json()])

    def test_filtering_by_building_space_and_active_state(self):
        self.authorize_api()
        sensor = self.create_sensor(name="Filtré")
        other_building = Building.objects.create(name="Autre bâtiment")
        other_space = Space.objects.create(building=other_building, name="Autre espace")
        other_sensor = self.create_sensor(
            name="Autre capteur", space=other_space, is_active=False
        )

        by_building = self.api.get(reverse("sensor-list"), {"building": self.building.pk})
        by_space = self.api.get(reverse("sensor-list"), {"space": other_space.pk})
        inactive = self.api.get(reverse("sensor-list"), {"is_active": "false"})
        active = self.api.get(reverse("sensor-list"), {"is_active": "true"})

        self.assertEqual([item["id"] for item in by_building.json()], [sensor.pk])
        self.assertEqual([item["id"] for item in by_space.json()], [other_sensor.pk])
        self.assertEqual([item["id"] for item in inactive.json()], [other_sensor.pk])
        self.assertEqual([item["id"] for item in active.json()], [sensor.pk])

    def test_invalid_filters_return_json_validation_error(self):
        self.authorize_api()
        response = self.api.get(reverse("sensor-list"), {"sensor_type": "CO2"})

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response["Content-Type"], "application/json")
        self.assertIn("sensor_type", response.json())

    def test_api_requires_token_and_valid_token_can_list_sensors(self):
        denied = self.api.get(reverse("sensor-list"))
        self.authorize_api()
        allowed = self.api.get(reverse("sensor-list"))

        self.assertEqual(denied.status_code, 401)
        self.assertEqual(denied["Content-Type"], "application/json")
        self.assertEqual(allowed.status_code, 200)

    def test_api_rejects_non_numeric_thresholds_with_json_error(self):
        self.authorize_api()
        response = self.api.post(
            reverse("sensor-list"),
            self.payload(minimum_threshold="chaud"),
            format="json",
        )

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response["Content-Type"], "application/json")
        self.assertIn("minimum_threshold", response.json())

    def test_html_sensor_pages_require_authentication(self):
        response = self.client.get(reverse("sensors:sensor-list"))

        self.assertRedirects(
            response,
            f"{reverse('accounts:login')}?next={reverse('sensors:sensor-list')}",
        )

    def test_html_sensor_pages_render_for_authenticated_user(self):
        user = get_user_model().objects.get(username="sensor-admin")
        self.client.force_login(user)
        sensor = self.create_sensor()
        urls = (
            reverse("sensors:sensor-list"),
            reverse("sensors:sensor-create"),
            reverse("sensors:sensor-detail", args=[sensor.pk]),
            reverse("sensors:sensor-update", args=[sensor.pk]),
            reverse("sensors:sensor-delete", args=[sensor.pk]),
        )

        responses = [self.client.get(url) for url in urls]

        self.assertEqual([response.status_code for response in responses], [200] * len(urls))
        self.assertContains(responses[2], "Bâtiment capteurs")
        self.assertContains(responses[2], "Seuil minimum")

    def test_html_form_enforces_threshold_rules_on_server(self):
        user = get_user_model().objects.get(username="sensor-admin")
        self.client.force_login(user)
        response = self.client.post(
            reverse("sensors:sensor-create"),
            {
                "name": "Capteur HTML invalide",
                "sensor_type": "TEMPERATURE",
                "space": self.space.pk,
                "minimum_threshold": "81",
                "maximum_threshold": "90",
                "description": "",
                "is_active": "on",
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertFalse(Sensor.objects.filter(name="Capteur HTML invalide").exists())
        self.assertContains(response, "doit être compris")


class MeasurementTests(TestCase):
    def setUp(self):
        user = get_user_model().objects.create_user(
            username="measurement-admin",
            password="SafeTestPassword-42",
        )
        self.token = Token.objects.create(user=user)
        self.api = APIClient()
        self.api.credentials(HTTP_AUTHORIZATION=f"Token {self.token.key}")
        self.building = Building.objects.create(name="Bâtiment mesures")
        self.space = Space.objects.create(building=self.building, name="Espace mesures")
        self.temperature_sensor = Sensor.objects.create(
            name="Température",
            sensor_type=Sensor.SensorType.TEMPERATURE,
            space=self.space,
            minimum_threshold=Decimal("10"),
            maximum_threshold=Decimal("30"),
        )
        self.humidity_sensor = Sensor.objects.create(
            name="Humidité",
            sensor_type=Sensor.SensorType.HUMIDITY,
            space=self.space,
            minimum_threshold=Decimal("20"),
            maximum_threshold=Decimal("80"),
        )

    def measurement_payload(self, sensor=None, value="22.5", **overrides):
        payload = {"sensor": (sensor or self.temperature_sensor).pk, "value": value}
        payload.update(overrides)
        return payload

    def post_measurement(self, sensor=None, value="22.5", **overrides):
        return self.api.post(
            reverse("measurement-list"),
            self.measurement_payload(sensor=sensor, value=value, **overrides),
            format="json",
        )

    def add_measurement(self, sensor=None, value="22.5", recorded_at=None):
        return Measurement.objects.create(
            sensor=sensor or self.temperature_sensor,
            value=Decimal(str(value)),
            recorded_at=recorded_at or timezone.now(),
        )

    def test_valid_temperature_measurement_is_recorded(self):
        response = self.post_measurement(value="35.25")

        self.assertEqual(response.status_code, 201)
        self.assertEqual(Measurement.objects.count(), 1)
        self.assertEqual(response.json()["unit"], "°C")
        self.assertEqual(response.json()["value"], "35.25")

    def test_valid_humidity_measurement_is_recorded(self):
        response = self.post_measurement(self.humidity_sensor, "95")

        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.json()["unit"], "%")
        self.assertEqual(response.json()["value"], "95.00")

    def test_measurement_can_exceed_environmental_thresholds_when_physically_valid(self):
        response = self.post_measurement(value="35")

        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.json()["value"], "35.00")
        self.assertEqual(Measurement.objects.count(), 1)

    def test_temperature_below_minus_fifty_is_rejected(self):
        response = self.post_measurement(value="-50.01")

        self.assertEqual(response.status_code, 400)
        self.assertIn("value", response.json())

    def test_temperature_above_eighty_is_rejected(self):
        response = self.post_measurement(value="80.01")

        self.assertEqual(response.status_code, 400)
        self.assertIn("value", response.json())

    def test_humidity_below_zero_is_rejected(self):
        response = self.post_measurement(self.humidity_sensor, "-0.01")

        self.assertEqual(response.status_code, 400)
        self.assertIn("value", response.json())

    def test_humidity_above_one_hundred_is_rejected(self):
        response = self.post_measurement(self.humidity_sensor, "100.01")

        self.assertEqual(response.status_code, 400)
        self.assertIn("value", response.json())

    def test_non_numeric_nan_and_infinite_values_are_rejected(self):
        for invalid in ("chaud", "NaN", "Infinity", "-Infinity", None):
            with self.subTest(value=invalid):
                response = self.post_measurement(value=invalid)
                self.assertEqual(response.status_code, 400)
                self.assertIn("value", response.json())

    def test_measurements_for_inactive_sensor_are_rejected(self):
        self.temperature_sensor.is_active = False
        self.temperature_sensor.save()

        response = self.post_measurement()

        self.assertEqual(response.status_code, 400)
        self.assertIn("sensor", response.json())

    def test_measurements_for_nonexistent_sensor_are_rejected(self):
        response = self.api.post(
            reverse("measurement-list"),
            {"sensor": 999999, "value": "20"},
            format="json",
        )

        self.assertEqual(response.status_code, 400)
        self.assertIn("sensor", response.json())

    def test_measurements_for_inactive_space_are_rejected(self):
        self.space.is_active = False
        self.space.save()

        response = self.post_measurement()

        self.assertEqual(response.status_code, 400)
        self.assertIn("sensor", response.json())

    def test_measurements_for_inactive_building_are_rejected(self):
        self.building.is_active = False
        self.building.save()

        response = self.post_measurement()

        self.assertEqual(response.status_code, 400)
        self.assertIn("sensor", response.json())

    def test_recorded_received_and_created_timestamps_are_saved(self):
        recorded_at = "2026-11-05T12:30:00-03:00"

        response = self.post_measurement(recorded_at=recorded_at)

        self.assertEqual(response.status_code, 201)
        measurement = Measurement.objects.get(pk=response.json()["id"])
        self.assertEqual(measurement.recorded_at, datetime.fromisoformat(recorded_at))
        self.assertTrue(timezone.is_aware(measurement.recorded_at))
        self.assertTrue(timezone.is_aware(measurement.received_at))
        self.assertTrue(timezone.is_aware(measurement.created_at))
        self.assertIsNotNone(response.json()["received_at"])

    def test_missing_recorded_at_uses_current_server_time(self):
        before = timezone.now()
        response = self.post_measurement()
        after = timezone.now()
        measurement = Measurement.objects.get(pk=response.json()["id"])

        self.assertEqual(response.status_code, 201)
        self.assertLessEqual(before, measurement.recorded_at)
        self.assertLessEqual(measurement.recorded_at, after)

    def test_invalid_recorded_at_is_rejected_as_json(self):
        response = self.post_measurement(recorded_at="not-a-date")

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response["Content-Type"], "application/json")
        self.assertIn("recorded_at", response.json())

    def test_measurements_can_be_listed_and_retrieved_as_json(self):
        measurement = self.add_measurement()

        listing = self.api.get(reverse("measurement-list"))
        detail = self.api.get(reverse("measurement-detail", args=[measurement.pk]))

        self.assertEqual(listing.status_code, 200)
        self.assertEqual(listing["Content-Type"], "application/json")
        self.assertEqual(listing.json()["count"], 1)
        self.assertEqual(detail.status_code, 200)
        self.assertEqual(detail.json()["id"], measurement.pk)

    def test_sensor_history_endpoint_returns_only_its_measurements(self):
        measurement = self.add_measurement(self.temperature_sensor)
        self.add_measurement(self.humidity_sensor, "50")

        response = self.api.get(
            reverse("sensor-measurements", args=[self.temperature_sensor.pk])
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["count"], 1)
        self.assertEqual(response.json()["results"][0]["id"], measurement.pk)

    def test_filtering_by_building_and_space(self):
        matching = self.add_measurement()
        other_building = Building.objects.create(name="Autre bâtiment mesures")
        other_space = Space.objects.create(building=other_building, name="Autre espace mesures")
        other_sensor = Sensor.objects.create(
            name="Autre capteur mesures",
            sensor_type=Sensor.SensorType.TEMPERATURE,
            space=other_space,
            minimum_threshold=Decimal("0"),
            maximum_threshold=Decimal("40"),
        )
        self.add_measurement(other_sensor, "18")

        by_building = self.api.get(reverse("measurement-list"), {"building": self.building.pk})
        by_space = self.api.get(reverse("measurement-list"), {"space": self.space.pk})

        self.assertEqual(by_building.status_code, 200)
        self.assertEqual(by_building.json()["count"], 1)
        self.assertEqual(by_building.json()["results"][0]["id"], matching.pk)
        self.assertEqual(by_space.json()["count"], 1)

    def test_filtering_by_period_includes_both_local_calendar_dates(self):
        tz = timezone.get_current_timezone()
        day_one = timezone.make_aware(datetime(2026, 11, 4, 23, 45), tz)
        day_two = timezone.make_aware(datetime(2026, 11, 5, 0, 15), tz)
        outside = timezone.make_aware(datetime(2026, 11, 6, 0, 0), tz)
        in_range = self.add_measurement(recorded_at=day_one)
        self.add_measurement(recorded_at=day_two)
        self.add_measurement(recorded_at=outside)

        response = self.api.get(
            reverse("measurement-list"),
            {"date_from": "2026-11-04", "date_to": "2026-11-05"},
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["count"], 2)
        self.assertIn(in_range.pk, [item["id"] for item in response.json()["results"]])

    def test_invalid_date_range_and_ordering_return_json_validation_errors(self):
        invalid_dates = self.api.get(
            reverse("measurement-list"),
            {"date_from": "2026-11-06", "date_to": "2026-11-05"},
        )
        invalid_ordering = self.api.get(reverse("measurement-list"), {"ordering": "value"})

        self.assertEqual(invalid_dates.status_code, 400)
        self.assertIn("date_to", invalid_dates.json())
        self.assertEqual(invalid_ordering.status_code, 400)
        self.assertIn("ordering", invalid_ordering.json())

    def test_measurements_can_be_ordered_oldest_first_and_newest_first(self):
        older = self.add_measurement(recorded_at=timezone.now() - timedelta(days=1))
        newer = self.add_measurement(recorded_at=timezone.now())

        ascending = self.api.get(reverse("measurement-list"), {"ordering": "recorded_at"})
        descending = self.api.get(reverse("measurement-list"), {"ordering": "-recorded_at"})

        self.assertEqual([item["id"] for item in ascending.json()["results"]], [older.pk, newer.pk])
        self.assertEqual([item["id"] for item in descending.json()["results"]], [newer.pk, older.pk])

    def test_measurements_are_paginated_twenty_per_page_and_size_can_be_changed(self):
        for index in range(22):
            self.add_measurement(value=10 + (index % 20))

        first_page = self.api.get(reverse("measurement-list"))
        second_page = self.api.get(reverse("measurement-list"), {"page": 2})
        custom_page = self.api.get(reverse("measurement-list"), {"page_size": 5})

        self.assertEqual(first_page.json()["count"], 22)
        self.assertEqual(len(first_page.json()["results"]), 20)
        self.assertIsNotNone(first_page.json()["next"])
        self.assertEqual(len(second_page.json()["results"]), 2)
        self.assertEqual(len(custom_page.json()["results"]), 5)

    def test_api_requires_token_and_valid_token_can_create_measurement(self):
        anonymous = APIClient()
        denied = anonymous.post(
            reverse("measurement-list"),
            self.measurement_payload(),
            format="json",
        )
        accepted = self.post_measurement()

        self.assertEqual(denied.status_code, 401)
        self.assertEqual(denied["Content-Type"], "application/json")
        self.assertEqual(accepted.status_code, 201)

    def test_html_measurement_pages_require_authentication(self):
        response = self.client.get(reverse("sensors:measurement-list"))

        self.assertRedirects(
            response,
            f"{reverse('accounts:login')}?next={reverse('sensors:measurement-list')}",
        )

    def test_html_measurement_list_history_and_detail_pages_render(self):
        user = get_user_model().objects.get(username="measurement-admin")
        self.client.force_login(user)
        measurement = self.add_measurement()
        urls = (
            reverse("sensors:measurement-list"),
            reverse("sensors:sensor-measurements", args=[self.temperature_sensor.pk]),
            reverse("sensors:measurement-detail", args=[measurement.pk]),
        )

        responses = [self.client.get(url) for url in urls]

        self.assertEqual([response.status_code for response in responses], [200, 200, 200])
        self.assertContains(responses[0], "Date de mesure")
        self.assertContains(responses[2], "Bâtiment mesures")

    def test_sensor_delete_confirmation_archives_instead_of_losing_measurements(self):
        user = get_user_model().objects.get(username="measurement-admin")
        self.client.force_login(user)
        measurement = self.add_measurement()

        confirmation = self.client.get(
            reverse("sensors:sensor-delete", args=[self.temperature_sensor.pk])
        )
        unconfirmed = self.client.post(
            reverse("sensors:sensor-delete", args=[self.temperature_sensor.pk])
        )
        self.temperature_sensor.refresh_from_db()
        remains_active = self.temperature_sensor.is_active
        deletion = self.client.post(
            reverse("sensors:sensor-delete", args=[self.temperature_sensor.pk]),
            {"confirmed": "1"},
        )

        self.temperature_sensor.refresh_from_db()
        self.assertEqual(confirmation.status_code, 200)
        self.assertContains(confirmation, "Désactiver le capteur")
        self.assertContains(confirmation, "Température")
        self.assertContains(confirmation, "données historiques")
        self.assertRedirects(
            unconfirmed,
            reverse("sensors:sensor-delete", args=[self.temperature_sensor.pk]),
        )
        self.assertTrue(remains_active)
        self.assertRedirects(deletion, reverse("sensors:sensor-list"))
        self.assertFalse(self.temperature_sensor.is_active)
        self.assertTrue(Measurement.objects.filter(pk=measurement.pk).exists())

    def test_sensor_delete_api_archives_and_preserves_measurements(self):
        measurement = self.add_measurement()

        response = self.api.delete(
            reverse("sensor-detail", args=[self.temperature_sensor.pk])
        )

        self.temperature_sensor.refresh_from_db()
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()["archived"])
        self.assertFalse(self.temperature_sensor.is_active)
        self.assertTrue(Measurement.objects.filter(pk=measurement.pk).exists())

    def test_measurement_endpoint_does_not_allow_deletion(self):
        measurement = self.add_measurement()

        response = self.api.delete(reverse("measurement-detail", args=[measurement.pk]))

        self.assertEqual(response.status_code, 405)
        self.assertTrue(Measurement.objects.filter(pk=measurement.pk).exists())
