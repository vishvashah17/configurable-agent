# Quick Start Guide

## 🚀 Starting the System

### Prerequisites
1. Ollama installed and running (`ollama serve`)
2. Models downloaded (`ollama pull qwen3:8b`)
3. Python dependencies installed (`pip install -r requirements.txt`)

### Option 1: Web Dashboard (Recommended)

**Start the server:**
```bash
cd src
python web/dashboard.py
```

**Open in browser:**
```
http://localhost:5000
```

**What you'll see:**
- Beautiful web interface
- Form to enter questions
- Real-time results display
- Metrics and similar examples

### Option 2: Command Line Interface

**Run interactive evaluation:**
```bash
cd src
python -m evaluation.interactive_eval
```

**How to use:**
1. Enter your question when prompted
2. Optionally provide expected answer
3. View results (baseline, configurable agent, metrics)
4. Type 'exit' to quit

## 📊 Understanding the Results

### Baseline Agent
- **What it does**: Direct question → answer
- **Model**: Uses default Ollama model (qwen3:8b)
- **Use case**: Simple, fast responses

### Configurable Agent
- **What it does**: Multi-stage processing
  1. **Planner**: Breaks question into steps
  2. **Tools**: Checks for math expressions
  3. **Reasoner**: Uses LLM to generate answer
  4. **Memory**: Stores question-answer pair
  5. **Reflection**: Evaluates answer quality

### Metrics
- **BLEU**: Measures exact match similarity
- **ROUGE**: Measures semantic overlap
- **Execution Time**: Total processing time

### Similar Examples
- Shows top 3 similar questions from loaded datasets
- Helps understand what type of question it is
- Displays similarity score (0-1)

## 🔍 Dataset Processing

### What Gets Loaded?
- **gsm8k.csv**: Math problems (Arithmetic)
- **boolq.csv**: Yes/No questions (Boolean)
- **wsc.csv**: Pronoun resolution (Linguistic)
- **anli.csv**: Entailment tasks (Inference)
- **proofwriter.csv**: Logical reasoning (Logical Reasoning)

### How It's Processed?
1. **CSV Reading**: Each dataset is loaded with pandas
2. **Formatting**: Different column structures are normalized
3. **Embedding**: Questions+answers converted to vectors
4. **Indexing**: FAISS vector index built for fast search
5. **Querying**: User questions matched against index

### Sample Size
- Default: 200 samples per dataset
- Total: ~1000 samples in vector index
- Configurable via `sample_n` parameter

## 🛠️ Troubleshooting

### "Ollama connection failed"
- Make sure `ollama serve` is running
- Check if model is downloaded: `ollama list`

### "Neo4j connection failed"
- This is optional - system will work without it
- Only affects graph logging feature

### "Dataset not found"
- Check `datasets/` folder exists
- Verify CSV files are present
- Check file permissions

### "Model not available"
- Download model: `ollama pull qwen3:8b`
- Check Ollama service is running

## 📝 Example Questions to Try

1. **Math**: "What is 25 * 4 + 10?"
2. **History**: "Who was the president of USA in 2010?"
3. **Logic**: "If all cats are animals, and Fluffy is a cat, what can we conclude?"
4. **General**: "Explain how photosynthesis works"

## 🎯 Next Steps

1. **Customize Config**: Edit `src/config/base_config.yaml`
2. **Add Datasets**: Place CSV files in `datasets/` folder
3. **Modify Agents**: Edit agent modules in `src/agent/`
4. **View Architecture**: See `ARCHITECTURE.md` for details











