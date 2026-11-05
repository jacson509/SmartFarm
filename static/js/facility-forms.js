document.addEventListener("DOMContentLoaded", () => {
  const requiredTextFields = document.querySelectorAll("[data-trim-required='true']");

  requiredTextFields.forEach((field) => {
    const validateTrimmedValue = () => {
      const isBlank = field.value.trim().length === 0;
      field.setCustomValidity(isBlank ? "Ce champ ne peut pas être vide." : "");
    };

    field.addEventListener("input", validateTrimmedValue);
    field.form?.addEventListener("submit", (event) => {
      validateTrimmedValue();
      if (!field.checkValidity()) {
        event.preventDefault();
        field.reportValidity();
      }
    });
  });
});
