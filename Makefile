QUERY ?= "What is my allocation to the banking sector?"

.PHONY: setup index start run eval rebuild clean

# ── Install dependencies ──────────────────────────────────────────────────────
setup:
	pip install -e .

# ── Build FAISS index from data/ (run once after adding data files) ───────────
index:
	python scripts/build_index.py

index-force:
	python scripts/build_index.py --force

# ── Start the interactive CLI ─────────────────────────────────────────────────
start:
	python -m portfolio_ask

# ── One-shot query (non-interactive) ─────────────────────────────────────────
run:
	python -m portfolio_ask --query $(QUERY)

run-json:
	python -m portfolio_ask --query $(QUERY) --json

# ── Run evals ─────────────────────────────────────────────────────────────────
eval:
	python evals/run_eval.py

# ── Clean generated artefacts ────────────────────────────────────────────────
clean:
	rm -rf .faiss_store
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	find . -name "*.pyc" -delete 2>/dev/null || true
