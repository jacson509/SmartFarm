from rest_framework import serializers

from apps.facilities.models import Space
from apps.actuators.models import Actuator, ActuatorCommand


class ActuatorSerializer(serializers.ModelSerializer):
    name = serializers.CharField(
        max_length=150,
        error_messages={
            "required": "Le nom de l’actionneur est obligatoire.",
            "blank": "Le nom de l’actionneur est obligatoire.",
            "max_length": "Le nom ne peut dépasser 150 caractères.",
        },
    )
    actuator_type = serializers.ChoiceField(
        choices=Actuator.ActuatorType.choices,
        error_messages={"invalid_choice": "Sélectionnez un type d’actionneur valide."},
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
        model = Actuator
        fields = (
            "id",
            "name",
            "actuator_type",
            "space",
            "description",
            "is_active",
            "created_at",
            "updated_at",
        )
        read_only_fields = ("id", "created_at", "updated_at")

    def validate_name(self, value):
        value = value.strip()
        if not value:
            raise serializers.ValidationError("Le nom de l’actionneur est obligatoire.")
        return value

    def validate(self, attrs):
        space = attrs.get("space", getattr(self.instance, "space", None))
        if space is None:
            raise serializers.ValidationError({"space": "Un espace actif est obligatoire."})
        if not space.is_active:
            raise serializers.ValidationError({"space": "Un espace inactif ne peut pas recevoir d’actionneur."})
        return attrs


class ActuatorCommandSerializer(serializers.ModelSerializer):
    actuator = serializers.PrimaryKeyRelatedField(
        queryset=Actuator.objects.filter(
            is_active=True,
            space__is_active=True,
            space__building__is_active=True,
        ),
        error_messages={
            "required": "Un actionneur actif est obligatoire.",
            "does_not_exist": "L’actionneur n’existe pas ou est inactif, ou son emplacement est inactif.",
            "incorrect_type": "L’identifiant de l’actionneur doit être un entier.",
        },
    )
    command_type = serializers.ChoiceField(
        choices=ActuatorCommand.CommandType.choices,
        required=False,
        default=ActuatorCommand.CommandType.POWER_STATE,
        error_messages={"invalid_choice": "Ce type de commande n’est pas autorisé."},
    )
    value = serializers.ChoiceField(
        choices=ActuatorCommand.Value.choices,
        error_messages={"invalid_choice": "La commande doit demander l’état ON ou OFF."},
    )
    status = serializers.CharField(read_only=True)
    requested_at = serializers.DateTimeField(read_only=True)
    executed_at = serializers.DateTimeField(read_only=True)
    created_at = serializers.DateTimeField(read_only=True)

    class Meta:
        model = ActuatorCommand
        fields = (
            "id",
            "actuator",
            "command_type",
            "value",
            "status",
            "requested_at",
            "executed_at",
            "created_at",
        )
        read_only_fields = ("id", "status", "requested_at", "executed_at", "created_at")

    def to_internal_value(self, data):
        if "status" in data:
            raise serializers.ValidationError(
                {"status": "Le statut initial est défini par le serveur."}
            )
        if "requested_at" in data or "executed_at" in data or "created_at" in data:
            raise serializers.ValidationError(
                {"requested_at": "Les dates de commande sont gérées par le serveur."}
            )
        return super().to_internal_value(data)

    def validate(self, attrs):
        actuator = attrs.get("actuator")
        if actuator is None:
            raise serializers.ValidationError({"actuator": "Un actionneur actif est obligatoire."})
        if not actuator.is_active:
            raise serializers.ValidationError({"actuator": "Un actionneur inactif ne peut pas recevoir de commande."})
        if not actuator.space.is_active:
            raise serializers.ValidationError({"actuator": "L’espace de l’actionneur est inactif."})
        if not actuator.space.building.is_active:
            raise serializers.ValidationError({"actuator": "Le bâtiment de l’actionneur est inactif."})
        return attrs
