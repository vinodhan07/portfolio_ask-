from __future__ import annotations

import json
import pickle
from pathlib import Path
from typing import Optional

import numpy as np

try:
    import faiss
    import os
    os.environ["HF_HUB_DISABLE_PROGRESS_BARS"] = "1"
    
    import transformers
    transformers.logging.set_verbosity_error()
    if hasattr(transformers.utils.logging, "disable_progress_bar"):
        transformers.utils.logging.disable_progress_bar()
        
    import huggingface_hub
    if hasattr(huggingface_hub, "logging") and hasattr(huggingface_hub.logging, "disable_progress_bar"):
        huggingface_hub.logging.disable_progress_bar()

    # Disable tqdm globally to silence weight loading logs
    from tqdm import tqdm
    from functools import partialmethod
    tqdm.__init__ = partialmethod(tqdm.__init__, disable=True)
    
    from sentence_transformers import SentenceTransformer
    _HAS_DEPS = True
except ImportError as e:
    _IMPORT_ERROR = str(e)
    _HAS_DEPS = False

_MODEL_NAME = "sentence-transformers/all-MiniLM-L6-v2"
_STORE_DIR = ".faiss_store"
_INDEX_FILE = "portfolio.faiss"
_META_FILE = "portfolio_meta.pkl"


class VectorStore:
    def __init__(self, model_name: str = _MODEL_NAME) -> None:
        if not _HAS_DEPS:
            raise ImportError(
                f"Missing dependencies: {_IMPORT_ERROR}.\n"
                "CRITICAL: Please use 'make start' to run the app correctly."
            )
        self.model = SentenceTransformer(model_name)
        self.index: Optional[faiss.Index] = None
        self.documents: list[str] = []
        self.metadata: list[dict] = []

    def add_documents(self, texts: list[str], metadata: Optional[list[dict]] = None) -> None:
        if not texts:
            return
        # Generate embeddings (Bi-Encoder approach)
        embeddings = self.model.encode(texts).astype("float32")

        if self.index is None:
            # Use IndexFlatL2 for simplicity (Euclidean distance)
            dim = embeddings.shape[1]
            self.index = faiss.IndexFlatL2(dim)

        self.index.add(embeddings)
        self.documents.extend(texts)
        self.metadata.extend(metadata or [{} for _ in texts])

    def search(self, query: str, top_k: int = 5) -> list[dict]:
        if not self.index:
            return []

        # Encode query and search the vector index
        query_vector = self.model.encode([query]).astype("float32")
        distances, indices = self.index.search(query_vector, top_k)

        results = []
        for dist, idx in zip(distances[0], indices[0]):
            if idx != -1:
                results.append({
                    "text": self.documents[idx],
                    "metadata": self.metadata[idx],
                    "score": float(dist)
                })
        return results

    def save(self, path: Path) -> None:
        path.mkdir(parents=True, exist_ok=True)
        faiss.write_index(self.index, str(path / _INDEX_FILE))
        with open(path / _META_FILE, "wb") as f:
            pickle.dump({"documents": self.documents, "metadata": self.metadata}, f)

    @classmethod
    def load(cls, path: Path, model_name: str = _MODEL_NAME) -> "VectorStore":
        store = cls(model_name)
        store.index = faiss.read_index(str(path / _INDEX_FILE))
        with open(path / _META_FILE, "rb") as f:
            data = pickle.load(f)
        store.documents = data["documents"]
        store.metadata = data["metadata"]
        return store

    @property
    def total_docs(self) -> int:
        return self.index.ntotal if self.index else 0


# ── Chunking helpers ──────────────────────────────────────────────────────────

def _chunk_portfolio(portfolio_path: Path) -> tuple[list[str], list[dict]]:
    """Chunks the portfolio.json (a JSON array of holdings)."""
    raw = json.loads(portfolio_path.read_text(encoding="utf-8"))
    # Support both list format and dict-with-holdings format
    holdings = raw if isinstance(raw, list) else raw.get("holdings", [])
    total_value = sum(h.get("holding_value", 0) for h in holdings)

    texts, meta = [], []
    for h in holdings:
        weight = (h.get("holding_value", 0) / total_value * 100) if total_value else 0
        text = (
            f"Holding: {h['name']} (ticker: {h['ticker']})\n"
            f"Type: {h['asset_type']}, Sector: {h['sector']}\n"
            f"Quantity: {h['quantity']} units  Avg Cost: ₹{h['avg_cost']:,.2f}\n"
            f"Current Price: ₹{h['current_price']:,.2f}  Value: ₹{h['holding_value']:,.0f}\n"
            f"Portfolio Weight: {weight:.2f}%\n"
            f"Unrealized P&L: ₹{h['unrealised_pnl']:,.0f} ({h['pnl_pct']:+.2f}%)"
        )
        texts.append(text)
        meta.append({"source": "portfolio.json", "ticker": h["ticker"], "type": "holding"})

        # Also chunk embedded news items from portfolio.json
        for news_item in h.get("news", []):
            news_text = (
                f"[{news_item['date']}] {news_item['title']}\n"
                f"{news_item['snippet']}\n"
                f"Related holding: {h['name']} ({h['ticker']})\n"
                f"Source: {news_item['source']}"
            )
            texts.append(news_text)
            meta.append({
                "source": f"portfolio_news_{h['ticker']}",
                "ticker": h["ticker"],
                "type": "news",
            })

    return texts, meta


def _chunk_augmented(aug_path: Path) -> tuple[list[str], list[dict]]:
    if not aug_path.exists():
        return [], []
    data = json.loads(aug_path.read_text(encoding="utf-8"))
    texts, meta = [], []
    items = data if isinstance(data, list) else data.get("holdings", [])
    for item in items:
        texts.append(json.dumps(item, indent=2))
        meta.append({"source": "portfolio_augmented.json", "type": "augmented"})
    return texts, meta


def _chunk_glossary(glossary_path: Path) -> tuple[list[str], list[dict]]:
    if not glossary_path.exists():
        return [], []
    content = glossary_path.read_text(encoding="utf-8")
    texts, meta = [], []
    current_term, current_lines = "", []

    def flush():
        if current_term and current_lines:
            texts.append(f"{current_term}\n" + "\n".join(current_lines))
            meta.append({"source": "glossary.md", "term": current_term, "type": "definition"})

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
    if not news_dir.exists():
        return [], []
    texts, meta = [], []
    for f in sorted(news_dir.glob("*.md")):
        content = f.read_text(encoding="utf-8")
        texts.append(content)
        meta.append({"source": f.name, "type": "news"})
    return texts, meta


def build_store(data_dir: Path, force_rebuild: bool = False) -> VectorStore:
    cache_path = data_dir.parent / _STORE_DIR
    if not force_rebuild and (cache_path / _INDEX_FILE).exists():
        return VectorStore.load(cache_path)

    store = VectorStore()
    for loader, args in [
        (_chunk_portfolio, (data_dir / "portfolio.json",)),
        (_chunk_augmented, (data_dir / "portfolio_augmented.json",)),
        (_chunk_glossary,  (data_dir / "glossary.md",)),
        (_chunk_news,      (data_dir / "news",)),
    ]:
        t, m = loader(*args)
        store.add_documents(t, m)

    store.save(cache_path)
    return store


def get_index_stats(data_dir: Path) -> dict[str, int]:
    """Return per-source document counts without building a full store."""
    counts: dict[str, int] = {}
    p, _ = _chunk_portfolio(data_dir / "portfolio.json") if (data_dir / "portfolio.json").exists() else ([], [])
    counts["portfolio"] = len(p)
    a, _ = _chunk_augmented(data_dir / "portfolio_augmented.json")
    counts["augmented"] = len(a)
    g, _ = _chunk_glossary(data_dir / "glossary.md")
    counts["glossary"] = len(g)
    n, _ = _chunk_news(data_dir / "news")
    counts["news"] = len(n)
    return counts
