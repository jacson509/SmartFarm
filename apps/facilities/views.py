from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.shortcuts import redirect
from django.shortcuts import get_object_or_404
from django.urls import reverse
from django.views.generic import CreateView, DetailView, ListView, TemplateView, UpdateView

from apps.facilities.forms import BuildingForm, SpaceForm
from apps.facilities.models import Building, Space
from apps.facilities.services import archive_or_delete, has_related_records


class BuildingListView(LoginRequiredMixin, ListView):
    model = Building
    template_name = "facilities/building_list.html"
    context_object_name = "buildings"


class BuildingDetailView(LoginRequiredMixin, DetailView):
    model = Building
    template_name = "facilities/building_detail.html"
    context_object_name = "building"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["spaces"] = self.object.spaces.all()
        context["has_related_records"] = has_related_records(self.object)
        return context


class BuildingCreateView(LoginRequiredMixin, CreateView):
    model = Building
    form_class = BuildingForm
    template_name = "facilities/object_form.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["page_title"] = "Créer un bâtiment"
        context["cancel_url"] = reverse("facilities:building-list")
        return context

    def form_valid(self, form):
        response = super().form_valid(form)
        messages.success(self.request, "Le bâtiment a été créé.")
        return response

    def get_success_url(self):
        return reverse("facilities:building-detail", kwargs={"pk": self.object.pk})


class BuildingUpdateView(LoginRequiredMixin, UpdateView):
    model = Building
    form_class = BuildingForm
    template_name = "facilities/object_form.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["page_title"] = "Modifier le bâtiment"
        context["cancel_url"] = reverse("facilities:building-detail", kwargs={"pk": self.object.pk})
        return context

    def form_valid(self, form):
        response = super().form_valid(form)
        messages.success(self.request, "Le bâtiment a été modifié.")
        return response

    def get_success_url(self):
        return reverse("facilities:building-detail", kwargs={"pk": self.object.pk})


class BuildingDeleteView(LoginRequiredMixin, TemplateView):
    template_name = "facilities/confirm_delete.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        building = get_object_or_404(Building, pk=self.kwargs["pk"])
        context.update(
            {
                "object": building,
                "object_type": "bâtiment",
                "has_related_records": has_related_records(building),
                "cancel_url": reverse("facilities:building-detail", kwargs={"pk": building.pk}),
                "delete_url": reverse("facilities:building-delete", kwargs={"pk": building.pk}),
            }
        )
        return context

    def post(self, request, *args, **kwargs):
        if request.POST.get("confirmed") != "1":
            messages.error(request, "Confirmez l’action depuis la page de confirmation.")
            return redirect("facilities:building-delete", pk=self.kwargs["pk"])
        building = get_object_or_404(Building, pk=self.kwargs["pk"])
        deleted = archive_or_delete(building)
        if deleted:
            messages.success(request, "Le bâtiment a été supprimé.")
        else:
            messages.warning(
                request,
                "Le bâtiment possède des espaces ou des données associées; il a été désactivé pour préserver ces données.",
            )
        return redirect("facilities:building-list")


class SpaceListView(LoginRequiredMixin, ListView):
    model = Space
    template_name = "facilities/space_list.html"
    context_object_name = "spaces"

    def get_queryset(self):
        queryset = Space.objects.select_related("building")
        building_id = self.request.GET.get("building")
        if building_id:
            if not building_id.isdecimal():
                return queryset.none()
            queryset = queryset.filter(building_id=int(building_id))
        return queryset

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["buildings"] = Building.objects.all()
        context["selected_building"] = self.request.GET.get("building", "")
        return context


class SpaceDetailView(LoginRequiredMixin, DetailView):
    model = Space
    queryset = Space.objects.select_related("building")
    template_name = "facilities/space_detail.html"
    context_object_name = "space"
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["has_related_records"] = has_related_records(self.object)
        return context


class SpaceCreateView(LoginRequiredMixin, CreateView):
    model = Space
    form_class = SpaceForm
    template_name = "facilities/object_form.html"

    def get_initial(self):
        initial = super().get_initial()
        building_id = self.request.GET.get("building")
        if building_id and building_id.isdecimal():
            initial["building"] = int(building_id)
        return initial

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["page_title"] = "Créer un espace"
        context["cancel_url"] = reverse("facilities:space-list")
        return context

    def form_valid(self, form):
        response = super().form_valid(form)
        messages.success(self.request, "L’espace a été créé.")
        return response

    def get_success_url(self):
        return reverse("facilities:space-detail", kwargs={"pk": self.object.pk})


class SpaceUpdateView(LoginRequiredMixin, UpdateView):
    model = Space
    form_class = SpaceForm
    template_name = "facilities/object_form.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["page_title"] = "Modifier l’espace"
        context["cancel_url"] = reverse("facilities:space-detail", kwargs={"pk": self.object.pk})
        return context

    def form_valid(self, form):
        response = super().form_valid(form)
        messages.success(self.request, "L’espace a été modifié.")
        return response

    def get_success_url(self):
        return reverse("facilities:space-detail", kwargs={"pk": self.object.pk})


class SpaceDeleteView(LoginRequiredMixin, TemplateView):
    template_name = "facilities/confirm_delete.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        space = get_object_or_404(Space.objects.select_related("building"), pk=self.kwargs["pk"])
        context.update(
            {
                "object": space,
                "object_type": "espace",
                "has_related_records": has_related_records(space),
                "cancel_url": reverse("facilities:space-detail", kwargs={"pk": space.pk}),
                "delete_url": reverse("facilities:space-delete", kwargs={"pk": space.pk}),
            }
        )
        return context

    def post(self, request, *args, **kwargs):
        if request.POST.get("confirmed") != "1":
            messages.error(request, "Confirmez l’action depuis la page de confirmation.")
            return redirect("facilities:space-delete", pk=self.kwargs["pk"])
        space = get_object_or_404(Space, pk=self.kwargs["pk"])
        deleted = archive_or_delete(space)
        if deleted:
            messages.success(request, "L’espace a été supprimé.")
        else:
            messages.warning(
                request,
                "L’espace possède des données associées; il a été désactivé pour préserver ces données.",
            )
        return redirect("facilities:space-list")
