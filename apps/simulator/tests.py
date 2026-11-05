import json
import time
from threading import Event
from unittest.mock import Mock, patch
from urllib.error import URLError

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from django.urls import reverse
from rest_framework.authtoken.models import Token
from rest_framework.test import APIClient

from apps.facilities.models import Building, Space
from apps.sensors.models import Sensor
from apps.simulator import runtime


class SimulatorTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(
            username="simulator-user", password="SafeTestPassword-42"
        )
        self.token = Token.objects.create(user=self.user)
        self.api = APIClient()
        self.api.credentials(HTTP_AUTHORIZATION=f"Token {self.token.key}")
        self.building = Building.objects.create(name="Bâtiment simulateur")
        self.space = Space.objects.create(building=self.building, name="Espace simulateur")
        self.temperature = self.create_sensor("Capteur température", Sensor.SensorType.TEMPERATURE)
        self.humidity = self.create_sensor("Capteur humidité", Sensor.SensorType.HUMIDITY)
        runtime.simulation_manager.stop(self.user.pk)

    def tearDown(self):
        runtime.simulation_manager.stop(self.user.pk)

    def create_sensor(self, name, sensor_type, space=None, is_active=True):
        minimum, maximum = (-10, 35) if sensor_type == Sensor.SensorType.TEMPERATURE else (20, 80)
        return Sensor.objects.create(
            name=name,
            sensor_type=sensor_type,
            space=space or self.space,
            minimum_threshold=minimum,
            maximum_threshold=maximum,
            is_active=is_active,
        )

    def start_data(self, **overrides):
        data = {
            "building_id": self.building.pk,
            "space_id": self.space.pk,
            "sensor_ids": [self.temperature.pk],
            "interval": 5,
        }
        data.update(overrides)
        return data

    def wait_for(self, predicate, timeout=2):
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            if predicate():
                return True
            time.sleep(0.01)
        return predicate()

    def test_simulator_page_requires_authentication(self):
        response = self.client.get(reverse("simulator:page"))
        self.assertEqual(response.status_code, 302)

    def test_authenticated_page_loads_buildings_spaces_and_sensors(self):
        self.client.force_login(self.user)
        response = self.client.get(reverse("simulator:page"), {"building": self.building.pk})
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Bâtiment simulateur")
        self.assertContains(response, "Espace simulateur")
        self.assertContains(response, "Capteur température")
        self.assertContains(response, "Capteur humidité")

    def test_spaces_endpoint_returns_active_spaces_for_building(self):
        inactive = Space.objects.create(building=self.building, name="Espace inactif", is_active=False)
        response = self.api.get(reverse("simulator:spaces"), {"building_id": self.building.pk})
        self.assertEqual(response.status_code, 200)
        self.assertEqual([item["id"] for item in response.json()["results"]], [self.space.pk])
        self.assertNotIn(inactive.pk, [item["id"] for item in response.json()["results"]])

    def test_spaces_endpoint_requires_authentication(self):
        response = APIClient().get(reverse("simulator:spaces"), {"building_id": self.building.pk})
        self.assertIn(response.status_code, (401, 403))
        self.assertEqual(response["Content-Type"], "application/json")

    def test_spaces_endpoint_validates_building(self):
        response = self.api.get(reverse("simulator:spaces"), {"building_id": "invalid"})
        self.assertEqual(response.status_code, 400)

    def test_start_rejects_inactive_sensor(self):
        self.temperature.is_active = False
        self.temperature.save()
        response = self.api.post(reverse("simulator:start"), self.start_data(), format="json")
        self.assertEqual(response.status_code, 400)
        self.assertIn("sensor_ids", response.json())

    def test_start_rejects_sensor_from_another_space(self):
        other_space = Space.objects.create(building=self.building, name="Autre espace")
        other_sensor = self.create_sensor("Capteur ailleurs", Sensor.SensorType.TEMPERATURE, space=other_space)
        response = self.api.post(
            reverse("simulator:start"), self.start_data(sensor_ids=[other_sensor.pk]), format="json"
        )
        self.assertEqual(response.status_code, 400)

    def test_start_rejects_space_outside_selected_building(self):
        other_building = Building.objects.create(name="Autre bâtiment")
        other_space = Space.objects.create(building=other_building, name="Autre espace")
        response = self.api.post(
            reverse("simulator:start"), self.start_data(space_id=other_space.pk), format="json"
        )
        self.assertEqual(response.status_code, 400)

    def test_start_validates_minimum_interval(self):
        for interval in (0, 4, "abc", 4.5):
            with self.subTest(interval=interval):
                response = self.api.post(
                    reverse("simulator:start"), self.start_data(interval=interval), format="json"
                )
                self.assertEqual(response.status_code, 400)
                self.assertIn("interval", response.json())

    @override_settings(SIMULATOR_API_BASE_URL="http://127.0.0.1:8000")
    @patch("apps.simulator.runtime.post_measurement")
    def test_start_and_stop_simulation(self, send_measurement):
        sent = Event()
        send_measurement.side_effect = lambda *args: sent.set()
        response = self.api.post(reverse("simulator:start"), self.start_data(), format="json")
        self.assertEqual(response.status_code, 202)
        self.assertTrue(response.json()["is_running"])
        self.assertTrue(sent.wait(2))
        stopped = self.api.post(reverse("simulator:stop"), {}, format="json")
        self.assertEqual(stopped.status_code, 200)
        self.assertFalse(stopped.json()["is_running"])
        self.assertEqual(stopped.json()["state"], "stopped")

    @patch("apps.simulator.runtime.post_measurement")
    def test_second_simulation_for_same_user_is_rejected(self, send_measurement):
        send_measurement.return_value = 201
        first = self.api.post(reverse("simulator:start"), self.start_data(), format="json")
        second = self.api.post(reverse("simulator:start"), self.start_data(), format="json")
        self.assertEqual(first.status_code, 202)
        self.assertEqual(second.status_code, 409)
        self.api.post(reverse("simulator:stop"), {}, format="json")

    @patch("apps.simulator.runtime.post_measurement")
    def test_status_endpoint_returns_measurement_counter(self, send_measurement):
        send_measurement.return_value = 201
        started = self.api.post(reverse("simulator:start"), self.start_data(), format="json")
        self.assertEqual(started.status_code, 202)
        self.assertTrue(self.wait_for(lambda: self.api.get(reverse("simulator:status")).json()["measurement_count"] >= 1))
        status_response = self.api.get(reverse("simulator:status"))
        self.assertEqual(status_response.status_code, 200)
        self.assertGreaterEqual(status_response.json()["measurement_count"], 1)
        self.assertTrue(status_response.json()["latest_values"])
        self.api.post(reverse("simulator:stop"), {}, format="json")

    @patch("apps.simulator.runtime.post_measurement")
    def test_stop_prevents_future_sends_after_response(self, send_measurement):
        send_measurement.return_value = 201
        self.api.post(reverse("simulator:start"), self.start_data(interval=10), format="json")
        self.assertTrue(self.wait_for(lambda: send_measurement.call_count >= 1))
        response = self.api.post(reverse("simulator:stop"), {}, format="json")
        count_after_stop = send_measurement.call_count
        time.sleep(0.05)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(send_measurement.call_count, count_after_stop)

    def test_stop_without_running_simulation_is_safe(self):
        response = self.api.post(reverse("simulator:stop"), {}, format="json")
        self.assertEqual(response.status_code, 200)
        self.assertFalse(response.json()["is_running"])

    @patch("apps.simulator.runtime.urlopen")
    def test_generated_measurement_is_posted_to_existing_api_with_token(self, open_url):
        response_context = Mock()
        response_context.status = 201
        response_context.__enter__ = Mock(return_value=response_context)
        response_context.__exit__ = Mock(return_value=False)
        open_url.return_value = response_context
        sensor = {"id": self.temperature.pk, "name": self.temperature.name, "sensor_type": "TEMPERATURE", "unit": "°C"}
        result = runtime.post_measurement("http://127.0.0.1:8000", self.token.key, sensor, "22.50")
        request = open_url.call_args.args[0]
        payload = json.loads(request.data.decode("utf-8"))
        self.assertEqual(result, 201)
        self.assertEqual(request.full_url, "http://127.0.0.1:8000/api/v1/measurements/")
        self.assertEqual(request.get_header("Authorization"), f"Token {self.token.key}")
        self.assertEqual(payload["sensor"], self.temperature.pk)
        self.assertEqual(payload["value"], "22.50")

    @patch("apps.simulator.runtime.urlopen", side_effect=URLError("offline"))
    def test_api_network_error_is_reported(self, open_url):
        sensor = {"id": self.temperature.pk}
        with self.assertRaisesRegex(RuntimeError, "inaccessible"):
            runtime.post_measurement("http://127.0.0.1:8000", self.token.key, sensor, "20.00")

    @patch("apps.simulator.runtime.random.uniform")
    def test_generated_values_are_decimal_and_within_physical_limits(self, random_uniform):
        random_uniform.side_effect = [24, 62]
        temperature = runtime.generate_value(Sensor.SensorType.TEMPERATURE)
        humidity = runtime.generate_value(Sensor.SensorType.HUMIDITY)
        self.assertEqual(str(temperature), "24.00")
        self.assertEqual(str(humidity), "62.00")
        self.assertEqual(random_uniform.call_args_list[0].args, (18, 30))
        self.assertEqual(random_uniform.call_args_list[1].args, (40, 75))
        self.assertGreaterEqual(temperature, -50)
        self.assertLessEqual(temperature, 80)
        self.assertGreaterEqual(humidity, 0)
        self.assertLessEqual(humidity, 100)

    @patch("apps.simulator.runtime.post_measurement", side_effect=RuntimeError("API indisponible"))
    def test_api_error_appears_in_simulator_status(self, send_measurement):
        self.api.post(reverse("simulator:start"), self.start_data(), format="json")
        self.assertTrue(self.wait_for(lambda: bool(self.api.get(reverse("simulator:status")).json()["errors"])))
        response = self.api.get(reverse("simulator:status"))
        self.assertEqual(response.status_code, 200)
        self.assertIn("API indisponible", response.json()["errors"][0])
        self.assertEqual(response.json()["measurement_count"], 0)
        self.api.post(reverse("simulator:stop"), {}, format="json")

    def test_status_endpoint_requires_authentication(self):
        response = APIClient().get(reverse("simulator:status"))
        self.assertIn(response.status_code, (401, 403))
        self.assertEqual(response["Content-Type"], "application/json")

