from rest_framework import mixins, status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import ValidationError
from rest_framework.response import Response

from apps.facilities.api import ArchiveAwareModelViewSet
from apps.facilities.models import Building, Space
from apps.actuators.models import Actuator, ActuatorCommand
from apps.sensors.pagination import MeasurementPagination
from apps.actuators.serializers import ActuatorCommandSerializer, ActuatorSerializer


class ActuatorViewSet(ArchiveAwareModelViewSet):
    queryset = Actuator.objects.select_related("space", "space__building").all()
    serializer_class = ActuatorSerializer

    def get_queryset(self):
        queryset = super().get_queryset()
        params = self.request.query_params

        actuator_type = params.get("actuator_type")
        if actuator_type is not None:
            if actuator_type not in Actuator.ActuatorType.values:
                raise ValidationError({"actuator_type": "Sélectionnez un type d’actionneur valide."})
            queryset = queryset.filter(actuator_type=actuator_type)

        for parameter, model, lookup in (
            ("building", Building, "space__building_id"),
            ("space", Space, "space_id"),
        ):
            raw_id = params.get(parameter)
            if raw_id is None:
                continue
            try:
                object_id = int(raw_id)
            except (TypeError, ValueError):
                raise ValidationError({parameter: "Fournissez un identifiant entier valide."})
            if object_id < 1 or not model.objects.filter(pk=object_id).exists():
                raise ValidationError({parameter: "L’objet associé demandé n’existe pas."})
            queryset = queryset.filter(**{lookup: object_id})

        is_active = params.get("is_active")
        if is_active is not None:
            normalized = is_active.lower()
            if normalized not in ("true", "false"):
                raise ValidationError({"is_active": "Utilisez true ou false."})
            queryset = queryset.filter(is_active=(normalized == "true"))
        return queryset

    @action(detail=True, methods=["post"])
    def archive(self, request, pk=None):
        actuator = self.get_object()
        actuator.is_active = False
        actuator.save(update_fields=("is_active", "updated_at"))
        return Response(self.get_serializer(actuator).data, status=status.HTTP_200_OK)


class ActuatorCommandViewSet(
    mixins.ListModelMixin,
    mixins.CreateModelMixin,
    mixins.RetrieveModelMixin,
    viewsets.GenericViewSet,
):
    queryset = ActuatorCommand.objects.select_related(
        "actuator", "actuator__space", "actuator__space__building"
    ).all()
    serializer_class = ActuatorCommandSerializer
    pagination_class = MeasurementPagination

    def get_queryset(self):
        queryset = super().get_queryset()
        params = self.request.query_params

        actuator_id = params.get("actuator")
        if actuator_id is not None:
            try:
                actuator_id = int(actuator_id)
            except (TypeError, ValueError):
                raise ValidationError({"actuator": "Fournissez un identifiant entier valide."})
            if actuator_id < 1 or not Actuator.objects.filter(pk=actuator_id).exists():
                raise ValidationError({"actuator": "L’actionneur demandé n’existe pas."})
            queryset = queryset.filter(actuator_id=actuator_id)

        status_filter = params.get("status")
        if status_filter is not None:
            if status_filter not in ActuatorCommand.Status.values:
                raise ValidationError({"status": "Sélectionnez un statut de commande valide."})
            queryset = queryset.filter(status=status_filter)

        command_type = params.get("command_type")
        if command_type is not None:
            if command_type not in ActuatorCommand.CommandType.values:
                raise ValidationError({"command_type": "Sélectionnez un type de commande valide."})
            queryset = queryset.filter(command_type=command_type)
        return queryset
