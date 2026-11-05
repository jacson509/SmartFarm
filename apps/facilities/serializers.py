from rest_framework import serializers

from apps.facilities.models import Building, Space


class BuildingSerializer(serializers.ModelSerializer):
    class Meta:
        model = Building
        fields = (
            "id",
            "name",
            "location",
            "description",
            "is_active",
            "created_at",
            "updated_at",
        )
        read_only_fields = ("id", "created_at", "updated_at")

    def validate_name(self, value):
        value = value.strip()
        if not value:
            raise serializers.ValidationError("Le nom du bâtiment est obligatoire.")
        return value


class SpaceSerializer(serializers.ModelSerializer):
    building = serializers.PrimaryKeyRelatedField(queryset=Building.objects.all())

    class Meta:
        model = Space
        fields = (
            "id",
            "building",
            "name",
            "description",
            "is_active",
            "created_at",
            "updated_at",
        )
        read_only_fields = ("id", "created_at", "updated_at")

    def validate_name(self, value):
        value = value.strip()
        if not value:
            raise serializers.ValidationError("Le nom de l’espace est obligatoire.")
        return value
