from rest_framework.routers import DefaultRouter

from apps.actuators.api import ActuatorCommandViewSet, ActuatorViewSet

router = DefaultRouter()
router.register("actuators", ActuatorViewSet, basename="actuator")
router.register("actuator-commands", ActuatorCommandViewSet, basename="actuator-command")

urlpatterns = router.urls
