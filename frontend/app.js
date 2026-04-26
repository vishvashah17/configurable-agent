(() => {
  "use strict";

  const API = window.location.origin;
  const POLL_MS = 1200;
  const TOKEN_KEY = "agentforge_token";
  const USER_KEY = "agentforge_user";

  const $ = (s) => document.querySelector(s);
  const $$ = (s) => document.querySelectorAll(s);

  // ═══════════════════════════════════════════
  //  DOM REFS
  // ═══════════════════════════════════════════

  const elAuthOverlay = $("#authOverlay");
  const elAppShell = $("#appShell");
  const elLoginForm = $("#loginForm");
  const elSignupForm = $("#signupForm");
  const elLoginError = $("#loginError");
  const elSignupError = $("#signupError");

  const elHistory = $("#history");
  const elStatus = $("#serverStatus");
  const elStatusValue = $("#serverStatus .value");
  const elStatusDot = $("#serverStatus .dot");
  const elChat = $("#chat");
  const elPrompt = $("#prompt");
  const elCounter = $("#counter");
  const elBtnRun = $("#btnRun");
  const elBtnTerminate = $("#btnTerminate");
  const elBtnClear = $("#btnClear");
  const elBtnLogout = $("#btnLogout");
  const elPipeline = $("#pipeline");
  const elPipelineStatus = $("#pipelineStatus");
  const elRouteBadge = $("#routeBadge");
  const elToastHost = $("#toastHost");
  const elVerifiedScore = $("#verifiedScore");
  const elBtnConfirmSpec = $("#btnConfirmSpec");
  const elUserAvatar = $("#userAvatar");
  const elUserName = $("#userName");

  const outReport = $("#outReport");
  const outAgent = $("#outAgent");
  const outMain = $("#outMain");
  const outReq = $("#outReq");
  const outReadme = $("#outReadme");
  const outSpec = $("#outSpec");

  let jobId = null;
  let pollTimer = null;
  let isRunning = false;
  let awaitingSpecConfirmation = false;
  let latestResult = null;
  let reportView = "summary";


  // ═══════════════════════════════════════════
  //  AUTH
  // ═══════════════════════════════════════════

  function getToken() { return localStorage.getItem(TOKEN_KEY); }
  function setToken(t) { localStorage.setItem(TOKEN_KEY, t); }
  function clearToken() { localStorage.removeItem(TOKEN_KEY); localStorage.removeItem(USER_KEY); }

  function getUser() {
    try { return JSON.parse(localStorage.getItem(USER_KEY)); } catch { return null; }
  }
  function setUser(u) { localStorage.setItem(USER_KEY, JSON.stringify(u)); }

  function authHeaders() {
    const t = getToken();
    return t ? { Authorization: `Bearer ${t}`, "Content-Type": "application/json" } : { "Content-Type": "application/json" };
  }

  function showAuth() {
    elAuthOverlay.classList.remove("hidden");
    elAppShell.classList.add("hidden");
  }

  function showApp(user) {
    elAuthOverlay.classList.add("hidden");
    elAppShell.classList.remove("hidden");
    if (user) {
      elUserAvatar.textContent = (user.username || "?")[0].toUpperCase();
      elUserName.textContent = user.username || "User";
    }
  }

  async function tryAutoLogin() {
    const token = getToken();
    if (!token) { showAuth(); return; }
    try {
      const r = await fetch(`${API}/api/auth/me`, { headers: { Authorization: `Bearer ${token}` } });
      if (r.ok) {
        const data = await r.json();
        setUser(data.user);
        showApp(data.user);
        initApp();
      } else {
        clearToken();
        showAuth();
      }
    } catch {
      clearToken();
      showAuth();
    }
  }

  function initAuthTabs() {
    $$(".auth-tab").forEach((tab) => {
      tab.addEventListener("click", () => {
        $$(".auth-tab").forEach((t) => t.classList.remove("active"));
        tab.classList.add("active");
        const target = tab.dataset.authTab;
        $$(".auth-form").forEach((f) => f.classList.remove("active"));
        $(`.auth-form[data-auth-form="${target}"]`)?.classList.add("active");
        elLoginError.textContent = "";
        elSignupError.textContent = "";
      });
    });
  }

  function initAuthForms() {
    elLoginForm.addEventListener("submit", async (e) => {
      e.preventDefault();
      elLoginError.textContent = "";
      const email = $("#loginEmail").value.trim();
      const password = $("#loginPassword").value;
      try {
        const r = await fetch(`${API}/api/auth/login`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ email, password }),
        });
        const data = await r.json();
        if (data.success) {
          setToken(data.token);
          setUser(data.user);
          showApp(data.user);
          initApp();
        } else {
          elLoginError.textContent = data.error || "Login failed";
        }
      } catch {
        elLoginError.textContent = "Cannot connect to server";
      }
    });

    elSignupForm.addEventListener("submit", async (e) => {
      e.preventDefault();
      elSignupError.textContent = "";
      const username = $("#signupUsername").value.trim();
      const email = $("#signupEmail").value.trim();
      const password = $("#signupPassword").value;
      try {
        const r = await fetch(`${API}/api/auth/signup`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ username, email, password }),
        });
        const data = await r.json();
        if (data.success) {
          setToken(data.token);
          setUser(data.user);
          showApp(data.user);
          initApp();
        } else {
          elSignupError.textContent = data.error || "Sign up failed";
        }
      } catch {
        elSignupError.textContent = "Cannot connect to server";
      }
    });
  }


  // ═══════════════════════════════════════════
  //  UTILITIES
  // ═══════════════════════════════════════════

  function toast(message, type = "info") {
    const node = document.createElement("div");
    node.className = `toast ${type}`;
    node.textContent = message;
    elToastHost.appendChild(node);
    setTimeout(() => node.remove(), 4500);
  }

  function addMessage(role, text) {
    const msg = document.createElement("div");
    msg.className = `msg ${role}`;
    msg.textContent = text;
    elChat.appendChild(msg);
    elChat.scrollTop = elChat.scrollHeight;
  }

  function setRunning(running) {
    isRunning = running;
    elBtnRun.disabled = running;
    elBtnRun.textContent = running ? "Running…" : "Run";
    elBtnTerminate.disabled = !running || !jobId;
  }

  function setRoute(route) {
    if (!route) { elRouteBadge.innerHTML = ""; return; }
    const label = route === "conversational" ? "Conversational" : "Agent Building";
    elRouteBadge.innerHTML = `<span class="badge">${label}</span>`;
  }

  function updateCounter() {
    elCounter.textContent = `${elPrompt.value.length} / 5000`;
  }

  function escapeHtml(str) {
    return String(str || "").replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
  }


  // ═══════════════════════════════════════════
  //  SERVER STATUS & HISTORY
  // ═══════════════════════════════════════════

  async function checkServer() {
    try {
      const r = await fetch(`${API}/api/history`, { cache: "no-store", headers: authHeaders() });
      if (!r.ok) throw new Error();
      elStatusValue.textContent = "Online";
      elStatusDot.style.background = "var(--good)";
    } catch {
      elStatusValue.textContent = "Offline";
      elStatusDot.style.background = "var(--bad)";
    }
  }

  function renderHistory(items) {
    if (!items || items.length === 0) {
      elHistory.innerHTML = '<div class="history-item"><div class="history-text">No prompts yet.</div></div>';
      return;
    }
    elHistory.innerHTML = items
      .map((it) => {
        const ts = new Date(it.timestamp || Date.now()).toLocaleString();
        const text = (it.prompt || "").slice(0, 200);
        const safe = text.replace(/</g, "&lt;").replace(/>/g, "&gt;");
        return `
          <div class="history-item" data-prompt="${encodeURIComponent(it.prompt || "")}">
            <div class="history-ts">${ts}</div>
            <div class="history-text">${safe}</div>
          </div>
        `;
      })
      .join("");

    $$("#history .history-item").forEach((node) => {
      node.addEventListener("click", () => {
        const prompt = decodeURIComponent(node.dataset.prompt || "");
        if (prompt) {
          elPrompt.value = prompt;
          updateCounter();
          elPrompt.focus();
        }
      });
    });
  }

  async function loadHistory() {
    try {
      const r = await fetch(`${API}/api/history`, { cache: "no-store", headers: authHeaders() });
      if (r.status === 401) {
        clearToken();
        showAuth();
        return;
      }
      renderHistory(await r.json());
    } catch {
      renderHistory([]);
    }
  }


  // ═══════════════════════════════════════════
  //  PIPELINE RENDERING
  // ═══════════════════════════════════════════

  function renderPipeline(steps, statusData) {
    if (!steps) { elPipeline.innerHTML = ""; return; }
    elPipeline.innerHTML = steps
      .map((s) => {
        const st = s.status || "pending";
        const labels = { error: "Error", done: "Done", running: "Running", skipped: "Skipped", waiting: "Waiting", pending: "Pending" };
        const right = labels[st] || st;
        return `
          <div class="step ${st}">
            <div class="icon">${s.icon || "•"}</div>
            <div class="left">
              <div class="name">${s.name}</div>
              <div class="desc">${s.description}</div>
              ${s.error ? `<div class="desc" style="color:var(--bad)">${escapeHtml(s.error).slice(0, 180)}</div>` : ""}
            </div>
            <div class="right">${right}</div>
          </div>
        `;
      })
      .join("");

    if (!statusData) { elPipelineStatus.textContent = "Idle"; return; }
    const statusLabels = { running: "Running", done: "Complete", error: "Error", awaiting_confirmation: "Awaiting Confirmation" };
    elPipelineStatus.textContent = statusLabels[statusData.status] || "Idle";
  }

  function renderReport(data) {
    const verifier = data.verifier_result || {};
    const attempts = data.attempts || [];

    if (reportView === "verifier") { outReport.textContent = JSON.stringify(verifier, null, 2); return; }
    if (reportView === "attempts") { outReport.textContent = JSON.stringify(attempts, null, 2); return; }

    const lines = [];
    lines.push(`Job: ${data.id || "-"}`);
    lines.push(`Route: ${data.route || "-"}`);
    lines.push(`Status: ${data.status || "-"}`);
    lines.push(`Verified Score: ${verifier.correctness_score ?? "--"}`);
    lines.push(`Band: ${verifier.correctness_band || "--"}`);
    lines.push(`Decision: ${verifier.delivery_decision || "--"}`);
    lines.push(`Notes: ${verifier.delivery_notes || "--"}`);
    lines.push(`Regeneration Attempts: ${verifier.regeneration_attempts ?? attempts.length - 1}`);
    outReport.textContent = lines.join("\n");
  }

  function setArtifacts(data) {
    latestResult = data;
    renderReport(data);
    const files = data.files || {};
    outAgent.textContent = files["agent.py"] || "";
    outMain.textContent = files["main.py"] || "";
    outReq.textContent = files["requirements.txt"] || "";
    outReadme.textContent = files["README.md"] || "";
    outSpec.value = JSON.stringify(data.agent_spec || {}, null, 2);
    const score = data.verifier_result?.correctness_score;
    elVerifiedScore.textContent = score ?? "--";
  }

  function activateTab(tabId) {
    $$(".tab").forEach((t) => t.classList.remove("active"));
    $$(".pane").forEach((p) => p.classList.remove("active"));
    $(`.tab[data-tab="${tabId}"]`)?.classList.add("active");
    $(`.pane[data-pane="${tabId}"]`)?.classList.add("active");
  }


  // ═══════════════════════════════════════════
  //  PIPELINE EXECUTION
  // ═══════════════════════════════════════════

  async function start(prompt) {
    setRunning(true);
    setRoute(null);
    addMessage("user", prompt);
    addMessage("system", "Starting pipeline…");
    awaitingSpecConfirmation = false;
    setArtifacts({ files: {}, agent_spec: {}, verifier_result: {}, attempts: [] });
    elVerifiedScore.textContent = "--";
    activateTab("report");

    try {
      const r = await fetch(`${API}/api/generate`, {
        method: "POST",
        headers: authHeaders(),
        body: JSON.stringify({ prompt }),
      });
      const data = await r.json();
      if (r.status === 401) {
        toast("Session expired. Please login again.", "error");
        clearToken();
        showAuth();
        setRunning(false);
        return;
      }
      if (r.status === 429) {
        setRunning(false);
        const wait = data.retry_after || 60;
        toast(`Rate limit reached. Try again in ${wait}s.`, "error");
        addMessage("assistant", `⏳ Rate limit: please wait ${wait} seconds before trying again.`);
        return;
      }
      if (r.status === 503) {
        setRunning(false);
        toast("Server busy. Try again shortly.", "error");
        addMessage("assistant", "Server is at capacity. Please try again in a minute.");
        return;
      }
      if (!r.ok) {
        setRunning(false);
        toast(data.error || "Request failed", "error");
        addMessage("assistant", `Error: ${data.error || "Request failed"}`);
        return;
      }
      jobId = data.job_id;
      toast("Pipeline started", "info");
      beginPolling();
    } catch (e) {
      setRunning(false);
      toast("Cannot reach backend. Start: python server.py", "error");
      addMessage("assistant", "Cannot reach backend. Start: python server.py");
    }
  }

  function beginPolling() {
    stopPolling();
    pollTimer = setInterval(poll, POLL_MS);
    poll();
  }

  function stopPolling() {
    if (pollTimer) clearInterval(pollTimer);
    pollTimer = null;
  }

  async function poll() {
    if (!jobId) return;
    try {
      const r = await fetch(`${API}/api/status/${jobId}`, { cache: "no-store", headers: authHeaders() });
      if (r.status === 401) {
        stopPolling();
        clearToken();
        showAuth();
        toast("Session expired. Please login again.", "error");
        return;
      }
      const d = await r.json();
      renderPipeline(d.steps, d);
      setRoute(d.route);

      if (d.status === "done") {
        stopPolling();
        setRunning(false);
        awaitingSpecConfirmation = false;
        toast("Done", "success");
        await fetchResult();
        await loadHistory();
      } else if (d.status === "terminated") {
        stopPolling();
        setRunning(false);
        awaitingSpecConfirmation = false;
        toast("Run terminated", "info");
        addMessage("assistant", d.error || "Run terminated by user.");
        await fetchResult();
      } else if (d.status === "awaiting_confirmation") {
        stopPolling();
        setRunning(false);
        awaitingSpecConfirmation = true;
        await fetchResult();
        activateTab("spec");
        addMessage("assistant", "Review the extracted JSON, edit if needed, then click Confirm JSON & Generate.");
        toast("Waiting for JSON confirmation", "info");
      } else if (d.status === "error") {
        stopPolling();
        setRunning(false);
        awaitingSpecConfirmation = false;
        toast("Pipeline error", "error");
        addMessage("assistant", d.error || "Pipeline error");
      }
    } catch { /* keep polling */ }
  }

  async function fetchResult() {
    if (!jobId) return;
    const r = await fetch(`${API}/api/result/${jobId}`, { cache: "no-store", headers: authHeaders() });
    if (r.status === 401) {
      clearToken();
      showAuth();
      toast("Session expired. Please login again.", "error");
      return;
    }
    const data = await r.json();
    setArtifacts(data);

    if (data.route === "conversational") {
      addMessage("assistant", data.conversational_response || "");
      toast(data.next_step_hint || 'Describe the agent you want to build.', "info");
      elPrompt.value = "";
      updateCounter();
      elPrompt.focus();
    } else {
      if (!awaitingSpecConfirmation) {
        addMessage("assistant", "Agent build complete. Review artifacts on the right.");
      }
    }
  }

  async function confirmSpecAndGenerate() {
    if (!jobId || !awaitingSpecConfirmation) { toast("No job waiting for confirmation", "error"); return; }
    let spec;
    try { spec = JSON.parse(outSpec.value || "{}"); } catch { toast("Spec JSON is invalid", "error"); return; }

    setRunning(true);
    try {
      const r = await fetch(`${API}/api/confirm/${jobId}`, {
        method: "POST",
        headers: authHeaders(),
        body: JSON.stringify({ agent_spec: spec }),
      });
      const data = await r.json();
      if (!r.ok) { setRunning(false); toast(data.error || "Confirmation failed", "error"); return; }
      awaitingSpecConfirmation = false;
      toast("JSON confirmed. Continuing generation.", "info");
      addMessage("system", "Spec confirmed. Generating code…");
      beginPolling();
    } catch {
      setRunning(false);
      toast("Could not confirm JSON", "error");
    }
  }

  async function terminateRun() {
    if (!jobId || !isRunning) {
      toast("No active run to terminate", "error");
      return;
    }
    try {
      const r = await fetch(`${API}/api/terminate/${jobId}`, {
        method: "POST",
        headers: authHeaders(),
      });
      const data = await r.json();
      if (!r.ok) {
        toast(data.error || "Terminate failed", "error");
        return;
      }
      toast("Termination requested", "info");
      addMessage("system", "Termination requested. Stopping current run...");
    } catch {
      toast("Could not request termination", "error");
    }
  }


  // ═══════════════════════════════════════════
  //  CLEAR & INIT
  // ═══════════════════════════════════════════

  function clearUI() {
    elChat.innerHTML = "";
    renderPipeline(
      [
        { icon: "🔍", name: "Perspective Agent", description: "Classify input", status: "pending" },
        { icon: "📋", name: "Input Extractor", description: "Extract spec", status: "pending" },
        { icon: "🛡️", name: "Security Scanner", description: "Scan for secrets & dangerous calls", status: "pending" },
        { icon: "⚙️", name: "Code Generator", description: "Generate project files", status: "pending" },
        { icon: "✅", name: "Verifier Agent", description: "Score and decision", status: "pending" },
      ],
      null
    );
    awaitingSpecConfirmation = false;
    jobId = null;
    setArtifacts({ files: {}, agent_spec: {}, verifier_result: {}, attempts: [] });
    elVerifiedScore.textContent = "--";
    setRoute(null);
    elPipelineStatus.textContent = "Idle";
    toast("Cleared", "info");
  }

  function initTabs() {
    $$(".tab").forEach((t) => t.addEventListener("click", () => activateTab(t.dataset.tab)));
  }

  function initReportSwitcher() {
    $$(".report-btn").forEach((btn) => {
      btn.addEventListener("click", () => {
        reportView = btn.dataset.reportView || "summary";
        $$(".report-btn").forEach((b) => b.classList.remove("active"));
        btn.classList.add("active");
        if (latestResult) renderReport(latestResult);
      });
    });
  }

  function initApp() {
    initTabs();
    initReportSwitcher();
    updateCounter();
    elPrompt.addEventListener("input", updateCounter);
    elPrompt.addEventListener("keydown", (e) => {
      if (e.key === "Enter" && (e.ctrlKey || e.metaKey)) { e.preventDefault(); elBtnRun.click(); }
    });

    elBtnRun.addEventListener("click", () => {
      if (isRunning) return;
      const prompt = elPrompt.value.trim();
      if (!prompt) return;
      if (prompt.length < 3) { toast("Prompt too short", "error"); return; }
      start(prompt);
    });

    elBtnClear.addEventListener("click", clearUI);
    elBtnConfirmSpec.addEventListener("click", confirmSpecAndGenerate);
    elBtnTerminate.addEventListener("click", terminateRun);

    elBtnLogout.addEventListener("click", async () => {
      try {
        await fetch(`${API}/api/auth/logout`, {
          method: "POST",
          headers: authHeaders(),
        });
      } catch { /* ok */ }
      clearToken();
      showAuth();
      toast("Logged out", "info");
    });

    checkServer();
    loadHistory();
    clearUI();
    elBtnTerminate.disabled = true;
    addMessage("assistant", "Ready. Ask a question or describe the agent you want to build.");
  }


  // ═══════════════════════════════════════════
  //  BOOT
  // ═══════════════════════════════════════════

  function boot() {
    initAuthTabs();
    initAuthForms();
    tryAutoLogin();
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", boot);
  } else {
    boot();
  }
})();
