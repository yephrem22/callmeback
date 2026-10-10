# Call Me Back: shared entry point for builders and their agents (PLAN.md §6, §23.1).
# Never `include .env` here and never echo a value from it; `make check-env` masks values.

PY ?= $(shell test -x .venv/bin/python && echo .venv/bin/python || echo python3)
PHASE ?= build
ARGS ?=
DEPLOY_SSH ?= root@$(shell $(PY) -c "from dotenv import dotenv_values as d; print(d('.env').get('HOST') or '')" 2>/dev/null)

.PHONY: install secrets check-env test dev fixtures deploy

install:
	@test -d .venv || uv venv .venv
	uv pip install -p .venv/bin/python -r requirements.txt

secrets:
	$(PY) -m scripts.gen_secrets $(ARGS)

check-env:
	$(PY) -m scripts.check_env --phase $(PHASE) $(ARGS)

test:
	$(PY) -m pytest -q
	@if [ -f web/package.json ]; then \
		echo "web checks (PLAN.md §17.1)"; \
		cd web && npm run typecheck && npm run lint && npm run build; \
	fi

dev:
	@if [ ! -f app/main.py ]; then echo "app/main.py not yet present (spec 005)"; exit 1; fi
	$(PY) -m uvicorn app.main:app --reload --port 8000

fixtures:
	@if [ ! -f scripts/export_fixtures.py ]; then echo "scripts/export_fixtures.py not yet present (spec 003)"; exit 1; fi
	$(PY) scripts/export_fixtures.py

deploy:
	@case "$(DEPLOY_SSH)" in \
		root@|root@172-105-12-34.sslip.io) echo "HOST in .env is unset or the example value; set it first (spec 002)"; exit 1;; \
	esac
	ssh -A $(DEPLOY_SSH) 'cd /opt/callmeback && bash scripts/deploy.sh'
