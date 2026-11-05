from datetime import timedelta

from django.utils import timezone
from rest_framework.exceptions import ValidationError

from apps.actuators.models import Actuator
from apps.facilities.models import Building, Space
from apps.sensors.models import Measurement, Sensor


PERIODS = {"24h": timedelta(hours=24), "7d": timedelta(days=7)}


def get_period_start(period):
    if period not in PERIODS:
        raise ValidationError({"period": "Choisissez 24h ou 7d."})
    return timezone.now() - PERIODS[period]


def active_environment_measurements():
    return Measurement.objects.filter(
        sensor__is_active=True,
        sensor__space__is_active=True,
        sensor__space__building__is_active=True,
    ).select_related("sensor", "sensor__space", "sensor__space__building")


def serialize_measurement(measurement):
    return {
        "id": measurement.pk,
        "sensor": measurement.sensor.name,
        "sensor_id": measurement.sensor_id,
        "type": measurement.sensor.sensor_type,
        "type_label": measurement.sensor.get_sensor_type_display(),
        "value": str(measurement.value),
        "unit": measurement.sensor.unit,
        "space": measurement.sensor.space.name,
        "recorded_at": measurement.recorded_at.isoformat(),
    }


def get_environment_data():
    measurements = active_environment_measurements()
    environment = {}
    for sensor_type, key in ((Sensor.SensorType.TEMPERATURE, "temperature"), (Sensor.SensorType.HUMIDITY, "humidity")):
        measurement = measurements.filter(sensor__sensor_type=sensor_type).order_by("-recorded_at", "-pk").first()
        environment[key] = serialize_measurement(measurement) if measurement else None
    return environment


def get_chart_data(period):
    start = get_period_start(period)
    measurements = active_environment_measurements().filter(recorded_at__gte=start).order_by("recorded_at", "pk")
    return {
        "period": period,
        "temperature": [
            {"date": item.recorded_at.isoformat(), "value": float(item.value)}
            for item in measurements.filter(sensor__sensor_type=Sensor.SensorType.TEMPERATURE)
        ],
        "humidity": [
            {"date": item.recorded_at.isoformat(), "value": float(item.value)}
            for item in measurements.filter(sensor__sensor_type=Sensor.SensorType.HUMIDITY)
        ],
    }


def get_dashboard_counts():
    return {
        "buildings": Building.objects.count(),
        "spaces": Space.objects.count(),
        "sensors": Sensor.objects.count(),
        "actuators": Actuator.objects.count(),
    }


def get_actuator_rows():
    rows = []
    actuators = Actuator.objects.select_related("space", "space__building").prefetch_related("commands")
    for actuator in actuators:
        command = actuator.commands.first()
        rows.append({
            "id": actuator.pk,
            "name": actuator.name,
            "type": actuator.get_actuator_type_display(),
            "space": actuator.space.name,
            "building": actuator.space.building.name,
            "is_active": actuator.is_active,
            "last_command": ({
                "value": command.get_value_display(),
                "status": command.get_status_display(),
                "requested_at": command.requested_at.isoformat(),
            } if command else None),
        })
    return rows
