from decimal import Decimal

from django.utils import timezone
from rest_framework import serializers

from apps.facilities.models import Space
from apps.sensors.models import Measurement, Sensor


class SensorSerializer(serializers.ModelSerializer):
    name = serializers.CharField(
        max_length=150,
        error_messages={
            "required": "Le nom du capteur est obligatoire.",
            "blank": "Le nom du capteur est obligatoire.",
            "max_length": "Le nom du capteur ne peut dépasser 150 caractères.",
        },
    )
    sensor_type = serializers.ChoiceField(
        choices=Sensor.SensorType.choices,
        error_messages={"invalid_choice": "Sélectionnez un type de capteur valide."},
    )
    unit = serializers.CharField(read_only=True)
    minimum_threshold = serializers.DecimalField(
        max_digits=5,
        decimal_places=2,
        error_messages={
            "required": "Le seuil minimum est obligatoire.",
            "null": "Le seuil minimum ne peut pas être nul.",
            "invalid": "Entrez une valeur numérique valide pour le seuil minimum.",
            "max_digits": "Le seuil minimum peut contenir au maximum 3 chiffres avant la décimale.",
            "max_decimal_places": "Le seuil minimum accepte au maximum deux décimales.",
        },
    )
    maximum_threshold = serializers.DecimalField(
        max_digits=5,
        decimal_places=2,
        error_messages={
            "required": "Le seuil maximum est obligatoire.",
            "null": "Le seuil maximum ne peut pas être nul.",
            "invalid": "Entrez une valeur numérique valide pour le seuil maximum.",
            "max_digits": "Le seuil maximum peut contenir au maximum 3 chiffres avant la décimale.",
            "max_decimal_places": "Le seuil maximum accepte au maximum deux décimales.",
        },
    )
    space = serializers.PrimaryKeyRelatedField(
        queryset=Space.objects.filter(is_active=True),
        error_messages={
            "required": "Un espace actif est obligatoire.",
            "does_not_exist": "L’espace sélectionné n’existe pas ou est inactif.",
            "incorrect_type": "L’identifiant de l’espace doit être un entier.",
        },
    )

    class Meta:
        model = Sensor
        fields = (
            "id",
            "name",
            "sensor_type",
            "unit",
            "space",
            "minimum_threshold",
            "maximum_threshold",
            "description",
            "is_active",
            "created_at",
            "updated_at",
        )
        read_only_fields = ("id", "unit", "created_at", "updated_at")

    def validate_name(self, value):
        value = value.strip()
        if not value:
            raise serializers.ValidationError("Le nom du capteur est obligatoire.")
        return value

    def validate(self, attrs):
        instance = self.instance
        sensor_type = attrs.get("sensor_type", getattr(instance, "sensor_type", None))
        space = attrs.get("space", getattr(instance, "space", None))
        minimum = attrs.get("minimum_threshold", getattr(instance, "minimum_threshold", None))
        maximum = attrs.get("maximum_threshold", getattr(instance, "maximum_threshold", None))
        errors = {}

        if space is None:
            errors["space"] = "Un espace actif est obligatoire."
        elif not space.is_active:
            errors["space"] = "Le capteur doit être associé à un espace actif."

        limits = Sensor.TECHNICAL_LIMITS.get(sensor_type)
        if limits is None:
            errors["sensor_type"] = "Sélectionnez un type de capteur valide."
        else:
            technical_minimum, technical_maximum = limits
            if minimum is not None and not technical_minimum <= minimum <= technical_maximum:
                errors["minimum_threshold"] = (
                    f"Le seuil minimum doit être compris entre {technical_minimum} et {technical_maximum}."
                )
            if maximum is not None and not technical_minimum <= maximum <= technical_maximum:
                errors["maximum_threshold"] = (
                    f"Le seuil maximum doit être compris entre {technical_minimum} et {technical_maximum}."
                )

        if minimum is not None and maximum is not None and minimum >= maximum:
            errors["maximum_threshold"] = "Le seuil maximum doit être supérieur au seuil minimum."

        if errors:
            raise serializers.ValidationError(errors)
        return attrs


class FiniteDecimalField(serializers.DecimalField):
    def to_internal_value(self, data):
        value = super().to_internal_value(data)
        if not value.is_finite():
            raise serializers.ValidationError("La valeur doit être un nombre fini.")
        return value


class MeasurementSerializer(serializers.ModelSerializer):
    sensor = serializers.PrimaryKeyRelatedField(
        queryset=Sensor.objects.filter(
            is_active=True,
            space__is_active=True,
            space__building__is_active=True,
        ),
        error_messages={
            "required": "Un capteur actif est obligatoire.",
            "does_not_exist": "Le capteur n’existe pas, ou le capteur, l’espace ou le bâtiment est inactif.",
            "incorrect_type": "L’identifiant du capteur doit être un entier.",
        },
    )
    value = FiniteDecimalField(
        max_digits=5,
        decimal_places=2,
        error_messages={
            "required": "La valeur de la mesure est obligatoire.",
            "null": "La valeur de la mesure ne peut pas être nulle.",
            "invalid": "Entrez une valeur numérique valide.",
            "max_digits": "La valeur accepte au maximum trois chiffres avant la décimale.",
            "max_decimal_places": "La valeur accepte au maximum deux décimales.",
        },
    )
    recorded_at = serializers.DateTimeField(required=False, default=timezone.now)
    unit = serializers.CharField(source="sensor.unit", read_only=True)
    received_at = serializers.DateTimeField(read_only=True)
    created_at = serializers.DateTimeField(read_only=True)

    class Meta:
        model = Measurement
        fields = (
            "id",
            "sensor",
            "value",
            "unit",
            "recorded_at",
            "received_at",
            "created_at",
        )
        read_only_fields = ("id", "unit", "received_at", "created_at")

    def validate(self, attrs):
        sensor = attrs.get("sensor")
        value = attrs.get("value")
        if sensor is None:
            raise serializers.ValidationError({"sensor": "Un capteur actif est obligatoire."})

        if not sensor.is_active:
            raise serializers.ValidationError({"sensor": "Le capteur est inactif."})
        if not sensor.space.is_active:
            raise serializers.ValidationError({"sensor": "L’espace du capteur est inactif."})
        if not sensor.space.building.is_active:
            raise serializers.ValidationError({"sensor": "Le bâtiment du capteur est inactif."})

        if value is not None:
            limits = Sensor.TECHNICAL_LIMITS[sensor.sensor_type]
            minimum, maximum = (Decimal(limit) for limit in limits)
            if not minimum <= value <= maximum:
                raise serializers.ValidationError(
                    {
                        "value": (
                            f"La mesure doit être comprise entre {minimum} et {maximum} {sensor.unit}."
                        )
                    }
                )
        return attrs
