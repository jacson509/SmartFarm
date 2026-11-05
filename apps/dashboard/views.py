from datetime import datetime

from django.contrib.auth.decorators import login_required
from django.shortcuts import render
from django.utils import timezone

from apps.actuators.models import Actuator
from apps.dashboard.data import (
    PERIODS,
    get_actuator_rows,
    get_chart_data,
    get_dashboard_counts,
    get_environment_data,
)
from apps.sensors.models import Measurement


@login_required
def dashboard(request):
    period = request.GET.get("period", "24h")
    if period not in PERIODS:
        period = "24h"

    latest_measurements = Measurement.objects.select_related(
        "sensor", "sensor__space", "sensor__space__building"
    ).order_by("-recorded_at", "-pk")[:10]
    actuators = Actuator.objects.select_related(
        "space", "space__building"
    ).prefetch_related("commands")
    for actuator in actuators:
        actuator.latest_command = actuator.commands.first()

    environment = get_environment_data()
    for reading in environment.values():
        if reading:
            reading["recorded_at_local"] = timezone.localtime(
                datetime.fromisoformat(reading["recorded_at"])
            )

    return render(request, "dashboard/dashboard.html", {
        "counts": get_dashboard_counts(),
        "environment": environment,
        "latest_measurements": latest_measurements,
        "actuators": actuators,
        "chart_data": get_chart_data(period),
        "selected_period": period,
        "generated_at": timezone.now(),
    })
