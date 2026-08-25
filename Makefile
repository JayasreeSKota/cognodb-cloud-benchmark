.PHONY: all benchmark test validate parity audit clean start-docker stop-docker

PYTHON ?= ./venv/bin/python

all: benchmark

start-docker:
	cd docker && docker compose up -d

stop-docker:
	cd docker && docker compose down

test:
	$(PYTHON) test_connection.py

audit:
	$(PYTHON) scripts/audit_docker_resources.py
	$(PYTHON) scripts/audit_environment.py
	$(PYTHON) scripts/measure_rtt.py

parity:
	$(PYTHON) scripts/verify_query_equivalence.py

validate:
	$(PYTHON) scripts/validate_results.py

validate-dev:
	$(PYTHON) scripts/validate_results.py --allow-dev

benchmark:
	./scripts/run_benchmark.sh

clean:
	rm -rf results/raw/* results/charts/* results/*.json results/*.csv results/*.png
