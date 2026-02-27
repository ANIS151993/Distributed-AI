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
  const checkBtn = document.getElementById("checkEndpointBtn");
  const selectAllBtn = document.getElementById("selectAllAgentsBtn");
  const clearAgentsBtn = document.getElementById("clearAgentsBtn");
  const agentSelector = document.getElementById("agentSelector");
  const tableBody = document.getElementById("queryAgentTableBody");
  const latencyCanvas = document.getElementById("queryLatencyChart");
  const tokenCanvas = document.getElementById("queryTokenChart");
  const answerCanvas = document.getElementById("queryAnswerChart");
  if (!form || !statusEl || !outputEl || !runBtn) return;

  const queryCharts = { latency: null, tokens: null, answers: null };
  const state = { agents: [] };

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

  function resolveEndpoint() {
    return form.apiEndpoint.value.trim().replace(/\/+$/, "");
  }

  function escapeHtml(value) {
    return String(value ?? "")
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;")
      .replace(/'/g, "&#39;");
  }

  function getSelectedAgentIds() {
    return Array.from(document.querySelectorAll('input[name="agentSelect"]:checked')).map((el) => el.value);
  }

  function setAllAgentSelection(checked) {
    Array.from(document.querySelectorAll('input[name="agentSelect"]')).forEach((el) => {
      el.checked = checked;
    });
  }

  function renderAgentSelector(agents) {
    if (!agentSelector) return;
    if (!Array.isArray(agents) || agents.length === 0) {
      agentSelector.innerHTML = '<p class="muted">No enabled agents found from /agents.</p>';
      return;
    }

    const existingSelection = new Set(getSelectedAgentIds());
    const useExisting = existingSelection.size > 0;
    agentSelector.innerHTML = agents
      .map((agent) => {
        const checked = useExisting ? existingSelection.has(agent.id) : true;
        return `
          <div class="agent-option">
            <label>
              <input type="checkbox" name="agentSelect" value="${escapeHtml(agent.id)}" ${checked ? "checked" : ""} />
              ${escapeHtml(agent.id)}
            </label>
            <div class="agent-meta">${escapeHtml(agent.model)} @ ${escapeHtml(agent.host)}:${escapeHtml(agent.port)}</div>
          </div>
        `;
      })
      .join("");
  }

  function destroyQueryCharts() {
    if (queryCharts.latency) queryCharts.latency.destroy();
    if (queryCharts.tokens) queryCharts.tokens.destroy();
    if (queryCharts.answers) queryCharts.answers.destroy();
    queryCharts.latency = null;
    queryCharts.tokens = null;
    queryCharts.answers = null;
  }

  function renderResultTable(responses) {
    if (!tableBody) return;
    if (!Array.isArray(responses) || responses.length === 0) {
      tableBody.innerHTML = '<tr><td colspan="6">No per-model responses available.</td></tr>';
      return;
    }

    tableBody.innerHTML = responses
      .map((row) => {
        const answer = row.normalized_answer || row.answer || "(empty)";
        const status = row.error ? `error: ${row.error}` : "ok";
        return `
          <tr>
            <td>${escapeHtml(row.agent_id || "")}</td>
            <td>${escapeHtml(row.model_id || "")}</td>
            <td>${escapeHtml(answer)}</td>
            <td>${Number(row.latency_ms || 0).toFixed(1)}</td>
            <td>${Number(row.token_count || 0)}</td>
            <td>${escapeHtml(status)}</td>
          </tr>
        `;
      })
      .join("");
  }

  function renderQueryCharts(responses) {
    destroyQueryCharts();
    if (!Array.isArray(responses) || responses.length === 0 || typeof Chart === "undefined") return;

    const labels = responses.map((row) => `${row.agent_id}`);
    const latency = responses.map((row) => Number(row.latency_ms || 0));
    const tokens = responses.map((row) => Number(row.token_count || 0));
    const palette = ["#0f766e", "#2563eb", "#d97706", "#dc2626", "#0ea5e9", "#6d28d9"];

    if (latencyCanvas) {
      queryCharts.latency = new Chart(latencyCanvas, {
        type: "bar",
        data: {
          labels,
          datasets: [
            {
              label: "Latency (ms)",
              data: latency,
              backgroundColor: labels.map((_, idx) => palette[idx % palette.length]),
              borderRadius: 8,
            },
          ],
        },
        options: {
          responsive: true,
          plugins: { legend: { display: false } },
          scales: { y: { title: { display: true, text: "ms" } } },
        },
      });
    }

    if (tokenCanvas) {
      queryCharts.tokens = new Chart(tokenCanvas, {
        type: "bar",
        data: {
          labels,
          datasets: [
            {
              label: "Token Count",
              data: tokens,
              backgroundColor: labels.map((_, idx) => palette[(idx + 2) % palette.length]),
              borderRadius: 8,
            },
          ],
        },
        options: {
          responsive: true,
          plugins: { legend: { display: false } },
          scales: { y: { title: { display: true, text: "tokens" } } },
        },
      });
    }

    const answerCounts = {};
    responses.forEach((row) => {
      const key = (row.normalized_answer || row.answer || "(empty)").toString().trim() || "(empty)";
      answerCounts[key] = (answerCounts[key] || 0) + 1;
    });

    if (answerCanvas) {
      const answerLabels = Object.keys(answerCounts);
      queryCharts.answers = new Chart(answerCanvas, {
        type: "pie",
        data: {
          labels: answerLabels,
          datasets: [
            {
              data: answerLabels.map((key) => answerCounts[key]),
              backgroundColor: answerLabels.map((_, idx) => palette[idx % palette.length]),
            },
          ],
        },
        options: { responsive: true, plugins: { legend: { position: "bottom" } } },
      });
    }
  }

  async function loadAgents(endpoint) {
    if (!endpoint) return [];
    try {
      const response = await fetch(`${endpoint}/agents`, { method: "GET" });
      const body = await response.json().catch(() => ({}));
      if (!response.ok) {
        throw new Error(`Failed to load agents: HTTP ${response.status}`);
      }
      const agents = Array.isArray(body.agents) ? body.agents.filter((agent) => agent.enabled !== false) : [];
      state.agents = agents;
      renderAgentSelector(agents);
      return agents;
    } catch (error) {
      state.agents = [];
      renderAgentSelector([]);
      statusEl.textContent = "Connected, but failed to load /agents.";
      outputEl.textContent = String(error);
      return [];
    }
  }

  if (checkBtn) {
    checkBtn.addEventListener("click", async () => {
      const endpoint = resolveEndpoint();
      if (!endpoint) {
        statusEl.textContent = "Add your base URL first, then click Check Connection.";
        outputEl.textContent = "Example: https://your-public-endpoint.example.com";
        return;
      }

      checkBtn.disabled = true;
      statusEl.textContent = "Checking /health...";
      outputEl.textContent = "Waiting for health response...";

      try {
        const response = await fetch(`${endpoint}/health`, { method: "GET" });
        const body = await response.json().catch(() => ({}));
        if (!response.ok) {
          statusEl.textContent = `Health check failed (${response.status}).`;
          outputEl.textContent = JSON.stringify(body, null, 2);
          return;
        }
        const agents = await loadAgents(endpoint);
        statusEl.textContent = `Connection OK. Loaded ${agents.length} model(s). You can run queries now.`;
        outputEl.textContent = JSON.stringify(body, null, 2);
      } catch (error) {
        statusEl.textContent = "Health check error. Verify endpoint and CORS.";
        outputEl.textContent = String(error);
      } finally {
        checkBtn.disabled = false;
      }
    });
  }

  if (selectAllBtn) {
    selectAllBtn.addEventListener("click", () => setAllAgentSelection(true));
  }

  if (clearAgentsBtn) {
    clearAgentsBtn.addEventListener("click", () => setAllAgentSelection(false));
  }

  form.addEventListener("submit", async (event) => {
    event.preventDefault();

    const endpoint = resolveEndpoint();
    if (!endpoint) {
      statusEl.textContent = "Set your public orchestrator endpoint first.";
      outputEl.textContent = "Example: https://your-public-endpoint.example.com";
      return;
    }

    localStorage.setItem("distributed_ai_endpoint", endpoint);
    localStorage.setItem("distributed_ai_prompt", form.prompt.value);
    if (!state.agents.length) {
      await loadAgents(endpoint);
    }

    const selectedAgentIds = getSelectedAgentIds();
    if (selectedAgentIds.length === 0) {
      statusEl.textContent = "Select at least one model before running query.";
      outputEl.textContent = "Use Select All or check individual models in the model selector.";
      return;
    }

    const payload = {
      prompt: form.prompt.value,
      strategy: form.strategy.value,
      seed: Number(form.seed.value || 42),
      temperature: Number(form.temperature.value || 0),
      deterministic: Boolean(form.deterministic.checked),
      max_tokens: Number(form.maxTokens.value || 64),
      agent_ids: selectedAgentIds,
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

      const answer =
        body.answer ||
        body.aggregate?.answer ||
        body.aggregate_answer ||
        body.response ||
        "No answer field in response.";
      statusEl.textContent = `Success in ${elapsed} ms | Strategy: ${payload.strategy} | Models: ${selectedAgentIds.length} | Answer: ${String(answer).slice(0, 120)}`;
      outputEl.textContent = JSON.stringify(body, null, 2);
      renderQueryCharts(body.agent_responses || []);
      renderResultTable(body.agent_responses || []);
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
