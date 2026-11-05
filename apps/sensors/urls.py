from django.urls import path

from apps.sensors import views
from apps.sensors import measurement_views

app_name = "sensors"

urlpatterns = [
    path("sensors/", views.SensorListView.as_view(), name="sensor-list"),
    path("sensors/create/", views.SensorCreateView.as_view(), name="sensor-create"),
    path("sensors/<int:pk>/", views.SensorDetailView.as_view(), name="sensor-detail"),
    path("sensors/<int:pk>/edit/", views.SensorUpdateView.as_view(), name="sensor-update"),
    path("sensors/<int:pk>/delete/", views.SensorDeleteView.as_view(), name="sensor-delete"),
    path("measurements/", measurement_views.MeasurementListView.as_view(), name="measurement-list"),
    path("measurements/<int:pk>/", measurement_views.MeasurementDetailView.as_view(), name="measurement-detail"),
    path(
        "sensors/<int:pk>/measurements/",
        measurement_views.SensorMeasurementHistoryView.as_view(),
        name="sensor-measurements",
    ),
]
