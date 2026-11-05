from django import forms

from apps.facilities.models import Space
from apps.actuators.models import Actuator, ActuatorCommand


class ActuatorForm(forms.ModelForm):
    space = forms.ModelChoiceField(
        queryset=Space.objects.none(),
        label="Espace",
        error_messages={
            "required": "Un espace actif est obligatoire.",
            "invalid_choice": "Choisissez un espace actif existant.",
        },
    )

    class Meta:
        model = Actuator
        fields = ("name", "actuator_type", "space", "description", "is_active")
        widgets = {
            "name": forms.TextInput(attrs={"data-trim-required": "true"}),
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
            raise forms.ValidationError("Le nom de l’actionneur est obligatoire.")
        return name


class ActuatorCommandForm(forms.ModelForm):
    class Meta:
        model = ActuatorCommand
        fields = ("value",)

    def __init__(self, *args, actuator=None, **kwargs):
        if kwargs.get("instance") is None:
            kwargs["instance"] = ActuatorCommand(actuator=actuator)
        super().__init__(*args, **kwargs)
        self.actuator = actuator or self.instance.actuator

    def clean(self):
        cleaned = super().clean()
        actuator = self.actuator
        if actuator is None:
            raise forms.ValidationError("Un actionneur est obligatoire.")
        if not actuator.is_active:
            raise forms.ValidationError("Un actionneur inactif ne peut pas recevoir de commande.")
        if not actuator.space.is_active:
            raise forms.ValidationError("L’espace de l’actionneur est inactif.")
        if not actuator.space.building.is_active:
            raise forms.ValidationError("Le bâtiment de l’actionneur est inactif.")
        return cleaned
