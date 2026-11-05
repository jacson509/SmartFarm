from django.urls import path

from apps.dashboard import api, views

app_name = "dashboard"

urlpatterns = [
    path("", views.dashboard, name="home"),
    path("api/v1/dashboard/summary/", api.DashboardSummaryAPIView.as_view(), name="api-summary"),
    path("api/v1/dashboard/environment/", api.DashboardEnvironmentAPIView.as_view(), name="api-environment"),
    path("api/v1/dashboard/measurements/", api.DashboardMeasurementsAPIView.as_view(), name="api-measurements"),
    path("api/v1/dashboard/actuators/", api.DashboardActuatorsAPIView.as_view(), name="api-actuators"),
]
