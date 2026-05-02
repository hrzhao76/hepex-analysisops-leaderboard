"""Archive the latest AgentBeats client results inside the benchmark run dir.

The AgentBeats client writes to a stable path, output/results.json. This helper
keeps that path intact for CI and submission scripts, then mirrors the same file
to output/runs/<run_id>/results.json for local debugging.
"""

from __future__ import annotations

import argparse
import json
import shutil
from pathlib import Path
from typing import Any


def load_json(path: Path) -> dict[str, Any]:
    with path.open(encoding="utf-8") as f:
        data = json.load(f)
    if not isinstance(data, dict):
        raise ValueError(f"{path} must contain a JSON object")
    return data


def latest_run_dir(output_dir: Path, run_id: str | None = None) -> Path:
    runs_dir = output_dir / "runs"
    if not runs_dir.is_dir():
        raise SystemExit(f"Run directory not found: {runs_dir}")

    if run_id:
        run_dir = runs_dir / run_id
        if not run_dir.is_dir():
            raise SystemExit(f"Requested run_id not found: {run_id}")
        return run_dir

    summaries = sorted(
        runs_dir.glob("*/run_summary.json"),
        key=lambda path: path.stat().st_mtime_ns,
        reverse=True,
    )
    if summaries:
        return summaries[0].parent

    run_dirs = sorted(
        (path for path in runs_dir.iterdir() if path.is_dir()),
        key=lambda path: path.stat().st_mtime_ns,
        reverse=True,
    )
    if not run_dirs:
        raise SystemExit(f"No benchmark runs found under {runs_dir}")
    return run_dirs[0]


def archive_results(output_dir: Path, results_path: Path, run_id: str | None = None) -> Path:
    if not results_path.exists():
        raise SystemExit(f"Results file not found: {results_path}")

    results = load_json(results_path)
    if not isinstance(results.get("results"), list):
        raise SystemExit(f"Results file has no results array: {results_path}")

    run_dir = latest_run_dir(output_dir, run_id)
    summary_path = run_dir / "run_summary.json"
    if summary_path.exists():
        summary = load_json(summary_path)
        summary_run_id = summary.get("run_id")
        if summary_run_id and summary_run_id != run_dir.name:
            raise SystemExit(
                f"Run summary mismatch: {summary_path} has run_id={summary_run_id!r}, "
                f"but directory is {run_dir.name!r}"
            )

    archive_path = run_dir / "results.json"
    if results_path.resolve() != archive_path.resolve():
        shutil.copyfile(results_path, archive_path)
    return archive_path


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, default=Path("output"))
    parser.add_argument("--results", type=Path, default=Path("output/results.json"))
    parser.add_argument("--run-id", help="Archive into a specific output/runs/<run-id> directory.")
    args = parser.parse_args()

    archive_path = archive_results(args.output_dir, args.results, args.run_id)
    print(f"Archived {args.results} to {archive_path}")


if __name__ == "__main__":
    main()
