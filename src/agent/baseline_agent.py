from utils.model_client import get_client


class BaselineAgent:
    def __init__(self, model_id=None):
        self.client = get_client(model_id)

    def run(self, question):
        prompt = f"Answer briefly:\n{question}\nAnswer:"
        return self.client.generate(prompt)











