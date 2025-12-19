# Complete System Explanation

## 🎯 How Everything Works

### 1. **Dataset Processing Pipeline**

```
CSV Files (datasets/)
    ↓
data_loader.py
    ├── Reads 5 CSV files
    ├── Handles different column formats
    ├── Formats questions appropriately
    └── Returns: List of {category, question, answer}
    ↓
vector_index.py
    ├── Uses SentenceTransformer to embed text
    ├── Creates 384-dimensional vectors
    ├── Builds FAISS index (L2 distance)
    └── Ready for similarity search
```

**Key Points:**
- **5 datasets loaded**: gsm8k, boolq, wsc, anli, proofwriter
- **200 samples per dataset** (default, configurable)
- **Different formats handled**: Standard Q&A, premise+hypothesis, pronoun resolution, etc.
- **Vector embeddings**: Text converted to numbers for similarity comparison

### 2. **Agent Architecture**

#### Baseline Agent (Simple)
```
Question → ModelClient → Ollama → Answer
```
- Direct path: no planning, no tools
- Fast response
- Uses same model as configurable agent

#### Configurable Agent (Multi-Stage)
```
Question
    ↓
┌─────────────────────────────────┐
│ 1. PLANNER                      │
│    Splits question into steps   │
│    Output: "Steps:\n1. ..."     │
└─────────────────────────────────┘
    ↓
┌─────────────────────────────────┐
│ 2. TOOLS                        │
│    Checks for math expressions  │
│    If found: Uses safe_eval()   │
│    If not: Skip to reasoner     │
└─────────────────────────────────┘
    ↓
┌─────────────────────────────────┐
│ 3. REASONER                     │
│    Combines: Plan + Question    │
│    Sends to Ollama (qwen3:8b)   │
│    Generates answer            │
└─────────────────────────────────┘
    ↓
┌─────────────────────────────────┐
│ 4. MEMORY                       │
│    Stores: (question, answer)   │
│    Short-term session memory   │
└─────────────────────────────────┘
    ↓
┌─────────────────────────────────┐
│ 5. REFLECTION                   │
│    Compares answer vs expected  │
│    Calculates similarity score  │
│    Provides feedback           │
└─────────────────────────────────┘
    ↓
Final Result: {plan, answer, reflection}
```

## 🔌 Component Connections

### Model Client (`model_client.py`)
- **Purpose**: Wrapper for Ollama API
- **Connects**: Local Ollama service (localhost)
- **Used by**: 
  - `Reasoner` (configurable agent)
  - `BaselineAgent`
- **Function**: Converts prompts to Ollama API calls

### Config File (`base_config.yaml`)
- **Purpose**: Control agent behavior
- **Read by**: `ConfigurableAgent.__init__()`
- **Controls**: 
  - Which model to use
  - Feature flags (planning, reasoning, etc.)

### Vector Index (`vector_index.py`)
- **Uses**: `data_loader.load_all()` to get datasets
- **Uses**: `SentenceTransformer` for embeddings
- **Uses**: `FAISS` for fast similarity search
- **Used by**: `interactive_eval.py` to find similar examples

### Graph Logger (`graph_logger.py`)
- **Connects**: Neo4j database (optional)
- **Used by**: `interactive_eval.py` and `dashboard.py`
- **Function**: Logs runs and creates relationships

## 📊 Data Flow Example

**Example Question**: "Who was the president of USA in 2010?"

### Step 1: User Input
```
User enters question → interactive_eval.py or dashboard.py
```

### Step 2: Similarity Search
```
Question → vector_index.query()
    ↓
Embed question → Search FAISS index
    ↓
Find top 3 similar examples
    ↓
Return: [{sample: {...}, similarity: 0.85}, ...]
```

### Step 3: Baseline Processing
```
Question → BaselineAgent.run()
    ↓
ModelClient.generate("Answer briefly:\n{question}\nAnswer:")
    ↓
Ollama API call
    ↓
Answer: "Barack Obama was the president..."
```

### Step 4: Configurable Agent Processing
```
Question → ConfigurableAgent.run()
    ↓
Planner.plan() → "Steps:\n1. Who was the president..."
    ↓
Tools.math_tool() → No math found
    ↓
Reasoner.reason(Plan + Question)
    ↓
ModelClient → Ollama → "Barack Obama..."
    ↓
Memory.remember(question, answer)
    ↓
Reflection.evaluate() → {score: 0.8, comment: "Good"}
    ↓
Return: {plan, answer, reflection}
```

### Step 5: Evaluation
```
If expected answer provided:
    ↓
compute_bleu(predicted, expected) → 0.75
compute_rouge(predicted, expected) → 0.82
```

### Step 6: Logging (Optional)
```
GraphLogger.log_run()
    ↓
Neo4j database
    ↓
Creates: Run node + Example nodes + SIMILAR_TO relationships
```

### Step 7: Output
```
Display:
- Baseline answer
- Configurable agent (plan + answer + reflection)
- Metrics (BLEU, ROUGE)
- Similar examples
- Execution time
```

## 🚀 Starting the Server

### Web Dashboard (Recommended)

```bash
# 1. Navigate to src directory
cd src

# 2. Start the server
python web/dashboard.py
```

**You'll see:**
```
============================================================
Starting Configurable Agent Web Dashboard
============================================================
Initializing components...
Loading vector index...
Initializing baseline agent...
Initializing configurable agent...
Connecting to Neo4j (optional)...

============================================================
Dashboard ready!
Open your browser and go to: http://localhost:5000
============================================================
 * Running on http://0.0.0.0:5000
```

**Then:**
1. Open browser: `http://localhost:5000`
2. Enter question in the form
3. Optionally provide expected answer
4. Click "Get Answer"
5. View results in real-time

### Command Line Interface

```bash
cd src
python -m evaluation.interactive_eval
```

**You'll see:**
```
============================================================
Configurable Agent Interactive Evaluation
============================================================
Initializing components (this may take a moment)...
Loading vector index...
Initializing baseline agent...
Initializing configurable agent...
Connecting to Neo4j (optional)...

============================================================
Ready! Enter questions to evaluate.
Type 'exit' or 'quit' to stop, or Ctrl+C to interrupt.
============================================================

Enter your question (or 'exit' to quit):
```

## 📁 File Structure & Responsibilities

```
src/
├── config/
│   └── base_config.yaml          # Agent configuration
│
├── utils/
│   ├── model_client.py            # Ollama API wrapper
│   ├── data_loader.py             # Loads & formats CSV datasets
│   ├── vector_index.py            # FAISS similarity search
│   └── graph_logger.py            # Neo4j logging (optional)
│
├── agent/
│   ├── planner.py                 # Breaks questions into steps
│   ├── reasoner.py                # LLM reasoning via Ollama
│   ├── memory.py                  # Stores Q&A pairs
│   ├── tools.py                    # Math evaluation
│   ├── reflection.py              # Answer quality evaluation
│   ├── baseline_agent.py         # Simple direct agent
│   └── agent_controller.py        # Orchestrates all components
│
├── evaluation/
│   ├── metrics.py                 # BLEU/ROUGE calculation
│   └── interactive_eval.py        # CLI evaluation interface
│
└── web/
    └── dashboard.py               # Web interface & API
```

## 🔄 How Components Work Together

1. **Initialization** (happens once):
   - Load datasets → Build vector index
   - Initialize agents (baseline + configurable)
   - Connect to Neo4j (optional)

2. **Question Processing** (per question):
   - Query vector index for similar examples
   - Run baseline agent (fast)
   - Run configurable agent (multi-stage)
   - Calculate metrics (if expected provided)
   - Log to Neo4j (if available)

3. **Output**:
   - Display all results
   - Show metrics
   - Show similar examples
   - Show execution time

## 🎓 Key Concepts

### Vector Embeddings
- Text → Numbers (384 dimensions)
- Similar text = similar numbers
- Enables fast similarity search

### FAISS Index
- Fast similarity search library
- L2 distance (Euclidean)
- Finds closest vectors efficiently

### Ollama Integration
- Local LLM server
- No GPU required (CPU works)
- Easy model switching

### Component Modularity
- Each component is independent
- Can be enabled/disabled via config
- Easy to extend or modify

## 💡 Tips

1. **First run is slow**: Loading datasets and building index takes time
2. **Subsequent questions are fast**: Components are reused
3. **Expected answer optional**: Metrics only calculated if provided
4. **Neo4j optional**: System works without it
5. **Model switching**: Change in config file, restart needed











