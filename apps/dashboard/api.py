from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.actuators.models import Actuator
from apps.dashboard.data import (
    get_actuator_rows,
    get_chart_data,
    get_dashboard_counts,
    get_environment_data,
    serialize_measurement,
)
from apps.sensors.models import Measurement


class DashboardSummaryAPIView(APIView):
    permission_classes = (IsAuthenticated,)

    def get(self, request):
        return Response(get_dashboard_counts())


class DashboardEnvironmentAPIView(APIView):
    permission_classes = (IsAuthenticated,)

    def get(self, request):
        return Response(get_environment_data())


class DashboardMeasurementsAPIView(APIView):
    permission_classes = (IsAuthenticated,)

    def get(self, request):
        period = request.query_params.get("period", "24h")
        chart = get_chart_data(period)
        results = Measurement.objects.select_related(
            "sensor", "sensor__space", "sensor__space__building"
        ).order_by("-recorded_at", "-pk")[:10]
        return Response({
            "period": period,
            "results": [serialize_measurement(item) for item in results],
            "chart": chart,
        })


class DashboardActuatorsAPIView(APIView):
    permission_classes = (IsAuthenticated,)

    def get(self, request):
        return Response({"results": get_actuator_rows()})
