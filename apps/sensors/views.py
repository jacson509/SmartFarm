from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse
from django.views.generic import CreateView, DetailView, ListView, TemplateView, UpdateView

from apps.facilities.models import Building, Space
from apps.facilities.services import archive_or_delete, has_related_records
from apps.sensors.forms import SensorForm
from apps.sensors.models import Sensor


class SensorListView(LoginRequiredMixin, ListView):
    model = Sensor
    template_name = "sensors/sensor_list.html"
    context_object_name = "sensors"

    def get_queryset(self):
        queryset = Sensor.objects.select_related("space", "space__building")
        params = self.request.GET

        sensor_type = params.get("sensor_type")
        if sensor_type:
            if sensor_type not in Sensor.SensorType.values:
                return queryset.none()
            queryset = queryset.filter(sensor_type=sensor_type)

        for param, field in (("building", "space__building_id"), ("space", "space_id")):
            raw_id = params.get(param)
            if raw_id:
                if not raw_id.isdecimal():
                    return queryset.none()
                queryset = queryset.filter(**{field: int(raw_id)})

        is_active = params.get("is_active")
        if is_active:
            if is_active.lower() not in ("true", "false"):
                return queryset.none()
            queryset = queryset.filter(is_active=(is_active.lower() == "true"))
        return queryset

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context.update(
            {
                "buildings": Building.objects.all(),
                "spaces": Space.objects.select_related("building").all(),
                "sensor_types": Sensor.SensorType.choices,
                "selected_sensor_type": self.request.GET.get("sensor_type", ""),
                "selected_building": self.request.GET.get("building", ""),
                "selected_space": self.request.GET.get("space", ""),
                "selected_is_active": self.request.GET.get("is_active", ""),
            }
        )
        return context


class SensorDetailView(LoginRequiredMixin, DetailView):
    model = Sensor
    queryset = Sensor.objects.select_related("space", "space__building")
    template_name = "sensors/sensor_detail.html"
    context_object_name = "sensor"


class SensorCreateView(LoginRequiredMixin, CreateView):
    model = Sensor
    form_class = SensorForm
    template_name = "sensors/sensor_form.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["page_title"] = "Créer un capteur"
        context["cancel_url"] = reverse("sensors:sensor-list")
        context["is_edit"] = False
        return context

    def form_valid(self, form):
        response = super().form_valid(form)
        messages.success(self.request, "Le capteur a été créé.")
        return response

    def get_success_url(self):
        return reverse("sensors:sensor-detail", kwargs={"pk": self.object.pk})


class SensorUpdateView(LoginRequiredMixin, UpdateView):
    model = Sensor
    form_class = SensorForm
    template_name = "sensors/sensor_form.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["page_title"] = "Modifier le capteur"
        context["cancel_url"] = reverse("sensors:sensor-detail", kwargs={"pk": self.object.pk})
        context["is_edit"] = True
        return context

    def form_valid(self, form):
        response = super().form_valid(form)
        messages.success(self.request, "Le capteur a été modifié.")
        return response

    def get_success_url(self):
        return reverse("sensors:sensor-detail", kwargs={"pk": self.object.pk})


class SensorDeleteView(LoginRequiredMixin, TemplateView):
    template_name = "sensors/confirm_delete.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        sensor = get_object_or_404(
            Sensor.objects.select_related("space", "space__building"), pk=self.kwargs["pk"]
        )
        context.update(
            {
                "sensor": sensor,
                "object": sensor,
                "has_related_records": has_related_records(sensor),
                "cancel_url": reverse("sensors:sensor-detail", kwargs={"pk": sensor.pk}),
                "delete_url": reverse("sensors:sensor-delete", kwargs={"pk": sensor.pk}),
            }
        )
        return context

    def post(self, request, *args, **kwargs):
        if request.POST.get("confirmed") != "1":
            messages.error(request, "Confirmez l’action depuis la page de confirmation.")
            return redirect("sensors:sensor-delete", pk=self.kwargs["pk"])
        sensor = get_object_or_404(Sensor, pk=self.kwargs["pk"])
        deleted = archive_or_delete(sensor)
        if deleted:
            messages.success(request, "Le capteur a été supprimé.")
        else:
            messages.warning(
                request,
                "Le capteur possède des données historiques associées; il a été désactivé pour les préserver.",
            )
        return redirect("sensors:sensor-list")
