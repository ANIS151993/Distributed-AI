(function () {
  const data = window.REPORT_DATA || {};
  const kpiGrid = document.getElementById("kpiGrid");
  const chartCanvas = document.getElementById("avgAccChart");
  if (!kpiGrid || !chartCanvas || !Array.isArray(data.strategies)) return;

  const strategies = data.strategies;
  const avgAcc = data.avg_accuracy || {};
  const avgLat = data.avg_latency_ms || {};

  const bestStrategy = strategies.reduce((best, current) => {
    if (!best) return current;
    return Number(avgAcc[current] || 0) > Number(avgAcc[best] || 0) ? current : best;
  }, null);

  const slowest = strategies.reduce((best, current) => {
    if (!best) return current;
    return Number(avgLat[current] || 0) > Number(avgLat[best] || 0) ? current : best;
  }, null);

  const fastest = strategies.reduce((best, current) => {
    if (!best) return current;
    return Number(avgLat[current] || 0) < Number(avgLat[best] || 0) ? current : best;
  }, null);

  const kpis = [
    { value: data.run_id || "N/A", label: "Experiment run ID" },
    { value: bestStrategy ? bestStrategy.toUpperCase() : "N/A", label: "Best average accuracy" },
    { value: fastest ? `${fastest.toUpperCase()} (${Number(avgLat[fastest]).toFixed(1)} ms)` : "N/A", label: "Fastest strategy" },
    { value: slowest ? `${slowest.toUpperCase()} (${Number(avgLat[slowest]).toFixed(1)} ms)` : "N/A", label: "Highest latency strategy" },
  ];

  kpiGrid.innerHTML = kpis
    .map(
      (kpi) =>
        `<div class="kpi"><div class="value">${kpi.value}</div><div class="label">${kpi.label}</div></div>`,
    )
    .join("");

  new Chart(chartCanvas, {
    type: "bar",
    data: {
      labels: strategies.map((s) => s.toUpperCase()),
      datasets: [
        {
          label: "Average Accuracy",
          data: strategies.map((s) => Number(avgAcc[s] || 0)),
          backgroundColor: ["#0f766e", "#2563eb", "#d97706", "#0ea5e9", "#dc2626"],
          borderRadius: 8,
        },
      ],
    },
    options: {
      responsive: true,
      plugins: {
        legend: { display: false },
      },
      scales: {
        y: {
          min: 0,
          max: 1.05,
          title: { display: true, text: "Accuracy" },
        },
        x: {
          title: { display: true, text: "Strategy" },
        },
      },
    },
  });
})();
