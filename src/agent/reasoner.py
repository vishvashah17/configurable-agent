from utils.model_client import get_client


class Reasoner:
    def __init__(self, model_id=None, persona_prompt=None):
        """
        Initialize Reasoner with optional persona.
        
        Args:
            model_id: Model identifier for Ollama
            persona_prompt: System prompt for persona (e.g., mathematician, linguist)
        """
        self.client = get_client(model_id)
        self.persona_prompt = persona_prompt

    def reason(self, text, persona_prompt=None):
        """
        Generate reasoning with optional persona.
        
        Args:
            text: Input text/question
            persona_prompt: Override persona prompt for this call (optional)
        """
        prompt_to_use = persona_prompt or self.persona_prompt
        return self.client.generate(text, system_prompt=prompt_to_use)
