class Reflection:
    def evaluate(self, question, answer, expected=None):
        if not expected:
            return {"score": None, "comment": "No ground truth"}
        expected, answer = str(expected).lower(), str(answer).lower()
        match = sum(1 for w in expected.split() if w in answer)
        score = match / max(1, len(expected.split()))
        return {"score": score, "comment": "Good" if score > 0.5 else "Weak"}

