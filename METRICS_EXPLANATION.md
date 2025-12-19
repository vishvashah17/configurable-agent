# Why BLEU and ROUGE Metrics?

## Overview

BLEU and ROUGE are **standard evaluation metrics** in Natural Language Processing (NLP) used to measure the quality of generated text by comparing it to reference (expected) answers.

## What They Measure

### BLEU (Bilingual Evaluation Understudy)
- **Focus**: **Precision** - How many words/phrases from the generated answer match the reference?
- **Measures**: N-gram (word sequences) overlap
- **Range**: 0.0 to 1.0 (higher is better)
- **Best for**: Measuring exact word/phrase matches

**Example:**
```
Reference: "The cat sat on the mat"
Generated: "A cat sat on a mat"
BLEU Score: ~0.7 (good match, but missing "the" and has "a" instead)
```

### ROUGE (Recall-Oriented Understudy for Gisting Evaluation)
- **Focus**: **Recall** - How much of the reference answer is captured in the generated answer?
- **Measures**: Overlapping units (words, phrases, longest common subsequence)
- **Range**: 0.0 to 1.0 (higher is better)
- **Best for**: Measuring semantic overlap and coverage

**Example:**
```
Reference: "The cat sat on the mat"
Generated: "The cat was sitting on the mat"
ROUGE Score: ~0.8 (good semantic overlap, captures meaning)
```

## Why Use Both?

### Complementary Strengths

1. **BLEU** catches:
   - Exact word matches
   - Precise terminology
   - Formulaic answers (like math solutions)

2. **ROUGE** catches:
   - Semantic similarity
   - Paraphrased but correct answers
   - Different wording with same meaning

### Example Scenario

**Question**: "What is 2 + 2?"

**Reference Answer**: "The answer is 4"

**Generated Answer 1**: "4"
- BLEU: Low (missing words "The answer is")
- ROUGE: Medium (has the key number "4")

**Generated Answer 2**: "The answer is four"
- BLEU: Low (word "four" instead of "4")
- ROUGE: High (captures all semantic content)

**Generated Answer 3**: "The answer is 4"
- BLEU: High (exact match)
- ROUGE: High (perfect semantic match)

## When They're Used in This System

### In `interactive_eval.py`:
```python
bleu = compute_bleu(conf["answer"], expected or "") if expected else 0.0
rouge = compute_rouge(conf["answer"], expected or "") if expected else 0.0
```

### When They're Calculated:
- **Only when expected answer is provided** (optional)
- Compares agent's answer to the ground truth
- Helps evaluate agent performance

## Why They're Important

### 1. **Objective Evaluation**
- Provides numerical scores instead of subjective judgment
- Allows comparison across different runs
- Tracks improvement over time

### 2. **Dataset Evaluation**
- Your datasets (GSM8K, BoolQ, ANLI, etc.) have expected answers
- BLEU/ROUGE help measure how well the agent matches those answers
- Useful for benchmarking and improvement

### 3. **Different Answer Styles**
- Some questions have multiple valid phrasings
- ROUGE captures semantic equivalence
- BLEU rewards exact matches

### 4. **Research Standard**
- Widely used in NLP research
- Allows comparison with other systems
- Standard metrics for text generation tasks

## Limitations

### BLEU Limitations:
- ❌ Doesn't handle paraphrasing well
- ❌ Penalizes different but correct wordings
- ❌ May miss semantic correctness

### ROUGE Limitations:
- ❌ May give high scores to verbose but less precise answers
- ❌ Doesn't penalize extra irrelevant information
- ❌ May miss subtle errors

### Why Use Both:
- **Together** they provide a more complete picture
- BLEU for precision, ROUGE for recall
- Better evaluation than either alone

## Real-World Example

**Question**: "Janet's ducks lay 16 eggs per day. She eats 3 for breakfast. How much does she make?"

**Expected Answer**: "Janet sells 13 eggs per day. At $2 per egg, she makes $26."

**Agent Answer 1**: "She makes $26 per day."
- BLEU: Medium (has key number "$26")
- ROUGE: Medium (captures main answer)

**Agent Answer 2**: "Janet sells 13 eggs per day. At $2 per egg, she makes $26."
- BLEU: High (exact match)
- ROUGE: High (perfect match)

**Agent Answer 3**: "The calculation: 16 - 3 = 13 eggs sold. 13 × $2 = $26. So she makes $26."
- BLEU: Medium (has answer but extra words)
- ROUGE: High (captures all information)

## In Your System

### Current Implementation:
- **Optional**: Only calculated if expected answer provided
- **Displayed**: In both CLI and web dashboard
- **Used for**: Evaluating agent performance on your datasets

### When to Provide Expected Answer:
- ✅ Testing on dataset examples (GSM8K, BoolQ, etc.)
- ✅ Benchmarking agent improvements
- ✅ Comparing baseline vs configurable agent
- ❌ Not needed for general questions

## Summary

**BLEU** = "Did you use the right words?"
**ROUGE** = "Did you capture the meaning?"

**Together** = Comprehensive evaluation of answer quality!

They're industry-standard metrics that help you:
1. Measure agent performance objectively
2. Compare different configurations
3. Track improvements over time
4. Evaluate on your datasets with ground truth

