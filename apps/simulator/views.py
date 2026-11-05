from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.shortcuts import render
from django.urls import reverse
from django.views.decorators.csrf import ensure_csrf_cookie
from rest_framework import status
from rest_framework.authentication import SessionAuthentication, TokenAuthentication
from rest_framework.authtoken.models import Token
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.facilities.models import Building, Space
from apps.sensors.models import Sensor
from apps.simulator.runtime import SensorSpec, simulation_manager


@login_required
@ensure_csrf_cookie
def simulator_page(request):
    buildings = Building.objects.filter(is_active=True).order_by("name")
    requested_building = request.GET.get("building", "")
    selected_building_id = None
    if requested_building.isdecimal():
        selected_building_id = int(requested_building)
    spaces = Space.objects.filter(
        is_active=True,
        building__is_active=True,
    ).select_related("building").order_by("building__name", "name")
    if selected_building_id:
        spaces = spaces.filter(building_id=selected_building_id)
    else:
        spaces = spaces.none()
    sensors = Sensor.objects.filter(
        is_active=True,
        space__is_active=True,
        space__building__is_active=True,
    ).select_related("space", "space__building").order_by("name")
    return render(request, "simulator/simulator.html", {
        "buildings": buildings,
        "spaces": spaces,
        "sensors": sensors,
        "selected_building_id": selected_building_id,
        "minimum_interval": 5,
        "urls": {
            "start": reverse("simulator:start"),
            "stop": reverse("simulator:stop"),
            "status": reverse("simulator:status"),
            "spaces": reverse("simulator:spaces"),
        },
    })


class SimulatorAPIView(APIView):
    authentication_classes = (SessionAuthentication, TokenAuthentication)
    permission_classes = (IsAuthenticated,)


class SimulatorSpacesAPIView(SimulatorAPIView):
    def get(self, request):
        raw_building_id = request.query_params.get("building_id", "")
        if not raw_building_id.isdecimal() or int(raw_building_id) < 1:
            return Response({"building_id": "Fournissez un identifiant de bâtiment valide."}, status=status.HTTP_400_BAD_REQUEST)
        building = Building.objects.filter(pk=int(raw_building_id), is_active=True).first()
        if building is None:
            return Response({"building_id": "Le bâtiment n’existe pas ou est inactif."}, status=status.HTTP_404_NOT_FOUND)
        spaces = Space.objects.filter(building=building, is_active=True).order_by("name")
        return Response({"results": [{"id": space.pk, "name": space.name} for space in spaces]})


class SimulatorStatusAPIView(SimulatorAPIView):
    def get(self, request):
        return Response(simulation_manager.status(request.user.pk))


class SimulatorStartAPIView(SimulatorAPIView):
    def post(self, request):
        data = request.data
        building_id = self._positive_int(data.get("building_id"))
        space_id = self._positive_int(data.get("space_id"))
        interval = self._positive_int(data.get("interval"))
        sensor_ids = data.get("sensor_ids")
        errors = {}
        if building_id is None:
            errors["building_id"] = "Sélectionnez un bâtiment valide."
        if space_id is None:
            errors["space_id"] = "Sélectionnez un espace valide."
        if interval is None or interval < 5:
            errors["interval"] = "L’intervalle doit être un nombre entier d’au moins 5 secondes."
        if not isinstance(sensor_ids, list) or not sensor_ids:
            errors["sensor_ids"] = "Sélectionnez au moins un capteur actif."
        elif any(self._positive_int(sensor_id) is None for sensor_id in sensor_ids):
            errors["sensor_ids"] = "La sélection contient un identifiant de capteur invalide."
        elif len(set(sensor_ids)) != len(sensor_ids):
            errors["sensor_ids"] = "Un capteur ne peut être sélectionné qu’une seule fois."
        if errors:
            return Response(errors, status=status.HTTP_400_BAD_REQUEST)

        building = Building.objects.filter(pk=building_id, is_active=True).first()
        if building is None:
            return Response({"building_id": "Le bâtiment n’existe pas ou est inactif."}, status=status.HTTP_400_BAD_REQUEST)
        space = Space.objects.filter(
            pk=space_id,
            building=building,
            is_active=True,
        ).first()
        if space is None:
            return Response({"space_id": "L’espace doit être actif et appartenir au bâtiment sélectionné."}, status=status.HTTP_400_BAD_REQUEST)

        normalized_ids = [self._positive_int(sensor_id) for sensor_id in sensor_ids]
        sensors = list(Sensor.objects.filter(
            pk__in=normalized_ids,
            space=space,
            is_active=True,
        ).select_related("space", "space__building").order_by("pk"))
        if len(sensors) != len(normalized_ids):
            return Response({"sensor_ids": "Tous les capteurs doivent être actifs et appartenir à l’espace sélectionné."}, status=status.HTTP_400_BAD_REQUEST)

        token, _ = Token.objects.get_or_create(user=request.user)
        specs = [SensorSpec(
            id=sensor.pk,
            name=sensor.name,
            sensor_type=sensor.sensor_type,
            type_label=sensor.get_sensor_type_display(),
            unit=sensor.unit,
        ) for sensor in sensors]
        base_url = getattr(settings, "SIMULATOR_API_BASE_URL", "http://127.0.0.1:8000")
        task = simulation_manager.start(
            request.user.pk,
            specs,
            interval,
            token.key,
            base_url,
        )
        if task is None:
            return Response({"detail": "Une simulation est déjà en cours pour cet utilisateur."}, status=status.HTTP_409_CONFLICT)
        return Response(task.as_dict(), status=status.HTTP_202_ACCEPTED)

    @staticmethod
    def _positive_int(value):
        if isinstance(value, bool):
            return None
        try:
            normalized = int(value)
        except (TypeError, ValueError, OverflowError):
            return None
        if str(value).strip() != str(normalized) or normalized < 1:
            return None
        return normalized


class SimulatorStopAPIView(SimulatorAPIView):
    def post(self, request):
        task = simulation_manager.stop(request.user.pk)
        if task is None:
            return Response(simulation_manager.status(request.user.pk), status=status.HTTP_200_OK)
        return Response(task.as_dict(), status=status.HTTP_200_OK)
