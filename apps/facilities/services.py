from django.core.exceptions import ObjectDoesNotExist
from django.db import transaction
from django.db.models.deletion import ProtectedError


def has_related_records(instance):
    """Return whether any reverse relation currently contains linked data."""
    for relation in instance._meta.related_objects:
        accessor = relation.get_accessor_name()
        try:
            related = getattr(instance, accessor)
            if relation.one_to_one:
                related.get()
                return True
            if related.exists():
                return True
        except ObjectDoesNotExist:
            continue
    return False


@transaction.atomic
def archive_or_delete(instance):
    """Delete unreferenced records; archive any record with dependent data."""
    instance = type(instance).objects.select_for_update().get(pk=instance.pk)
    if has_related_records(instance):
        instance.is_active = False
        instance.save(update_fields=("is_active", "updated_at"))
        return False

    try:
        instance.delete()
    except ProtectedError:
        instance.is_active = False
        instance.save(update_fields=("is_active", "updated_at"))
        return False
    return True
