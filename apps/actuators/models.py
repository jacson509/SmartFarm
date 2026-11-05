from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import Q
from django.utils import timezone

from apps.facilities.models import Space


class Actuator(models.Model):
    class ActuatorType(models.TextChoices):
        FAN = "FAN", "Ventilateur"
        HEATER = "HEATER", "Chauffage"
        LIGHTING = "LIGHTING", "Éclairage"
        WATER_PUMP = "WATER_PUMP", "Pompe à eau"
        VENTILATION = "VENTILATION", "Système de ventilation"
        OTHER = "OTHER", "Autre équipement"

    name = models.CharField("nom", max_length=150)
    actuator_type = models.CharField("type", max_length=20, choices=ActuatorType.choices)
    space = models.ForeignKey(
        Space,
        on_delete=models.PROTECT,
        related_name="actuators",
        verbose_name="espace",
    )
    description = models.TextField("description", blank=True)
    is_active = models.BooleanField("actif", default=True)
    created_at = models.DateTimeField("créé le", auto_now_add=True)
    updated_at = models.DateTimeField("modifié le", auto_now=True)

    class Meta:
        ordering = ("name", "pk")
        verbose_name = "actionneur"
        verbose_name_plural = "actionneurs"
        constraints = [
            models.CheckConstraint(
                condition=Q(
                    actuator_type__in=("FAN", "HEATER", "LIGHTING", "WATER_PUMP", "VENTILATION", "OTHER")
                ),
                name="actuator_type_valid",
            ),
        ]

    def clean(self):
        self.name = self.name.strip() if self.name else self.name
        errors = {}
        if not self.name:
            errors["name"] = "Le nom de l’actionneur est obligatoire."
        if self.actuator_type not in self.ActuatorType.values:
            errors["actuator_type"] = "Sélectionnez un type d’actionneur valide."

        if self.space_id:
            try:
                if not self.space.is_active:
                    errors["space"] = "Un actionneur doit être associé à un espace actif."
            except Space.DoesNotExist:
                errors["space"] = "Sélectionnez un espace existant."
        else:
            errors["space"] = "Un espace actif est obligatoire."

        if errors:
            raise ValidationError(errors)

    def save(self, *args, **kwargs):
        self.full_clean()
        return super().save(*args, **kwargs)

    def __str__(self):
        return self.name


class ActuatorCommand(models.Model):
    class CommandType(models.TextChoices):
        POWER_STATE = "POWER_STATE", "État marche/arrêt"

    class Value(models.TextChoices):
        ON = "ON", "Marche"
        OFF = "OFF", "Arrêt"

    class Status(models.TextChoices):
        PENDING = "PENDING", "En attente"
        EXECUTED = "EXECUTED", "Exécutée"
        FAILED = "FAILED", "Échec"
        CANCELLED = "CANCELLED", "Annulée"

    actuator = models.ForeignKey(
        Actuator,
        on_delete=models.PROTECT,
        related_name="commands",
        verbose_name="actionneur",
    )
    command_type = models.CharField(
        "type de commande",
        max_length=20,
        choices=CommandType.choices,
        default=CommandType.POWER_STATE,
    )
    value = models.CharField("état demandé", max_length=3, choices=Value.choices)
    status = models.CharField(
        "statut",
        max_length=10,
        choices=Status.choices,
        default=Status.PENDING,
    )
    requested_at = models.DateTimeField("demandée le", default=timezone.now)
    executed_at = models.DateTimeField("exécutée le", null=True, blank=True)
    created_at = models.DateTimeField("créée le", auto_now_add=True)

    class Meta:
        ordering = ("-requested_at", "-pk")
        verbose_name = "commande d’actionneur"
        verbose_name_plural = "commandes d’actionneurs"
        constraints = [
            models.CheckConstraint(
                condition=Q(command_type="POWER_STATE"),
                name="actuator_command_type_valid",
            ),
            models.CheckConstraint(
                condition=Q(value__in=("ON", "OFF")),
                name="actuator_command_value_valid",
            ),
            models.CheckConstraint(
                condition=Q(status__in=("PENDING", "EXECUTED", "FAILED", "CANCELLED")),
                name="actuator_command_status_valid",
            ),
        ]

    def clean(self):
        errors = {}
        if not self.actuator_id:
            errors["actuator"] = "Un actionneur est obligatoire."
        else:
            try:
                if not self.actuator.is_active:
                    errors["actuator"] = "Un actionneur inactif ne peut pas recevoir de commande."
                if not self.actuator.space.is_active:
                    errors["actuator"] = "L’espace de l’actionneur est inactif."
                if not self.actuator.space.building.is_active:
                    errors["actuator"] = "Le bâtiment de l’actionneur est inactif."
            except Actuator.DoesNotExist:
                errors["actuator"] = "L’actionneur sélectionné n’existe pas."

        if self.command_type not in self.CommandType.values:
            errors["command_type"] = "Ce type de commande n’est pas autorisé."
        if self.value not in self.Value.values:
            errors["value"] = "La commande doit demander l’état ON ou OFF."
        if self.status not in self.Status.values:
            errors["status"] = "Sélectionnez un statut de commande valide."
        if self.status == self.Status.EXECUTED and self.executed_at is None:
            errors["executed_at"] = "Une commande exécutée doit avoir une date d’exécution."

        if errors:
            raise ValidationError(errors)

    def save(self, *args, **kwargs):
        self.full_clean()
        return super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.actuator.name} — {self.get_value_display()} ({self.get_status_display()})"
