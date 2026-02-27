(function () {
  initMetrics();
  initArchitecture();
  initPlayground();
})();

function initMetrics() {
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

  const fastest = strategies.reduce((best, current) => {
    if (!best) return current;
    return Number(avgLat[current] || 0) < Number(avgLat[best] || 0) ? current : best;
  }, null);

  const slowest = strategies.reduce((best, current) => {
    if (!best) return current;
    return Number(avgLat[current] || 0) > Number(avgLat[best] || 0) ? current : best;
  }, null);

  const kpis = [
    { value: data.run_id || "N/A", label: "Experiment run ID" },
    { value: bestStrategy ? bestStrategy.toUpperCase() : "N/A", label: "Best average accuracy" },
    { value: fastest ? `${fastest.toUpperCase()} (${Number(avgLat[fastest]).toFixed(1)} ms)` : "N/A", label: "Fastest strategy" },
    { value: slowest ? `${slowest.toUpperCase()} (${Number(avgLat[slowest]).toFixed(1)} ms)` : "N/A", label: "Highest latency strategy" },
  ];

  kpiGrid.innerHTML = kpis
    .map((kpi) => `<div class="kpi"><div class="value">${kpi.value}</div><div class="label">${kpi.label}</div></div>`)
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
}

function initArchitecture() {
  const details = document.getElementById("archDetails");
  const nodes = Array.from(document.querySelectorAll(".arch-node"));
  const simulateBtn = document.getElementById("simulateFlow");
  const resetBtn = document.getElementById("resetFlow");
  if (!details || nodes.length === 0) return;

  const nodeInfo = {
    user: "User Query: point where user prompt enters the distributed system.",
    orchestrator: "Orchestrator: performs async fan-out, strategy selection, and response aggregation.",
    agent1: "Agent 1: llama3.2:3b served by Ollama endpoint.",
    agent2: "Agent 2: qwen2.5:3b served by Ollama endpoint.",
    agent3: "Agent 3: phi3:mini served by Ollama endpoint.",
    agent4: "Agent 4: gemma2:2b served by Ollama endpoint.",
    aggregation: "Aggregation Layer: majority/weighted/ISP/topic/debate + metrics + logging + statistics.",
  };

  function activate(nodeId) {
    nodes.forEach((node) => node.classList.toggle("active", node.dataset.node === nodeId));
    details.textContent = nodeInfo[nodeId] || "Click any node in the architecture map to view role details.";
  }

  nodes.forEach((node) => {
    node.addEventListener("click", () => activate(node.dataset.node));
  });

  function reset() {
    nodes.forEach((node) => node.classList.remove("active"));
    details.textContent = "Click any node in the architecture map to view role details.";
  }

  if (resetBtn) {
    resetBtn.addEventListener("click", reset);
  }

  if (simulateBtn) {
    simulateBtn.addEventListener("click", async () => {
      reset();
      const flow = ["user", "orchestrator", "agent1", "agent2", "agent3", "agent4", "aggregation"];
      for (const nodeId of flow) {
        activate(nodeId);
        await sleep(500);
      }
    });
  }
}

function initPlayground() {
  const form = document.getElementById("playgroundForm");
  const statusEl = document.getElementById("playgroundStatus");
  const outputEl = document.getElementById("playgroundOutput");
  const runBtn = document.getElementById("runQueryBtn");
  if (!form || !statusEl || !outputEl || !runBtn) return;

  const params = new URLSearchParams(window.location.search);
  const qsEndpoint = params.get("endpoint");
  const savedEndpoint = localStorage.getItem("distributed_ai_endpoint");
  const savedPrompt = localStorage.getItem("distributed_ai_prompt");

  if (qsEndpoint && !form.apiEndpoint.value) {
    form.apiEndpoint.value = qsEndpoint;
  } else if (savedEndpoint && !form.apiEndpoint.value) {
    form.apiEndpoint.value = savedEndpoint;
  }
  if (savedPrompt && !form.prompt.value.trim()) {
    form.prompt.value = savedPrompt;
  }

  form.addEventListener("submit", async (event) => {
    event.preventDefault();

    const endpoint = form.apiEndpoint.value.trim().replace(/\/+$/, "");
    if (!endpoint) {
      statusEl.textContent = "Set your public orchestrator endpoint first.";
      outputEl.textContent = "Example: https://your-public-endpoint.example.com";
      return;
    }

    localStorage.setItem("distributed_ai_endpoint", endpoint);
    localStorage.setItem("distributed_ai_prompt", form.prompt.value);

    const payload = {
      prompt: form.prompt.value,
      strategy: form.strategy.value,
      seed: Number(form.seed.value || 42),
      temperature: Number(form.temperature.value || 0),
      deterministic: Boolean(form.deterministic.checked),
      max_tokens: Number(form.maxTokens.value || 64),
    };

    runBtn.disabled = true;
    statusEl.textContent = "Running query...";
    outputEl.textContent = "Waiting for response...";
    const started = performance.now();

    try {
      const response = await fetch(`${endpoint}/query`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });

      const body = await response.json().catch(() => ({}));
      const elapsed = (performance.now() - started).toFixed(0);

      if (!response.ok) {
        statusEl.textContent = `Request failed (${response.status}) in ${elapsed} ms.`;
        outputEl.textContent = JSON.stringify(body, null, 2);
        return;
      }

      const answer = body.answer || body.response || "No answer field in response.";
      statusEl.textContent = `Success in ${elapsed} ms | Strategy: ${payload.strategy} | Answer: ${String(answer).slice(0, 120)}`;
      outputEl.textContent = JSON.stringify(body, null, 2);
    } catch (error) {
      statusEl.textContent = "Network/CORS error. Ensure endpoint is reachable and CORS allows this origin.";
      outputEl.textContent = String(error);
    } finally {
      runBtn.disabled = false;
    }
  });
}

function sleep(ms) {
  return new Promise((resolve) => setTimeout(resolve, ms));
}
