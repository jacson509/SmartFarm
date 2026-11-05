import json
import random
import threading
from dataclasses import dataclass
from datetime import datetime, timezone as datetime_timezone
from decimal import Decimal, ROUND_HALF_UP
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from django.conf import settings
from django.utils import timezone

from apps.sensors.models import Sensor


def generate_value(sensor_type):
    if sensor_type == Sensor.SensorType.TEMPERATURE:
        physical_minimum, physical_maximum = -50, 80
        normal_minimum = getattr(settings, "SIMULATOR_TEMPERATURE_MIN", 18)
        normal_maximum = getattr(settings, "SIMULATOR_TEMPERATURE_MAX", 30)
    elif sensor_type == Sensor.SensorType.HUMIDITY:
        physical_minimum, physical_maximum = 0, 100
        normal_minimum = getattr(settings, "SIMULATOR_HUMIDITY_MIN", 40)
        normal_maximum = getattr(settings, "SIMULATOR_HUMIDITY_MAX", 75)
    else:
        raise ValueError("Type de capteur non pris en charge.")

    minimum = max(physical_minimum, float(normal_minimum))
    maximum = min(physical_maximum, float(normal_maximum))
    if minimum > maximum:
        minimum, maximum = physical_minimum, physical_maximum
    return Decimal(str(random.uniform(minimum, maximum))).quantize(
        Decimal("0.01"), rounding=ROUND_HALF_UP
    )


def post_measurement(api_base_url, token, sensor, value):
    payload = json.dumps({
        "sensor": sensor["id"],
        "value": str(value),
        "recorded_at": timezone.now().isoformat(),
    }).encode("utf-8")
    request = Request(
        f"{api_base_url.rstrip('/')}/api/v1/measurements/",
        data=payload,
        headers={
            "Authorization": f"Token {token}",
            "Content-Type": "application/json",
            "Accept": "application/json",
        },
        method="POST",
    )
    try:
        with urlopen(request, timeout=5) as response:
            if response.status < 200 or response.status >= 300:
                raise RuntimeError(f"L’API a répondu avec le statut HTTP {response.status}.")
            return response.status
    except HTTPError as error:
        detail = error.read(500).decode("utf-8", errors="replace")
        raise RuntimeError(f"Erreur HTTP {error.code} de l’API: {detail}") from error
    except URLError as error:
        raise RuntimeError(f"API de mesures inaccessible: {error.reason}") from error


@dataclass(frozen=True)
class SensorSpec:
    id: int
    name: str
    sensor_type: str
    type_label: str
    unit: str


class SimulationTask:
    def __init__(self, user_id, sensors, interval, token, api_base_url):
        self.user_id = user_id
        self.sensors = tuple(sensors)
        self.interval = interval
        self.token = token
        self.api_base_url = api_base_url
        self.stop_event = threading.Event()
        self.lock = threading.Lock()
        self.thread = threading.Thread(
            target=self._run,
            name=f"smartfarm-simulator-{user_id}",
            daemon=True,
        )
        self.started_at = timezone.now()
        self.measurement_count = 0
        self.last_sent_at = None
        self.latest_values = []
        self.errors = []
        self.state = "running"

    @property
    def is_running(self):
        return self.thread.is_alive() and not self.stop_event.is_set()

    def start(self):
        self.thread.start()

    def stop(self):
        self.stop_event.set()
        if self.thread.is_alive() and threading.current_thread() is not self.thread:
            # Each HTTP call is bounded by a five-second timeout, so join waits
            # until any in-flight request ends before the stop response returns.
            self.thread.join()
        with self.lock:
            self.state = "stopped"

    def _run(self):
        try:
            while not self.stop_event.is_set():
                for sensor in self.sensors:
                    if self.stop_event.is_set():
                        break
                    value = generate_value(sensor.sensor_type)
                    try:
                        post_measurement(
                            self.api_base_url,
                            self.token,
                            {
                                "id": sensor.id,
                                "name": sensor.name,
                                "sensor_type": sensor.sensor_type,
                                "unit": sensor.unit,
                            },
                            value,
                        )
                    except Exception as error:
                        with self.lock:
                            self.errors.append(str(error))
                            self.errors = self.errors[-10:]
                        continue

                    sent_at = datetime.now(datetime_timezone.utc).isoformat()
                    with self.lock:
                        self.measurement_count += 1
                        self.last_sent_at = sent_at
                        self.latest_values = [
                            item for item in self.latest_values
                            if item["sensor_id"] != sensor.id
                        ]
                        self.latest_values.insert(0, {
                            "sensor_id": sensor.id,
                            "sensor": sensor.name,
                            "type": sensor.type_label,
                            "value": str(value),
                            "unit": sensor.unit,
                            "sent_at": sent_at,
                        })
                        self.latest_values = self.latest_values[:10]
                if self.stop_event.wait(self.interval):
                    break
        finally:
            with self.lock:
                if self.stop_event.is_set():
                    self.state = "stopped"

    def as_dict(self):
        with self.lock:
            return {
                "state": self.state if self.thread.is_alive() else "stopped",
                "is_running": self.is_running,
                "interval": self.interval,
                "sensor_ids": [sensor.id for sensor in self.sensors],
                "measurement_count": self.measurement_count,
                "last_sent_at": self.last_sent_at,
                "latest_values": list(self.latest_values),
                "errors": list(self.errors),
                "started_at": self.started_at.isoformat(),
            }


class SimulationManager:
    """Process-local registry: designed for one local Django development server."""

    def __init__(self):
        self._tasks = {}
        self._lock = threading.Lock()

    def start(self, user_id, sensors, interval, token, api_base_url):
        with self._lock:
            existing = self._tasks.get(user_id)
            if existing and existing.is_running:
                return None
            task = SimulationTask(user_id, sensors, interval, token, api_base_url)
            self._tasks[user_id] = task
            task.start()
            return task

    def stop(self, user_id):
        with self._lock:
            task = self._tasks.get(user_id)
        if task is None:
            return None
        task.stop()
        return task

    def status(self, user_id):
        with self._lock:
            task = self._tasks.get(user_id)
        if task is None:
            return {
                "state": "stopped",
                "is_running": False,
                "interval": None,
                "sensor_ids": [],
                "measurement_count": 0,
                "last_sent_at": None,
                "latest_values": [],
                "errors": [],
                "started_at": None,
            }
        return task.as_dict()


simulation_manager = SimulationManager()
