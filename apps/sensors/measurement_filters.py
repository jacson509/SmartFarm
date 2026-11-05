from datetime import datetime, time, timedelta

from django.utils import timezone
from django.utils.dateparse import parse_date


class MeasurementFilterError(Exception):
    def __init__(self, field, message):
        self.field = field
        self.message = message
        super().__init__(message)


def filter_measurements(queryset, params):
    """Apply validated location, sensor, date and ordering filters."""
    from apps.facilities.models import Building, Space
    from apps.sensors.models import Sensor

    for parameter, model, lookup in (
        ("sensor", Sensor, "sensor_id"),
        ("space", Space, "sensor__space_id"),
        ("building", Building, "sensor__space__building_id"),
    ):
        raw_id = params.get(parameter)
        if not raw_id:
            continue
        try:
            object_id = int(raw_id)
        except (TypeError, ValueError):
            raise MeasurementFilterError(parameter, "Fournissez un identifiant entier valide.")
        if object_id < 1 or not model.objects.filter(pk=object_id).exists():
            raise MeasurementFilterError(parameter, "L’objet demandé n’existe pas.")
        queryset = queryset.filter(**{lookup: object_id})

    parsed_dates = {}
    for parameter in ("date_from", "date_to"):
        raw_date = params.get(parameter)
        if not raw_date:
            continue
        parsed = parse_date(raw_date)
        if parsed is None:
            raise MeasurementFilterError(parameter, "Utilisez le format de date AAAA-MM-JJ.")
        parsed_dates[parameter] = parsed

    date_from = parsed_dates.get("date_from")
    date_to = parsed_dates.get("date_to")
    if date_from and date_to and date_from > date_to:
        raise MeasurementFilterError("date_to", "La date de fin doit être égale ou postérieure à la date de début.")

    current_timezone = timezone.get_current_timezone()
    if date_from:
        start = timezone.make_aware(datetime.combine(date_from, time.min), current_timezone)
        queryset = queryset.filter(recorded_at__gte=start)
    if date_to:
        try:
            end_date = date_to + timedelta(days=1)
        except OverflowError:
            raise MeasurementFilterError("date_to", "La date de fin est hors plage.")
        end = timezone.make_aware(datetime.combine(end_date, time.min), current_timezone)
        queryset = queryset.filter(recorded_at__lt=end)

    ordering = params.get("ordering", "-recorded_at")
    if ordering not in ("recorded_at", "-recorded_at"):
        raise MeasurementFilterError("ordering", "Utilisez recorded_at ou -recorded_at.")
    secondary_order = "pk" if ordering == "recorded_at" else "-pk"
    return queryset.order_by(ordering, secondary_order)
