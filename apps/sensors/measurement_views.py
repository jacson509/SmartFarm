from django.conf import settings
from django.contrib.auth.mixins import LoginRequiredMixin
from django.shortcuts import get_object_or_404
from django.views.generic import DetailView, ListView

from apps.facilities.models import Building, Space
from apps.sensors.measurement_filters import MeasurementFilterError, filter_measurements
from apps.sensors.models import Measurement, Sensor


class MeasurementListView(LoginRequiredMixin, ListView):
    model = Measurement
    template_name = "sensors/measurement_list.html"
    context_object_name = "measurements"

    def get_paginate_by(self, queryset):
        requested_size = self.request.GET.get("page_size")
        if requested_size and requested_size.isdecimal():
            size = int(requested_size)
            if 1 <= size <= 100:
                return size
        return settings.MEASUREMENTS_PAGE_SIZE

    def get_base_queryset(self):
        return Measurement.objects.select_related("sensor", "sensor__space", "sensor__space__building")

    def get_queryset(self):
        queryset = self.get_base_queryset()
        try:
            return filter_measurements(queryset, self.request.GET)
        except MeasurementFilterError as error:
            self.filter_error = error.message
            return queryset.none()

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        query = self.request.GET.copy()
        query.pop("page", None)
        context.update(
            {
                "filter_error": getattr(self, "filter_error", ""),
                "buildings": Building.objects.all(),
                "spaces": Space.objects.select_related("building").all(),
                "sensors": Sensor.objects.select_related("space", "space__building").all(),
                "selected_sensor": self.request.GET.get("sensor", ""),
                "selected_space": self.request.GET.get("space", ""),
                "selected_building": self.request.GET.get("building", ""),
                "selected_date_from": self.request.GET.get("date_from", ""),
                "selected_date_to": self.request.GET.get("date_to", ""),
                "selected_ordering": self.request.GET.get("ordering", "-recorded_at"),
                "filter_query": query.urlencode(),
                "history_sensor": getattr(self, "history_sensor", None),
            }
        )
        return context


class SensorMeasurementHistoryView(MeasurementListView):
    def get_base_queryset(self):
        self.history_sensor = get_object_or_404(
            Sensor.objects.select_related("space", "space__building"),
            pk=self.kwargs["pk"],
        )
        return super().get_base_queryset().filter(sensor=self.history_sensor)


class MeasurementDetailView(LoginRequiredMixin, DetailView):
    model = Measurement
    queryset = Measurement.objects.select_related("sensor", "sensor__space", "sensor__space__building")
    template_name = "sensors/measurement_detail.html"
    context_object_name = "measurement"
