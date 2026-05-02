#!/usr/bin/env python3
"""Run a local shared-manifest assessment and save local-only results.

This script mirrors the useful parts of .github/workflows/run-scenario.yml:

1. Build a temporary scenario that uses local_shared_mount/shared_manifest.
2. Generate docker-compose.yml/a2a-scenario.toml with generate_compose.py.
3. Add a Docker Compose override that mounts local ROOT inputs into green/purple.
4. Run the assessment with docker compose.
5. Record image provenance.
6. Copy the scenario/results/provenance into local_runs/submissions/ and
   local_runs/results/.

It intentionally does not rewrite scenario.toml or generate_compose.py.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

try:
    import tomllib
except ModuleNotFoundError:
    try:
        import tomli as tomllib
    except ModuleNotFoundError:
        print("Missing TOML parser. Install with: python -m pip install tomli", file=sys.stderr)
        raise


REPO_ROOT = Path(__file__).resolve().parents[1]
LOCAL_DIR = REPO_ROOT / ".local-submit"
LOCAL_RUNS_DIR = REPO_ROOT / "local_runs"
GENERATED_SCENARIO = LOCAL_DIR / "scenario.local.generated.toml"
COMPOSE_OVERRIDE = REPO_ROOT / "docker-compose.local-shared.yml"
DEFAULT_TASK_ID = "t002_hyy_v5_l1"
DEFAULT_CONTAINER_INPUT_DIR = "/shared/hepex/input/2025e-13tev-beta/data/GamGam"
DEFAULT_INPUT_CANDIDATES = [
    REPO_ROOT / "shared_input" / "2025e-13tev-beta" / "data" / "GamGam",
    REPO_ROOT.parent / "hepex-analysisops-benchmark" / "shared_input" / "2025e-13tev-beta" / "data" / "GamGam",
    REPO_ROOT.parent / "hepex-analysisops-benchmark" / "output" / "cache",
    REPO_ROOT.parent / "hepex-analysisops-benchmark" / "output-old" / "cache",
    REPO_ROOT / "output-v1.1" / "cache",
]
DEFAULT_BENCHMARK_REPO = REPO_ROOT.parent / "hepex-analysisops-benchmark"
DEFAULT_PURPLE_REPO = REPO_ROOT.parent / "hepex-analysisops-agents"
DEFAULT_GREEN_IMAGE = "hepex-green-agent:local"
DEFAULT_PURPLE_IMAGE = "hepex-purple-agent:local"


def run(cmd: list[str], *, cwd: Path = REPO_ROOT, check: bool = True) -> subprocess.CompletedProcess:
    print("+ " + " ".join(cmd), flush=True)
    return subprocess.run(cmd, cwd=cwd, check=check)


def capture(cmd: list[str], *, cwd: Path = REPO_ROOT, check: bool = True) -> str:
    result = subprocess.run(cmd, cwd=cwd, check=check, text=True, capture_output=True)
    return result.stdout.strip()


def toml_value(value: Any) -> str:
    if isinstance(value, str):
        return json.dumps(value)
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, (int, float)):
        return str(value)
    if isinstance(value, list):
        return "[" + ", ".join(toml_value(item) for item in value) + "]"
    if isinstance(value, dict):
        items = ", ".join(f"{key} = {toml_value(val)}" for key, val in value.items())
        return "{ " + items + " }"
    if value is None:
        raise ValueError("TOML cannot encode None in this scenario writer")
    raise TypeError(f"Unsupported TOML value type: {type(value).__name__}")


def write_scenario(data: dict[str, Any], path: Path) -> None:
    lines: list[str] = []

    green = data.get("green_agent", {})
    lines.append("[green_agent]")
    for key, value in green.items():
        lines.append(f"{key} = {toml_value(value)}")
    lines.append("")

    for participant in data.get("participants", []):
        lines.append("[[participants]]")
        for key, value in participant.items():
            lines.append(f"{key} = {toml_value(value)}")
        lines.append("")

    config = data.get("config", {})
    lines.append("[config]")
    for key, value in config.items():
        if key == "task_overrides":
            continue
        lines.append(f"{key} = {toml_value(value)}")
    lines.append("")

    task_overrides = config.get("task_overrides", {})
    for task_id, override in task_overrides.items():
        lines.append(f"[config.task_overrides.{task_id}]")
        for key, value in override.items():
            lines.append(f"{key} = {toml_value(value)}")
        lines.append("")

    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")


def docker_service_name(name: str) -> str:
    service_name = re.sub(r"[^A-Za-z0-9.-]+", "-", name).strip("-").lower()
    return service_name or "participant"


def load_and_patch_scenario(
    scenario_path: Path,
    *,
    task_id: str,
    container_input_dir: str,
    max_files: int | None,
    mode: str | None,
    solver_backend: str | None,
    green_image: str | None,
    purple_image: str | None,
) -> dict[str, Any]:
    data = tomllib.loads(scenario_path.read_text(encoding="utf-8"))
    if green_image:
        data.setdefault("green_agent", {})["image"] = green_image
    if purple_image:
        for participant in data.get("participants", []):
            participant["image"] = purple_image

    config = data.setdefault("config", {})
    config["input_access_mode"] = "local_shared_mount"
    config["shared_input_dir"] = container_input_dir
    config["input_manifest_path"] = f"{container_input_dir.rstrip('/')}/input_manifest.json"
    config["allow_green_download"] = False
    if solver_backend:
        config["solver_backend"] = solver_backend

    task_overrides = config.setdefault("task_overrides", {})
    override = task_overrides.setdefault(task_id, {})
    override["enabled"] = True
    override["input_strategy"] = "shared_manifest"
    if mode is not None:
        override["mode"] = mode
    if max_files is not None:
        override["max_files"] = max_files

    return data


def participant_service_names(scenario: dict[str, Any]) -> list[str]:
    names = []
    for participant in scenario.get("participants", []):
        name = participant.get("name")
        if not isinstance(name, str) or not name.strip():
            raise ValueError("Every participant must have a non-empty name.")
        names.append(docker_service_name(name))
    return names


def write_compose_override(
    *,
    host_input_dir: Path,
    container_input_dir: str,
    participants: list[str],
) -> None:
    host = str(host_input_dir.resolve())
    target = container_input_dir.rstrip("/")
    lines = [
        "# Auto-generated by scripts/local_shared_submit.py",
        "services:",
        "  green-agent:",
        "    volumes:",
        "      - type: bind",
        f"        source: {json.dumps(host)}",
        f"        target: {json.dumps(target)}",
    ]
    for name in participants:
        lines.extend(
            [
                f"  {name}:",
                "    volumes:",
                "      - type: bind",
                f"        source: {json.dumps(host)}",
                f"        target: {json.dumps(target)}",
                "        read_only: true",
            ]
        )
    COMPOSE_OVERRIDE.write_text("\n".join(lines) + "\n", encoding="utf-8")


def ensure_shared_input(host_input_dir: Path) -> None:
    if not host_input_dir.exists() or not host_input_dir.is_dir():
        raise SystemExit(f"Shared input directory does not exist: {host_input_dir}")
    root_files = sorted(host_input_dir.glob("*.root"))
    if not root_files:
        raise SystemExit(f"No .root files found in shared input directory: {host_input_dir}")
    print(f"Found {len(root_files)} ROOT file(s) in {host_input_dir}")


def resolve_host_input_dir(path: Optional[Path]) -> Path:
    if path is not None:
        return path.resolve()
    for candidate in DEFAULT_INPUT_CANDIDATES:
        if candidate.exists() and any(candidate.glob("*.root")):
            print(f"Using discovered shared input directory: {candidate}")
            return candidate.resolve()
    searched = "\n".join(f"  - {path}" for path in DEFAULT_INPUT_CANDIDATES)
    raise SystemExit(
        "Could not find a local shared input directory with ROOT files. "
        "Pass --host-input-dir explicitly.\nSearched:\n" + searched
    )


def ensure_env_file(env_file: Path) -> None:
    if env_file.exists():
        return
    example = REPO_ROOT / ".env.example"
    if example.exists():
        shutil.copyfile(example, env_file)
        raise SystemExit(f"Created {env_file} from .env.example. Fill secrets, then rerun.")
    raise SystemExit(f"Missing env file: {env_file}")


def backup_previous_results() -> None:
    results_path = REPO_ROOT / "output" / "results.json"
    if not results_path.exists():
        return
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    backup = results_path.with_name(f"results.json.bak.{timestamp}")
    shutil.copyfile(results_path, backup)
    print(f"Backed up previous output/results.json to {backup}")


def build_local_images(*, benchmark_repo: Path, purple_repo: Path) -> None:
    if not benchmark_repo.exists():
        raise SystemExit(f"Benchmark repo does not exist: {benchmark_repo}")
    if not purple_repo.exists():
        raise SystemExit(f"Purple agent repo does not exist: {purple_repo}")
    run(["docker", "build", "-t", "hepex-green-agent:local", "."], cwd=benchmark_repo)
    run(["docker", "build", "-t", "hepex-purple-agent:local", "."], cwd=purple_repo)


def unique_submission_name(prefix: str) -> str:
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    return f"{prefix}-{timestamp}"


def display_path(path: Path) -> Path:
    try:
        return path.resolve().relative_to(REPO_ROOT)
    except ValueError:
        return path


def copy_submission_files(
    name: str,
    scenario_path: Path,
    *,
    local_runs_dir: Path = LOCAL_RUNS_DIR,
) -> tuple[Path, Path, Path]:
    results_src = REPO_ROOT / "output" / "results.json"
    provenance_src = REPO_ROOT / "output" / "provenance.json"
    if not results_src.exists():
        raise SystemExit("Assessment did not produce output/results.json")
    if not provenance_src.exists():
        raise SystemExit("Provenance step did not produce output/provenance.json")

    submission_dir = local_runs_dir / "submissions"
    results_dir = local_runs_dir / "results"
    submission_toml = submission_dir / f"{name}.toml"
    submission_provenance = submission_dir / f"{name}.provenance.json"
    result_json = results_dir / f"{name}.json"
    submission_dir.mkdir(parents=True, exist_ok=True)
    results_dir.mkdir(parents=True, exist_ok=True)

    shutil.copyfile(scenario_path, submission_toml)
    shutil.copyfile(results_src, result_json)
    shutil.copyfile(provenance_src, submission_provenance)
    return submission_toml, submission_provenance, result_json


def current_repo() -> str | None:
    try:
        return capture(["gh", "repo", "view", "--json", "nameWithOwner", "-q", ".nameWithOwner"])
    except Exception:
        return None


def target_repo() -> str | None:
    try:
        return capture(["gh", "repo", "view", "--json", "parent,nameWithOwner", "-q", ".parent.nameWithOwner // .nameWithOwner"])
    except Exception:
        return None


def create_commit_and_pr(
    *,
    name: str,
    paths: tuple[Path, Path, Path],
    base: str,
    branch: str,
    no_pr: bool,
) -> None:
    run(["git", "switch", "-c", branch])
    rel_paths = [str(path.relative_to(REPO_ROOT)) for path in paths]
    run(["git", "add", *rel_paths])
    run(["git", "commit", "-m", f"Submission: {name}"])
    run(["git", "push", "-u", "origin", branch])

    if no_pr:
        print(f"Skipped PR creation. Branch pushed: {branch}")
        return

    repo = target_repo()
    current = current_repo()
    head = branch
    if repo and current and repo != current:
        owner = current.split("/", 1)[0]
        head = f"{owner}:{branch}"

    cmd = [
        "gh",
        "pr",
        "create",
        "--base",
        base,
        "--head",
        head,
        "--title",
        f"Submission: {name}",
        "--body",
        f"Local shared-manifest submission generated from {GENERATED_SCENARIO.name}.",
    ]
    if repo:
        cmd.extend(["--repo", repo])
    run(cmd)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--scenario", type=Path, default=REPO_ROOT / "scenario.toml")
    parser.add_argument("--task-id", default=DEFAULT_TASK_ID)
    parser.add_argument(
        "--host-input-dir",
        type=Path,
        default=None,
        help="Local directory containing ROOT files to mount into green and purple containers.",
    )
    parser.add_argument("--container-input-dir", default=DEFAULT_CONTAINER_INPUT_DIR)
    parser.add_argument("--env-file", type=Path, default=REPO_ROOT / ".env")
    parser.add_argument("--max-files", type=int, default=None)
    parser.add_argument("--mode", default=None, help="Override task mode, e.g. call_white or mock.")
    parser.add_argument("--solver-backend", default=None, help="Forward a solver backend name to the green/purple agents, e.g. agent_1_oh.")
    parser.add_argument("--build-local-images", action="store_true", help="Build hepex-green-agent:local and hepex-purple-agent:local before running compose.")
    parser.add_argument("--green-image", default=DEFAULT_GREEN_IMAGE, help="Green image to write into the generated local scenario.")
    parser.add_argument("--purple-image", default=DEFAULT_PURPLE_IMAGE, help="Purple image to write into the generated local scenario.")
    parser.add_argument("--benchmark-repo", type=Path, default=DEFAULT_BENCHMARK_REPO)
    parser.add_argument("--purple-repo", type=Path, default=DEFAULT_PURPLE_REPO)
    parser.add_argument("--pull", action="store_true", help="Run docker compose pull before up. Off by default for local :local images.")
    parser.add_argument("--submission-prefix", default=os.environ.get("USER", "local"))
    parser.add_argument("--base", default="main", help="Deprecated no-op: local runs are not pushed.")
    parser.add_argument("--branch", default=None, help="Deprecated no-op: local runs are not pushed.")
    parser.add_argument("--skip-run", action="store_true", help="Do not run docker compose; reuse output/results.json.")
    parser.add_argument(
        "--local-runs-dir",
        type=Path,
        default=LOCAL_RUNS_DIR,
        help="Directory for local-only packaged results. Default: local_runs/.",
    )
    parser.add_argument(
        "--no-pr",
        action="store_true",
        help="Deprecated no-op: local_shared_submit.py no longer pushes PRs.",
    )
    parser.add_argument(
        "--no-commit",
        action="store_true",
        help="Deprecated no-op: local_shared_submit.py always keeps packaged files local.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    scenario_path = args.scenario.resolve()
    env_file = args.env_file.resolve()
    host_input_dir = resolve_host_input_dir(args.host_input_dir)

    ensure_shared_input(host_input_dir)
    ensure_env_file(env_file)

    patched = load_and_patch_scenario(
        scenario_path,
        task_id=args.task_id,
        container_input_dir=args.container_input_dir,
        max_files=args.max_files,
        mode=args.mode,
        solver_backend=args.solver_backend,
        green_image=args.green_image,
        purple_image=args.purple_image,
    )
    write_scenario(patched, GENERATED_SCENARIO)
    write_compose_override(
        host_input_dir=host_input_dir,
        container_input_dir=args.container_input_dir,
        participants=participant_service_names(patched),
    )

    run([sys.executable, "generate_compose.py", "--scenario", str(GENERATED_SCENARIO)])
    (REPO_ROOT / "output").mkdir(exist_ok=True)

    if not args.skip_run:
        backup_previous_results()
        if args.build_local_images:
            build_local_images(
                benchmark_repo=args.benchmark_repo.resolve(),
                purple_repo=args.purple_repo.resolve(),
            )
        if args.pull:
            run(["docker", "compose", "pull"])
        run(
            [
                "docker",
                "compose",
                "-f",
                "docker-compose.yml",
                "-f",
                str(COMPOSE_OVERRIDE.name),
                "--env-file",
                str(env_file),
                "up",
                "--timestamps",
                "--no-color",
                "--exit-code-from",
                "agentbeats-client",
                "--abort-on-container-exit",
            ]
        )

    run([sys.executable, "record_provenance.py", "--compose", "docker-compose.yml", "--output", "output/provenance.json"])
    run([sys.executable, "scripts/archive_latest_results.py"])

    name = unique_submission_name(args.submission_prefix)
    paths = copy_submission_files(
        name,
        GENERATED_SCENARIO,
        local_runs_dir=args.local_runs_dir.resolve(),
    )
    print(f"Prepared local run files for {name}:")
    for path in paths:
        print(f"  {display_path(path)}")
    print("Local run packaging is complete. Commit/PR creation is disabled for this wrapper.")


if __name__ == "__main__":
    main()
