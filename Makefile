.PHONY: test rust forge python bench figures gas guest sp1-cycles paper reproduce

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

figures: bench
	$(PY) bench/plot_results.py
	MPLCONFIGDIR=/tmp/mpl $(PY) paper/tools/fig_architecture.py

gas:
	$(PY) bench/gas_samples.py

guest:
	bash prover/script/prove.sh

# Needs the SP1 v6 toolchain (cargo-prove). Runs the guest in the SP1 executor, no proof.
sp1-cycles:
	cd prover/program && cargo prove build --output-directory elf --elf-name zkleash-guest
	cd prover/exec && CARGO_TARGET_DIR=$(CURDIR)/prover/exec/target cargo run --release -q > $(CURDIR)/bench/results/sp1_cycles.json

paper: figures
	$(PY) paper/tools/revise_docx.py

reproduce: test gas figures paper
	@echo "results: bench/results/summary.json bench/results/gas.json zkLeash_IEEE_paper_v3.docx"
