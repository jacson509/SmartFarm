from django.urls import path

from apps.facilities import views

app_name = "facilities"

urlpatterns = [
    path("buildings/", views.BuildingListView.as_view(), name="building-list"),
    path("buildings/create/", views.BuildingCreateView.as_view(), name="building-create"),
    path("buildings/<int:pk>/", views.BuildingDetailView.as_view(), name="building-detail"),
    path("buildings/<int:pk>/edit/", views.BuildingUpdateView.as_view(), name="building-update"),
    path("buildings/<int:pk>/delete/", views.BuildingDeleteView.as_view(), name="building-delete"),
    path("spaces/", views.SpaceListView.as_view(), name="space-list"),
    path("spaces/create/", views.SpaceCreateView.as_view(), name="space-create"),
    path("spaces/<int:pk>/", views.SpaceDetailView.as_view(), name="space-detail"),
    path("spaces/<int:pk>/edit/", views.SpaceUpdateView.as_view(), name="space-update"),
    path("spaces/<int:pk>/delete/", views.SpaceDeleteView.as_view(), name="space-delete"),
]
