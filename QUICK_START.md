# Quick Start Guide

## Running the Interactive Evaluation

### Option 1: From Project Root (Easiest)
```bash
python run_interactive.py
```

### Option 2: From src Directory
```bash
cd src
python -m evaluation.interactive_eval
```

### Option 3: Direct Python Script
```bash
cd src
python evaluation/interactive_eval.py
```

## Running the Web Dashboard

```bash
cd src
python web/dashboard.py
```

Then open: http://localhost:5000

## What You'll See

When you run the interactive evaluation, you'll see:

1. **Persona Detection**: The system automatically detects the question type and shows:
   ```
   [Persona: Mathematician]
   ```

2. **Agent Output**: 
   - Baseline agent answer (simple direct response)
   - Configurable agent answer (with planning, reasoning, persona-specific behavior)

3. **Similar Examples**: Top 3 similar questions from your datasets

4. **Metrics**: BLEU and ROUGE scores (if expected answer provided)

## Example Questions to Try

### Mathematical (Mathematician Persona)
```
What is 15 * 23 + 45?
Janet's ducks lay 16 eggs per day. She eats three for breakfast. How much does she make?
```

### Boolean (Boolean QA Persona)
```
Is France the same timezone as the UK?
Does ethanol take more energy to make than it produces?
```

### Inference (Inference Specialist Persona)
```
Premise: All birds can fly. Hypothesis: Penguins can fly. Is the hypothesis entailed?
```

### Pronoun Resolution (Pronoun Resolver Persona)
```
The ball crashed through the table because it was made of styrofoam. Does 'it' refer to the ball or table?
```

## Troubleshooting

### ModuleNotFoundError
- Make sure you're running from the correct directory
- Use `run_interactive.py` from project root for easiest setup

### Neo4j Connection Issues
- The system will work without Neo4j (logging is optional)
- If you want Neo4j logging, make sure Neo4j is running

### Model Not Found
- Make sure Ollama is running: `ollama serve`
- Check that the model exists: `ollama list`
- Default model is `qwen3:8b`

