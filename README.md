# pk_alm

Clean rebuild of the pension fund ALM simulation tool for the bachelor thesis
**Enhanced Portfolio Analytics for Pension Funds using ACTUS and Python**.

The current scope is **Stage 1 / Goal 1**: a deterministic economic ALM
baseline focused on cashflow projection, liquidity analysis, and a
transparent liability proxy with deterministic funding-ratio reporting.

## Current Status

- Deterministic Stage-1 BVG liability baseline implemented end-to-end.
- Deterministic asset baseline, funding-ratio trajectory, and funding summary
  implemented.
- Scenario-level result summary implemented for thesis-ready baseline
  reporting.
- Minimal ACTUS/AAL-style adapter boundary implemented for mapping simplified
  event dictionaries into the shared cashflow schema.
- Deterministic ACTUS-style fixed-rate bond fixtures implemented as
  manually checkable adapter inputs.
- Separate asset-cashflow overlay helper implemented for combining BVG
  baseline cashflows with ACTUS-style fixture cashflows.
- Optional AAL availability probe implemented for future real AAL integration.
- Optional AAL API introspection and real-AAL smoke tests document that AAL
  `1.0.12` can construct `PAM` and `Portfolio` objects when available.
- Standalone annual/monthly time-grid feasibility utilities implemented for
  later monthly cashflow work.
- An end-to-end scenario is available as both a library function and a
  manual-run script.
- Current tests: **809 passed, 8 skipped**.

## Quick Run

Run the test suite:

```bash
python -m pytest -v
```

Run the Stage-1 baseline demo:

```bash
python examples/stage1_baseline.py
```

When working directly from the `src/` layout without an editable install, run:

```bash
PYTHONPATH=src python3 examples/stage1_baseline.py
```

Alternatively, install the package locally first:

```bash
python3 -m pip install -e .
python3 examples/stage1_baseline.py
```

## Generated Outputs

Running the demo writes seven CSV files to
`outputs/stage1_baseline/` (relative to the working directory):

- `outputs/stage1_baseline/cashflows.csv` — schema-valid BVG cashflows.
- `outputs/stage1_baseline/valuation_snapshots.csv` — Stage-1 liability
  snapshots per projection year.
- `outputs/stage1_baseline/annual_cashflows.csv` — annual cashflow
  analytics including the liquidity inflection year.
- `outputs/stage1_baseline/asset_snapshots.csv` — deterministic asset
  roll-forward snapshots.
- `outputs/stage1_baseline/funding_ratio_trajectory.csv` — funding-ratio
  trajectory based on `total_stage1_liability`.
- `outputs/stage1_baseline/funding_summary.csv` — compact funding-ratio
  summary for thesis reporting.
- `outputs/stage1_baseline/scenario_summary.csv` — one-row scenario result
  summary for baseline reporting.

## Documentation

- [docs/implementation_progress.md](docs/implementation_progress.md) —
  current sprint-by-sprint status, architecture summary, and known limitations.
- [docs/stage1_pipeline.md](docs/stage1_pipeline.md) — technical description
  of the end-to-end Stage-1 pipeline.
- [docs/stage1_outputs.md](docs/stage1_outputs.md) — reproducibility guide
  for the generated Stage-1 output files.
- [docs/time_grid_feasibility.md](docs/time_grid_feasibility.md) — feasibility
  note for future monthly cashflow timing.
- [docs/stage1_spec.md](docs/stage1_spec.md) — Stage-1 specification.
- [docs/domain_notes.md](docs/domain_notes.md) — domain background.
- [docs/decisions.md](docs/decisions.md) — architectural decision records.

## Scope

The current implementation is the **deterministic Stage-1 baseline**:

- Deterministic asset roll-forward, funding-ratio trajectory, and funding
  summary are included.
- Scenario-level result summary export is included.
- A minimal ACTUS/AAL-style adapter boundary exists for schema-compatible
  cashflow conversion.
- Deterministic ACTUS-style fixed-rate bond fixtures exist as manual
  test/example data for the adapter boundary; they are not an ACTUS engine.
- A separate asset-cashflow overlay helper can combine BVG baseline cashflows
  with ACTUS-style fixture cashflows for annual liquidity analytics.
- The overlay is a shared-schema demonstration, not the default Stage-1
  scenario, and the default Stage-1 CSV outputs remain unchanged.
- An optional AAL availability probe can detect `awesome_actus_lib`, version
  metadata, and expose `get_aal_module()` as a controlled future gateway.
- Optional AAL API introspection and `tests/test_aal_real_contract_smoke.py`
  show that real AAL `PAM` and `Portfolio` objects can be constructed when AAL
  is available. `PublicActusService.generateEvents(...)` appears
  service-backed via `/eventsBatch`, so no production AAL event adapter has
  been added. Sprint 5C recorded `753 passed, 8 skipped` in the system
  environment and `761 passed` in the temporary AAL venv.
- `src/pk_alm/time_grid.py` provides standalone annual/monthly feasibility
  utilities. The annual baseline remains the reference, and monthly simulation
  is not part of the default Stage-1 run.
- Full ACTUS/AAL scenario integration is not implemented yet.
- AAL remains optional and is not wired into the default Stage-1 baseline.
- Real AAL cashflow generation is not implemented yet.
- No stochastic interest-rate scenarios yet.
- No mortality, new entrants, wage growth, inflation, survivor benefits, or
  disability benefits.
- The `total_stage1_liability` reported by the valuation layer is a
  deterministic Stage-1 proxy and intentionally excludes technical reserves.

These extensions are deferred to later sprints; see
`docs/implementation_progress.md` for the next planned step.
