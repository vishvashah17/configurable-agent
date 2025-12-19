# Configurable Agent System

A modular, configurable agent system with planning, reasoning, memory, tools, and reflection capabilities.

## Structure

```
CONFIGURABLE_AGENT/
├── datasets/
│   ├── boolq.csv
│   ├── gsm8k.csv
│   ├── wsc.csv
│   ├── anli.csv
│   ├── proofwriter.csv
│   └── README.md
├── requirements.txt
└── src/
    ├── config/
    │   └── base_config.yaml
    ├── utils/
    │   ├── __init__.py
    │   ├── model_client.py
    │   ├── data_loader.py
    │   ├── vector_index.py
    │   └── graph_logger.py
    ├── agent/
    │   ├── __init__.py
    │   ├── planner.py
    │   ├── reasoner.py
    │   ├── memory.py
    │   ├── tools.py
    │   ├── reflection.py
    │   ├── baseline_agent.py
    │   └── agent_controller.py
    ├── evaluation/
    │   ├── __init__.py
    │   ├── metrics.py
    │   └── interactive_eval.py
    └── web/
        └── dashboard.py
```

## Setup

1. **Install and start Ollama:**
   ```bash
   # Download Ollama from https://ollama.ai
   # Start the Ollama service
   ollama serve
   ```

2. **Pull required models:**
   ```bash
   ollama pull qwen3:8b     # For reasoning + planning
   ollama pull llama3       # For reflection (optional)
   ollama pull tinyllama    # For baseline (optional)
   ```

3. **Create virtual environment:**
   ```bash
   python -m venv venv
   venv\Scripts\activate  # Windows
   # or
   source venv/bin/activate  # Linux/Mac
   ```

4. **Install dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

5. **Download NLTK data (required for BLEU):**
   ```python
   import nltk
   nltk.download('punkt')
   ```

6. **Setup Neo4j (optional, for graph logging):**
   - Install and run Neo4j database
   - Update connection details in `src/utils/graph_logger.py` if needed

## Usage

### Interactive Evaluation

Run the interactive evaluation script:

```bash
cd src
python -m evaluation.interactive_eval
```

Or run directly:
```bash
python -m evaluation.interactive_eval
```

Then enter your question when prompted:
```
Enter your question: Who was the president of USA in 2010?
Enter expected answer (optional): Barack Obama
```

### Web Dashboard

Start the Flask dashboard:

```bash
cd src
python web/dashboard.py
```

Then open `http://localhost:5000` in your browser.

**Features:**
- Interactive web interface to ask questions
- Real-time processing with loading indicators
- Displays baseline and configurable agent responses
- Shows planning steps, answers, and reflection
- Calculates BLEU/ROUGE metrics (if expected answer provided)
- Displays similar examples from datasets
- Shows execution time and system status

## Configuration

Edit `src/config/base_config.yaml` to customize agent behavior:

```yaml
agent:
  model: "qwen3:8b"        # switch to llama3 or qwen3:4b anytime
  planning: true
  reasoning: true
  memory: true
  tools: true
  reflection: true

evaluation:
  sample_size_per_dataset: 50
```

### Model Selection Guide

| Task | Recommended Model | Why |
|------|------------------|-----|
| Reasoning + Planning | `qwen3:8b` | Strong reasoning + small enough to run locally |
| Reflection + Evaluation | `llama3` or `qwen3:4b` | Slightly smaller and stable for meta-evaluation |
| Quick baseline responses | `tinyllama` | Instant replies for baseline comparisons |
| Low memory systems | `qwen3:4b` | Smaller footprint while maintaining quality |

### Switching Models at Runtime

You can switch models programmatically:

```python
from utils.model_client import get_client

# For baseline (fast responses)
baseline_client = get_client("tinyllama")

# For reasoning (default)
reasoning_client = get_client("qwen3:8b")

# For reflection
reflection_client = get_client("llama3")
```

## Features

- **Planning**: Breaks down tasks into steps
- **Reasoning**: Uses LLM for generating answers
- **Memory**: Stores short-term and long-term memory
- **Tools**: Math evaluation and computation tools
- **Reflection**: Evaluates answer quality
- **Vector Search**: FAISS-based similarity search over datasets
- **Graph Logging**: Neo4j integration for tracking runs

## Components

- **BaselineAgent**: Simple direct question-answering
- **ConfigurableAgent**: Full-featured agent with all modules
- **DatasetVectorIndex**: Semantic search over training examples
- **GraphLogger**: Logs runs and relationships to Neo4j

