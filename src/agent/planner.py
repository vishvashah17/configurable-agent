class Planner:
    def plan(self, task_text):
        parts = [p.strip() for p in task_text.split(".") if p.strip()]
        steps = [f"{i+1}. {p}" for i, p in enumerate(parts)]
        return "Steps:\n" + "\n".join(steps)











