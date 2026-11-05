from django import forms

from apps.facilities.models import Space
from apps.sensors.models import Sensor


class SensorForm(forms.ModelForm):
    space = forms.ModelChoiceField(
        queryset=Space.objects.none(),
        label="Espace",
        error_messages={
            "required": "Un espace actif est obligatoire.",
            "invalid_choice": "Choisissez un espace actif existant.",
        },
    )

    class Meta:
        model = Sensor
        fields = (
            "name",
            "sensor_type",
            "space",
            "minimum_threshold",
            "maximum_threshold",
            "description",
            "is_active",
        )
        widgets = {
            "name": forms.TextInput(attrs={"data-trim-required": "true"}),
            "minimum_threshold": forms.NumberInput(
                attrs={"step": "0.01", "data-threshold": "minimum"}
            ),
            "maximum_threshold": forms.NumberInput(
                attrs={"step": "0.01", "data-threshold": "maximum"}
            ),
            "description": forms.Textarea(attrs={"rows": 4}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["space"].queryset = Space.objects.filter(is_active=True).select_related(
            "building"
        )
        self.fields["space"].label_from_instance = lambda space: (
            f"{space.name} — {space.building.name}"
        )

    def clean_name(self):
        name = self.cleaned_data["name"].strip()
        if not name:
            raise forms.ValidationError("Le nom du capteur est obligatoire.")
        return name
