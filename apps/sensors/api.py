from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import ValidationError
from rest_framework.response import Response

from apps.facilities.models import Building, Space
from apps.facilities.services import archive_or_delete
from apps.sensors.measurement_filters import MeasurementFilterError, filter_measurements
from apps.sensors.models import Measurement, Sensor
from apps.sensors.pagination import MeasurementPagination
from apps.sensors.serializers import MeasurementSerializer, SensorSerializer


class SensorViewSet(viewsets.ModelViewSet):
    queryset = Sensor.objects.select_related("space", "space__building").all()
    serializer_class = SensorSerializer

    @action(detail=True, methods=["get"], url_path="measurements")
    def measurements(self, request, pk=None):
        sensor = self.get_object()
        queryset = Measurement.objects.filter(sensor=sensor).select_related(
            "sensor", "sensor__space", "sensor__space__building"
        )
        try:
            queryset = filter_measurements(queryset, request.query_params)
        except MeasurementFilterError as error:
            raise ValidationError({error.field: error.message})

        paginator = MeasurementPagination()
        page = paginator.paginate_queryset(queryset, request, view=self)
        serializer = MeasurementSerializer(page, many=True, context=self.get_serializer_context())
        return paginator.get_paginated_response(serializer.data)

    def get_queryset(self):
        queryset = super().get_queryset()
        params = self.request.query_params

        sensor_type = params.get("sensor_type")
        if sensor_type is not None:
            valid_types = Sensor.SensorType.values
            if sensor_type not in valid_types:
                raise ValidationError(
                    {"sensor_type": "Utilisez TEMPERATURE ou HUMIDITY."}
                )
            queryset = queryset.filter(sensor_type=sensor_type)

        for param, model, field in (
            ("building", Building, "space__building_id"),
            ("space", Space, "space_id"),
        ):
            raw_id = params.get(param)
            if raw_id is None:
                continue
            try:
                related_id = int(raw_id)
            except (TypeError, ValueError):
                raise ValidationError({param: "Fournissez un identifiant entier valide."})
            if related_id < 1 or not model.objects.filter(pk=related_id).exists():
                raise ValidationError({param: "L’objet associé demandé n’existe pas."})
            queryset = queryset.filter(**{field: related_id})

        is_active = params.get("is_active")
        if is_active is not None:
            normalized = is_active.lower()
            if normalized not in ("true", "false"):
                raise ValidationError({"is_active": "Utilisez true ou false."})
            queryset = queryset.filter(is_active=(normalized == "true"))

        return queryset

    def destroy(self, request, *args, **kwargs):
        sensor = self.get_object()
        deleted = archive_or_delete(sensor)
        if deleted:
            return Response(status=status.HTTP_204_NO_CONTENT)
        return Response(
            {
                "detail": "Le capteur possède des données associées; il a été désactivé pour les préserver.",
                "archived": True,
            },
            status=status.HTTP_200_OK,
        )

    @action(detail=True, methods=["post"])
    def archive(self, request, pk=None):
        sensor = self.get_object()
        sensor.is_active = False
        sensor.save(update_fields=("is_active", "updated_at"))
        return Response(self.get_serializer(sensor).data)
