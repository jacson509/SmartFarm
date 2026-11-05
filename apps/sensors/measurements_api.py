from rest_framework import mixins, viewsets
from rest_framework.exceptions import ValidationError

from apps.sensors.measurement_filters import MeasurementFilterError, filter_measurements
from apps.sensors.models import Measurement
from apps.sensors.pagination import MeasurementPagination
from apps.sensors.serializers import MeasurementSerializer


class MeasurementViewSet(
    mixins.ListModelMixin,
    mixins.CreateModelMixin,
    mixins.RetrieveModelMixin,
    viewsets.GenericViewSet,
):
    queryset = Measurement.objects.select_related(
        "sensor", "sensor__space", "sensor__space__building"
    ).all()
    serializer_class = MeasurementSerializer
    pagination_class = MeasurementPagination

    def get_queryset(self):
        try:
            return filter_measurements(super().get_queryset(), self.request.query_params)
        except MeasurementFilterError as error:
            raise ValidationError({error.field: error.message})
