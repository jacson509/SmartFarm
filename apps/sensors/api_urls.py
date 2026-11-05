from rest_framework.routers import DefaultRouter

from apps.sensors.api import SensorViewSet
from apps.sensors.measurements_api import MeasurementViewSet

router = DefaultRouter()
router.register("sensors", SensorViewSet, basename="sensor")
router.register("measurements", MeasurementViewSet, basename="measurement")

urlpatterns = router.urls
