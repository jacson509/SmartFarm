from datetime import timedelta

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone
from rest_framework.authtoken.models import Token
from rest_framework.test import APIClient

from apps.actuators.models import Actuator, ActuatorCommand
from apps.facilities.models import Building, Space
from apps.sensors.models import Measurement, Sensor


class DashboardTests(TestCase):
    def setUp(self):
        user = get_user_model().objects.create_user(username="dashboard-user", password="SafeTestPassword-42")
        self.token = Token.objects.create(user=user)
        self.api = APIClient()
        self.building = Building.objects.create(name="Bâtiment tableau")
        self.space = Space.objects.create(building=self.building, name="Espace tableau")

    def authorize(self):
        self.api.credentials(HTTP_AUTHORIZATION=f"Token {self.token.key}")

    def create_sensor(self, sensor_type, name, value, recorded_at=None):
        minimum, maximum = ((-20, 40) if sensor_type == Sensor.SensorType.TEMPERATURE else (10, 90))
        sensor = Sensor.objects.create(
            name=name,
            sensor_type=sensor_type,
            space=self.space,
            minimum_threshold=minimum,
            maximum_threshold=maximum,
        )
        return Measurement.objects.create(
            sensor=sensor,
            value=value,
            recorded_at=recorded_at or timezone.now(),
        )

    def test_dashboard_requires_login(self):
        response = self.client.get(reverse("dashboard:home"))
        self.assertEqual(response.status_code, 302)

    def test_authenticated_dashboard_renders(self):
        self.client.login(username="dashboard-user", password="SafeTestPassword-42")
        self.assertEqual(self.client.get(reverse("dashboard:home")).status_code, 200)

    def test_dashboard_counts_buildings_and_spaces(self):
        self.client.login(username="dashboard-user", password="SafeTestPassword-42")
        response = self.client.get(reverse("dashboard:home"))
        self.assertEqual(response.context["counts"]["buildings"], 1)
        self.assertEqual(response.context["counts"]["spaces"], 1)

    def test_dashboard_counts_sensors_and_actuators(self):
        self.create_sensor(Sensor.SensorType.TEMPERATURE, "Temp", "20")
        Actuator.objects.create(name="Ventilateur", actuator_type=Actuator.ActuatorType.FAN, space=self.space)
        self.client.login(username="dashboard-user", password="SafeTestPassword-42")
        counts = self.client.get(reverse("dashboard:home")).context["counts"]
        self.assertEqual(counts["sensors"], 1)
        self.assertEqual(counts["actuators"], 1)

    def test_dashboard_displays_latest_temperature_and_humidity(self):
        self.create_sensor(Sensor.SensorType.TEMPERATURE, "Thermomètre", "21.50")
        self.create_sensor(Sensor.SensorType.HUMIDITY, "Hygromètre", "62.00")
        self.client.login(username="dashboard-user", password="SafeTestPassword-42")
        response = self.client.get(reverse("dashboard:home"))
        self.assertEqual(response.context["environment"]["temperature"]["value"], "21.50")
        self.assertEqual(response.context["environment"]["humidity"]["unit"], "%")
        self.assertContains(response, "Dernière mesure enregistrée")

    def test_dashboard_lists_latest_measurements(self):
        self.create_sensor(Sensor.SensorType.TEMPERATURE, "Thermomètre", "19.25")
        self.client.login(username="dashboard-user", password="SafeTestPassword-42")
        response = self.client.get(reverse("dashboard:home"))
        self.assertEqual(len(response.context["latest_measurements"]), 1)
        self.assertContains(response, "Thermomètre")

    def test_dashboard_shows_empty_messages_when_no_data(self):
        self.client.login(username="dashboard-user", password="SafeTestPassword-42")
        response = self.client.get(reverse("dashboard:home"))
        self.assertContains(response, "Aucune mesure enregistrée")
        self.assertContains(response, "Aucun actionneur enregistré")
        self.assertIsNone(response.context["environment"]["temperature"])

    def test_chart_uses_real_records_and_selected_period(self):
        self.create_sensor(Sensor.SensorType.TEMPERATURE, "Température", "20", timezone.now() - timedelta(hours=3))
        self.create_sensor(Sensor.SensorType.HUMIDITY, "Humidité", "60", timezone.now() - timedelta(days=3))
        self.client.login(username="dashboard-user", password="SafeTestPassword-42")
        day = self.client.get(reverse("dashboard:home"), {"period": "24h"}).context["chart_data"]
        week = self.client.get(reverse("dashboard:home"), {"period": "7d"}).context["chart_data"]
        self.assertEqual(len(day["temperature"]), 1)
        self.assertEqual(len(day["humidity"]), 0)
        self.assertEqual(len(week["humidity"]), 1)

    def test_dashboard_shows_actuator_and_latest_command(self):
        actuator = Actuator.objects.create(name="Ventilateur", actuator_type=Actuator.ActuatorType.FAN, space=self.space)
        ActuatorCommand.objects.create(actuator=actuator, value=ActuatorCommand.Value.ON)
        self.client.login(username="dashboard-user", password="SafeTestPassword-42")
        response = self.client.get(reverse("dashboard:home"))
        self.assertContains(response, "Ventilateur")
        self.assertContains(response, "En attente")

    def test_dashboard_endpoints_require_authentication(self):
        for name in ("api-summary", "api-environment", "api-measurements", "api-actuators"):
            response = self.api.get(reverse(f"dashboard:{name}"))
            self.assertEqual(response.status_code, 401)

    def test_dashboard_api_summary_and_data_endpoints(self):
        self.create_sensor(Sensor.SensorType.TEMPERATURE, "Température", "20")
        Actuator.objects.create(name="Ventilateur", actuator_type=Actuator.ActuatorType.FAN, space=self.space)
        self.authorize()
        summary = self.api.get(reverse("dashboard:api-summary"))
        environment = self.api.get(reverse("dashboard:api-environment"))
        measurements = self.api.get(reverse("dashboard:api-measurements"))
        actuators = self.api.get(reverse("dashboard:api-actuators"))
        self.assertEqual(summary.json()["buildings"], 1)
        self.assertEqual(environment.json()["temperature"]["unit"], "°C")
        self.assertEqual(len(measurements.json()["results"]), 1)
        self.assertEqual(actuators.json()["results"][0]["name"], "Ventilateur")

    def test_dashboard_measurements_api_validates_period(self):
        self.authorize()
        response = self.api.get(reverse("dashboard:api-measurements"), {"period": "30d"})
        self.assertEqual(response.status_code, 400)

