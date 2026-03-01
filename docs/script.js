(function () {
  initMetrics();
  initArchitecture();
  initPaperAccess();
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

function initPaperAccess() {
  const heroPaperGateBtn = document.getElementById("heroPaperGateBtn");
  const unlockPaperBtn = document.getElementById("unlockPaperBtn");
  const lockPaperBtn = document.getElementById("lockPaperBtn");
  const passwordInput = document.getElementById("paperAccessPassword");
  const statusEl = document.getElementById("paperAccessStatus");
  const protectedPanel = document.getElementById("paperProtectedPanel");
  const paperFrame = document.getElementById("paperFrame");
  const ruleGithub = document.getElementById("paperRuleGithub");
  const ruleYoutube = document.getElementById("paperRuleYoutube");
  const rulePermission = document.getElementById("paperRulePermission");
  const paperPdfLink = document.getElementById("paperPdfLink");
  const paperDocxLink = document.getElementById("paperDocxLink");
  const paperTxtLink = document.getElementById("paperTxtLink");
  const paperTexLink = document.getElementById("paperTexLink");

  if (!unlockPaperBtn || !lockPaperBtn || !passwordInput || !statusEl || !protectedPanel || !paperFrame) return;

  const storageKey = "distributed_ai_paper_access";
  const expectedHash = "5b484d8b2799daf74779ce686501847d4a08b5e917c1e8395e1da7f7e73bce0d";
  const paperFiles = {
    pdf: "assets/paper/IEEE_Distributed_AI_Ensemble.pdf",
    docx: "assets/paper/IEEE_Distributed_AI_Ensemble.docx",
    txt: "assets/paper/IEEE_Distributed_AI_Ensemble.txt",
    tex: "assets/paper/IEEE_Distributed_AI_Ensemble.tex",
  };

  function setHeroState(unlocked) {
    if (!heroPaperGateBtn) return;
    heroPaperGateBtn.textContent = unlocked ? "Open Full Paper" : "Request Full Paper";
    heroPaperGateBtn.setAttribute("href", "#paper");
  }

  function setFileLinks(unlocked) {
    const mappings = [
      [paperPdfLink, paperFiles.pdf],
      [paperDocxLink, paperFiles.docx],
      [paperTxtLink, paperFiles.txt],
      [paperTexLink, paperFiles.tex],
    ];

    mappings.forEach(([el, href]) => {
      if (!el) return;
      if (unlocked) {
        el.setAttribute("href", href);
        el.setAttribute("target", "_blank");
        el.setAttribute("rel", "noreferrer");
      } else {
        el.setAttribute("href", "#paper");
        el.removeAttribute("target");
        el.removeAttribute("rel");
      }
    });
  }

  function applyAccessState(unlocked) {
    protectedPanel.hidden = !unlocked;
    setHeroState(unlocked);
    setFileLinks(unlocked);

    if (unlocked) {
      paperFrame.setAttribute("src", `${paperFiles.pdf}#view=FitH`);
      statusEl.textContent = "Access granted for this browser session. You can now read and download the full paper.";
    } else {
      paperFrame.removeAttribute("src");
      statusEl.textContent = "Complete all three steps, then enter the approved password to read or download the full manuscript.";
    }
  }

  function allRequirementsChecked() {
    return [ruleGithub, ruleYoutube, rulePermission].every((el) => el && el.checked);
  }

  async function sha256(text) {
    if (!window.crypto || !window.crypto.subtle) {
      throw new Error("This browser does not support secure password verification.");
    }

    const buffer = await window.crypto.subtle.digest("SHA-256", new TextEncoder().encode(text));
    return Array.from(new Uint8Array(buffer))
      .map((byte) => byte.toString(16).padStart(2, "0"))
      .join("");
  }

  if (sessionStorage.getItem(storageKey) === "granted") {
    applyAccessState(true);
  } else {
    applyAccessState(false);
  }

  if (heroPaperGateBtn) {
    heroPaperGateBtn.addEventListener("click", () => {
      if (sessionStorage.getItem(storageKey) === "granted") {
        statusEl.textContent = "Access granted for this browser session. Scroll down to read the full paper.";
      } else {
        statusEl.textContent = "Follow GitHub, subscribe on YouTube, send your permission request, then enter the approved password.";
      }
    });
  }

  unlockPaperBtn.addEventListener("click", async () => {
    if (!allRequirementsChecked()) {
      statusEl.textContent = "Please complete and confirm all three required steps before unlocking the paper.";
      return;
    }

    const attempt = passwordInput.value;
    if (!attempt) {
      statusEl.textContent = "Enter the approved paper access password.";
      return;
    }

    unlockPaperBtn.disabled = true;
    statusEl.textContent = "Verifying access password...";

    try {
      const digest = await sha256(attempt);
      if (digest !== expectedHash) {
        statusEl.textContent = "Access denied. The password is incorrect.";
        passwordInput.value = "";
        applyAccessState(false);
        sessionStorage.removeItem(storageKey);
        return;
      }

      sessionStorage.setItem(storageKey, "granted");
      applyAccessState(true);
    } catch (error) {
      statusEl.textContent = error instanceof Error ? error.message : "Unable to verify access password.";
    } finally {
      unlockPaperBtn.disabled = false;
    }
  });

  lockPaperBtn.addEventListener("click", () => {
    sessionStorage.removeItem(storageKey);
    passwordInput.value = "";
    applyAccessState(false);
  });

  passwordInput.addEventListener("keydown", (event) => {
    if (event.key === "Enter") {
      event.preventDefault();
      unlockPaperBtn.click();
    }
  });
}

function initPlayground() {
  const form = document.getElementById("playgroundForm");
  const statusEl = document.getElementById("playgroundStatus");
  const outputEl = document.getElementById("playgroundOutput");
  const runBtn = document.getElementById("runQueryBtn");
  const checkBtn = document.getElementById("checkEndpointBtn");
  const useRecommendedEndpointBtn = document.getElementById("useRecommendedEndpointBtn");
  const recommendedEndpointEl = document.getElementById("recommendedEndpoint");
  const selectAllBtn = document.getElementById("selectAllAgentsBtn");
  const clearAgentsBtn = document.getElementById("clearAgentsBtn");
  const agentSelector = document.getElementById("agentSelector");
  const tableBody = document.getElementById("queryAgentTableBody");
  const latencyCanvas = document.getElementById("queryLatencyChart");
  const tokenCanvas = document.getElementById("queryTokenChart");
  const answerCanvas = document.getElementById("queryAnswerChart");
  const insightAnswer = document.getElementById("insightAnswer");
  const insightAgreement = document.getElementById("insightAgreement");
  const insightLatency = document.getElementById("insightLatency");
  const insightModels = document.getElementById("insightModels");
  const agreementMeterFill = document.getElementById("agreementMeterFill");
  const agreementLabel = document.getElementById("agreementLabel");
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

  function resetQueryInsights() {
    if (insightAnswer) insightAnswer.textContent = "-";
    if (insightAgreement) insightAgreement.textContent = "-";
    if (insightLatency) insightLatency.textContent = "-";
    if (insightModels) insightModels.textContent = "-";
    if (agreementMeterFill) agreementMeterFill.style.width = "0%";
    if (agreementLabel) agreementLabel.textContent = "Agreement distribution will appear after query.";
  }

  function updateQueryInsights(body, selectedModelCount, answerText, elapsedMs) {
    const agreement = Number(body?.aggregate?.agreement_rate ?? 0);
    const totalLatency = Number(body?.total_latency_ms ?? elapsedMs ?? 0);
    const modelCount = Array.isArray(body?.selected_agent_ids)
      ? body.selected_agent_ids.length
      : selectedModelCount;
    const agreementPct = Number.isFinite(agreement) ? Math.max(0, Math.min(100, agreement * 100)) : 0;

    if (insightAnswer) insightAnswer.textContent = String(answerText || "-").slice(0, 28);
    if (insightAgreement) insightAgreement.textContent = `${agreementPct.toFixed(0)}%`;
    if (insightLatency) insightLatency.textContent = `${totalLatency.toFixed(1)} ms`;
    if (insightModels) insightModels.textContent = String(modelCount || 0);
    if (agreementMeterFill) agreementMeterFill.style.width = `${agreementPct.toFixed(1)}%`;
    if (agreementLabel) {
      agreementLabel.textContent = `Agreement rate is ${agreementPct.toFixed(1)}% across selected models.`;
    }
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

  if (useRecommendedEndpointBtn && recommendedEndpointEl) {
    useRecommendedEndpointBtn.addEventListener("click", () => {
      const value = recommendedEndpointEl.textContent.trim();
      if (!value) return;
      form.apiEndpoint.value = value;
      localStorage.setItem("distributed_ai_endpoint", value);
      statusEl.textContent = "Recommended endpoint applied. Click Check Connection.";
    });
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
    resetQueryInsights();
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
      updateQueryInsights(body, selectedAgentIds.length, answer, elapsed);
    } catch (error) {
      statusEl.textContent = "Network/CORS error. Ensure endpoint is reachable and CORS allows this origin.";
      outputEl.textContent = String(error);
      resetQueryInsights();
    } finally {
      runBtn.disabled = false;
    }
  });
}

function sleep(ms) {
  return new Promise((resolve) => setTimeout(resolve, ms));
}
