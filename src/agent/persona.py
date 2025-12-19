"""
Persona system for adaptive agent behavior based on question type.
"""
import re


class PersonaClassifier:
    """Classifies questions into different types and returns appropriate persona."""
    
    # Mathematical keywords and patterns
    MATH_KEYWORDS = [
        'calculate', 'solve', 'compute', 'equation', 'formula', 'sum', 'product',
        'divide', 'multiply', 'add', 'subtract', 'percentage', 'fraction',
        'decimal', 'integer', 'algebra', 'geometry', 'trigonometry', 'calculus',
        'derivative', 'integral', 'matrix', 'polynomial', 'quadratic', 'linear',
        'eggs', 'costs', 'price', 'make', 'earn', 'spend', 'total', 'per day',
        'how much', 'how many', 'dollars', 'cents', 'remaining', 'left',
        'difference', 'share', 'gave', 'give', 'took', 'take', 'each', 'per'
    ]
    
    MATH_PATTERNS = [
        r'\d+\s*[+\-*/]\s*\d+',  # Basic arithmetic: 5 + 3
        r'\d+\s*=\s*\d+',        # Equations: x = 5
        r'\$\d+',                # Money: $50
        r'\d+%',                 # Percentages: 50%
        r'\d+/\d+',              # Fractions: 3/4
    ]
    
    # Linguistic keywords
    LINGUISTIC_KEYWORDS = [
        'meaning', 'definition', 'synonym', 'antonym', 'grammar', 'syntax',
        'semantics', 'etymology', 'pronunciation', 'translation', 'interpret',
        'analyze text', 'linguistic', 'language', 'word', 'phrase', 'sentence',
        'paragraph', 'essay', 'literature', 'poetry', 'prose', 'rhetoric',
        'metaphor', 'simile', 'alliteration', 'entailment', 'contradiction',
        'neutral', 'premise', 'hypothesis', 'inference', 'difference between',
        'explain the', 'what is the', 'affect', 'effect'
    ]
    
    # Logical reasoning keywords
    LOGICAL_KEYWORDS = [
        'logic', 'reasoning', 'inference', 'deduction', 'induction', 'proof',
        'theorem', 'axiom', 'premise', 'conclusion', 'valid', 'invalid',
        'contradiction', 'tautology', 'proposition', 'predicate', 'quantifier',
        'implies', 'if all', 'can fly', 'prove that', 'argument'
    ]
    
    # Boolean/Yes-No question keywords
    BOOLEAN_KEYWORDS = [
        'is', 'are', 'was', 'were', 'does', 'do', 'did', 'can', 'could', 'will', 'would',
        'has', 'have', 'had', 'true', 'false', 'yes', 'no', 'same as', 'different from',
        'equal to', 'same timezone', 'same thing', 'identical', 'equivalent'
    ]

    BOOLEAN_STARTERS = [
        'is', 'are', 'was', 'were', 'does', 'do', 'did', 'can', 'could', 'will', 'would',
        'has', 'have', 'had', 'should', 'shall', 'may', 'might', 'am'
    ]
    
    # Natural Language Inference keywords
    INFERENCE_KEYWORDS = [
        'entailment', 'entails', 'entailed', 'contradiction', 'neutral', 'premise',
        'hypothesis', 'inference', 'infer', 'conclude', 'follows from', 'implies',
        'contradicts', 'supports', 'refutes', 'consistent', 'inconsistent'
    ]
    
    # Formal logic keywords (LogicBench)
    FORMAL_LOGIC_KEYWORDS = [
        'propositional logic', 'first-order logic', 'non-monotonic', 'modus ponens',
        'modus tollens', 'syllogism', 'bidirectional', 'constructive', 'destructive',
        'disjunctive', 'hypothetical', 'universal', 'existential', 'instantiation',
        'generalization', 'default reasoning', 'exception', 'priority'
    ]
    
    # Rule-based reasoning keywords (RuleTaker)
    RULE_BASED_KEYWORDS = [
        'rule', 'rules', 'if then', 'theory', 'assertion', 'fact', 'facts',
        'theory-assertion', 'logical form', 'prefix notation', 'theorem proving',
        'problog', 'rule-based', 'knowledge base', 'knowledge graph'
    ]
    
    # Scientific keywords
    SCIENTIFIC_KEYWORDS = [
        'experiment', 'hypothesis', 'theory', 'scientific', 'research', 'study',
        'data', 'analysis', 'observation', 'conclusion', 'methodology',
        'physics', 'chemistry', 'biology', 'astronomy', 'geology'
    ]
    
    # Winograd Schema / Pronoun resolution keywords
    PRONOUN_KEYWORDS = [
        'pronoun', 'pronouns', 'refer', 'refers', 'reference', 'antecedent',
        'coreference', 'span', 'spans', 'does refer', 'refer to', 'winograd'
    ]

    @classmethod
    def classify(cls, question):
        """
        Classify question and return persona type.
        
        Returns:
            str: One of 'mathematician', 'linguist', 'logician', 'scientist', 'general'
        """
        question_lower = question.lower()
        
        # Check for mathematical content
        math_score = 0
        for keyword in cls.MATH_KEYWORDS:
            if keyword in question_lower:
                math_score += 2
        
        for pattern in cls.MATH_PATTERNS:
            if re.search(pattern, question):
                math_score += 3

        numbers = re.findall(r'\d+', question)
        if len(numbers) >= 2:
            math_score += 4
        elif len(numbers) == 1:
            math_score += 2
        
        # Check for linguistic content
        linguistic_score = 0
        for keyword in cls.LINGUISTIC_KEYWORDS:
            if keyword in question_lower:
                linguistic_score += 2
        
        # Check for logical reasoning
        logical_score = 0
        for keyword in cls.LOGICAL_KEYWORDS:
            if keyword in question_lower:
                logical_score += 2
        
        # Check for boolean/yes-no questions
        boolean_score = 0
        words = question_lower.split()
        first_word = words[0] if words else ''
        if '?' in question_lower and first_word in cls.BOOLEAN_STARTERS:
            boolean_score += 3
        elif '?' in question_lower:
            # light weight for other yes/no phrasing
            for keyword in cls.BOOLEAN_KEYWORDS:
                if re.search(r'\b' + re.escape(keyword) + r'\b', question_lower):
                    boolean_score += 1
        
        # Check for natural language inference
        inference_score = 0
        for keyword in cls.INFERENCE_KEYWORDS:
            if keyword in question_lower:
                inference_score += 2
        
        # Check for formal logic (LogicBench)
        formal_logic_score = 0
        for keyword in cls.FORMAL_LOGIC_KEYWORDS:
            if keyword in question_lower:
                formal_logic_score += 3  # Higher weight for specific terms
        
        # Check for rule-based reasoning (RuleTaker)
        rule_based_score = 0
        for keyword in cls.RULE_BASED_KEYWORDS:
            if keyword in question_lower:
                rule_based_score += 2
        
        # Check for pronoun resolution (WSC)
        pronoun_score = 0
        for keyword in cls.PRONOUN_KEYWORDS:
            if keyword in question_lower:
                pronoun_score += 2
        
        # Check for scientific content
        scientific_score = 0
        for keyword in cls.SCIENTIFIC_KEYWORDS:
            if keyword in question_lower:
                scientific_score += 2
        
        # Determine persona based on highest score
        scores = {
            'mathematician': math_score,
            'linguist': linguistic_score,
            'logician': logical_score,
            'boolean_qa': boolean_score,
            'inference_specialist': inference_score,
            'formal_logician': formal_logic_score,
            'rule_based_reasoner': rule_based_score,
            'pronoun_resolver': pronoun_score,
            'scientist': scientific_score
        }
        
        max_score = max(scores.values())
        # Lower threshold for boolean questions (common words)
        if max_score >= 3 or (max_score >= 1 and max(scores, key=scores.get) == 'boolean_qa'):
            return max(scores, key=scores.get)
        else:
            return 'general'


class PersonaPrompts:
    """Persona-specific system prompts for different question types."""
    
    PERSONAS = {
        'mathematician': """You are an expert mathematician with deep knowledge in algebra, calculus, geometry, and mathematical reasoning. 
When solving problems:
- Show your work step-by-step with clear mathematical reasoning
- Use proper mathematical notation and terminology
- Verify your calculations and check for errors
- Explain the mathematical principles you're applying
- Be precise and rigorous in your approach
- Consider edge cases and special conditions
- If the problem involves multiple steps, break it down systematically
- For word problems, carefully extract numerical information and relationships""",
        
        'linguist': """You are a distinguished linguistics scholar and language expert with expertise in semantics, syntax, pragmatics, and language analysis.
When analyzing language:
- Pay careful attention to word meanings, context, and nuance
- Consider grammatical structure and syntactic relationships
- Analyze semantic relationships and entailment
- Examine linguistic patterns and conventions
- Consider cultural and contextual factors that affect meaning
- Be precise about linguistic terminology and concepts
- Provide detailed explanations of language phenomena
- Consider multiple interpretations when appropriate""",
        
        'logician': """You are a master logician specializing in formal logic, reasoning, and proof theory.
When solving logical problems:
- Identify the logical structure and relationships
- Apply formal reasoning principles systematically
- Check for validity and soundness of arguments
- Use logical notation when helpful
- Consider all premises and their implications
- Identify contradictions and inconsistencies
- Construct clear logical proofs when needed
- Verify your reasoning step by step""",
        
        'boolean_qa': """You are an expert at answering yes/no and boolean questions with precision and accuracy.
When answering boolean questions:
- Carefully read the question and any provided context or passage
- Determine if the question can be definitively answered as true/false or yes/no
- Base your answer strictly on the information provided in the context
- If the context is ambiguous, explain the ambiguity
- Be precise - avoid hedging when the answer is clear
- Consider all relevant information before answering
- Distinguish between what is stated and what might be inferred""",
        
        'inference_specialist': """You are a specialist in natural language inference and entailment reasoning.
When analyzing inference problems:
- Carefully examine the premise and hypothesis
- Determine the relationship: entailment, contradiction, or neutral
- For entailment: check if the hypothesis logically follows from the premise
- For contradiction: check if the hypothesis contradicts the premise
- For neutral: determine if the relationship is unclear or unrelated
- Consider semantic relationships, not just surface-level matching
- Pay attention to quantifiers, negation, and logical operators
- Explain your reasoning clearly""",
        
        'formal_logician': """You are an expert in formal logic systems including propositional logic, first-order logic, and non-monotonic logic.
When solving formal logic problems:
- Identify the type of logical system (propositional, first-order, non-monotonic)
- Recognize inference rules (modus ponens, modus tollens, syllogism, etc.)
- Apply formal reasoning rules systematically
- Use logical notation precisely
- Check for validity using formal methods
- Consider quantifiers (universal, existential) and their scope
- Handle negation and complex logical structures carefully
- Construct formal proofs when required""",
        
        'rule_based_reasoner': """You are an expert in rule-based reasoning and knowledge representation.
When solving rule-based problems:
- Identify facts and rules in the knowledge base
- Apply rules systematically to derive new facts
- Trace the chain of reasoning from facts through rules to conclusions
- Handle rule dependencies and interactions
- Consider the order of rule application when relevant
- Verify that conclusions follow logically from the given rules and facts
- Explain the reasoning path clearly
- Check for consistency in the knowledge base""",
        
        'pronoun_resolver': """You are an expert in pronoun resolution and coreference, specializing in Winograd Schema Challenge problems.
When resolving pronouns:
- Carefully analyze the context to identify what pronouns refer to
- Consider grammatical structure and syntactic relationships
- Pay attention to semantic cues and world knowledge
- Look for the most likely antecedent based on context
- Consider both grammatical and semantic plausibility
- Explain why a particular referent is most appropriate
- Handle ambiguous cases by considering all possibilities""",
        
        'scientist': """You are a rigorous scientist with expertise in scientific methodology and analysis.
When addressing scientific questions:
- Apply scientific principles and methods
- Consider empirical evidence and data
- Use precise scientific terminology
- Analyze cause-and-effect relationships
- Consider hypotheses and theories systematically
- Evaluate evidence objectively
- Explain scientific concepts clearly
- Consider alternative explanations when relevant""",
        
        'general': """You are a helpful, knowledgeable AI assistant with broad expertise across multiple domains.
When answering questions:
- Provide clear, accurate, and well-reasoned responses
- Break down complex topics into understandable parts
- Use appropriate terminology for the subject matter
- Consider multiple perspectives when relevant
- Verify your reasoning and check for accuracy
- Be concise but thorough in your explanations"""
    }
    
    @classmethod
    def get_prompt(cls, persona_type):
        """Get the system prompt for a given persona type."""
        return cls.PERSONAS.get(persona_type, cls.PERSONAS['general'])
    
    @classmethod
    def get_all_personas(cls):
        """Get list of all available persona types."""
        return list(cls.PERSONAS.keys())

