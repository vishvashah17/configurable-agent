from flask import Flask, render_template_string, request, jsonify
import os, sys, time, json
from datetime import datetime

# --- Add src to path ---
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# --- Import backend components ---
from agent.baseline_agent import BaselineAgent
from agent.agent_controller import ConfigurableAgent
from evaluation.result_logger import ResultLogger

# --- Flask App ---
app = Flask(__name__)

_components = {
    "baseline": None,
    "configured": None,
    "logger": None,
    "initialized": False
}


def initialize_components():
    """Initialize backend agents and logger"""
    if _components["initialized"]:
        return
    
    print("[+] Initializing backend components...")
    _components["baseline"] = BaselineAgent()

    # Configurable Agent
    config_path = os.path.join(
        os.path.dirname(os.path.dirname(__file__)), "config", "base_config.yaml"
    )
    _components["configured"] = ConfigurableAgent(config_path)

    # Logger
    results_dir = os.path.join(
        os.path.dirname(os.path.dirname(__file__)), "evaluation", "results"
    )
    _components["logger"] = ResultLogger(base_dir=results_dir)

    _components["initialized"] = True
    print(f"[✓] Components initialized. Results saved in: {results_dir}")


# --- HTML Template ---
HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<title>Configurable Agent Dashboard</title>
<style>
    body {
        font-family: 'Segoe UI', sans-serif;
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        margin: 0;
        padding: 0;
        color: #333;
    }
    .container {
        max-width: 1100px;
        margin: 50px auto;
        background: #fff;
        border-radius: 12px;
        box-shadow: 0 10px 30px rgba(0,0,0,0.2);
        overflow: hidden;
    }
    header {
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        color: white;
        text-align: center;
        padding: 40px 20px;
    }
    header h1 {
        margin: 0;
        font-size: 2.5em;
        font-weight: 600;
    }
    main {
        padding: 30px;
    }
    h2 {
        color: #444;
        border-left: 4px solid #667eea;
        padding-left: 10px;
        margin-bottom: 15px;
    }
    textarea, input {
        width: 100%;
        padding: 12px;
        border-radius: 8px;
        border: 1px solid #ccc;
        margin-bottom: 15px;
        font-size: 16px;
    }
    button {
        background: #667eea;
        color: white;
        border: none;
        padding: 14px 28px;
        border-radius: 8px;
        cursor: pointer;
        font-size: 16px;
        font-weight: 600;
        transition: background 0.3s ease;
    }
    button:hover {
        background: #5a6de0;
    }
    .loading {
        text-align: center;
        margin: 20px 0;
        color: #667eea;
        font-weight: 600;
    }
    .card {
        background: #fafafa;
        padding: 20px;
        border-radius: 10px;
        box-shadow: 0 2px 6px rgba(0,0,0,0.1);
        margin-top: 20px;
    }
    pre {
        background: #2d2d2d;
        color: #f8f8f2;
        padding: 15px;
        border-radius: 8px;
        overflow-x: auto;
        font-family: 'Consolas', monospace;
    }
    .similar-card {
        background: #eef2ff;
        border-left: 5px solid #667eea;
        margin: 10px 0;
        padding: 15px;
        border-radius: 8px;
    }
    .similar-card h4 {
        margin: 0;
        color: #333;
    }
    .footer {
        text-align: center;
        color: white;
        margin: 30px 0;
        font-size: 0.9em;
        opacity: 0.8;
    }
</style>
</head>
<body>
<div class="container">
    <header>
        <h1>Configurable Agent Dashboard</h1>
        <p>Plan | Reason | Persona | Tool | Memory</p>
    </header>
    <main>
        <h2>Ask a Question</h2>
        <form id="queryForm">
            <textarea id="question" required placeholder="Enter your question..."></textarea>
            <input type="text" id="expected" placeholder="Expected answer (optional)">
            <button type="submit">Run Agent</button>
        </form>
        <div id="loading" class="loading" style="display:none;">Processing...</div>
        <div id="results"></div>
    </main>
</div>
<div class="footer">© 2025 Configurable AI Agent | All Rights Reserved</div>

<script>
const form = document.getElementById("queryForm");
const loading = document.getElementById("loading");
const resultsDiv = document.getElementById("results");

form.addEventListener("submit", async (e) => {
    e.preventDefault();
    const question = document.getElementById("question").value.trim();
    const expected = document.getElementById("expected").value.trim();
    if (!question) return alert("Please enter a question!");

    loading.style.display = "block";
    resultsDiv.innerHTML = "";

    try {
        const res = await fetch("/api/ask", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ question, expected })
        });
        const data = await res.json();
        loading.style.display = "none";

        if (data.error) {
            resultsDiv.innerHTML = `<div class='card' style='color:red;'>Error: ${data.error}</div>`;
            return;
        }

        let html = `
            <div class="card">
                <h2>Question</h2>
                <p>${data.question}</p>
                <h2>Baseline Agent</h2>
                <pre>${data.baseline_answer}</pre>
                <h2>Configurable Agent</h2>
                <p><b>Persona:</b> ${data.persona || "General"}</p>
                <h3>Plan:</h3>
                <pre>${data.plan}</pre>
                <h3>Answer:</h3>
                <pre>${data.answer}</pre>
                <p><b>Execution Time:</b> ${data.execution_time.toFixed(2)} seconds</p>
                <p style="color:green;font-weight:bold;">✔ Result saved successfully</p>
            </div>
        `;

        if (data.similar_examples && data.similar_examples.length > 0) {
            html += `<div class="card"><h2>Top Similar Examples</h2>`;
            data.similar_examples.forEach(ex => {
                html += `
                    <div class="similar-card">
                        <h4>${ex.sample.category}</h4>
                        <p><b>Similarity:</b> ${(ex.similarity * 100).toFixed(1)}%</p>
                        <p>${ex.sample.question}</p>
                    </div>`;
            });
            html += `</div>`;
        }

        resultsDiv.innerHTML = html;
    } catch (err) {
        loading.style.display = "none";
        resultsDiv.innerHTML = `<div class='card' style='color:red;'>Error: ${err.message}</div>`;
    }
});
</script>
</body>
</html>
"""


@app.route("/")
def index():
    if not _components["initialized"]:
        initialize_components()
    return render_template_string(HTML_TEMPLATE)


@app.route("/api/ask", methods=["POST"])
def ask_question():
    try:
        data = request.json
        question = data.get("question", "").strip()
        expected = data.get("expected", "").strip() or None
        if not question:
            return jsonify({"error": "Question is required"}), 400

        if not _components["initialized"]:
            initialize_components()

        baseline = _components["baseline"]
        configured = _components["configured"]
        logger = _components["logger"]

        start = time.time()
        baseline_answer = baseline.run(question)
        configurable_result = configured.run(question, expected)

        # Dummy similar examples for now (replace with dataset logic if available)
        similar_examples = [
            {
                "sample": {
                    "category": "Arithmetic",
                    "question": "If John has 3 apples and eats one, how many are left?"
                },
                "similarity": 0.78
            },
            {
                "sample": {
                    "category": "Logic",
                    "question": "If all cats are animals, are some animals cats?"
                },
                "similarity": 0.64
            },
            {
                "sample": {
                    "category": "Language",
                    "question": "Explain the difference between affect and effect."
                },
                "similarity": 0.59
            }
        ]

        execution_time = time.time() - start

        # Save results
        logger.save_result(
            question=question,
            baseline=baseline_answer,
            configurable=configurable_result,
            similar=similar_examples,
            reflection=None,
            metrics={"execution_time": execution_time}
        )

        return jsonify({
            "question": question,
            "baseline_answer": baseline_answer,
            "plan": configurable_result.get("plan", ""),
            "answer": configurable_result.get("answer", ""),
            "persona": configurable_result.get("persona", None),
            "similar_examples": similar_examples,
            "execution_time": execution_time
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500


if __name__ == "__main__":
    print("=" * 60)
    print("Starting Configurable Agent Web Dashboard")
    print("=" * 60)
    initialize_components()
    print("Dashboard running at http://localhost:5000")
    print("=" * 60)
    app.run(host="0.0.0.0", port=5000, debug=True)
