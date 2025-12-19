import ollama


class ModelClient:
    def __init__(self, model_id="qwen3:8b"):
        self.model_id = model_id

    def generate(self, prompt, max_new_tokens=256, temperature=0.3, system_prompt=None):
        """
        Uses local Ollama model for text generation.
        
        Args:
            prompt: User prompt/question
            max_new_tokens: Maximum tokens to generate
            temperature: Sampling temperature
            system_prompt: Custom system prompt (persona). If None, uses default.
        """
        try:
            system_content = system_prompt or "You are a helpful reasoning AI agent."
            response = ollama.chat(model=self.model_id, messages=[
                {"role": "system", "content": system_content},
                {"role": "user", "content": prompt}
            ])
            return response["message"]["content"]
        except Exception as e:
            return f"[Error generating response: {e}]"


# Client cache for multiple models
_clients = {}

def get_client(model_id=None):
    """
    Get or create a ModelClient for the specified model.
    Supports multiple models by caching clients per model_id.
    """
    global _clients
    model_key = model_id or "qwen3:8b"
    if model_key not in _clients:
        _clients[model_key] = ModelClient(model_key)
    return _clients[model_key]

