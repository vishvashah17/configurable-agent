import os
import pandas as pd

DATA_ROOT = os.path.join(os.path.dirname(__file__), "..", "..", "datasets")


def load_csv(name, category, n=5, question_col="question", answer_col="answer"):
    """
    Load CSV file with flexible column mapping.
    
    Args:
        name: CSV filename
        category: Category name for the dataset
        n: Number of samples to load
        question_col: Column name for questions
        answer_col: Column name for answers
    """
    path = os.path.join(DATA_ROOT, name)
    if not os.path.exists(path):
        return []
    
    try:
        df = pd.read_csv(path).head(n)
        data = []
        
        for _, r in df.iterrows():
            # Handle different column structures
            question = ""
            answer = ""
            
            if name == "boolq.csv":
                # boolq has question + passage
                q = str(r.get("question", ""))
                p = str(r.get("passage", ""))
                question = f"{q} Context: {p}"
                answer = str(r.get("label", ""))
            elif name == "wsc.csv":
                # wsc has text with pronoun resolution
                text = str(r.get("text", ""))
                span1 = str(r.get("span1_text", ""))
                span2 = str(r.get("span2_text", ""))
                question = f"{text} (Does '{span1}' refer to '{span2}'?)"
                answer = str(r.get("label", ""))
            elif name == "anli.csv":
                # anli has premise + hypothesis
                premise = str(r.get("premise", ""))
                hypothesis = str(r.get("hypothesis", ""))
                question = f"Premise: {premise}. Hypothesis: {hypothesis}. Is the hypothesis entailed?"
                answer = str(r.get("label", ""))
            else:
                # Default: standard question/answer format (gsm8k, proofwriter)
                question = str(r.get(question_col, ""))
                answer = str(r.get(answer_col, ""))
            
            if question:  # Only add if we have a question
                data.append({
                    "category": category,
                    "question": question,
                    "answer": answer
                })
        
        return data
    except Exception as e:
        print(f"Warning: Failed to load {name}: {e}")
        return []


def load_all(sample_n=5):
    """
    Load all available datasets.
    
    Args:
        sample_n: Number of samples to load from each dataset
    """
    data = []
    
    # Standard question-answer format
    data += load_csv("gsm8k.csv", "Arithmetic", sample_n)
    data += load_csv("proofwriter.csv", "Logical Reasoning", sample_n)
    
    # Special formats (handled with custom logic in load_csv)
    data += load_csv("boolq.csv", "Boolean", sample_n)
    data += load_csv("wsc.csv", "Linguistic", sample_n)
    data += load_csv("anli.csv", "Inference", sample_n)
    
    return data

