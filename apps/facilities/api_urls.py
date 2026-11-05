from rest_framework.routers import DefaultRouter

from apps.facilities.api import BuildingViewSet, SpaceViewSet

router = DefaultRouter()
router.register("buildings", BuildingViewSet, basename="building")
router.register("spaces", SpaceViewSet, basename="space")

urlpatterns = router.urls
