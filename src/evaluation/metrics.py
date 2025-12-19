from nltk.translate.bleu_score import sentence_bleu, SmoothingFunction
from rouge_score import rouge_scorer

def compute_bleu(pred, ref):
    smoothie = SmoothingFunction().method4
    try:
        return sentence_bleu([ref.split()], pred.split(), smoothing_function=smoothie)
    except Exception:
        return 0.0

def compute_rouge(pred, ref):
    try:
        scorer = rouge_scorer.RougeScorer(['rougeL'], use_stemmer=True)
        return scorer.score(ref, pred)['rougeL'].fmeasure
    except Exception:
        return 0.0

