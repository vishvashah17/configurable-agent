import yaml
from .planner import Planner
from .reasoner import Reasoner
from .memory import Memory
from .tools import Tools
from .reflection import Reflection
from .persona import PersonaClassifier, PersonaPrompts

class ConfigurableAgent:
    def __init__(self, config_path):
        with open(config_path, 'r') as f:
            cfg = yaml.safe_load(f)
        self.model_id = cfg["agent"]["model"]
        self.planner = Planner()
        self.reasoner = Reasoner(self.model_id)
        self.memory = Memory()
        self.tools = Tools()
        self.reflection = Reflection()
        # Persona system
        self.persona_classifier = PersonaClassifier()
        self.use_personas = cfg.get("agent", {}).get("personas", True)  # Enable by default

    def run(self, question, expected=None):
        # Classify question and get appropriate persona
        persona_type = None
        persona_prompt = None
        
        if self.use_personas:
            persona_type = self.persona_classifier.classify(question)
            persona_prompt = PersonaPrompts.get_prompt(persona_type)
        
        plan = self.planner.plan(question)
        tool_res = self.tools.math_tool(question)

        if tool_res and tool_res.get("value") is not None:
            answer = str(tool_res["value"])
        else:
            reasoning_input = f"Plan:\n{plan}\n\nQuestion:\n{question}\nAnswer:"
            answer = self.reasoner.reason(reasoning_input, persona_prompt=persona_prompt)

        
        self.memory.remember(question, answer)
        reflection = self.reflection.evaluate(question, answer, expected)
        
        return {
            "plan": plan, 
            "answer": answer, 
            "reflection": reflection,
            "persona": persona_type if self.use_personas else None
        }
