.PHONY: test rust forge python bench guest reproduce

export PATH := $(HOME)/.foundry/bin:$(PATH)
PY := $(CURDIR)/.venv/bin/python
PYTEST := $(CURDIR)/.venv/bin/pytest

test: rust forge python bench

rust:
	cd prover && CARGO_TARGET_DIR=$(CURDIR)/prover/target cargo test -p leash-risk
	cd prover && CARGO_TARGET_DIR=$(CURDIR)/prover/target cargo build -p leash-risk-cli

forge:
	cd contracts && forge test

python:
	test -x $(PYTEST) || python3 -m venv .venv && .venv/bin/pip install -q -r requirements.txt
	PYTHONPATH=agent $(PYTEST) -q agent/tests prover/reference/test_ewma_numpy.py services/test_orchestrator.py

bench:
	$(PY) bench/leashbench.py

guest:
	bash prover/script/prove.sh

reproduce: test
	@echo "results: bench/results/summary.json bench/results/gas.json"
