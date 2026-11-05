from django.urls import path

from apps.simulator import views

app_name = "simulator"

urlpatterns = [
    path("simulator/", views.simulator_page, name="page"),
    path("simulator/start/", views.SimulatorStartAPIView.as_view(), name="start"),
    path("simulator/stop/", views.SimulatorStopAPIView.as_view(), name="stop"),
    path("simulator/status/", views.SimulatorStatusAPIView.as_view(), name="status"),
    path("simulator/spaces/", views.SimulatorSpacesAPIView.as_view(), name="spaces"),
]
