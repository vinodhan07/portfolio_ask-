QUERY ?= "What is my allocation to the banking sector?"

.PHONY: setup run eval rebuild clean

setup:
	pip install -e .

run:
	python -m portfolio_ask $(QUERY)

eval:
	python evals/run_eval.py

rebuild:
	python -m portfolio_ask --rebuild $(QUERY)

clean:
	rm -rf .vector_cache
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	find . -name "*.pyc" -delete 2>/dev/null || true
