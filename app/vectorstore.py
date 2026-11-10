"""FAISS-backed vendor-name normalization ("ACME Ltd" == "Acme Limited").

To swap in Pinecone, keep the same two methods: lookup() and canonicalize().
Tune `threshold` on your own vendors: too low merges different companies.
"""
import json
import os

import faiss
from sentence_transformers import SentenceTransformer

DIM = 384  # all-MiniLM-L6-v2


class VendorIndex:
    def __init__(self, directory: str = "data/vendors", threshold: float = 0.85):
        self.threshold = threshold
        os.makedirs(directory, exist_ok=True)
        self.model = SentenceTransformer("all-MiniLM-L6-v2")
        self.idx_path = os.path.join(directory, "vendors.index")
        self.names_path = os.path.join(directory, "names.json")
        if os.path.exists(self.idx_path) and os.path.exists(self.names_path):
            self.index = faiss.read_index(self.idx_path)
            with open(self.names_path, encoding="utf-8") as f:
                self.names = json.load(f)
        else:
            self.index = faiss.IndexFlatIP(DIM)  # cosine on normalized vectors
            self.names = []

    def _embed(self, text: str):
        return self.model.encode([text.lower().strip()], normalize_embeddings=True).astype("float32")

    def lookup(self, name: str):
        """Return (canonical_name or None, similarity)."""
        if not self.names:
            return None, 0.0
        scores, ids = self.index.search(self._embed(name), 1)
        score = float(scores[0][0])
        return (self.names[int(ids[0][0])], score) if score >= self.threshold else (None, score)

    def canonicalize(self, name: str) -> str:
        """Find the existing canonical vendor, or register this one as new."""
        found, _ = self.lookup(name)
        if found:
            return found
        self.index.add(self._embed(name))
        self.names.append(name)
        faiss.write_index(self.index, self.idx_path)
        with open(self.names_path, "w", encoding="utf-8") as f:
            json.dump(self.names, f, ensure_ascii=False)
        return name
