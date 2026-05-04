# CI Submit Scenarios

These scenarios are ready-to-run GitHub CI smoke suites for comparing the
baseline OH backend (`agent_1_oh`) and the SciFi-OH backend
(`agent_2_scifi_oh`) on the Hyy and HZZ4l task families.

Use the `Run Scenario` GitHub Actions workflow and choose one of these from the
`scenario_path` dropdown:

- `ci-submit/scenario.agent01.hyy.toml`
- `ci-submit/scenario.agent02.hyy.toml`
- `ci-submit/scenario.agent03b.hyy.toml`
- `ci-submit/scenario.agent01.hzz.toml`
- `ci-submit/scenario.agent02.hzz.toml`
- `ci-submit/scenario.agent03b.hzz.toml`

Each scenario uses Green-managed shared input and caps inputs at
`max_files = 5` for smoke testing. For HZZ4l this cap is applied per sample
group. Change `max_files` to `0` only when you deliberately want a full-data
run. `agent03b` scenarios use the native SciFi backend
`agent_3b_scifi_native`; in local smoke testing it successfully ran Hyy L1 with
5 ROOT files.

The workflow still defaults to the root `scenario.toml`, so existing behavior is
unchanged unless `scenario_path` is provided.

These files do not require Green rubric changes. They only select the solver
backend and task family. Keep using the same `GREEN_SECRETS_JSON` mechanism:
regenerate it only when a public submission contract or private rubric changes.
If the GitHub secret is too large, export the matching family only:

```bash
cd ../hepex-analysisops-benchmark
uv run python scripts/export_green_secrets.py --suite hyy
uv run python scripts/export_green_secrets.py --suite hzz
```
