document.addEventListener("DOMContentLoaded", () => {
  const form = document.querySelector("[data-sensor-form]");
  if (!form) return;

  const typeField = form.querySelector("#id_sensor_type");
  const minimumField = form.querySelector("[data-threshold='minimum']");
  const maximumField = form.querySelector("[data-threshold='maximum']");
  const unitPreview = form.querySelector("[data-unit-preview]");
  const ranges = {
    TEMPERATURE: { min: -50, max: 80, unit: "°C" },
    HUMIDITY: { min: 0, max: 100, unit: "%" },
  };

  const validateThresholds = () => {
    const range = ranges[typeField.value];
    minimumField.setCustomValidity("");
    maximumField.setCustomValidity("");
    if (!range) return;

    minimumField.min = String(range.min);
    minimumField.max = String(range.max);
    maximumField.min = String(range.min);
    maximumField.max = String(range.max);

    const minimum = minimumField.valueAsNumber;
    const maximum = maximumField.valueAsNumber;
    if (minimumField.value && (minimum < range.min || minimum > range.max)) {
      minimumField.setCustomValidity(`Le seuil minimum doit être entre ${range.min} et ${range.max} ${range.unit}.`);
    }
    if (maximumField.value && (maximum < range.min || maximum > range.max)) {
      maximumField.setCustomValidity(`Le seuil maximum doit être entre ${range.min} et ${range.max} ${range.unit}.`);
    } else if (minimumField.value && maximumField.value && minimum >= maximum) {
      maximumField.setCustomValidity("Le seuil maximum doit être supérieur au seuil minimum.");
    }
    if (unitPreview) unitPreview.textContent = range.unit;
  };

  typeField.addEventListener("change", validateThresholds);
  minimumField.addEventListener("input", validateThresholds);
  maximumField.addEventListener("input", validateThresholds);
  form.addEventListener("submit", (event) => {
    validateThresholds();
    if (!form.checkValidity()) {
      event.preventDefault();
      form.reportValidity();
    }
  });
  validateThresholds();
});
