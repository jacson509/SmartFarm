from django.core.exceptions import ValidationError
from django.db import models


class Building(models.Model):
    name = models.CharField("nom", max_length=150)
    location = models.CharField("emplacement", max_length=200, blank=True)
    description = models.TextField("description", blank=True)
    is_active = models.BooleanField("actif", default=True)
    created_at = models.DateTimeField("créé le", auto_now_add=True)
    updated_at = models.DateTimeField("modifié le", auto_now=True)

    class Meta:
        ordering = ("name", "pk")
        verbose_name = "bâtiment"
        verbose_name_plural = "bâtiments"

    def clean(self):
        self.name = self.name.strip() if self.name else self.name
        if not self.name:
            raise ValidationError({"name": "Le nom du bâtiment est obligatoire."})

    def __str__(self):
        return self.name


class Space(models.Model):
    building = models.ForeignKey(
        Building,
        on_delete=models.PROTECT,
        related_name="spaces",
        verbose_name="bâtiment",
    )
    name = models.CharField("nom", max_length=150)
    description = models.TextField("description", blank=True)
    is_active = models.BooleanField("actif", default=True)
    created_at = models.DateTimeField("créé le", auto_now_add=True)
    updated_at = models.DateTimeField("modifié le", auto_now=True)

    class Meta:
        ordering = ("name", "pk")
        verbose_name = "espace"
        verbose_name_plural = "espaces"

    def clean(self):
        self.name = self.name.strip() if self.name else self.name
        if not self.name:
            raise ValidationError({"name": "Le nom de l’espace est obligatoire."})
        if not self.building_id:
            raise ValidationError({"building": "Un bâtiment valide est obligatoire."})

    def __str__(self):
        return f"{self.name} — {self.building.name}"
