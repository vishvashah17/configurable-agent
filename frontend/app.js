/* ═══════════════════════════════════════════════════════════════
   AgentForge — Frontend Application Logic
   ═══════════════════════════════════════════════════════════════ */

(() => {
    'use strict';

    // ─── Constants ─────────────────────────────────────────────
    const API_BASE = window.location.origin;
    const POLL_INTERVAL = 1500; // ms

    // ─── DOM Elements ──────────────────────────────────────────
    const $ = (sel) => document.querySelector(sel);
    const $$ = (sel) => document.querySelectorAll(sel);

    const promptInput      = $('#prompt-input');
    const charCount        = $('#char-count');
    const btnSubmit        = $('#btn-submit');
    const btnHistory       = $('#btn-history');
    const btnCloseHistory  = $('#btn-close-history');
    const sidebarOverlay   = $('#sidebar-overlay');
    const historySidebar   = $('#history-sidebar');
    const historyList      = $('#history-list');
    const pipelineTracker  = $('#pipeline-tracker');
    const pipelineStatusTx = $('#pipeline-status-text');
    const welcomeState     = $('#welcome-state');
    const convPanel        = $('#conversational-panel');
    const codeOutputPanel  = $('#code-output-panel');
    const errorPanel       = $('#error-panel');
    const errorMessage     = $('#error-message');
    const btnRetry         = $('#btn-retry');
    const verifierCard     = $('#verifier-card');
    const tabBar           = $('#tab-bar');
    const toastContainer   = $('#toast-container');

    // ─── State ─────────────────────────────────────────────────
    let currentJobId = null;
    let pollTimer    = null;
    let isSubmitting = false;

    // ─── Background Canvas (Particle Network) ─────────────────
    function initBackground() {
        const canvas = $('#bg-canvas');
        if (!canvas) return;
        const ctx = canvas.getContext('2d');
        let particles = [];
        let w, h;

        function resize() {
            w = canvas.width = window.innerWidth;
            h = canvas.height = window.innerHeight;
        }

        function createParticles() {
            particles = [];
            const count = Math.floor((w * h) / 18000);
            for (let i = 0; i < count; i++) {
                particles.push({
                    x: Math.random() * w,
                    y: Math.random() * h,
                    vx: (Math.random() - 0.5) * 0.3,
                    vy: (Math.random() - 0.5) * 0.3,
                    r: Math.random() * 1.5 + 0.5,
                    o: Math.random() * 0.4 + 0.1,
                });
            }
        }

        function draw() {
            ctx.clearRect(0, 0, w, h);

            // Draw connections
            for (let i = 0; i < particles.length; i++) {
                for (let j = i + 1; j < particles.length; j++) {
                    const dx = particles[i].x - particles[j].x;
                    const dy = particles[i].y - particles[j].y;
                    const dist = Math.sqrt(dx * dx + dy * dy);
                    if (dist < 120) {
                        ctx.beginPath();
                        ctx.moveTo(particles[i].x, particles[i].y);
                        ctx.lineTo(particles[j].x, particles[j].y);
                        ctx.strokeStyle = `rgba(0, 180, 220, ${0.06 * (1 - dist / 120)})`;
                        ctx.lineWidth = 0.5;
                        ctx.stroke();
                    }
                }
            }

            // Draw particles
            for (const p of particles) {
                ctx.beginPath();
                ctx.arc(p.x, p.y, p.r, 0, Math.PI * 2);
                ctx.fillStyle = `rgba(0, 200, 255, ${p.o})`;
                ctx.fill();

                // Move
                p.x += p.vx;
                p.y += p.vy;

                // Bounce
                if (p.x < 0 || p.x > w) p.vx *= -1;
                if (p.y < 0 || p.y > h) p.vy *= -1;
            }

            requestAnimationFrame(draw);
        }

        window.addEventListener('resize', () => {
            resize();
            createParticles();
        });

        resize();
        createParticles();
        draw();
    }

    // ─── Toast Notifications ───────────────────────────────────
    function showToast(message, type = 'info') {
        const icons = { success: '✅', error: '❌', info: 'ℹ️' };
        const toast = document.createElement('div');
        toast.className = `toast ${type}`;
        toast.innerHTML = `<span class="toast-icon">${icons[type]}</span><span>${message}</span>`;
        toastContainer.appendChild(toast);

        setTimeout(() => {
            toast.classList.add('leaving');
            setTimeout(() => toast.remove(), 300);
        }, 4000);
    }

    // ─── Character Counter ─────────────────────────────────────
    function updateCharCount() {
        const len = promptInput.value.length;
        charCount.textContent = `${len} / 5000`;
        charCount.style.color = len > 4500 ? '#ef4444' : '';
    }

    // ─── Suggestion Chips ──────────────────────────────────────
    function initSuggestions() {
        $$('.suggestion-chip').forEach(chip => {
            chip.addEventListener('click', () => {
                promptInput.value = chip.dataset.prompt;
                updateCharCount();
                promptInput.focus();
            });
        });
    }

    // ─── History Sidebar ───────────────────────────────────────
    function toggleHistory(show) {
        if (show) {
            historySidebar.classList.remove('hidden');
            sidebarOverlay.classList.remove('hidden');
            requestAnimationFrame(() => {
                historySidebar.classList.add('visible');
                sidebarOverlay.classList.add('visible');
            });
            loadHistory();
        } else {
            historySidebar.classList.remove('visible');
            sidebarOverlay.classList.remove('visible');
            setTimeout(() => {
                historySidebar.classList.add('hidden');
                sidebarOverlay.classList.add('hidden');
            }, 500);
        }
    }

    async function loadHistory() {
        try {
            const res = await fetch(`${API_BASE}/api/history`);
            const data = await res.json();

            if (data.length === 0) {
                historyList.innerHTML = '<div class="history-empty">No prompts yet</div>';
                return;
            }

            historyList.innerHTML = data.map(item => {
                const date = new Date(item.timestamp);
                const timeStr = date.toLocaleString();
                return `
                    <div class="history-item" data-prompt="${escapeAttr(item.prompt)}">
                        <div class="history-timestamp">${timeStr}</div>
                        <div class="history-prompt">${escapeHtml(item.prompt)}</div>
                    </div>
                `;
            }).join('');

            // Click handler for history items
            historyList.querySelectorAll('.history-item').forEach(item => {
                item.addEventListener('click', () => {
                    promptInput.value = item.dataset.prompt;
                    updateCharCount();
                    toggleHistory(false);
                    promptInput.focus();
                });
            });
        } catch (err) {
            historyList.innerHTML = '<div class="history-empty">Failed to load history</div>';
        }
    }

    // ─── Pipeline UI ───────────────────────────────────────────
    const stepElements = [
        $('#step-perspective'),
        $('#step-extractor'),
        $('#step-builder'),
        $('#step-verifier'),
        $('#step-interface'),
    ];

    function resetPipeline() {
        stepElements.forEach(el => {
            el.className = 'pipeline-step pending';
        });
        pipelineStatusTx.textContent = '';
        verifierCard.classList.add('hidden');
    }

    function updatePipelineUI(statusData) {
        if (!statusData || !statusData.steps) return;

        statusData.steps.forEach((step, i) => {
            if (stepElements[i]) {
                stepElements[i].className = `pipeline-step ${step.status}`;
            }
        });

        // Status text
        const currentIdx = statusData.current_step;
        if (statusData.status === 'done') {
            pipelineStatusTx.textContent = '✓ Complete';
            pipelineStatusTx.style.color = '#22c55e';
        } else if (statusData.status === 'error') {
            pipelineStatusTx.textContent = '✗ Error';
            pipelineStatusTx.style.color = '#ef4444';
        } else if (currentIdx < 5) {
            const names = ['Classifying...', 'Extracting...', 'Generating...', 'Verifying...', 'Documenting...'];
            pipelineStatusTx.textContent = names[currentIdx] || '';
            pipelineStatusTx.style.color = '#00d4ff';
        }
    }

    // ─── Submit Prompt ─────────────────────────────────────────
    async function submitPrompt() {
        const prompt = promptInput.value.trim();
        if (!prompt || isSubmitting) return;

        if (prompt.length < 3) {
            showToast('Prompt too short — min 3 characters.', 'error');
            return;
        }

        isSubmitting = true;
        setSubmitLoading(true);
        resetPipeline();
        showPanel('none'); // hide all output panels

        try {
            const res = await fetch(`${API_BASE}/api/generate`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ prompt }),
            });

            const data = await res.json();

            if (!res.ok) {
                showToast(data.error || 'Request failed', 'error');
                setSubmitLoading(false);
                isSubmitting = false;
                return;
            }

            currentJobId = data.job_id;
            showToast('Pipeline started — generating your agent...', 'info');
            startPolling();
        } catch (err) {
            showToast('Cannot reach server. Is it running?', 'error');
            setSubmitLoading(false);
            isSubmitting = false;
        }
    }

    function setSubmitLoading(loading) {
        const btnText = btnSubmit.querySelector('.btn-text');
        const btnArrow = btnSubmit.querySelector('.btn-arrow');
        const btnSpinner = btnSubmit.querySelector('.btn-spinner');

        if (loading) {
            btnText.textContent = 'Generating...';
            btnArrow.style.display = 'none';
            btnSpinner.style.display = 'block';
            btnSubmit.disabled = true;
        } else {
            btnText.textContent = 'Generate';
            btnArrow.style.display = 'block';
            btnSpinner.style.display = 'none';
            btnSubmit.disabled = false;
        }
    }

    // ─── Polling ───────────────────────────────────────────────
    function startPolling() {
        stopPolling();
        pollTimer = setInterval(pollStatus, POLL_INTERVAL);
        pollStatus(); // immediate first call
    }

    function stopPolling() {
        if (pollTimer) {
            clearInterval(pollTimer);
            pollTimer = null;
        }
    }

    async function pollStatus() {
        if (!currentJobId) return;

        try {
            const res = await fetch(`${API_BASE}/api/status/${currentJobId}`);
            const data = await res.json();

            updatePipelineUI(data);

            if (data.status === 'done' || data.status === 'error') {
                stopPolling();
                setSubmitLoading(false);
                isSubmitting = false;

                if (data.status === 'done') {
                    showToast('Pipeline complete!', 'success');
                    fetchAndDisplayResult();
                } else {
                    showToast('Pipeline encountered an error.', 'error');
                    showError(data.error || 'Unknown error occurred.');
                }
            }
        } catch (err) {
            // Network error, keep polling
        }
    }

    // ─── Fetch & Display Result ────────────────────────────────
    async function fetchAndDisplayResult() {
        if (!currentJobId) return;

        try {
            const res = await fetch(`${API_BASE}/api/result/${currentJobId}`);
            const data = await res.json();

            if (data.route === 'conversational') {
                displayConversational(data);
            } else {
                displayAgentBuild(data);
            }
        } catch (err) {
            showError('Failed to fetch results: ' + err.message);
        }
    }

    // ─── Display: Conversational ───────────────────────────────
    function displayConversational(data) {
        showPanel('conversational');

        const responseEl = $('#conv-response');
        const text = data.conversational_response || 'No response received.';

        // Typing animation
        responseEl.innerHTML = '';
        typeText(responseEl, text);
    }

    function typeText(el, text, speed = 8) {
        let i = 0;
        el.innerHTML = '<span class="typing-cursor"></span>';

        function tick() {
            if (i < text.length) {
                // Insert character before cursor
                const cursor = el.querySelector('.typing-cursor');
                const charNode = document.createTextNode(text[i]);
                el.insertBefore(charNode, cursor);
                i++;
                setTimeout(tick, speed);
            } else {
                // Remove cursor after done
                const cursor = el.querySelector('.typing-cursor');
                if (cursor) {
                    setTimeout(() => cursor.remove(), 2000);
                }
            }
        }
        tick();
    }

    // ─── Display: Agent Build ──────────────────────────────────
    function displayAgentBuild(data) {
        showPanel('code-output');

        // Populate code tabs
        const files = data.files || {};

        setCodeContent('code-agent', files['agent.py'] || '# No agent.py generated', 'python');
        setCodeContent('code-main', files['main.py'] || '# No main.py generated', 'python');
        setCodeContent('code-requirements', files['requirements.txt'] || '# No requirements.txt generated', 'text');
        setCodeContent('code-spec', JSON.stringify(data.agent_spec || {}, null, 2), 'json');

        // README as markdown
        const readmeContent = files['README.md'] || '*No README generated.*';
        $('#readme-content').innerHTML = renderMarkdown(readmeContent);

        // Report (output.md)
        const reportContent = data.output_md || '*No report generated yet.*';
        $('#report-content').innerHTML = renderMarkdown(reportContent);

        // Verifier Score
        if (data.verifier_result) {
            displayVerifier(data.verifier_result);
        }

        // Activate first tab
        activateTab('report');
    }

    function setCodeContent(elementId, code, language) {
        const el = $(`#${elementId}`);
        if (!el) return;
        el.textContent = code;
        el.className = `language-${language}`;
        hljs.highlightElement(el);
    }

    function renderMarkdown(md) {
        try {
            const html = marked.parse(md, {
                breaks: true,
                gfm: true,
            });
            // Post-process: highlight code blocks
            const container = document.createElement('div');
            container.innerHTML = html;
            container.querySelectorAll('pre code').forEach(block => {
                hljs.highlightElement(block);
            });
            return container.innerHTML;
        } catch {
            return `<pre>${escapeHtml(md)}</pre>`;
        }
    }

    // ─── Display: Verifier ─────────────────────────────────────
    function displayVerifier(result) {
        verifierCard.classList.remove('hidden');

        const pct = result.overall_correctness_percentage || 0;
        const status = result.overall_status || 'UNKNOWN';
        const aiReview = result.ai_review || {};

        // Animate gauge
        const circumference = 326.73;
        const offset = circumference - (pct / 100) * circumference;
        const gaugeFill = $('#gauge-fill');

        // Set color based on score
        let gaugeColor = '#ef4444'; // red
        if (pct >= 80) gaugeColor = '#22c55e'; // green
        else if (pct >= 60) gaugeColor = '#f59e0b'; // amber

        gaugeFill.style.stroke = gaugeColor;

        // Animate after a small delay
        setTimeout(() => {
            gaugeFill.style.strokeDashoffset = offset;
        }, 200);

        // Score value animation
        animateValue($('#score-value'), 0, pct, 1200);

        // Label
        const scoreLabel = $('#score-label');
        scoreLabel.textContent = status;
        scoreLabel.style.color = gaugeColor;

        // Details
        const details = $('#verifier-details');
        let detailsHtml = '';

        if (aiReview.summary) {
            detailsHtml += `
                <div class="verifier-detail-item">
                    <span class="detail-label">Verdict</span>
                    <span class="detail-value">${escapeHtml(aiReview.summary)}</span>
                </div>
            `;
        }

        if (aiReview.implemented_correctly && aiReview.implemented_correctly.length > 0) {
            detailsHtml += `
                <div class="verifier-detail-item">
                    <span class="detail-label">Correct</span>
                    <span class="detail-value">${aiReview.implemented_correctly.map(i => `✓ ${escapeHtml(i)}`).join('<br>')}</span>
                </div>
            `;
        }

        if (aiReview.issues && aiReview.issues.length > 0) {
            detailsHtml += `
                <div class="verifier-detail-item">
                    <span class="detail-label">Issues</span>
                    <span class="detail-value">${aiReview.issues.map(i => `• ${escapeHtml(i)}`).join('<br>')}</span>
                </div>
            `;
        }

        details.innerHTML = detailsHtml;
    }

    function animateValue(el, start, end, duration) {
        const startTime = performance.now();
        function update(currentTime) {
            const elapsed = currentTime - startTime;
            const progress = Math.min(elapsed / duration, 1);
            // Ease out
            const eased = 1 - Math.pow(1 - progress, 3);
            const current = Math.round(start + (end - start) * eased);
            el.textContent = `${current}%`;
            if (progress < 1) {
                requestAnimationFrame(update);
            }
        }
        requestAnimationFrame(update);
    }

    // ─── Panel Visibility ──────────────────────────────────────
    function showPanel(panel) {
        welcomeState.classList.add('hidden');
        convPanel.classList.add('hidden');
        codeOutputPanel.classList.add('hidden');
        errorPanel.classList.add('hidden');

        switch (panel) {
            case 'welcome':
                welcomeState.classList.remove('hidden');
                break;
            case 'conversational':
                convPanel.classList.remove('hidden');
                break;
            case 'code-output':
                codeOutputPanel.classList.remove('hidden');
                break;
            case 'error':
                errorPanel.classList.remove('hidden');
                break;
            // 'none' hides all
        }
    }

    function showError(msg) {
        showPanel('error');
        errorMessage.textContent = msg;
    }

    // ─── Tabs ──────────────────────────────────────────────────
    function activateTab(tabId) {
        // Tab buttons
        tabBar.querySelectorAll('.tab').forEach(t => t.classList.remove('active'));
        const activeBtn = tabBar.querySelector(`[data-tab="${tabId}"]`);
        if (activeBtn) activeBtn.classList.add('active');

        // Tab panes
        $$('.tab-pane').forEach(p => p.classList.remove('active'));
        const activePane = $(`[data-pane="${tabId}"]`);
        if (activePane) activePane.classList.add('active');
    }

    // ─── Copy to Clipboard ─────────────────────────────────────
    function handleCopy(btn) {
        const targetId = btn.dataset.target;
        const codeEl = $(`#${targetId}`);
        if (!codeEl) return;

        const text = codeEl.textContent;
        navigator.clipboard.writeText(text).then(() => {
            btn.classList.add('copied');
            const span = btn.querySelector('span');
            const original = span.textContent;
            span.textContent = 'Copied!';

            setTimeout(() => {
                btn.classList.remove('copied');
                span.textContent = original;
            }, 2000);
        }).catch(() => {
            showToast('Failed to copy to clipboard', 'error');
        });
    }

    // ─── Utility Functions ─────────────────────────────────────
    function escapeHtml(str) {
        if (!str) return '';
        const div = document.createElement('div');
        div.textContent = str;
        return div.innerHTML;
    }

    function escapeAttr(str) {
        if (!str) return '';
        return str.replace(/"/g, '&quot;').replace(/'/g, '&#39;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
    }

    // ─── Event Listeners ───────────────────────────────────────
    function initEvents() {
        // Prompt input
        promptInput.addEventListener('input', updateCharCount);
        promptInput.addEventListener('keydown', (e) => {
            if (e.key === 'Enter' && (e.ctrlKey || e.metaKey)) {
                e.preventDefault();
                submitPrompt();
            }
        });

        // Submit button
        btnSubmit.addEventListener('click', submitPrompt);

        // Retry button
        btnRetry.addEventListener('click', () => {
            showPanel('welcome');
            resetPipeline();
        });

        // History
        btnHistory.addEventListener('click', () => toggleHistory(true));
        btnCloseHistory.addEventListener('click', () => toggleHistory(false));
        sidebarOverlay.addEventListener('click', () => toggleHistory(false));

        // Tabs
        tabBar.addEventListener('click', (e) => {
            const tab = e.target.closest('.tab');
            if (tab) activateTab(tab.dataset.tab);
        });

        // Copy buttons
        document.addEventListener('click', (e) => {
            const copyBtn = e.target.closest('.btn-copy');
            if (copyBtn) handleCopy(copyBtn);
        });

        // Suggestions
        initSuggestions();

        // Keyboard shortcut hints
        promptInput.setAttribute('title', 'Ctrl+Enter to submit');
    }

    // ─── Initialization ────────────────────────────────────────
    function init() {
        initBackground();
        initEvents();
        updateCharCount();
        showPanel('welcome');
        console.log('%c⚡ AgentForge Frontend Loaded', 'color: #00d4ff; font-weight: bold; font-size: 14px;');
    }

    // Start
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', init);
    } else {
        init();
    }

})();
