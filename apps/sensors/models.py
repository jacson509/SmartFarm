from datetime import datetime
from decimal import Decimal, InvalidOperation

from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import Q
from django.utils import timezone

from apps.facilities.models import Space


class Sensor(models.Model):
    class SensorType(models.TextChoices):
        TEMPERATURE = "TEMPERATURE", "Température"
        HUMIDITY = "HUMIDITY", "Humidité"

    UNIT_BY_TYPE = {
        SensorType.TEMPERATURE: "°C",
        SensorType.HUMIDITY: "%",
    }
    TECHNICAL_LIMITS = {
        SensorType.TEMPERATURE: (-50, 80),
        SensorType.HUMIDITY: (0, 100),
    }

    name = models.CharField("nom", max_length=150)
    sensor_type = models.CharField("type", max_length=20, choices=SensorType.choices)
    unit = models.CharField(
        "unité",
        max_length=2,
        choices=(("°C", "°C"), ("%", "%")),
        editable=False,
    )
    space = models.ForeignKey(
        Space,
        on_delete=models.PROTECT,
        related_name="sensors",
        verbose_name="espace",
    )
    minimum_threshold = models.DecimalField("seuil minimum", max_digits=5, decimal_places=2)
    maximum_threshold = models.DecimalField("seuil maximum", max_digits=5, decimal_places=2)
    description = models.TextField("description", blank=True)
    is_active = models.BooleanField("actif", default=True)
    created_at = models.DateTimeField("créé le", auto_now_add=True)
    updated_at = models.DateTimeField("modifié le", auto_now=True)

    class Meta:
        ordering = ("name", "pk")
        verbose_name = "capteur"
        verbose_name_plural = "capteurs"
        constraints = [
            models.CheckConstraint(
                condition=Q(sensor_type__in=("TEMPERATURE", "HUMIDITY")),
                name="sensor_type_valid",
            ),
            models.CheckConstraint(
                condition=Q(minimum_threshold__lt=models.F("maximum_threshold")),
                name="sensor_thresholds_ordered",
            ),
            models.CheckConstraint(
                condition=(
                    Q(
                        sensor_type="TEMPERATURE",
                        unit="°C",
                        minimum_threshold__gte=-50,
                        maximum_threshold__lte=80,
                    )
                    | Q(
                        sensor_type="HUMIDITY",
                        unit="%",
                        minimum_threshold__gte=0,
                        maximum_threshold__lte=100,
                    )
                ),
                name="sensor_thresholds_within_limits",
            ),
        ]

    def clean(self):
        self.name = self.name.strip() if self.name else self.name
        errors = {}
        if not self.name:
            errors["name"] = "Le nom du capteur est obligatoire."

        limits = self.TECHNICAL_LIMITS.get(self.sensor_type)
        if limits is None:
            errors["sensor_type"] = "Sélectionnez un type de capteur valide."
        else:
            minimum, maximum = limits
            if self.minimum_threshold is not None and not minimum <= self.minimum_threshold <= maximum:
                errors["minimum_threshold"] = (
                    f"Le seuil minimum doit être compris entre {minimum} et {maximum} {self.UNIT_BY_TYPE[self.sensor_type]}."
                )
            if self.maximum_threshold is not None and not minimum <= self.maximum_threshold <= maximum:
                errors["maximum_threshold"] = (
                    f"Le seuil maximum doit être compris entre {minimum} et {maximum} {self.UNIT_BY_TYPE[self.sensor_type]}."
                )
        if (
            self.minimum_threshold is not None
            and self.maximum_threshold is not None
            and self.minimum_threshold >= self.maximum_threshold
        ):
            errors["maximum_threshold"] = "Le seuil maximum doit être supérieur au seuil minimum."

        if self.space_id:
            try:
                if not self.space.is_active:
                    errors["space"] = "Le capteur doit être associé à un espace actif."
            except Space.DoesNotExist:
                errors["space"] = "Sélectionnez un espace existant."
        else:
            errors["space"] = "Un espace actif est obligatoire."

        if errors:
            raise ValidationError(errors)

    def save(self, *args, **kwargs):
        self.unit = self.UNIT_BY_TYPE.get(self.sensor_type, "")
        self.full_clean()
        update_fields = kwargs.get("update_fields")
        if update_fields is not None and "sensor_type" in update_fields:
            kwargs["update_fields"] = tuple(dict.fromkeys((*update_fields, "unit")))
        return super().save(*args, **kwargs)

    def __str__(self):
        return self.name


class Measurement(models.Model):
    sensor = models.ForeignKey(
        Sensor,
        on_delete=models.PROTECT,
        related_name="measurements",
        verbose_name="capteur",
    )
    value = models.DecimalField("valeur", max_digits=5, decimal_places=2)
    recorded_at = models.DateTimeField("mesuré le", default=timezone.now)
    received_at = models.DateTimeField("reçu le", auto_now_add=True)
    created_at = models.DateTimeField("enregistré le", auto_now_add=True)

    class Meta:
        ordering = ("-recorded_at", "-pk")
        verbose_name = "mesure"
        verbose_name_plural = "mesures"
        constraints = [
            models.CheckConstraint(
                condition=Q(value__gte=-50, value__lte=100),
                name="measurement_value_finite_range",
            ),
        ]
        indexes = [
            models.Index(fields=("sensor", "-recorded_at"), name="measurement_sensor_date_idx"),
            models.Index(fields=("-recorded_at",), name="measurement_date_idx"),
        ]

    def clean(self):
        errors = {}

        if self.value is not None:
            try:
                self.value = Decimal(str(self.value))
                if not self.value.is_finite():
                    errors["value"] = "La valeur doit être un nombre fini."
            except (InvalidOperation, TypeError, ValueError):
                errors["value"] = "Entrez une valeur numérique valide."
        else:
            errors["value"] = "La valeur de la mesure est obligatoire."

        if self.recorded_at is None:
            errors["recorded_at"] = "La date de mesure est obligatoire."
        elif not isinstance(self.recorded_at, datetime):
            errors["recorded_at"] = "Entrez une date et une heure valides."
        elif timezone.is_naive(self.recorded_at):
            self.recorded_at = timezone.make_aware(
                self.recorded_at,
                timezone.get_current_timezone(),
            )

        sensor = None
        if self.sensor_id:
            try:
                sensor = self.sensor
            except Sensor.DoesNotExist:
                errors["sensor"] = "Le capteur sélectionné n’existe pas."
        else:
            errors["sensor"] = "Un capteur est obligatoire."

        if sensor is not None:
            if not sensor.is_active:
                errors["sensor"] = "Les mesures ne peuvent être enregistrées pour un capteur inactif."
            if not sensor.space.is_active:
                errors["sensor"] = "L’espace du capteur est inactif."
            if not sensor.space.building.is_active:
                errors["sensor"] = "Le bâtiment du capteur est inactif."
            if isinstance(self.value, Decimal) and self.value.is_finite():
                minimum, maximum = Sensor.TECHNICAL_LIMITS.get(sensor.sensor_type, (None, None))
                if minimum is not None and not Decimal(minimum) <= self.value <= Decimal(maximum):
                    unit = Sensor.UNIT_BY_TYPE[sensor.sensor_type]
                    errors["value"] = (
                        f"La mesure doit être comprise entre {minimum} et {maximum} {unit}."
                    )

        if errors:
            raise ValidationError(errors)

    def save(self, *args, **kwargs):
        self.full_clean()
        return super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.value} {self.sensor.unit} — {self.sensor.name} ({self.recorded_at:%Y-%m-%d %H:%M})"
