from django.conf import settings
from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse
from django.views.generic import CreateView, DetailView, ListView, TemplateView, UpdateView

from apps.facilities.models import Building, Space
from apps.facilities.services import archive_or_delete, has_related_records
from apps.actuators.forms import ActuatorCommandForm, ActuatorForm
from apps.actuators.models import Actuator, ActuatorCommand


def can_receive_command(actuator):
    return (
        actuator.is_active
        and actuator.space.is_active
        and actuator.space.building.is_active
    )


class ActuatorListView(LoginRequiredMixin, ListView):
    model = Actuator
    template_name = "actuators/actuator_list.html"
    context_object_name = "actuators"

    def get_queryset(self):
        queryset = Actuator.objects.select_related("space", "space__building")
        params = self.request.GET
        actuator_type = params.get("actuator_type")
        if actuator_type:
            if actuator_type not in Actuator.ActuatorType.values:
                return queryset.none()
            queryset = queryset.filter(actuator_type=actuator_type)
        for parameter, lookup in (("building", "space__building_id"), ("space", "space_id")):
            raw_id = params.get(parameter)
            if raw_id:
                if not raw_id.isdecimal():
                    return queryset.none()
                queryset = queryset.filter(**{lookup: int(raw_id)})
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
                "actuator_types": Actuator.ActuatorType.choices,
                "selected_building": self.request.GET.get("building", ""),
                "selected_space": self.request.GET.get("space", ""),
                "selected_type": self.request.GET.get("actuator_type", ""),
                "selected_is_active": self.request.GET.get("is_active", ""),
            }
        )
        return context


class ActuatorDetailView(LoginRequiredMixin, DetailView):
    model = Actuator
    queryset = Actuator.objects.select_related("space", "space__building")
    template_name = "actuators/actuator_detail.html"
    context_object_name = "actuator"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["can_receive_command"] = can_receive_command(self.object)
        context["command_count"] = self.object.commands.count()
        return context


class ActuatorCreateView(LoginRequiredMixin, CreateView):
    model = Actuator
    form_class = ActuatorForm
    template_name = "actuators/actuator_form.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["page_title"] = "Créer un actionneur"
        context["cancel_url"] = reverse("actuators:actuator-list")
        return context

    def form_valid(self, form):
        response = super().form_valid(form)
        messages.success(self.request, "L’actionneur a été créé.")
        return response

    def form_invalid(self, form):
        messages.error(self.request, "Vérifiez les champs du formulaire.")
        return super().form_invalid(form)

    def get_success_url(self):
        return reverse("actuators:actuator-detail", kwargs={"pk": self.object.pk})


class ActuatorUpdateView(LoginRequiredMixin, UpdateView):
    model = Actuator
    form_class = ActuatorForm
    template_name = "actuators/actuator_form.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["page_title"] = "Modifier l’actionneur"
        context["cancel_url"] = reverse("actuators:actuator-detail", kwargs={"pk": self.object.pk})
        return context

    def form_valid(self, form):
        response = super().form_valid(form)
        messages.success(self.request, "L’actionneur a été modifié.")
        return response

    def form_invalid(self, form):
        messages.error(self.request, "Vérifiez les champs du formulaire.")
        return super().form_invalid(form)

    def get_success_url(self):
        return reverse("actuators:actuator-detail", kwargs={"pk": self.object.pk})


class ActuatorDeleteView(LoginRequiredMixin, TemplateView):
    template_name = "actuators/confirm_delete.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        actuator = get_object_or_404(
            Actuator.objects.select_related("space", "space__building"), pk=self.kwargs["pk"]
        )
        context.update(
            {
                "actuator": actuator,
                "has_related_records": has_related_records(actuator),
                "cancel_url": reverse("actuators:actuator-detail", kwargs={"pk": actuator.pk}),
                "delete_url": reverse("actuators:actuator-delete", kwargs={"pk": actuator.pk}),
            }
        )
        return context

    def post(self, request, *args, **kwargs):
        if request.POST.get("confirmed") != "1":
            messages.error(request, "Confirmez l’action depuis la page de confirmation.")
            return redirect("actuators:actuator-delete", pk=self.kwargs["pk"])
        actuator = get_object_or_404(Actuator, pk=self.kwargs["pk"])
        deleted = archive_or_delete(actuator)
        if deleted:
            messages.success(request, "L’actionneur a été supprimé.")
        else:
            messages.warning(
                request,
                "Cet actionneur possède des commandes ou des données associées; il a été désactivé pour préserver l’historique.",
            )
        return redirect("actuators:actuator-list")


class ActuatorCommandHistoryView(LoginRequiredMixin, ListView):
    model = ActuatorCommand
    template_name = "actuators/command_list.html"
    context_object_name = "commands"

    def get_actuator(self):
        if not hasattr(self, "actuator"):
            self.actuator = get_object_or_404(
                Actuator.objects.select_related("space", "space__building"),
                pk=self.kwargs["pk"],
            )
        return self.actuator

    def get_queryset(self):
        queryset = self.get_actuator().commands.select_related(
            "actuator", "actuator__space", "actuator__space__building"
        )
        status_filter = self.request.GET.get("status")
        if status_filter:
            if status_filter not in ActuatorCommand.Status.values:
                self.filter_error = "Sélectionnez un statut de commande valide."
                return queryset.none()
            queryset = queryset.filter(status=status_filter)
        command_type = self.request.GET.get("command_type")
        if command_type:
            if command_type not in ActuatorCommand.CommandType.values:
                self.filter_error = "Sélectionnez un type de commande valide."
                return queryset.none()
            queryset = queryset.filter(command_type=command_type)
        return queryset

    def get_paginate_by(self, queryset):
        requested_size = self.request.GET.get("page_size")
        if requested_size and requested_size.isdecimal() and 1 <= int(requested_size) <= 100:
            return int(requested_size)
        return settings.MEASUREMENTS_PAGE_SIZE

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context.update(
            {
                "actuator": self.get_actuator(),
                "status_choices": ActuatorCommand.Status.choices,
                "selected_status": self.request.GET.get("status", ""),
                "selected_command_type": self.request.GET.get("command_type", ""),
                "filter_error": getattr(self, "filter_error", ""),
                "can_receive_command": can_receive_command(self.get_actuator()),
            }
        )
        params = self.request.GET.copy()
        params.pop("page", None)
        context["filter_query"] = params.urlencode()
        return context


class AllActuatorCommandHistoryView(LoginRequiredMixin, ListView):
    model = ActuatorCommand
    template_name = "actuators/all_command_list.html"
    context_object_name = "commands"

    def get_queryset(self):
        queryset = ActuatorCommand.objects.select_related(
            "actuator", "actuator__space", "actuator__space__building"
        )
        status_filter = self.request.GET.get("status")
        if status_filter:
            if status_filter not in ActuatorCommand.Status.values:
                self.filter_error = "Sélectionnez un statut de commande valide."
                return queryset.none()
            queryset = queryset.filter(status=status_filter)
        return queryset

    def get_paginate_by(self, queryset):
        requested_size = self.request.GET.get("page_size")
        if requested_size and requested_size.isdecimal() and 1 <= int(requested_size) <= 100:
            return int(requested_size)
        return settings.MEASUREMENTS_PAGE_SIZE

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["status_choices"] = ActuatorCommand.Status.choices
        context["selected_status"] = self.request.GET.get("status", "")
        context["filter_error"] = getattr(self, "filter_error", "")
        params = self.request.GET.copy()
        params.pop("page", None)
        context["filter_query"] = params.urlencode()
        return context


class ActuatorCommandCreateView(LoginRequiredMixin, CreateView):
    model = ActuatorCommand
    form_class = ActuatorCommandForm
    template_name = "actuators/command_form.html"

    def dispatch(self, request, *args, **kwargs):
        if request.user.is_authenticated:
            self.actuator = get_object_or_404(
                Actuator.objects.select_related("space", "space__building"),
                pk=self.kwargs["pk"],
            )
            if not can_receive_command(self.actuator):
                messages.error(request, "Cet actionneur, son espace ou son bâtiment est inactif; aucune commande ne peut être créée.")
                return redirect("actuators:actuator-detail", pk=self.actuator.pk)
        return super().dispatch(request, *args, **kwargs)

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs["actuator"] = self.actuator
        return kwargs

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["actuator"] = self.actuator
        context["page_title"] = "Créer une commande"
        context["cancel_url"] = reverse("actuators:actuator-detail", kwargs={"pk": self.actuator.pk})
        return context

    def form_valid(self, form):
        form.instance.actuator = self.actuator
        self.object = form.save()
        messages.success(self.request, "La commande a été enregistrée avec le statut En attente.")
        return redirect("actuators:command-list", pk=self.actuator.pk)

    def form_invalid(self, form):
        messages.error(self.request, "La commande n’a pas été enregistrée. Vérifiez les informations saisies.")
        return super().form_invalid(form)
