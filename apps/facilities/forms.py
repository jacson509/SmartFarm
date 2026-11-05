from django import forms

from apps.facilities.models import Building, Space


class BuildingForm(forms.ModelForm):
    class Meta:
        model = Building
        fields = ("name", "location", "description", "is_active")
        widgets = {
            "name": forms.TextInput(attrs={"data-trim-required": "true"}),
            "description": forms.Textarea(attrs={"rows": 4}),
        }

    def clean_name(self):
        name = self.cleaned_data["name"].strip()
        if not name:
            raise forms.ValidationError("Le nom du bâtiment est obligatoire.")
        return name


class SpaceForm(forms.ModelForm):
    class Meta:
        model = Space
        fields = ("building", "name", "description", "is_active")
        widgets = {
            "name": forms.TextInput(attrs={"data-trim-required": "true"}),
            "description": forms.Textarea(attrs={"rows": 4}),
        }

    def clean_name(self):
        name = self.cleaned_data["name"].strip()
        if not name:
            raise forms.ValidationError("Le nom de l’espace est obligatoire.")
        return name
