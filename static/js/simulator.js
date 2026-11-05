(function () {
  const buildingSelect = document.getElementById("sim-building");
  const spaceSelect = document.getElementById("sim-space");
  const sensorList = document.getElementById("sim-sensor-list");
  const urlsElement = document.getElementById("simulator-urls");
  if (!buildingSelect || !spaceSelect || !urlsElement) return;

  const urls = JSON.parse(urlsElement.textContent);
  const startButton = document.getElementById("sim-start");
  const stopButton = document.getElementById("sim-stop");
  const stateBadge = document.getElementById("sim-state");
  const message = document.getElementById("sim-action-message");
  const csrfToken = document.querySelector("input[name=csrfmiddlewaretoken]").value;
  let statusTimer = null;

  function showMessage(text, isError) {
    message.textContent = text || "";
    message.hidden = !text;
    message.classList.toggle("message-error", Boolean(isError));
  }

  function setSensorsForSpace() {
    let visibleCount = 0;
    if (!sensorList) return;
    sensorList.querySelectorAll("li").forEach((item) => {
      const visible = item.dataset.spaceId === spaceSelect.value && Boolean(spaceSelect.value);
      item.hidden = !visible;
      if (!visible) item.querySelector("input").checked = false;
      if (visible) visibleCount += 1;
    });
    const noSensors = document.getElementById("sim-no-sensors");
    noSensors.hidden = !spaceSelect.value || visibleCount > 0;
    sensorList.hidden = !spaceSelect.value || visibleCount === 0;
  }

  async function loadSpaces() {
    const buildingId = buildingSelect.value;
    spaceSelect.innerHTML = '<option value="">Choisir un espace</option>';
    setSensorsForSpace();
    if (!buildingId) return;
    try {
      const response = await fetch(`${urls.spaces}?building_id=${encodeURIComponent(buildingId)}`, { credentials: "same-origin" });
      const payload = await response.json();
      if (!response.ok) throw new Error(payload.detail || payload.building_id || "Impossible de charger les espaces.");
      payload.results.forEach((space) => {
        const option = document.createElement("option");
        option.value = space.id;
        option.textContent = space.name;
        spaceSelect.appendChild(option);
      });
    } catch (error) {
      showMessage(error.message, true);
    }
  }

  async function requestStatus() {
    try {
      const response = await fetch(urls.status, { credentials: "same-origin", headers: { Accept: "application/json" } });
      const payload = await response.json();
      if (!response.ok) throw new Error(payload.detail || "Impossible de lire l’état du simulateur.");
      renderStatus(payload);
    } catch (error) {
      showMessage(error.message, true);
    } finally {
      statusTimer = window.setTimeout(requestStatus, 2000);
    }
  }

  function formatDate(value) {
    return value ? new Date(value).toLocaleString() : "—";
  }

  function renderStatus(payload) {
    const running = payload.is_running;
    stateBadge.textContent = running ? "En cours" : "Arrêtée";
    stateBadge.classList.toggle("badge-active", running);
    stateBadge.classList.toggle("badge-inactive", !running);
    startButton.disabled = running;
    stopButton.disabled = !running;
    document.getElementById("sim-count").textContent = payload.measurement_count || 0;
    document.getElementById("sim-last-sent").textContent = formatDate(payload.last_sent_at);

    const tbody = document.getElementById("sim-values");
    tbody.replaceChildren();
    (payload.latest_values || []).forEach((reading) => {
      const row = document.createElement("tr");
      [reading.sensor, reading.type, `${reading.value} ${reading.unit}`, formatDate(reading.sent_at)].forEach((value) => {
        const cell = document.createElement("td");
        cell.textContent = value;
        row.appendChild(cell);
      });
      tbody.appendChild(row);
    });
    const hasValues = (payload.latest_values || []).length > 0;
    document.getElementById("sim-values-empty").hidden = hasValues;
    document.getElementById("sim-values-wrap").hidden = !hasValues;

    const errorList = document.getElementById("sim-errors");
    errorList.replaceChildren();
    (payload.errors || []).forEach((error) => {
      const item = document.createElement("li");
      item.textContent = error;
      errorList.appendChild(item);
    });
    document.getElementById("sim-errors-empty").hidden = (payload.errors || []).length > 0;
  }

  async function postAction(url, body) {
    const response = await fetch(url, {
      method: "POST",
      credentials: "same-origin",
      headers: { "Content-Type": "application/json", "X-CSRFToken": csrfToken, Accept: "application/json" },
      body: JSON.stringify(body || {}),
    });
    const payload = await response.json();
    if (!response.ok) {
      const firstError = Object.values(payload)[0];
      throw new Error(Array.isArray(firstError) ? firstError.join(" ") : (firstError || "La requête a échoué."));
    }
    renderStatus(payload);
    return payload;
  }

  buildingSelect.addEventListener("change", loadSpaces);
  spaceSelect.addEventListener("change", setSensorsForSpace);
  startButton.addEventListener("click", async () => {
    const sensorIds = sensorList
      ? Array.from(sensorList.querySelectorAll('input[name="sensor_ids"]:checked')).map((input) => Number(input.value))
      : [];
    try {
      showMessage("", false);
      const payload = await postAction(urls.start, {
        building_id: Number(buildingSelect.value),
        space_id: Number(spaceSelect.value),
        sensor_ids: sensorIds,
        interval: Number(document.getElementById("sim-interval").value),
      });
      showMessage("Simulation démarrée.", false);
      renderStatus(payload);
    } catch (error) {
      showMessage(error.message, true);
    }
  });
  stopButton.addEventListener("click", async () => {
    try {
      const payload = await postAction(urls.stop);
      showMessage("Simulation arrêtée.", false);
      renderStatus(payload);
    } catch (error) {
      showMessage(error.message, true);
    }
  });

  setSensorsForSpace();
  if (buildingSelect.value) loadSpaces();
  requestStatus();
})();
