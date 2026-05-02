# HEPEx AnalysisOps Leaderboard

This repository is the AgentBeats leaderboard and scenario runner for the
HEPEx AnalysisOps Benchmark.

It does not implement benchmark logic. The Green Agent in
`hepex-analysisops-benchmark` is the source of truth for task loading,
submission validation, scoring, and result schema. This repository owns the
runner configuration, generated assessment outputs, leaderboard query files,
and contributor submission flow.

## Repository Role

This repo provides:

- `scenario.toml`: the canonical AgentBeats assessment scenario
- `generate_compose.py`: conversion from scenario config to Docker Compose
- `.github/workflows/run-scenario.yml`: CI assessment runner
- `hyy_l1_queries.json`: DuckDB queries for AgentBeats leaderboard rendering
- `scripts/local_shared_submit.py`: local full-data/shared-manifest workflow
- `scripts/archive_latest_results.py`: archive root `output/results.json` into
  the timestamped Green run directory
- `submissions/`: submitted scenario/provenance metadata
- `results/`: final leaderboard-ingested result JSON files

## Current Assessment

The current default task is:

- Task: `tasks_public/t002_hyy_v5_l1`
- Response format: `submission_bundle_v1`
- Input strategy in CI default: `download` with a small `max_files` setting
- Input strategy for local full-data testing: `local_shared_mount`
- Green scoring: public directory contract plus optional hidden L1 rubric
- Default solver backend: `agent_1_oh`

For full local testing, place or mount ATLAS Open Data ROOT files at:

```text
../hepex-analysisops-benchmark/shared_input/2025e-13tev-beta/data/GamGam
```

## Environment

Create `.env` in this repository:

```bash
OPENAI_API_KEY=...
GREEN_SECRETS_JSON='...'
```

The easiest way to generate `GREEN_SECRETS_JSON` is from the benchmark repo:

```bash
cd ../hepex-analysisops-benchmark
uv run python scripts/export_green_secrets.py
```

That script writes the value into both the benchmark and leaderboard `.env`
files. Rerun it whenever the public `submission_contract.yaml` or private rubric
changes.

Do not print or commit `.env`.

## Complete Local E2E Test Flow

Use this flow when you want to simulate the real assessment locally with Docker
Compose, local Green/Purple images, and local ATLAS ROOT files. It is the
recommended collaborator workflow for debugging before CI.

### 1. Check Out Repositories

Place the three repositories next to each other:

```text
AgentBeats/
├── hepex-analysisops-benchmark
├── hepex-analysisops-agents
└── hepex-analysisops-leaderboard
```

Initialize the Purple Agent submodules:

```bash
cd ../hepex-analysisops-agents
git submodule update --init --recursive
```

### 2. Install Local Python Environments

```bash
cd ../hepex-analysisops-benchmark
uv sync
uv run pytest -q

cd ../hepex-analysisops-agents
uv sync
uv run pytest tests/test_submission_bundle_agent.py \
  tests/test_agent.py::test_submission_bundle_request_returns_minimal_valid_bundle \
  tests/test_agent.py::test_submission_bundle_request_returns_error_for_missing_manifest \
  tests/test_agent.py::test_submission_bundle_request_returns_error_for_invalid_manifest_json \
  -q
```

### 3. Download Shared Input Data

From the benchmark repository, download the GamGam ROOT files:

```bash
cd ../hepex-analysisops-benchmark
uv run python scripts/download_root_files.py \
  --skim GamGam \
  --max-files -1 \
  --json-output ./shared_input/download_manifest.json
```

The default destination is:

```text
../hepex-analysisops-benchmark/shared_input/2025e-13tev-beta/data/GamGam
```

For a quick smoke run, the local wrapper can cap the manifest with
`--max-files 1`. For a fuller local assessment, use `--max-files 16` or omit
the cap once the workflow is stable.

### 4. Prepare Secrets

Create or update `.env` files from the benchmark repo:

```bash
cd ../hepex-analysisops-benchmark
uv run python scripts/export_green_secrets.py
```

Then confirm the leaderboard `.env` contains:

```bash
OPENAI_API_KEY=...
GREEN_SECRETS_JSON='...'
```

Do not commit `.env`.

### 5. Run The Local Compose Assessment

From the leaderboard repository:

```bash
cd ../hepex-analysisops-leaderboard
python3 scripts/local_shared_submit.py \
  --host-input-dir ../hepex-analysisops-benchmark/shared_input/2025e-13tev-beta/data/GamGam \
  --max-files 16 \
  --mode call_white \
  --solver-backend agent_1_oh \
  --build-local-images \
  --no-commit
```

What this does:

1. Creates `.local-submit/scenario.local.generated.toml`.
2. Generates `docker-compose.yml` and `a2a-scenario.toml`.
3. Writes `docker-compose.local-shared.yml` to mount local ROOT files.
4. Optionally builds `hepex-green-agent:local` and `hepex-purple-agent:local`.
5. Runs Docker Compose with the local shared input mount.
6. Writes root `output/results.json`.
7. Archives that file into `output/runs/<run_id>/results.json`.
8. Records image provenance.
9. Prepares files under `submissions/` and `results/`.
10. Skips commit/PR creation when `--no-commit` is set.

`scripts/local_shared_submit.py` is the wrapper for local testing. It is
intentionally separate from the default CI path: it writes local overrides,
mounts local data, and can build local images without changing `scenario.toml`.

### 6. Verify Results

After a successful run, check the machine-readable result shape:

```bash
python3 - <<'PY'
import json
from pathlib import Path

data = json.loads(Path("output/results.json").read_text())
print("results_len =", len(data.get("results", [])))
for result in data.get("results", []):
    print(result["task_id"], result["status"], result["final"]["normalized_score"])
PY
```

Expected minimal E2E shape:

- `results_len = 1`
- the only `task_id` is `t002_hyy_v5_l1`
- `output/runs/<run_id>/results.json` exists
- `output/runs/<run_id>/t002_hyy_v5_l1/judge_output.json` exists
- `submission_trace.json.input_file_count` matches the local manifest cap
- `submission_trace.json.selected_events_total` is nonzero for realistic
  multi-file GamGam runs

### 7. Inspect A Failed Run

The useful debug files are:

```text
output/runs/<run_id>/eval_request.json
output/runs/<run_id>/green_config.json
output/runs/<run_id>/run_summary.json
output/runs/<run_id>/t002_hyy_v5_l1/purple_request.json
output/runs/<run_id>/t002_hyy_v5_l1/purple_response_raw.txt
output/runs/<run_id>/t002_hyy_v5_l1/judge_output.json
output/runs/<run_id>/t002_hyy_v5_l1/solver_work/debug_oh_output.log
```

Start with `judge_output.json` for scoring/contract failures, then inspect
`solver_work/` for generated solver code and OpenHarness logs.

### 8. Clean Up Compose

The wrapper stops containers at the end of a normal run. To force cleanup:

```bash
docker compose \
  -f docker-compose.yml \
  -f docker-compose.local-shared.yml \
  --env-file .env \
  down
```

Useful variations:

```bash
# Reuse already-built local images
python3 scripts/local_shared_submit.py --max-files 16 --mode call_white --no-commit

# Run only one ROOT file for a fast smoke pass
python3 scripts/local_shared_submit.py --max-files 1 --mode call_white --no-commit

# Reuse output/results.json and only package/archive it
python3 scripts/local_shared_submit.py --skip-run --no-commit
```

The wrapper does not run `docker compose pull` by default because the local
workflow normally uses `:local` images. Pass `--pull` only when you explicitly
want Compose to pull configured images.

## Manual Compose Debugging

For lower-level debugging:

```bash
docker build -t hepex-green-agent:local ../hepex-analysisops-benchmark
docker build -t hepex-purple-agent:local ../hepex-analysisops-agents

docker compose \
  -f docker-compose.yml \
  -f docker-compose.local-shared.yml \
  --env-file .env \
  up \
  --timestamps \
  --no-color \
  --exit-code-from agentbeats-client \
  --abort-on-container-exit

python3 scripts/archive_latest_results.py
docker compose -f docker-compose.yml -f docker-compose.local-shared.yml --env-file .env down
```

Use this manual path when you want to inspect service logs directly. Use
`scripts/local_shared_submit.py` when preparing a shareable local run.

## Result Layout

Root output:

```text
output/results.json
```

Timestamped Green run:

```text
output/runs/<run_id>/
├── eval_request.json
├── green_config.json
├── run_summary.json
├── results.json
└── t002_hyy_v5_l1/
    ├── purple_request.json
    ├── purple_response_raw.txt
    ├── submission_bundle_raw.json
    ├── submission_trace.json
    ├── judge_output.json
    └── solver_work/
```

Leaderboard ingestion uses `results/*.json`. The timestamped run directory is
for audit and debugging.

## CI Submission Flow

For a normal AgentBeats submission:

1. Fork this repository.
2. Edit `scenario.toml` with the participant `agentbeats_id`.
3. Configure repository secrets such as `OPENAI_API_KEY` and
   `GREEN_SECRETS_JSON`.
4. Push a branch.
5. Let `.github/workflows/run-scenario.yml` run the scenario.
6. Open the generated PR or use the workflow output to submit results.

The CI flow should stay stable and minimal. Local-only compose overrides and
large local data mounts are intentionally kept out of the default CI path.

## Leaderboard Queries

The query file is:

```text
hyy_l1_queries.json
```

Queries should read only final Green task reports from `results/*.json`. They
should not depend on `output/runs/*`, Purple raw responses, or solver work
directories.

The first selected column must be the AgentBeats participant id. The current
recommended expression is:

```sql
COALESCE(t.participants.purple_agent, t.participants.white_agent) AS id
```

## Generated Files

These files are local/generated and should be treated carefully:

- `docker-compose.yml`
- `a2a-scenario.toml`
- `docker-compose.local-shared.yml`
- `output/`
- `.local-submit/`

Only commit generated submission/result files intentionally.

## Troubleshooting

- If the private hidden score is unavailable, rerun
  `../hepex-analysisops-benchmark/scripts/export_green_secrets.py`.
- If local Compose cannot see ROOT files, pass `--host-input-dir` explicitly.
- If `docker compose pull` fails for `:local` images, omit `--pull`.
- If port `9009` is busy, stop old containers with
  `docker compose --env-file .env down`.

## Related Repositories

- Green Agent: `../hepex-analysisops-benchmark`
- Reference Purple Agent: `../hepex-analysisops-agents`
- Private task/rubric workspace: `../hepex-analysisops-dev`
