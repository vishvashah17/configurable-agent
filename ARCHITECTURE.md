# System Architecture & Data Flow

## 🏗️ System Overview

The Configurable Agent System is a modular AI agent that processes questions through multiple stages: planning, reasoning, tool usage, memory, and reflection.

```
┌─────────────────────────────────────────────────────────────┐
│                    USER QUESTION                            │
└──────────────────────┬──────────────────────────────────────┘
                       │
                       ▼
┌─────────────────────────────────────────────────────────────┐
│              DATASET PROCESSING PIPELINE                    │
│  ┌──────────────────────────────────────────────────────┐   │
│  │ 1. data_loader.py                                    │   
│  │    • Loads 5 CSV datasets (gsm8k, boolq, wsc, anli,   │ │
│  │      proofwriter)                                     │ │
│  │    • Formats different column structures              │ │
│  │    • Returns: [{category, question, answer}, ...]    │ │
│  └──────────────────────────────────────────────────────┘ │
│                       │                                       │
│                       ▼                                       │
│  ┌──────────────────────────────────────────────────────┐ │
│  │ 2. vector_index.py (DatasetVectorIndex)              │ │
│  │    • Uses SentenceTransformer to embed questions     │ │
│  │    • Builds FAISS vector index for similarity search │ │
│  │    • Stores embeddings of all loaded samples          │ │
│  └──────────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────────┘
                       │
                       ▼
┌─────────────────────────────────────────────────────────────┐
│              AGENT PROCESSING PIPELINE                        │
│                                                               │
│  ┌──────────────────────────────────────────────────────┐  │
│  │ BASELINE AGENT (Simple)                             │  │
│  │ • Direct question → Ollama → Answer                 │  │
│  └──────────────────────────────────────────────────────┘  │
│                                                               │
│  ┌──────────────────────────────────────────────────────┐  │
│  │ CONFIGURABLE AGENT (Multi-Stage)                     │  │
│  │                                                       │  │
│  │  Step 1: PLANNER                                     │  │
│  │  • Splits question into steps                       │  │
│  │  • Input: "Who was president in 2010?"              │  │
│  │  • Output: "Steps:\n1. Who was president in 2010?"   │  │
│  │                                                       │  │
│  │  Step 2: TOOLS                                       │  │
│  │  • Checks if question contains math expressions     │  │
│  │  • If math found: Uses safe_eval()                  │  │
│  │  • If no math: Skip to reasoning                    │  │
│  │                                                       │  │
│  │  Step 3: REASONER                                    │  │
│  │  • Uses Ollama (qwen3:8b) via ModelClient           │  │
│  │  • Input: Plan + Question                           │  │
│  │  • Output: Generated answer                        │  │
│  │                                                       │  │
│  │  Step 4: MEMORY                                      │  │
│  │  • Stores (question, answer) pair                   │  │
│  │  • Short-term memory for session                   │  │
│  │                                                       │  │
│  │  Step 5: REFLECTION                                  │  │
│  │  • Compares answer with expected (if provided)      │  │
│  │  • Calculates similarity score                      │  │
│  │  • Output: {score, comment}                        │  │
│  └──────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────┘
                       │
                       ▼
┌─────────────────────────────────────────────────────────────┐
│              EVALUATION & OUTPUT                              │
│  ┌──────────────────────────────────────────────────────┐ │
│  │ 1. Vector Similarity Search                         │ │
│  │    • Query user question against dataset index      │ │
│  │    • Find top 3 similar examples                    │ │
│  │                                                       │ │
│  │ 2. Metrics Calculation                              │ │
│  │    • BLEU score (if expected answer provided)       │ │
│  │    • ROUGE score (if expected answer provided)      │ │
│  │                                                       │ │
│  │ 3. Neo4j Logging (optional)                          │ │
│  │    • Logs run to graph database                     │ │
│  │    • Creates relationships between runs/examples   │ │
│  └──────────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────────┘
```

## 📊 Dataset Processing Flow

### 1. **Data Loading** (`src/utils/data_loader.py`)

**Process:**
```
For each CSV file:
├── Check if file exists
├── Load CSV with pandas
├── Handle different column structures:
│   ├── gsm8k.csv → question, answer (standard)
│   ├── proofwriter.csv → question, answer (standard)
│   ├── boolq.csv → question + passage → formatted question
│   ├── wsc.csv → text + spans → pronoun resolution format
│   └── anli.csv → premise + hypothesis → entailment format
└── Return: List of {category, question, answer} dicts
```

**Example transformations:**
- **BoolQ**: `"Is this true? Context: [passage]"` 
- **WSC**: `"[text] (Does 'span1' refer to 'span2'?)"`
- **ANLI**: `"Premise: X. Hypothesis: Y. Is the hypothesis entailed?"`

### 2. **Vector Index Building** (`src/utils/vector_index.py`)

**Process:**
```
1. Initialize SentenceTransformer (all-MiniLM-L6-v2)
2. Load all datasets via data_loader.load_all(sample_n=200)
3. For each sample:
   ├── Combine question + answer into text
   ├── Generate embedding vector (384 dimensions)
   └── Add to FAISS index
4. Index is ready for similarity search
```

**Embedding:**
- Text → 384-dimensional vector
- Stored in FAISS IndexFlatL2 (L2 distance)
- Enables fast similarity search

### 3. **Similarity Query**

**Process:**
```
User question → Embed → Search FAISS index → Find top_k similar
                                                      │
                                                      ▼
                    Returns: [{sample, similarity}, ...]
```

## 🔄 Agent Execution Flow

### Baseline Agent
```
Question → ModelClient.generate() → Ollama → Answer
```

### Configurable Agent
```
Question
    │
    ├─→ Planner.plan() → Steps
    │
    ├─→ Tools.math_tool() → Check for math
    │   └─→ If math found: Use safe_eval()
    │   └─→ If no math: Continue
    │
    ├─→ Reasoner.reason(Plan + Question)
    │   └─→ ModelClient.generate() → Ollama
    │   └─→ Answer
    │
    ├─→ Memory.remember(question, answer)
    │
    └─→ Reflection.evaluate(question, answer, expected)
        └─→ Score + Comment
```

## 🔌 Component Connections

### Model Client (`src/utils/model_client.py`)
- **Connects to**: Ollama service (local)
- **Used by**: Reasoner, BaselineAgent
- **Function**: Wraps Ollama API calls

### Config File (`src/config/base_config.yaml`)
- **Read by**: ConfigurableAgent
- **Controls**: Model selection, feature flags

### Vector Index (`src/utils/vector_index.py`)
- **Uses**: data_loader.py (loads datasets)
- **Used by**: interactive_eval.py (finds similar examples)

### Graph Logger (`src/utils/graph_logger.py`)
- **Connects to**: Neo4j database (optional)
- **Used by**: interactive_eval.py (logs runs)

## 🚀 How to Start the System

### Option 1: Interactive Evaluation (CLI)
```bash
cd src
python -m evaluation.interactive_eval
```

### Option 2: Web Dashboard
```bash
cd src
python web/dashboard.py
```
Then open: http://localhost:5000

## 📝 Data Flow Summary

1. **Startup**: Load datasets → Build vector index → Initialize agents
2. **Question Input**: User provides question
3. **Similarity Search**: Find similar examples from datasets
4. **Agent Processing**: 
   - Baseline: Direct answer
   - Configurable: Plan → Tools → Reason → Memory → Reflect
5. **Evaluation**: Calculate BLEU/ROUGE (if expected provided)
6. **Logging**: Store to Neo4j (if available)
7. **Output**: Display results
8. **Loop**: Back to step 2 for next question











