from rest_framework import viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import ValidationError
from rest_framework.response import Response
from rest_framework import status

from apps.facilities.models import Building, Space
from apps.facilities.serializers import BuildingSerializer, SpaceSerializer
from apps.facilities.services import archive_or_delete


class ArchiveAwareModelViewSet(viewsets.ModelViewSet):
    def destroy(self, request, *args, **kwargs):
        instance = self.get_object()
        deleted = archive_or_delete(instance)
        if deleted:
            return Response(status=status.HTTP_204_NO_CONTENT)
        return Response(
            {
                "detail": "L’objet possède des données associées; il a été désactivé pour les préserver.",
                "archived": True,
            },
            status=status.HTTP_200_OK,
        )

    @action(detail=True, methods=["post"])
    def archive(self, request, pk=None):
        instance = self.get_object()
        instance.is_active = False
        instance.save(update_fields=("is_active", "updated_at"))
        return Response(self.get_serializer(instance).data)


class BuildingViewSet(ArchiveAwareModelViewSet):
    queryset = Building.objects.all()
    serializer_class = BuildingSerializer


class SpaceViewSet(ArchiveAwareModelViewSet):
    queryset = Space.objects.select_related("building").all()
    serializer_class = SpaceSerializer

    def get_queryset(self):
        queryset = super().get_queryset()
        raw_building = self.request.query_params.get("building")
        if raw_building is None:
            return queryset
        try:
            building_id = int(raw_building)
        except (TypeError, ValueError):
            raise ValidationError({"building": "Fournissez un identifiant de bâtiment valide."})
        if building_id < 1 or not Building.objects.filter(pk=building_id).exists():
            raise ValidationError({"building": "Le bâtiment demandé n’existe pas."})
        return queryset.filter(building_id=building_id)
