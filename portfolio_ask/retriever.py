from __future__ import annotations

import json
import pickle
from pathlib import Path
from typing import Optional

import numpy as np

try:
    import faiss
    from sentence_transformers import SentenceTransformer
    _HAS_DEPS = True
except ImportError:
    _HAS_DEPS = False

_MODEL_NAME = "sentence-transformers/all-MiniLM-L6-v2"
_CACHE_DIR = ".vector_cache"


class VectorStore:
    def __init__(self, model_name: str = _MODEL_NAME) -> None:
        if not _HAS_DEPS:
            raise ImportError(
                "Missing deps. Run: pip install faiss-cpu sentence-transformers"
            )
        self.model = SentenceTransformer(model_name)
        self.index: Optional[faiss.Index] = None
        self.documents: list[str] = []
        self.metadata: list[dict] = []

    def add_documents(self, texts: list[str], metadata: Optional[list[dict]] = None) -> None:
        if not texts:
            return
        embeddings = self.model.encode(texts, convert_to_numpy=True, show_progress_bar=False)
        norms = np.linalg.norm(embeddings, axis=1, keepdims=True)
        norms = np.where(norms == 0, 1, norms)
        embeddings = (embeddings / norms).astype(np.float32)
        if self.index is None:
            self.index = faiss.IndexFlatIP(embeddings.shape[1])
        self.index.add(embeddings)
        self.documents.extend(texts)
        self.metadata.extend(metadata or [{} for _ in texts])

    def search(self, query: str, k: int = 5) -> list[dict]:
        if self.index is None or self.index.ntotal == 0:
            return []
        q_emb = self.model.encode([query], convert_to_numpy=True).astype(np.float32)
        q_norm = np.linalg.norm(q_emb)
        if q_norm > 0:
            q_emb = q_emb / q_norm
        k = min(k, self.index.ntotal)
        scores, indices = self.index.search(q_emb, k)
        return [
            {
                "text": self.documents[idx],
                "metadata": self.metadata[idx],
                "score": float(score),
            }
            for score, idx in zip(scores[0], indices[0])
            if idx >= 0
        ]

    def save(self, path: Path) -> None:
        path.mkdir(parents=True, exist_ok=True)
        faiss.write_index(self.index, str(path / "index.faiss"))
        with open(path / "docs.pkl", "wb") as f:
            pickle.dump({"documents": self.documents, "metadata": self.metadata}, f)

    @classmethod
    def load(cls, path: Path, model_name: str = _MODEL_NAME) -> "VectorStore":
        store = cls(model_name)
        store.index = faiss.read_index(str(path / "index.faiss"))
        with open(path / "docs.pkl", "rb") as f:
            data = pickle.load(f)
        store.documents = data["documents"]
        store.metadata = data["metadata"]
        return store


def _chunk_portfolio(portfolio_path: Path) -> tuple[list[str], list[dict]]:
    portfolio = json.loads(portfolio_path.read_text(encoding="utf-8"))
    texts, meta = [], []
    for h in portfolio["holdings"]:
        text = (
            f"Holding: {h['company']} (ticker: {h['ticker']})\n"
            f"Type: {h['type']}, Sector: {h['sector']}\n"
            f"Quantity: {h['quantity']} units, Avg Buy Price: ₹{h['avg_buy_price']:,.2f}\n"
            f"Current Price: ₹{h['current_price']:,.2f}, Current Value: ₹{h['current_value']:,.0f}\n"
            f"Portfolio Weight: {h['weight_pct']:.2f}%\n"
            f"Unrealized P&L: ₹{h['unrealized_pnl']:,.0f} ({h['unrealized_pnl_pct']:+.2f}%)"
        )
        texts.append(text)
        meta.append({"source": "portfolio", "ticker": h["ticker"], "type": "holding"})
    return texts, meta


def _chunk_glossary(glossary_path: Path) -> tuple[list[str], list[dict]]:
    content = glossary_path.read_text(encoding="utf-8")
    texts, meta = [], []
    current_term = ""
    current_lines: list[str] = []

    def flush():
        if current_term and current_lines:
            texts.append(f"{current_term}\n" + "\n".join(current_lines))
            meta.append({"source": "glossary", "term": current_term, "type": "definition"})

    for line in content.splitlines():
        if line.startswith("## "):
            flush()
            current_term = line[3:].strip()
            current_lines = []
        elif line.strip() and not line.startswith("# "):
            current_lines.append(line.strip())
    flush()
    return texts, meta


def _chunk_news(news_dir: Path) -> tuple[list[str], list[dict]]:
    texts, meta = [], []
    for f in sorted(news_dir.glob("*.md")):
        content = f.read_text(encoding="utf-8")
        texts.append(content)
        meta.append({"source": f.name, "type": "news"})
    return texts, meta


def build_store(data_dir: Path, force_rebuild: bool = False) -> VectorStore:
    cache_path = data_dir.parent / _CACHE_DIR
    if not force_rebuild and (cache_path / "index.faiss").exists():
        return VectorStore.load(cache_path)

    store = VectorStore()
    p_texts, p_meta = _chunk_portfolio(data_dir / "portfolio.json")
    g_texts, g_meta = _chunk_glossary(data_dir / "glossary.md")
    n_texts, n_meta = _chunk_news(data_dir / "news")

    store.add_documents(p_texts, p_meta)
    store.add_documents(g_texts, g_meta)
    store.add_documents(n_texts, n_meta)
    store.save(cache_path)
    return store
