(() => {
  "use strict";

  const LOCAL_API = "http://localhost:5000";
  const _isLocal = location.hostname === "localhost" || location.hostname === "127.0.0.1";
  const _isFile = location.protocol === "file:";
  const _meta = document.querySelector('meta[name="api-base"]');
  const API = (_isLocal || _isFile)
    ? LOCAL_API
    : (_meta?.content || window.location.origin);
  const POLL_MS = 1200;
  const TOKEN_KEY = "agentforge_token";
  const USER_KEY = "agentforge_user";

  const $ = (s) => document.querySelector(s);
  const $$ = (s) => document.querySelectorAll(s);

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

  const elBtnNavArtifacts = $("#btnNavArtifacts");
  const elBtnBackTerminal = $("#btnBackTerminal");
  const elPanelArtifacts = $("#panelArtifacts");
  const elBtnCopyArtifact = $("#btnCopyArtifact");

  let jobId = null;
  let pollTimer = null;
  let isRunning = false;
  let awaitingSpecConfirmation = false;
  let latestResult = null;
  let reportView = "summary";


  // ══════════════ THREE.JS PARTICLE BG ══════════════

  function initParticles() {
    const canvas = document.getElementById('bgCanvas');
    if (!canvas || typeof THREE === 'undefined') return;

    const renderer = new THREE.WebGLRenderer({ canvas, antialias: false, alpha: true });
    renderer.setPixelRatio(Math.min(window.devicePixelRatio, 1.5));
    renderer.setSize(window.innerWidth, window.innerHeight);
    renderer.setClearColor(0x000000, 0);

    const scene = new THREE.Scene();
    const camera = new THREE.PerspectiveCamera(60, window.innerWidth / window.innerHeight, 0.1, 1000);
    camera.position.z = 28;

    const N = 600;
    const positions = new Float32Array(N * 3);
    const colors = new Float32Array(N * 3);
    const sizes = new Float32Array(N);

    const col1 = new THREE.Color(0x00f078);
    const col2 = new THREE.Color(0x00d4ff);
    const col3 = new THREE.Color(0xffb020);

    for (let i = 0; i < N; i++) {
      positions[i * 3] = (Math.random() - 0.5) * 80;
      positions[i * 3 + 1] = (Math.random() - 0.5) * 60;
      positions[i * 3 + 2] = (Math.random() - 0.5) * 40;

      const t = Math.random();
      let c;
      if (t < 0.65) c = col1;
      else if (t < 0.85) c = col2;
      else c = col3;
      colors[i * 3] = c.r;
      colors[i * 3 + 1] = c.g;
      colors[i * 3 + 2] = c.b;
      sizes[i] = Math.random() * 2.5 + 0.5;
    }

    const geo = new THREE.BufferGeometry();
    geo.setAttribute('position', new THREE.BufferAttribute(positions, 3));
    geo.setAttribute('color', new THREE.BufferAttribute(colors, 3));
    geo.setAttribute('size', new THREE.BufferAttribute(sizes, 1));

    const mat = new THREE.PointsMaterial({
      size: 0.25,
      vertexColors: true,
      transparent: true,
      opacity: 0.55,
      sizeAttenuation: true,
    });

    const points = new THREE.Points(geo, mat);
    scene.add(points);

    // Line connections between nearby particles (sparse)
    const lineMat = new THREE.LineBasicMaterial({
      color: 0x00f078,
      transparent: true,
      opacity: 0.04,
    });
    const lineGeo = new THREE.BufferGeometry();
    const linePositions = [];
    const thresh = 8;
    for (let i = 0; i < Math.min(N, 200); i++) {
      for (let j = i + 1; j < Math.min(N, 200); j++) {
        const dx = positions[i * 3] - positions[j * 3];
        const dy = positions[i * 3 + 1] - positions[j * 3 + 1];
        const dz = positions[i * 3 + 2] - positions[j * 3 + 2];
        if (Math.sqrt(dx * dx + dy * dy + dz * dz) < thresh) {
          linePositions.push(positions[i * 3], positions[i * 3 + 1], positions[i * 3 + 2]);
          linePositions.push(positions[j * 3], positions[j * 3 + 1], positions[j * 3 + 2]);
        }
      }
    }
    lineGeo.setAttribute('position', new THREE.Float32BufferAttribute(linePositions, 3));
    const lines = new THREE.LineSegments(lineGeo, lineMat);
    scene.add(lines);

    let mouseX = 0, mouseY = 0;
    document.addEventListener('mousemove', (e) => {
      mouseX = (e.clientX / window.innerWidth - 0.5) * 0.4;
      mouseY = (e.clientY / window.innerHeight - 0.5) * 0.4;
    });

    let t = 0;
    function animate() {
      requestAnimationFrame(animate);
      t += 0.0006;
      points.rotation.y = t + mouseX;
      points.rotation.x = mouseY * 0.3;
      lines.rotation.y = t + mouseX;
      lines.rotation.x = mouseY * 0.3;
      renderer.render(scene, camera);
    }
    animate();

    window.addEventListener('resize', () => {
      camera.aspect = window.innerWidth / window.innerHeight;
      camera.updateProjectionMatrix();
      renderer.setSize(window.innerWidth, window.innerHeight);
    });
  }


  // ══════════════ GSAP ANIMATIONS ══════════════

  function animateAppEntrance() {
    if (typeof gsap === 'undefined') return;
    gsap.from('.sidebar', { x: -30, opacity: 0, duration: 0.6, ease: 'power3.out' });
    gsap.from('.topbar', { y: -20, opacity: 0, duration: 0.5, ease: 'power2.out', delay: 0.15 });
    gsap.from('.panel-chat', { x: -20, opacity: 0, duration: 0.55, ease: 'power2.out', delay: 0.25 });
    gsap.from('.panel-right', { x: 20, opacity: 0, duration: 0.55, ease: 'power2.out', delay: 0.35 });
  }

  function animateStepUpdate(el) {
    if (typeof gsap === 'undefined') return;
    gsap.fromTo(el, { scale: 0.97, opacity: 0.7 }, { scale: 1, opacity: 1, duration: 0.3, ease: 'back.out(2)' });
  }

  function animateScore(val) {
    if (typeof gsap === 'undefined') return;
    const fill = document.getElementById('scoreBarFill');
    if (!fill || isNaN(val)) return;
    gsap.to(fill, { width: val + '%', duration: 0.9, ease: 'power2.out' });
  }


  // ══════════════ CLOCK ══════════════

  function startClock() {
    const el = document.getElementById('topbarClock');
    if (!el) return;
    function tick() {
      const now = new Date();
      const hh = String(now.getHours()).padStart(2, '0');
      const mm = String(now.getMinutes()).padStart(2, '0');
      const ss = String(now.getSeconds()).padStart(2, '0');
      el.textContent = `${hh}:${mm}:${ss}`;
    }
    tick();
    setInterval(tick, 1000);
  }


  // ══════════════ AUTH ══════════════

  function getToken() { return localStorage.getItem(TOKEN_KEY); }
  function setToken(t) { localStorage.setItem(TOKEN_KEY, t); }
  function clearToken() { localStorage.removeItem(TOKEN_KEY); localStorage.removeItem(USER_KEY); }
  function getUser() { try { return JSON.parse(localStorage.getItem(USER_KEY)); } catch { return null; } }
  function setUser(u) { localStorage.setItem(USER_KEY, JSON.stringify(u)); }
  function authHeaders() {
    const t = getToken();
    return t ? { Authorization: `Bearer ${t}`, "Content-Type": "application/json" } : { "Content-Type": "application/json" };
  }

  function showAuth() {
    elAuthOverlay.classList.remove("hidden");
    elAppShell.classList.add("hidden");
    if (typeof gsap !== 'undefined') {
      gsap.from('.auth-card', { y: 30, opacity: 0, duration: 0.6, ease: 'power3.out' });
    }
  }

  function showApp(user) {
    elAuthOverlay.classList.add("hidden");
    elAppShell.classList.remove("hidden");
    if (user) {
      elUserAvatar.textContent = (user.username || "?")[0].toUpperCase();
      elUserName.textContent = (user.username || "USER_NODE").toUpperCase();
    }
    animateAppEntrance();
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
          elLoginError.textContent = "ERR: " + (data.error || "Login failed");
        }
      } catch {
        elLoginError.textContent = "ERR: Cannot connect to server";
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
          elSignupError.textContent = "ERR: " + (data.error || "Sign up failed");
        }
      } catch {
        elSignupError.textContent = "ERR: Cannot connect to server";
      }
    });
  }


  // ══════════════ UTILITIES ══════════════

  function toast(message, type = "info") {
    const node = document.createElement("div");
    node.className = `toast ${type}`;
    const prefix = type === 'success' ? '✓ ' : type === 'error' ? '✗ ' : '◆ ';
    node.textContent = prefix + message.toUpperCase();
    elToastHost.appendChild(node);
    setTimeout(() => {
      if (typeof gsap !== 'undefined') {
        gsap.to(node, { opacity: 0, x: 20, duration: 0.3, onComplete: () => node.remove() });
      } else {
        node.remove();
      }
    }, 4200);
  }

  function addMessage(role, text) {
    const wrapper = document.createElement("div");
    wrapper.style.marginTop = '12px';

    const msg = document.createElement("div");
    msg.className = `msg ${role} msg-enter`;
    msg.textContent = text;
    wrapper.appendChild(msg);
    elChat.appendChild(wrapper);
    elChat.scrollTop = elChat.scrollHeight;
  }

  function setRunning(running) {
    isRunning = running;
    elBtnRun.disabled = running;
    elBtnRun.textContent = running ? "⏳ EXEC..." : "▶ EXEC";
    elBtnTerminate.disabled = !running || !jobId;
    if (running && typeof gsap !== 'undefined') {
      gsap.to(elBtnRun, { opacity: 0.6, duration: 0.2 });
    } else if (typeof gsap !== 'undefined') {
      gsap.to(elBtnRun, { opacity: 1, duration: 0.2 });
    }
  }

  function setRoute(route) {
    if (!route) { elRouteBadge.innerHTML = ""; return; }
    const label = route === "conversational" ? "CONV_ROUTE" : "AGENT_BUILD";
    elRouteBadge.innerHTML = `<span class="badge">${label}</span>`;
  }

  function updateCounter() {
    const len = elPrompt.value.length;
    elCounter.textContent = `${len}/5000`;
    elCounter.style.color = len > 4500 ? 'var(--amber)' : 'var(--text3)';
  }

  function escapeHtml(str) {
    return String(str || "").replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
  }


  // ══════════════ SERVER STATUS & HISTORY ══════════════

  async function checkServer() {
    try {
      const r = await fetch(`${API}/api/history`, { cache: "no-store", headers: authHeaders() });
      if (!r.ok) throw new Error();
      elStatusValue.textContent = "ONLINE";
      elStatusDot.style.background = "var(--green)";
      elStatusDot.style.boxShadow = "0 0 8px var(--green)";
    } catch {
      elStatusValue.textContent = "OFFLINE";
      elStatusDot.style.background = "var(--red)";
      elStatusDot.style.boxShadow = "0 0 8px var(--red)";
    }
  }

  function renderHistory(items) {
    if (!items || items.length === 0) {
      elHistory.innerHTML = '<div class="history-item"><div class="history-text">// no_records_found</div></div>';
      return;
    }
    elHistory.innerHTML = items.map((it) => {
      const ts = new Date(it.timestamp || Date.now()).toLocaleString();
      const safe = (it.prompt || "").replace(/</g, "&lt;").replace(/>/g, "&gt;");
      return `<div class="history-item" data-prompt="${encodeURIComponent(it.prompt || "")}">
        <div class="history-ts">${ts}</div>
        <div class="history-text">${safe}</div>
      </div>`;
    }).join("");

    $$("#history .history-item").forEach((node) => {
      node.addEventListener("click", () => {
        const prompt = decodeURIComponent(node.dataset.prompt || "");
        if (prompt) {
          elPrompt.value = prompt;
          updateCounter();
          elPrompt.focus();
          if (typeof gsap !== 'undefined') {
            gsap.fromTo(elPrompt, { borderColor: 'var(--green)' }, { borderColor: 'var(--border2)', duration: 1 });
          }
        }
      });
    });
  }

  async function loadHistory() {
    try {
      const r = await fetch(`${API}/api/history`, { cache: "no-store", headers: authHeaders() });
      if (r.status === 401) { clearToken(); showAuth(); return; }
      renderHistory(await r.json());
    } catch { renderHistory([]); }
  }


  // ══════════════ PIPELINE RENDERING ══════════════

  function renderPipeline(steps, statusData) {
    if (!steps) { elPipeline.innerHTML = ""; return; }
    elPipeline.innerHTML = steps.map((s, i) => {
      const st = s.status || "pending";
      const labels = { error: "ERR", done: "DONE", running: "EXEC", skipped: "SKIP", waiting: "WAIT", pending: "PEND" };
      return `<div class="step ${st}" data-step="${i}">
        <div class="icon">${s.icon || "•"}</div>
        <div class="step-left">
          <div class="name">${s.name.toUpperCase()}</div>
          <div class="desc">${s.description}</div>
          ${s.error ? `<div class="desc" style="color:var(--red);margin-top:2px">ERR: ${escapeHtml(s.error).slice(0, 120)}</div>` : ""}
        </div>
        <div class="right">${labels[st] || st}</div>
        <div class="step-progress-bar"></div>
      </div>`;
    }).join("");

    document.querySelectorAll('.step').forEach((el, i) => {
      const delay = i * 0.06;
      if (typeof gsap !== 'undefined') {
        gsap.fromTo(el, { opacity: 0, x: -8 }, { opacity: 1, x: 0, duration: 0.3, delay, ease: 'power2.out' });
      }
    });

    if (!statusData) { elPipelineStatus.textContent = "IDLE"; return; }
    const statusLabels = { running: "EXEC", done: "DONE", error: "ERROR", awaiting_confirmation: "CONFIRM_REQ" };
    elPipelineStatus.textContent = statusLabels[statusData.status] || "IDLE";
  }

  function renderReport(data) {
    const verifier = data.verifier_result || {};
    const attempts = data.attempts || [];
    if (reportView === "verifier") { outReport.textContent = JSON.stringify(verifier, null, 2); return; }
    if (reportView === "attempts") { outReport.textContent = JSON.stringify(attempts, null, 2); return; }

    const lines = [
      `JOB_ID       : ${data.id || "—"}`,
      `ROUTE        : ${data.route || "—"}`,
      `STATUS       : ${data.status || "—"}`,
      ``,
      `SCORE        : ${verifier.correctness_score ?? "--"}`,
      `BAND         : ${verifier.correctness_band || "--"}`,
      `DECISION     : ${verifier.delivery_decision || "--"}`,
      `NOTES        : ${verifier.delivery_notes || "--"}`,
      `REGEN_ATTS   : ${verifier.regeneration_attempts ?? attempts.length - 1}`,
    ];
    outReport.textContent = lines.join("\n");
  }

  function setArtifacts(data) {
    latestResult = data;
    renderReport(data);
    const files = data.files || {};
    outAgent.textContent = files["agent.py"] || "// no_output";
    outMain.textContent = files["main.py"] || "// no_output";
    outReq.textContent = files["requirements.txt"] || "// no_output";
    outReadme.textContent = files["README.md"] || "// no_output";
    outSpec.value = JSON.stringify(data.agent_spec || {}, null, 2);
    const score = data.verifier_result?.correctness_score;
    elVerifiedScore.textContent = score ?? "--";
    if (score !== undefined && score !== null) animateScore(score);
  }

  function activateTab(tabId) {
    $$(".tab").forEach((t) => t.classList.remove("active"));
    $$(".pane").forEach((p) => p.classList.remove("active"));
    $(`.tab[data-tab="${tabId}"]`)?.classList.add("active");
    $(`.pane[data-pane="${tabId}"]`)?.classList.add("active");
  }


  // ══════════════ PIPELINE EXECUTION ══════════════

  async function start(prompt) {
    setRunning(true);
    setRoute(null);
    addMessage("user", prompt);
    addMessage("system", "INITIATING PIPELINE EXECUTION...");
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
        toast("Session expired — please re-authenticate", "error");
        clearToken(); showAuth(); setRunning(false); return;
      }
      if (r.status === 429) {
        setRunning(false);
        const wait = data.retry_after || 60;
        toast(`Rate limit: retry in ${wait}s`, "error");
        addMessage("assistant", `RATE_LIMIT: retry after ${wait}s`);
        return;
      }
      if (r.status === 503) {
        setRunning(false);
        toast("Server at capacity", "error");
        addMessage("assistant", "SRV_BUSY: retry in ~60s");
        return;
      }
      if (!r.ok) {
        setRunning(false);
        toast(data.error || "Request failed", "error");
        addMessage("assistant", `ERR: ${data.error || "Request failed"}`);
        return;
      }
      jobId = data.job_id;
      toast("Pipeline started", "info");
      beginPolling();
    } catch {
      setRunning(false);
      toast("Backend unreachable", "error");
      addMessage("assistant", "ERR: Cannot reach backend. Run: python server.py");
    }
  }

  function beginPolling() { stopPolling(); pollTimer = setInterval(poll, POLL_MS); poll(); }
  function stopPolling() { if (pollTimer) clearInterval(pollTimer); pollTimer = null; }

  async function poll() {
    if (!jobId) return;
    try {
      const r = await fetch(`${API}/api/status/${jobId}`, { cache: "no-store", headers: authHeaders() });
      if (r.status === 401) { stopPolling(); clearToken(); showAuth(); return; }
      const d = await r.json();
      renderPipeline(d.steps, d);
      setRoute(d.route);

      if (d.status === "done") {
        stopPolling(); setRunning(false); awaitingSpecConfirmation = false;
        toast("Pipeline complete", "success");
        await fetchResult(); await loadHistory();
        if (d.route !== "conversational" && elPanelArtifacts && elPanelArtifacts.classList.contains("hidden")) {
          elPanelArtifacts.classList.remove("hidden");
        }
      } else if (d.status === "terminated") {
        stopPolling(); setRunning(false); awaitingSpecConfirmation = false;
        toast("Run terminated", "info");
        addMessage("assistant", d.error || "RUN_TERMINATED: stopped by user");
        await fetchResult();
      } else if (d.status === "awaiting_confirmation") {
        stopPolling(); setRunning(false); awaitingSpecConfirmation = true;
        await fetchResult();
        activateTab("spec");
        if (elPanelArtifacts && elPanelArtifacts.classList.contains("hidden")) {
          elPanelArtifacts.classList.remove("hidden");
        }
        addMessage("assistant", "CONFIRM_REQ: Review spec JSON, edit if needed, then confirm.");
        toast("Awaiting JSON confirmation", "info");
      } else if (d.status === "error") {
        stopPolling(); setRunning(false); awaitingSpecConfirmation = false;
        toast("Pipeline error", "error");
        addMessage("assistant", d.error || "PIPELINE_ERR");
      }
    } catch { /* keep polling */ }
  }

  async function fetchResult() {
    if (!jobId) return;
    const r = await fetch(`${API}/api/result/${jobId}`, { cache: "no-store", headers: authHeaders() });
    if (r.status === 401) { clearToken(); showAuth(); return; }
    const data = await r.json();
    setArtifacts(data);
    if (data.route === "conversational") {
      addMessage("assistant", data.conversational_response || "");
      toast(data.next_step_hint || "Describe the agent to build.", "info");
      elPrompt.value = ""; updateCounter(); elPrompt.focus();
    } else {
      if (!awaitingSpecConfirmation) {
        addMessage("assistant", "AGENT_BUILD_COMPLETE: review artifacts →");
      }
    }
  }

  async function confirmSpecAndGenerate() {
    if (!jobId || !awaitingSpecConfirmation) { toast("No job awaiting confirmation", "error"); return; }
    let spec;
    try { spec = JSON.parse(outSpec.value || "{}"); } catch { toast("Spec JSON parse error", "error"); return; }
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
      toast("Spec confirmed — generating", "info");
      addMessage("system", "SPEC_CONFIRMED: generating code...");
      beginPolling();
    } catch {
      setRunning(false);
      toast("Confirmation request failed", "error");
    }
  }

  async function terminateRun() {
    if (!jobId || !isRunning) { toast("No active run to terminate", "error"); return; }
    try {
      const r = await fetch(`${API}/api/terminate/${jobId}`, { method: "POST", headers: authHeaders() });
      const data = await r.json();
      if (!r.ok) { toast(data.error || "Terminate failed", "error"); return; }
      toast("Termination requested", "info");
      addMessage("system", "TERMINATE_SIG sent — stopping...");
    } catch { toast("Terminate request failed", "error"); }
  }


  // ══════════════ CLEAR & INIT ══════════════

  function clearUI() {
    elChat.innerHTML = "";
    renderPipeline([
      { icon: "🔍", name: "Perspective Agent", description: "Classify input route", status: "pending" },
      { icon: "📋", name: "Input Extractor", description: "Extract agent spec", status: "pending" },
      { icon: "🛡️", name: "Security Scanner", description: "Scan for secrets & dangerous calls", status: "pending" },
      { icon: "⚙️", name: "Code Generator", description: "Generate project files", status: "pending" },
      { icon: "✅", name: "Verifier Agent", description: "Score and delivery decision", status: "pending" },
    ], null);
    awaitingSpecConfirmation = false;
    jobId = null;
    setArtifacts({ files: {}, agent_spec: {}, verifier_result: {}, attempts: [] });
    elVerifiedScore.textContent = "--";
    setRoute(null);
    elPipelineStatus.textContent = "IDLE";
    toast("Buffer cleared", "info");
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
    startClock();
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
      if (prompt.length < 3) { toast("Input too short", "error"); return; }
      start(prompt);
    });
    elBtnClear.addEventListener("click", clearUI);
    elBtnConfirmSpec.addEventListener("click", confirmSpecAndGenerate);
    elBtnTerminate.addEventListener("click", terminateRun);
    elBtnLogout.addEventListener("click", async () => {
      try { await fetch(`${API}/api/auth/logout`, { method: "POST", headers: authHeaders() }); } catch { }
      clearToken(); showAuth(); toast("Session terminated", "info");
    });

    if (elBtnNavArtifacts && elPanelArtifacts) {
      elBtnNavArtifacts.addEventListener("click", () => {
        elPanelArtifacts.classList.remove("hidden");
      });
    }

    if (elBtnBackTerminal && elPanelArtifacts) {
      elBtnBackTerminal.addEventListener("click", () => {
        elPanelArtifacts.classList.add("hidden");
      });
    }

    if (elBtnCopyArtifact) {
      elBtnCopyArtifact.addEventListener("click", async () => {
        const activePane = document.querySelector(".pane.active");
        if (!activePane) return;
        
        let textToCopy = "";
        const pre = activePane.querySelector("pre");
        const textarea = activePane.querySelector("textarea");
        
        if (pre) {
          textToCopy = pre.textContent;
        } else if (textarea) {
          textToCopy = textarea.value;
        }
        
        if (textToCopy) {
          try {
            await navigator.clipboard.writeText(textToCopy);
            toast("Artifact copied to clipboard", "success");
            const originalText = elBtnCopyArtifact.innerHTML;
            elBtnCopyArtifact.innerHTML = "✓ COPIED";
            setTimeout(() => {
              elBtnCopyArtifact.innerHTML = originalText;
            }, 2000);
          } catch (err) {
            toast("Failed to copy text", "error");
          }
        } else {
          toast("Nothing to copy", "info");
        }
      });
    }

    checkServer();
    loadHistory();
    clearUI();
    elBtnTerminate.disabled = true;
    addMessage("assistant", "SYS_READY: describe your agent requirements or submit a query.");
  }


  // ══════════════ BOOT ══════════════

  function boot() {
    initParticles();
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