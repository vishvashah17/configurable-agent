# Persona System Documentation

## Overview

The persona system enables the agent to adapt its behavior and expertise based on the type of question being asked. This creates more specialized and contextually appropriate responses for all dataset types.

## Supported Datasets and Personas

The system supports **10 specialized personas** covering all your datasets:

1. **Mathematician** - For GSM8K, ASDiv (math word problems)
2. **Boolean QA** - For BoolQ, boolean-questions (yes/no questions)
3. **Inference Specialist** - For ANLI (natural language inference)
4. **Pronoun Resolver** - For WSC (Winograd Schema Challenge)
5. **Formal Logician** - For LogicBench (propositional, first-order, non-monotonic logic)
6. **Rule-Based Reasoner** - For RuleTaker (rule-based reasoning)
7. **Logician** - For ProofWriter (logical reasoning with proofs)
8. **Linguist** - For general linguistic analysis
9. **Scientist** - For scientific questions
10. **General** - Default for general questions

## How It Works

### 1. **Question Classification**

When a question is received, the `PersonaClassifier` analyzes it to determine the most appropriate persona:

- **Mathematical Questions**: Detects math keywords (calculate, solve, equation, etc.) and patterns (arithmetic expressions, percentages, etc.)
- **Boolean Questions**: Detects yes/no question patterns (is, are, does, can, etc.)
- **Inference Questions**: Detects entailment keywords (premise, hypothesis, entails, etc.)
- **Pronoun Resolution**: Detects pronoun-related keywords (refer, antecedent, span, etc.)
- **Formal Logic**: Detects formal logic terms (modus ponens, propositional logic, etc.)
- **Rule-Based**: Detects rule-based reasoning terms (theory, assertion, fact, etc.)
- **Linguistic Questions**: Detects language-related keywords (meaning, grammar, semantics, translation, etc.)
- **Logical Questions**: Detects logic keywords (reasoning, inference, proof, etc.)
- **Scientific Questions**: Detects scientific keywords (experiment, hypothesis, theory, etc.)
- **General Questions**: Default persona for questions that don't fit specialized categories

### 2. **Persona-Specific Prompts**

Each persona has a specialized system prompt that guides the agent's behavior:

#### **Mathematician Persona**
- Emphasizes step-by-step mathematical reasoning
- Uses proper mathematical notation
- Verifies calculations
- Explains mathematical principles
- Considers edge cases

#### **Linguist Persona**
- Focuses on word meanings, context, and nuance
- Analyzes grammatical structure and syntax
- Examines semantic relationships
- Considers cultural and contextual factors
- Uses precise linguistic terminology

#### **Logician Persona**
- Applies formal reasoning principles
- Checks for validity and soundness
- Uses logical notation
- Constructs clear logical proofs

#### **Scientist Persona**
- Applies scientific methodology
- Considers empirical evidence
- Uses precise scientific terminology
- Analyzes cause-and-effect relationships

#### **Boolean QA Persona**
- Expert at answering yes/no and boolean questions
- Carefully reads context and passages
- Bases answers strictly on provided information
- Distinguishes between stated facts and inferences
- Provides precise true/false or yes/no answers

#### **Inference Specialist Persona**
- Specializes in natural language inference and entailment
- Determines relationships: entailment, contradiction, or neutral
- Analyzes semantic relationships beyond surface matching
- Considers quantifiers, negation, and logical operators
- Explains reasoning clearly

#### **Formal Logician Persona**
- Expert in formal logic systems (propositional, first-order, non-monotonic)
- Recognizes and applies inference rules (modus ponens, modus tollens, etc.)
- Uses precise logical notation
- Handles quantifiers and complex logical structures
- Constructs formal proofs

#### **Rule-Based Reasoner Persona**
- Expert in rule-based reasoning and knowledge representation
- Identifies facts and rules in knowledge bases
- Traces reasoning chains from facts through rules
- Handles rule dependencies and interactions
- Verifies logical consistency

#### **Pronoun Resolver Persona**
- Expert in pronoun resolution and coreference
- Analyzes context to identify pronoun referents
- Considers grammatical and semantic cues
- Handles Winograd Schema Challenge problems
- Explains referent choices clearly

#### **General Persona**
- Balanced approach for general questions
- Clear and well-reasoned responses
- Appropriate terminology for the subject

## Usage Examples

### Example 1: Mathematical Question
```python
question = "Janet's ducks lay 16 eggs per day. She eats three for breakfast every morning and bakes muffins for her friends every day with four. She sells the remainder at the farmers' market daily for $2 per fresh duck egg. How much in dollars does she make every day at the farmers' market?"

# Agent will:
# 1. Classify as "mathematician" persona
# 2. Use mathematician system prompt
# 3. Show step-by-step calculations
# 4. Verify the math
```

### Example 2: Linguistic Question
```python
question = "What is the meaning of the word 'ephemeral' and how is it used in literature?"

# Agent will:
# 1. Classify as "linguist" persona
# 2. Use linguist system prompt
# 3. Provide detailed linguistic analysis
# 4. Consider contextual usage
```

### Example 3: Boolean Question (BoolQ)
```python
question = "Is France the same timezone as the UK? Context: [passage about timezones]"

# Agent will:
# 1. Classify as "boolean_qa" persona
# 2. Use boolean QA system prompt
# 3. Carefully analyze the context
# 4. Provide precise yes/no answer
```

### Example 4: Inference Question (ANLI)
```python
question = "Premise: X. Hypothesis: Y. Is the hypothesis entailed?"

# Agent will:
# 1. Classify as "inference_specialist" persona
# 2. Use inference specialist system prompt
# 3. Analyze entailment relationship
# 4. Determine if hypothesis follows from premise
```

### Example 5: Pronoun Resolution (WSC)
```python
question = "The ball crashed through the table because it was made of styrofoam. Does 'it' refer to the ball or table?"

# Agent will:
# 1. Classify as "pronoun_resolver" persona
# 2. Use pronoun resolver system prompt
# 3. Analyze context and semantic cues
# 4. Identify the correct referent
```

### Example 6: Formal Logic (LogicBench)
```python
question = "Apply modus ponens to prove the conclusion given these premises"

# Agent will:
# 1. Classify as "formal_logician" persona
# 2. Use formal logician system prompt
# 3. Apply formal inference rules
# 4. Construct formal proof
```

### Example 7: Rule-Based Reasoning (RuleTaker)
```python
question = "Given the theory with facts and rules, does this assertion follow?"

# Agent will:
# 1. Classify as "rule_based_reasoner" persona
# 2. Use rule-based reasoner system prompt
# 3. Trace reasoning chain
# 4. Verify logical consistency
```

## Configuration

In `src/config/base_config.yaml`:

```yaml
agent:
  personas: true  # Enable/disable persona system
```

## Implementation Details

### Files Modified/Created

1. **`src/agent/persona.py`** (NEW)
   - `PersonaClassifier`: Classifies questions into persona types
   - `PersonaPrompts`: Contains persona-specific system prompts

2. **`src/utils/model_client.py`** (MODIFIED)
   - Added `system_prompt` parameter to `generate()` method

3. **`src/agent/reasoner.py`** (MODIFIED)
   - Added persona support with `persona_prompt` parameter

4. **`src/agent/agent_controller.py`** (MODIFIED)
   - Integrated persona classification
   - Returns persona type in response

5. **`src/config/base_config.yaml`** (MODIFIED)
   - Added `personas: true` configuration option

## Customization

### Adding New Personas

1. Add keywords to `PersonaClassifier`:
```python
NEW_KEYWORDS = ['keyword1', 'keyword2', ...]
```

2. Add persona prompt to `PersonaPrompts.PERSONAS`:
```python
'new_persona': """Your custom system prompt here..."""
```

3. Update classification logic in `PersonaClassifier.classify()`

### Adjusting Classification Sensitivity

Modify the threshold in `PersonaClassifier.classify()`:
```python
if max_score >= 2:  # Lower = more sensitive, Higher = less sensitive
    return max(scores, key=scores.get)
```

## Response Format

The agent now returns persona information:

```python
{
    "plan": "...",
    "answer": "...",
    "reflection": {...},
    "persona": "mathematician"  # or "linguist", "logician", etc.
}
```

## Benefits

1. **Specialized Expertise**: Agent adapts to show domain-specific knowledge
2. **Better Context**: Responses are more appropriate for the question type
3. **Improved Accuracy**: Persona-specific prompts guide better reasoning
4. **User Experience**: More natural and expert-like responses

## Testing

Test with different question types:

```python
# Math question
agent.run("What is 15 * 23 + 45?")

# Linguistic question  
agent.run("Explain the difference between 'affect' and 'effect'")

# Logical question
agent.run("If A implies B, and B implies C, does A imply C?")
```

The persona will automatically adapt to each question type!

