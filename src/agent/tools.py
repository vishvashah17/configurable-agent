import ast
import operator as op
import re


class Tools:
    def __init__(self):
        # Allow only basic arithmetic operators
        self.allowed = {
            ast.Add: op.add,
            ast.Sub: op.sub,
            ast.Mult: op.mul,
            ast.Div: op.truediv
        }

    def safe_eval(self, expr):
        """Safely evaluate basic arithmetic expressions."""
        try:
            node = ast.parse(expr, mode='eval').body
            return self._eval(node)
        except Exception:
            return None

    def _eval(self, node):
        if isinstance(node, ast.Constant):  # Numbers
            return node.value
        if isinstance(node, ast.BinOp):  # Binary operations like 4+4
            return self.allowed[type(node.op)](
                self._eval(node.left), self._eval(node.right)
            )
        raise ValueError("Unsupported expression")

    def math_tool(self, text):
        """Detect and safely compute simple math expressions in text."""
        for token in text.split():
            if any(operator in token for operator in "+-*/"):
                # Clean token: remove all non-numeric and non-operator characters
                expr = re.sub(r"[^0-9+\-*/().]", "", token)
                value = self.safe_eval(expr)
                if value is not None:
                    return {"expr": expr, "value": value, "confidence": 0.9}
        return None
