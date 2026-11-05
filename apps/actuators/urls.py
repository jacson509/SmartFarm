from django.urls import path

from apps.actuators import views

app_name = "actuators"

urlpatterns = [
    path("commands/", views.AllActuatorCommandHistoryView.as_view(), name="all-command-list"),
    path("actuators/", views.ActuatorListView.as_view(), name="actuator-list"),
    path("actuators/create/", views.ActuatorCreateView.as_view(), name="actuator-create"),
    path("actuators/<int:pk>/commands/", views.ActuatorCommandHistoryView.as_view(), name="command-list"),
    path("actuators/<int:pk>/commands/create/", views.ActuatorCommandCreateView.as_view(), name="command-create"),
    path("actuators/<int:pk>/", views.ActuatorDetailView.as_view(), name="actuator-detail"),
    path("actuators/<int:pk>/edit/", views.ActuatorUpdateView.as_view(), name="actuator-update"),
    path("actuators/<int:pk>/delete/", views.ActuatorDeleteView.as_view(), name="actuator-delete"),
]
