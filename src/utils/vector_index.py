import faiss
import numpy as np
from sentence_transformers import SentenceTransformer
from utils.data_loader import load_all


class DatasetVectorIndex:
    def __init__(self, sample_n=200, embed_model="all-MiniLM-L6-v2"):
        self.embedder = SentenceTransformer(embed_model)
        self.samples = load_all(sample_n)
        self._build_index()

    def _build_index(self):
        texts = [(s["question"] + " " + s.get("answer", "")).strip() for s in self.samples]
        self.embeddings = np.array(self.embedder.encode(texts, convert_to_numpy=True))
        dim = self.embeddings.shape[1]
        self.index = faiss.IndexFlatL2(dim)
        self.index.add(self.embeddings)

    def query(self, text, top_k=3):
        q_emb = self.embedder.encode([text], convert_to_numpy=True)
        D, I = self.index.search(q_emb, top_k)
        results = []
        for dist, idx in zip(D[0], I[0]):
            s = self.samples[idx]
            sim = 1 / (1 + dist)
            results.append({"sample": s, "similarity": float(sim)})
        return results






