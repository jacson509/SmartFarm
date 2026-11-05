(function () {
  const svg = document.getElementById("environment-chart");
  const dataElement = document.getElementById("dashboard-chart-data");
  if (!svg || !dataElement) return;

  const data = JSON.parse(dataElement.textContent);
  const width = 760;
  const height = 300;
  const margin = { top: 20, right: 48, bottom: 42, left: 48 };
  const chartWidth = width - margin.left - margin.right;
  const chartHeight = height - margin.top - margin.bottom;
  const namespace = "http://www.w3.org/2000/svg";

  function element(name, attributes, text) {
    const node = document.createElementNS(namespace, name);
    Object.entries(attributes || {}).forEach(([key, value]) => node.setAttribute(key, value));
    if (text !== undefined) node.textContent = text;
    svg.appendChild(node);
    return node;
  }

  const allDates = data.temperature.concat(data.humidity).map((point) => new Date(point.date).getTime());
  if (!allDates.length) return;
  const minDate = Math.min(...allDates);
  const maxDate = Math.max(...allDates);
  const x = (date) => margin.left + (maxDate === minDate ? chartWidth / 2 : ((new Date(date).getTime() - minDate) / (maxDate - minDate)) * chartWidth);

  function drawSeries(points, color, side) {
    if (!points.length) return;
    const values = points.map((point) => point.value);
    let minimum = Math.min(...values);
    let maximum = Math.max(...values);
    if (minimum === maximum) { minimum -= 1; maximum += 1; }
    const y = (value) => margin.top + chartHeight - ((value - minimum) / (maximum - minimum)) * chartHeight;
    const axisX = side === "left" ? margin.left : width - margin.right;
    element("line", { x1: axisX, y1: margin.top, x2: axisX, y2: margin.top + chartHeight, stroke: "#aabbb1" });
    element("text", { x: axisX, y: margin.top - 5, "text-anchor": side === "left" ? "start" : "end", class: "chart-axis-label" }, maximum.toFixed(1));
    element("text", { x: axisX, y: margin.top + chartHeight + 16, "text-anchor": side === "left" ? "start" : "end", class: "chart-axis-label" }, minimum.toFixed(1));
    const coordinates = points.map((point) => `${x(point.date)},${y(point.value)}`).join(" ");
    element("polyline", { points: coordinates, fill: "none", stroke: color, "stroke-width": 2.5, "stroke-linejoin": "round", "stroke-linecap": "round" });
    points.forEach((point) => element("circle", { cx: x(point.date), cy: y(point.value), r: 3.5, fill: color }));
  }

  element("line", { x1: margin.left, y1: margin.top + chartHeight, x2: width - margin.right, y2: margin.top + chartHeight, stroke: "#aabbb1" });
  element("text", { x: margin.left, y: height - 8, class: "chart-date-label" }, new Date(minDate).toLocaleString());
  element("text", { x: width - margin.right, y: height - 8, "text-anchor": "end", class: "chart-date-label" }, new Date(maxDate).toLocaleString());
  drawSeries(data.temperature, "#176b4b", "left");
  drawSeries(data.humidity, "#b36b18", "right");
})();
