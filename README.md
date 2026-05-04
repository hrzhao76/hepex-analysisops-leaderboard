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
- `local_runs/`: ignored local-only packaged runs from
  `scripts/local_shared_submit.py`
- `scripts/archive_latest_results.py`: archive root `output/results.json` into
  the timestamped Green run directory
- `submissions/`: submitted scenario/provenance metadata
- `results/`: final leaderboard-ingested result JSON files

## Current Assessments

The benchmark now has two public analysis families, each with L1/L2/L3 tasks:
Hyy diphoton and HZZ4l. This leaderboard repo does not own those task packages;
it selects them through scenario files and records the resulting assessment
outputs.

| Family | Level | Task directory | CI submit scenarios | Typical cap |
| --- | --- | --- | --- | --- |
| Hyy | L1 | `tasks_public/t002_hyy_v5_l1` | `ci-submit/scenario.agent01.hyy.toml`, `ci-submit/scenario.agent02.hyy.toml`, `ci-submit/scenario.agent03b.hyy.toml` | `max_files = 5` smoke |
| Hyy | L2 | `tasks_public/t003_hyy_v5_l2` | `ci-submit/scenario.agent01.hyy.toml`, `ci-submit/scenario.agent02.hyy.toml`, `ci-submit/scenario.agent03b.hyy.toml` | `max_files = 5` smoke |
| Hyy | L3 | `tasks_public/t004_hyy_v5_l3` | `ci-submit/scenario.agent01.hyy.toml`, `ci-submit/scenario.agent02.hyy.toml`, `ci-submit/scenario.agent03b.hyy.toml` | `max_files = 5` smoke |
| HZZ4l | L1 | `tasks_public/t005_hzz4l_l1` | `ci-submit/scenario.agent01.hzz.toml`, `ci-submit/scenario.agent02.hzz.toml`, `ci-submit/scenario.agent03b.hzz.toml` | `max_files = 5` per sample group smoke |
| HZZ4l | L2 | `tasks_public/t006_hzz4l_l2` | `ci-submit/scenario.agent01.hzz.toml`, `ci-submit/scenario.agent02.hzz.toml`, `ci-submit/scenario.agent03b.hzz.toml` | `max_files = 5` per sample group smoke |
| HZZ4l | L3 | `tasks_public/t007_hzz4l_l3` | `ci-submit/scenario.agent01.hzz.toml`, `ci-submit/scenario.agent02.hzz.toml`, `ci-submit/scenario.agent03b.hzz.toml` | `max_files = 5` per sample group smoke |

`scenario.toml` is the root default scenario used when no CI submit scenario is
selected. At the moment it runs the HZZ4l L1/L2/L3 suite with
`agent_2_scifi_oh` and `max_files = 0`, which means full Green-managed input.
Use the files under `ci-submit/` for controlled GitHub smoke comparisons.

For local benchmark development, this repo also includes ready-to-run templates
under `.local-submit/`, including Hyy L2/L3 and HZZ4l L1/L2/L3 workflows.

Common runtime settings:

- Response format: `submission_bundle_v1`
- CI/default input strategy: Green-managed shared input via
  `scenario_shared_mount` plus `shared_manifest`
- Local realistic input strategy: local shared mount plus `shared_manifest`
- Final task results include `solver_backend`, `purple_agent_runtime_seconds`,
  and a `timing` object for runtime debugging and leaderboard queries.
- Green scoring: public contract plus optional hidden rubric from
  `GREEN_SECRETS_JSON`
- Solver backends used in local testing: `agent_1_oh` for the baseline OH
  executor, or `agent_2_scifi_oh` for the SciFi-OH controller over the same OH
  executor.

## CI Submit Scenarios

Reusable GitHub CI smoke scenarios live under `ci-submit/`. To run one, open
GitHub Actions, choose the `Run Scenario` workflow, click `Run workflow`, and
pick a file from the `scenario_path` dropdown. This lets you run the CI matrix
without overwriting root `scenario.toml`.

```text
scenario.toml
ci-submit/scenario.agent01.hyy.toml
ci-submit/scenario.agent02.hyy.toml
ci-submit/scenario.agent03b.hyy.toml
ci-submit/scenario.agent01.hzz.toml
ci-submit/scenario.agent02.hzz.toml
ci-submit/scenario.agent03b.hzz.toml
```

The matrix currently covers `agent_1_oh`, `agent_2_scifi_oh`, and
`agent_3b_scifi_native` on the Hyy and HZZ4l public task families. Each file
uses Green-managed shared input and `max_files = 5` for smoke testing.

These scenario files do not change Green rubrics. They only choose task
directories, solver backend, input mode, and file caps. `GREEN_SECRETS_JSON`
only needs to be regenerated when a public `submission_contract.yaml` or a
private rubric changes.

If the repository secret is too long for all tasks, export only the task family
you are about to run and manually copy that value into the GitHub repository
secret:

```bash
cd ../hepex-analysisops-benchmark
uv run python scripts/export_green_secrets.py --suite hyy
# or
uv run python scripts/export_green_secrets.py --suite hzz
```

Use the Hyy secret for `scenario.agent01.hyy.toml`,
`scenario.agent02.hyy.toml`, and `scenario.agent03b.hyy.toml`; use the HZZ
secret for `scenario.agent01.hzz.toml`, `scenario.agent02.hzz.toml`, and
`scenario.agent03b.hzz.toml`.

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
files. It exports both Hyy and HZZ hidden rubrics by default. Rerun it whenever
a public `submission_contract.yaml` or private rubric changes. For GitHub
repository secrets with stricter length limits, use `--suite hyy` or
`--suite hzz` and copy the smaller value manually.

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

For a quick smoke run, the local wrapper can cap the mounted manifest with
`--max-files 1` for L1 or `--max-files 5` for L2/L3. For a fuller local Hyy
assessment, use `--max-files 16` once the workflow is stable.

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

From the leaderboard repository, pick a matching scenario/task pair. The
`--scenario` and `--task-id` values should point to the same level.

After the ROOT files and `.env` are ready, `scripts/local_shared_submit.py` is
the single command-line entry point for the whole local workflow: it patches the
scenario, generates Compose config, optionally builds local Green/Purple images,
runs Docker Compose, archives Green output, records provenance, and prepares
local-only packaged files under `local_runs/submissions/` and
`local_runs/results/`.

The checked-in GitHub scenario uses Green-managed shared input for the SciFi-OH
smoke run. The scenario uses the task-templated shared input path
`/home/agent/output/shared_input/{release}/{dataset}/{skim}`. Green expands it
per task, downloads the requested ROOT files there, writes `input_manifest.json`,
and passes that read-only manifest to the Purple Agent.
SciFi-OH still runs as the Purple backend/controller, with OpenHarness as its
worker executor. The scenario sets `solver_request_timeout_seconds = 1800`,
which is the Green-to-Purple per-task wait limit; it is not a hard timeout for
the Green download step.

For CI debugging, SciFi-OH writes
`output/runs/<run_id>/<task_id>/solver_work/debug_scifi_oh_output.log` and also
prints that log into the Purple container stdout near the end of each task, so
the ordinary GitHub Actions log contains the prompt, OpenHarness stdout/stderr,
and independent review trail without requiring a workflow artifact upload.

Default SciFi-OH collaborator smoke workflow, L1 with one ROOT file:

```bash
cd ../hepex-analysisops-leaderboard
python3 scripts/local_shared_submit.py \
  --host-input-dir ../hepex-analysisops-benchmark/shared_input/2025e-13tev-beta/data/GamGam \
  --task-id t002_hyy_v5_l1 \
  --max-files 1 \
  --mode call_white \
  --solver-backend agent_2_scifi_oh \
  --build-local-images \
  --submission-prefix scifi-oh-l1-local
```

SciFi-OH L2 smoke workflow with five ROOT files:

```bash
python3 scripts/local_shared_submit.py \
  --scenario .local-submit/scenario.l2.base.toml \
  --host-input-dir ../hepex-analysisops-benchmark/shared_input/2025e-13tev-beta/data/GamGam \
  --task-id t003_hyy_v5_l2 \
  --max-files 5 \
  --mode call_white \
  --solver-backend agent_2_scifi_oh \
  --build-local-images \
  --submission-prefix scifi-oh-l2-local
```

SciFi-OH L2 full local run with all 16 GamGam ROOT files:

```bash
python3 scripts/local_shared_submit.py \
  --scenario .local-submit/scenario.l2.base.toml \
  --host-input-dir ../hepex-analysisops-benchmark/shared_input/2025e-13tev-beta/data/GamGam \
  --task-id t003_hyy_v5_l2 \
  --max-files 16 \
  --mode call_white \
  --solver-backend agent_2_scifi_oh \
  --build-local-images \
  --submission-prefix scifi-oh-l2-full
```

SciFi-OH L3 smoke run with five ROOT files:

```bash
python3 scripts/local_shared_submit.py \
  --scenario .local-submit/scenario.l3.base.toml \
  --host-input-dir ../hepex-analysisops-benchmark/shared_input/2025e-13tev-beta/data/GamGam \
  --task-id t004_hyy_v5_l3 \
  --max-files 5 \
  --mode call_white \
  --solver-backend agent_2_scifi_oh \
  --build-local-images \
  --submission-prefix scifi-oh-l3-local
```

Use `--build-local-images` after changing `hepex-analysisops-benchmark` or
`hepex-analysisops-agents`. You can omit it when you deliberately want to reuse
already-built `hepex-green-agent:local` and `hepex-purple-agent:local` images.
Replace `--solver-backend agent_2_scifi_oh` with `agent_1_oh` when you want the
baseline OH backend.

What this does:

1. Creates `.local-submit/scenario.local.generated.toml`.
2. Generates `docker-compose.yml` and `a2a-scenario.toml`.
3. Writes `docker-compose.local-shared.yml` to mount local ROOT files.
4. Optionally builds `hepex-green-agent:local` and `hepex-purple-agent:local`.
5. Runs Docker Compose with the local shared input mount.
6. Writes root `output/results.json`.
7. Archives that file into `output/runs/<run_id>/results.json`.
8. Records image provenance.
9. Prepares local-only files under `local_runs/submissions/` and
   `local_runs/results/`.
10. Never commits or opens a PR; local runs stay outside leaderboard ingestion
    directories.

`scripts/local_shared_submit.py` is the wrapper for local testing. It is
intentionally separate from the default CI path: it writes local overrides,
mounts local data, and can build local images without changing `scenario.toml`.

### 6. Verify Results

After a successful run, check the machine-readable result shape without assuming
a specific level:

```bash
python3 - <<'PY'
import json
from pathlib import Path

data = json.loads(Path("output/results.json").read_text())
print("results_len =", len(data.get("results", [])))
for result in data.get("results", []):
    final = result.get("final", {})
    print(
        "task_id =", result.get("task_id"),
        "status =", result.get("status"),
        "type =", result.get("type"),
        "score =", final.get("normalized_score"),
        "visibility =", result.get("score_visibility"),
    )

runs = sorted(Path("output/runs").iterdir(), key=lambda path: path.stat().st_mtime)
print("latest_run =", runs[-1] if runs else "<none>")
PY
```

Expected minimal E2E shape:

- `results_len = 1`
- the only `task_id` matches the level you selected
- `output/runs/<run_id>/results.json` exists
- `output/runs/<run_id>/<task_id>/judge_output.json` exists
- `score_visibility` is `official_with_hidden` when `GREEN_SECRETS_JSON`
  contains the selected task
- `submission_trace.json.input_file_count` matches the local manifest cap
- `submission_trace.json.selected_events_total` is nonzero for realistic
  multi-file L1/L2 GamGam runs; L3 may report broader discovery evidence instead

### 7. Inspect A Failed Run

The useful debug files are:

```text
output/runs/<run_id>/eval_request.json
output/runs/<run_id>/green_config.json
output/runs/<run_id>/run_summary.json
output/runs/<run_id>/<task_id>/purple_request.json
output/runs/<run_id>/<task_id>/purple_response_raw.txt
output/runs/<run_id>/<task_id>/submission_bundle_raw.json
output/runs/<run_id>/<task_id>/submission_trace.json
output/runs/<run_id>/<task_id>/judge_output.json
output/runs/<run_id>/<task_id>/solver_work/debug_oh_output.log
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
# Reuse already-built local images for an L2 full run
python3 scripts/local_shared_submit.py \
  --scenario .local-submit/scenario.l2.base.toml \
  --task-id t003_hyy_v5_l2 \
  --max-files 16 \
  --mode call_white \
  --solver-backend agent_2_scifi_oh \
  --submission-prefix scifi-oh-l2-full

# Run only five ROOT files for an L3 smoke pass
python3 scripts/local_shared_submit.py \
  --scenario .local-submit/scenario.l3.base.toml \
  --task-id t004_hyy_v5_l3 \
  --max-files 5 \
  --mode call_white \
  --solver-backend agent_2_scifi_oh \
  --submission-prefix scifi-oh-l3-local

# Reuse output/results.json and only package/archive it; keep the scenario/task pair matched
python3 scripts/local_shared_submit.py \
  --scenario .local-submit/scenario.l2.base.toml \
  --task-id t003_hyy_v5_l2 \
  --solver-backend agent_2_scifi_oh \
  --skip-run \
  --submission-prefix scifi-oh-l2-repackage
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
└── <task_id>/
    ├── purple_request.json
    ├── purple_response_raw.txt
    ├── submission_bundle_raw.json
    ├── submission_trace.json
    ├── judge_output.json
    └── solver_work/
```

Local packaged run files:

```text
local_runs/
├── results/
│   └── <submission-prefix>-<timestamp>.json
└── submissions/
    ├── <submission-prefix>-<timestamp>.toml
    └── <submission-prefix>-<timestamp>.provenance.json
```

Leaderboard ingestion uses committed `results/*.json`. The timestamped Green
run directory and `local_runs/` are for audit and debugging and are ignored by
Git.

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
- `local_runs/`
- `.local-submit/scenario.local.generated.toml`

The checked-in `.local-submit/scenario.l2.base.toml` and
`.local-submit/scenario.l3.base.toml` files are reusable local templates, not
per-run output.

Only commit generated submission/result files intentionally. Local wrapper
outputs under `local_runs/` are not leaderboard submissions until you
deliberately promote them.

## Troubleshooting

- If the private hidden score is unavailable, rerun
  `../hepex-analysisops-benchmark/scripts/export_green_secrets.py`.
- If L2/L3 still show public-only scoring, make sure you are using the matching
  `--scenario` and `--task-id`, then rerun the secrets export so contract and
  rubric hashes match.
- If local Compose cannot see ROOT files, pass `--host-input-dir` explicitly.
- If `docker compose pull` fails for `:local` images, omit `--pull`.
- If a full L2/L3 run times out while waiting for the Purple Agent, prefer
  increasing `solver_request_timeout_seconds` in `scenario.toml`. The
  `A2A_CLIENT_TIMEOUT_SECONDS` environment variable remains a fallback when the
  scenario does not set an explicit timeout.
- If CI output is poor, search the GitHub Actions log for
  `BEGIN debug_scifi_oh_output.log`; the backend prints the SciFi-OH debug log
  directly to container stdout.
- If port `9009` is busy, stop old containers with
  `docker compose --env-file .env down`.

## Related Repositories

- Green Agent: `../hepex-analysisops-benchmark`
- Reference Purple Agent: `../hepex-analysisops-agents`
- Private task/rubric workspace: `../hepex-analysisops-dev`
