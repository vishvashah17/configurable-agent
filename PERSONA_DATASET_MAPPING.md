# Persona-Dataset Mapping Guide

## Complete Mapping of Personas to Datasets

This document shows how each persona maps to your datasets and when it will be activated.

### 1. **Mathematician Persona**
**Datasets:** GSM8K, ASDiv (nlu-asdiv-dataset-master)

**When Activated:**
- Questions with math keywords: calculate, solve, compute, equation, formula, etc.
- Questions with math patterns: arithmetic expressions (5 + 3), percentages (50%), money ($50), fractions
- Word problems with numerical information

**Example Questions:**
- "Janet's ducks lay 16 eggs per day. How much does she make?"
- "What is 15 * 23 + 45?"
- "If a shirt costs $50 and is 20% off, what's the final price?"

---

### 2. **Boolean QA Persona**
**Datasets:** BoolQ, boolean-questions-master

**When Activated:**
- Yes/no questions starting with: is, are, was, were, does, do, did, can, could, will, would
- Questions asking about equivalence: same as, identical, equivalent
- Questions that can be answered with true/false or yes/no

**Example Questions:**
- "Is France the same timezone as the UK?"
- "Does ethanol take more energy to make than it produces?"
- "Is house tax and property tax the same?"

---

### 3. **Inference Specialist Persona**
**Datasets:** ANLI

**When Activated:**
- Questions mentioning: premise, hypothesis, entailment, entails, entailed
- Questions asking about relationships: contradicts, supports, refutes, consistent
- Questions about inference: infer, conclude, follows from

**Example Questions:**
- "Premise: X. Hypothesis: Y. Is the hypothesis entailed?"
- "Does the premise entail the hypothesis?"
- "Is the hypothesis consistent with the premise?"

---

### 4. **Pronoun Resolver Persona**
**Datasets:** WSC

**When Activated:**
- Questions mentioning: pronoun, refer, refers, reference, antecedent, coreference
- Questions with "span" or "spans" (WSC format)
- Questions asking "Does X refer to Y?"

**Example Questions:**
- "The ball crashed through the table because it was made of styrofoam. Does 'it' refer to the ball or table?"
- "Bernard did not consider that he had done anything dishonest. Does 'he' refer to Bernard?"

---

### 5. **Formal Logician Persona**
**Datasets:** LogicBench-main

**When Activated:**
- Questions mentioning: propositional logic, first-order logic, non-monotonic logic
- Questions about inference rules: modus ponens, modus tollens, syllogism
- Questions about logical operations: universal instantiation, existential generalization
- Questions about logical types: bidirectional, constructive, destructive, disjunctive

**Example Questions:**
- "Apply modus ponens to prove the conclusion"
- "Using propositional logic, determine if this is valid"
- "Apply universal instantiation to this first-order logic statement"

---

### 6. **Rule-Based Reasoner Persona**
**Datasets:** ruletaker-master

**When Activated:**
- Questions mentioning: rule, rules, theory, assertion, fact, facts
- Questions about: theory-assertion, logical form, prefix notation
- Questions about: theorem proving, problog, knowledge base
- Questions asking if assertions follow from theories

**Example Questions:**
- "Given the theory and rules, does this assertion follow?"
- "Apply the rules to determine if the fact is true"
- "Using the knowledge base, prove this assertion"

---

### 7. **Logician Persona**
**Datasets:** ProofWriter

**When Activated:**
- Questions about: logic, reasoning, inference, proof, theorem, axiom
- Questions asking: valid, invalid, contradiction, tautology
- Questions about: proposition, predicate, quantifier
- General logical reasoning questions

**Example Questions:**
- "If all birds can fly, and penguins are birds, can penguins fly?"
- "Prove that if A implies B, and B implies C, then A implies C"
- "Is this argument valid or invalid?"

---

### 8. **Linguist Persona**
**Datasets:** General linguistic questions

**When Activated:**
- Questions about: meaning, definition, grammar, syntax, semantics, etymology
- Questions about: translation, interpretation, language analysis
- Questions about: word, phrase, sentence structure
- General language-related questions

**Example Questions:**
- "What is the meaning of the word 'ephemeral'?"
- "Explain the difference between 'affect' and 'effect'"
- "What is the etymology of the word 'philosophy'?"

---

### 9. **Scientist Persona**
**Datasets:** General scientific questions

**When Activated:**
- Questions about: experiment, hypothesis, theory, scientific method
- Questions about: research, study, data, analysis, observation
- Questions about specific sciences: physics, chemistry, biology, etc.

**Example Questions:**
- "Explain the scientific method"
- "What is the hypothesis in this experiment?"
- "How does photosynthesis work?"

---

### 10. **General Persona**
**Datasets:** Questions that don't fit specialized categories

**When Activated:**
- Questions that don't match any specialized persona keywords
- General knowledge questions
- Questions requiring broad expertise

**Example Questions:**
- "What is the capital of France?"
- "Tell me about the weather"
- "Who won the World Cup in 2022?"

---

## Classification Priority

The system uses a scoring mechanism where:
1. **Higher specificity = Higher priority**: Formal logic terms score higher than general logic terms
2. **Multiple matches**: The persona with the highest score wins
3. **Threshold**: Most personas require a score of 2+, boolean_qa requires 1+ (since it uses common words)

## Customization

You can adjust the classification by:
1. Adding keywords to the keyword lists in `src/agent/persona.py`
2. Adjusting scoring weights (currently 1-3 points per keyword match)
3. Modifying the threshold in `PersonaClassifier.classify()`

## Testing

Run the test script to see classification in action:
```bash
python test_personas.py
```

This will show you which persona is selected for various question types.

