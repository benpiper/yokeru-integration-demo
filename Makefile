.PHONY: install test lint format run serve replay docker docker-test inspect clean

install:
	uv sync

test:
	uv run pytest -v

lint:
	uv run ruff check src tests

format:
	uv run ruff format src tests

run:
	uv run yokeru-agent run $(PATIENT_ID)

serve:
	uv run yokeru-agent serve

replay:
	uv run yokeru-agent replay

docker:
	docker build -t yokeru-integration .

docker-test:
	docker run --rm -e YOKERU_LOG_FORMAT=text yokeru-integration run --help

inspect:
	@sqlite3 -column -header integration_state.db \
		"SELECT * FROM call_buffer ORDER BY updated_at DESC;"

clean:
	rm -rf .pytest_cache .ruff_cache __pycache__ src/__pycache__ tests/__pycache__
	rm -f integration_state.db integration_state.db-journal
