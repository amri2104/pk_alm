# Stage 2 Specification — Demographic Dynamics

> **Status: Bauplan.** This document specifies Stage 2. The modules,
> functions, and tests referenced here exist as **skeletons only**. Their
> bodies raise `NotImplementedError("Stage 2 Bauplan: implementation
> deferred")` until Sprint 10 implements them. Stage 1 (`run_stage1_baseline`,
> `run_full_alm_scenario`) remains untouched, protected, and fully runnable.

## 1. Purpose

Stage 1 models a **closed population**: the same active and retired cohorts age
through the projection horizon. No member joins. No member leaves except
through retirement. No salary changes over time. This is the central
limitation called out in `docs/stage1_spec.md` and in
`docs/results_review.md`.

Stage 2 closes this gap by introducing **deterministic demographic dynamics**:

- **New entrants** join the active population every projection year.
- **Turnover (Austritte)** removes a fraction of active members each year and
  emits an exit cashflow (Austrittsleistung / Freizügigkeitsleistung).
- **Salary growth** scales the coordinated salary of remaining active members
  each year, lifting their age credits and PR contributions.

Stage 2 is **deterministic**. It does not introduce mortality (Stage 3),
dynamic asset rebalancing (Stage 4), or stochastic interest rates (Stage 5).

## 2. Scope

Stage 2 covers Goal 1 of the bachelor thesis with a more realistic
going-concern population. Specifically:

- Project an **open population** with new entrants, turnover, and salary
  growth alongside the existing aging, interest crediting, and retirement
  transitions of Stage 1.
- Emit `EX` (exit) cashflows for departing members at the value of their
  vested savings capital.
- Compute the same KPIs as Stage 1 (funding ratio, structural cashflow,
  liquidity inflection, Pensionierungsverlust) on the Stage-2 projection.
- Provide a **Stage-2 baseline scenario** parallel to `run_stage1_baseline`,
  with its own deliberately conservative defaults.

## 3. Explicit Non-Scope

Stage 2 deliberately **excludes**:

- Mortality / biometric risk (Stage 3).
- Stochastic salary or stochastic turnover (would belong with Stage 5).
- Disability / survivor benefits.
- Reglements-specific or BVG-Überobligatorium logic.
- Dynamic rebalancing or asset-strategy changes (Stage 4).
- Stochastic interest-rate scenarios (Stage 5; PA hand-off).
- Monthly granularity for entries/exits — Stage 2 stays annual.
- Re-employment / multiple plan transitions.

These are deferred or out of scope for this thesis stage.

## 4. Architectural Boundaries

Stage 2 is **additive**. It must not modify Stage 1 modules. The protected
files are:

```text
src/pk_alm/bvg/formulas.py
src/pk_alm/bvg/cohorts.py
src/pk_alm/bvg/projection.py
src/pk_alm/bvg/portfolio.py
src/pk_alm/bvg/cashflow_generation.py
src/pk_alm/bvg/retirement_transition.py
src/pk_alm/bvg/engine.py
src/pk_alm/bvg/valuation.py
src/pk_alm/scenarios/stage1_baseline.py
src/pk_alm/scenarios/full_alm_scenario.py
outputs/stage1_baseline/*
```

Stage 2 lives in **new files**:

```text
src/pk_alm/bvg/salary_dynamics.py
src/pk_alm/bvg/turnover.py
src/pk_alm/bvg/entry_dynamics.py
src/pk_alm/bvg/engine_stage2.py
src/pk_alm/scenarios/stage2_baseline.py
```

The Stage-2 engine reuses Stage-1 building blocks (`project_portfolio_one_year`,
`apply_retirement_transitions_to_portfolio`,
`generate_bvg_cashflow_dataframe_for_state`) without altering them.

## 5. Year-Loop Specification

The Stage-2 annual loop extends the Stage-1 three-step pattern by three new
steps. The **canonical order** within each projection year `t → t+1` is:

| Step | What happens | Module |
|---|---|---|
| 1 | Generate regular **PR / RP** cashflows from the current state at `t` | `cashflow_generation.py` (Stage 1, reused) |
| 2 | Apply **turnover**: reduce active counts by `turnover_rate`, emit `EX` cashflows for departed vested capital | `turnover.py` (Stage 2, **new**) |
| 3 | **Project** portfolio one year: interest crediting on capital + age + 1 | `projection.py` (Stage 1, reused) |
| 4 | Apply **salary growth**: multiply `gross_salary_per_person` by `(1 + salary_growth_rate)` for each remaining active cohort | `salary_dynamics.py` (Stage 2, **new**) |
| 5 | Apply **retirement transitions** to the projected state: convert age-65 actives into retirees, emit `KA` cashflows | `retirement_transition.py` (Stage 1, reused) |
| 6 | Apply **new entrants**: add a fresh active cohort at `entry_age` with `entry_count`, `entry_salary`, and `entry_capital` | `entry_dynamics.py` (Stage 2, **new**) |

### 5.1 Why this order

- **Turnover before projection** so that interest is credited only on capital
  that stays. A leaver takes their vested capital out at year-start; their
  fraction does not earn the year's interest.
- **Salary growth after projection** so that age credits used in step 1 still
  reflect last year's salary (the salary that earned that contribution).
  The new salary applies to next year's PR.
- **Retirement after salary growth** so that retiring members carry the
  bumped salary into their retirement-base capital — same convention as a
  real plan where salary growth is recognised before retirement is computed.
- **Entries after retirement** so that the entering cohort starts at the
  end-of-year balance sheet, with its own clean entry capital, and
  participates from `t+1` onwards.

### 5.2 Per-step counts

If the year `t` starts with `N_active` active members, then after step 6:

```text
N_active(t+1) = floor( N_active(t) * (1 - turnover_rate) )
              - retired_during_year
              + entry_count_per_year
```

`floor(...)` is used because counts are integers; the rounding rule is
"floor of remaining", consistent with the conservative-staffing convention.
The fractional residual is **not** carried over to the next year; it is
reported as `turnover_rounding_residual_count` in the Stage-2 KPI summary
for transparency.

## 6. New Cashflow Type: `EX`

The shared `CashflowRecord` schema (`src/pk_alm/cashflows/schema.py`) already
allows arbitrary non-empty `type` strings. Stage 2 introduces:

```text
type   = "EX"
source = "BVG"
payoff = -(vested_capital_per_person * departing_count)   # outflow
nominalValue = vested_capital_per_person * departing_count
```

Sign convention: `payoff < 0` because the fund pays out vested capital to a
Freizügigkeitseinrichtung. This is consistent with the existing `KA` and `RP`
sign conventions.

`EX` events are emitted on the same year-end timestamp as `PR/RP/KA`.
Distribution within the year (e.g. quarterly leavers) is out of scope for
Stage 2.

## 7. Salary Dynamics Specification

### 7.1 Model

For each active cohort `c` at the start of year `t`:

```text
gross_salary_per_person(t+1) = gross_salary_per_person(t) * (1 + g)
```

where `g` is `salary_growth_rate`, a single deterministic scalar per scenario
run. Default `g = 0.015` (1.5 % per year), aligned with long-run Swiss
nominal wage growth.

Coordinated salary, age credit, and PR contribution then follow the existing
BVG-2024 formulas in `formulas.py`. **No formula changes** — the only thing
that changes is the input.

### 7.2 Edge cases

- `g = 0` reproduces Stage 1 salary behaviour for active cohorts.
- `g < 0` (deflation) is **rejected** in Stage 2 (`g >= 0` enforced). A future
  Stage-2.1 may relax this; the Bauplan does not.
- Salary growth applies to **all** remaining active cohorts uniformly. Per-age
  or per-cohort salary scales are out of scope.

## 8. Turnover Specification

### 8.1 Model

For each active cohort `c` at year `t`, after step 1 (PR/RP emission) and
before step 3 (projection):

```text
departing_count(c, t) = floor( c.count * turnover_rate )
remaining_count(c, t) = c.count - departing_count(c, t)
```

If `remaining_count(c, t) == 0` the cohort is removed from the portfolio.
Otherwise `c.count` is updated; all other cohort fields stay.

The departing members carry their vested capital out:

```text
vested_capital_per_person = c.capital_active_per_person  (full vesting assumed)
EX_payoff = -(departing_count * vested_capital_per_person)
```

### 8.2 Vesting

Stage 2 assumes **full vesting** of the BVG savings capital from year 1.
Real-world Freizügigkeitsleistung formulas (BVG Art. 17, BVG Art. 15) are a
superset of full vesting once a member has more than ~1 year of service;
full vesting is a conservative simplification consistent with the Stage-1
deterministic philosophy.

### 8.3 Edge cases

- `turnover_rate = 0` reproduces Stage-1 active-side count behaviour.
- `turnover_rate = 1.0` empties the active book in one year — invalid in
  Stage 2 (rejected at `> 0.5` to avoid pathological scenarios; the limit is
  itself a defaults-question and is configurable).
- Turnover is applied to **active cohorts only**. Retirees do not "leave"
  through turnover in Stage 2; mortality is Stage 3.
- Cohorts with `count == 0` after turnover are removed.

## 9. Entry Dynamics Specification

### 9.1 Model

`EntryAssumptions` is a frozen dataclass:

```text
EntryAssumptions(
    entry_age: int                     = 25
    entry_count_per_year: int          = 1
    entry_gross_salary: float          = 65_000.0
    entry_capital_per_person: float    = 0.0
    cohort_id_prefix: str              = "ENTRY"
)
```

Each year a fresh `ActiveCohort` is generated:

```text
new_cohort = ActiveCohort(
    cohort_id                  = f"{prefix}_{start_year + step}_{nonce}"
    age                        = entry_age
    count                      = entry_count_per_year
    gross_salary_per_person    = entry_gross_salary
    capital_active_per_person  = entry_capital_per_person
)
```

`nonce` ensures uniqueness even when multiple entry batches share the same
year. By default `nonce = "0"`; a future extension may distribute entries
across sub-cohorts.

### 9.2 Cashflow handling

If `entry_capital_per_person > 0`, an inflow cashflow of type `IN`
(incoming Freizügigkeitsleistung) is emitted:

```text
type    = "IN"
source  = "BVG"
payoff  = +entry_count_per_year * entry_capital_per_person
nominalValue = same
```

If `entry_capital_per_person == 0`, **no `IN` cashflow** is emitted (a zero
event would only add noise).

### 9.3 Edge cases

- `entry_count_per_year = 0` disables entries entirely (reduces Stage 2 to
  turnover-only-with-salary-growth).
- `entry_age >= retirement_age` is rejected.
- Multi-batch entries (e.g. 5 entries at age 25, 2 at age 30) are out of
  Stage-2 scope; the Bauplan supports a single uniform entry batch per year.

## 10. Engine Specification

### 10.1 Public API

```text
src/pk_alm/bvg/engine_stage2.py:

@dataclass(frozen=True)
class Stage2EngineResult:
    portfolio_states: tuple[BVGPortfolioState, ...]
    cashflows: pd.DataFrame
    turnover_rounding_residual_count: tuple[int, ...]
    entry_count_per_year: int
    salary_growth_rate: float
    turnover_rate: float
    # plus: properties for initial_state, final_state, horizon_years,
    # cashflow_count, total_entries, total_exits

def run_bvg_engine_stage2(
    initial_state: BVGPortfolioState,
    horizon_years: int,
    active_interest_rate: float,
    retired_interest_rate: float,
    salary_growth_rate: float = 0.015,
    turnover_rate: float = 0.02,
    entry_assumptions: EntryAssumptions | None = None,
    contribution_multiplier: float = 1.4,
    start_year: int = 2026,
    retirement_age: int = 65,
    capital_withdrawal_fraction: float = 0.35,
    conversion_rate: float = 0.068,
) -> Stage2EngineResult: ...
```

### 10.2 Stage-1 invariants preserved

- `Stage2EngineResult.cashflows` validates against
  `validate_cashflow_dataframe`.
- `portfolio_states[0] == initial_state` (no mutation of input).
- `len(portfolio_states) == horizon_years + 1`.
- `Pensionierungsverlust` semantics carry over from `valuation.py` unchanged.

### 10.3 Stage-2 specific invariants

- The number of active members at year `t+1` must equal the count formula
  in section 5.2.
- `cashflows[cashflows.type == "EX"]["payoff"].sum() <= 0`.
- `cashflows[cashflows.type == "IN"]["payoff"].sum() >= 0`.
- The total `EX` payoff over the horizon equals the sum of vested capital
  released, no double-counting of leavers' age credits.
- Setting `salary_growth_rate=0`, `turnover_rate=0`, and
  `entry_count_per_year=0` must produce **identical** cashflows and
  portfolio states as `run_bvg_engine` (Stage 1) — this is a pinned regression
  test (see section 12).

## 11. Scenario Layer

### 11.1 Public API

```text
src/pk_alm/scenarios/stage2_baseline.py:

@dataclass(frozen=True)
class Stage2BaselineResult:
    scenario_id: str
    engine_result: Stage2EngineResult
    valuation_snapshots: pd.DataFrame
    annual_cashflows: pd.DataFrame
    asset_snapshots: pd.DataFrame
    funding_ratio_trajectory: pd.DataFrame
    funding_summary: pd.DataFrame
    scenario_summary: pd.DataFrame
    output_dir: Path | None

def run_stage2_baseline(
    scenario_id: str = "stage2_baseline",
    horizon_years: int = 12,
    start_year: int = 2026,
    active_interest_rate: float = 0.0176,
    retired_interest_rate: float = 0.0176,
    technical_interest_rate: float = 0.0176,
    contribution_multiplier: float = 1.4,
    valuation_terminal_age: int = 90,
    target_funding_ratio: float = 1.076,
    annual_asset_return: float = 0.0,
    salary_growth_rate: float = 0.015,
    turnover_rate: float = 0.02,
    entry_assumptions: EntryAssumptions | None = None,
    output_dir: str | Path | None = "outputs/stage2_baseline",
) -> Stage2BaselineResult: ...
```

### 11.2 Output structure

`outputs/stage2_baseline/` mirrors `outputs/stage1_baseline/` plus two new
files:

```text
outputs/stage2_baseline/cashflows.csv
outputs/stage2_baseline/valuation_snapshots.csv
outputs/stage2_baseline/annual_cashflows.csv
outputs/stage2_baseline/asset_snapshots.csv
outputs/stage2_baseline/funding_ratio_trajectory.csv
outputs/stage2_baseline/funding_summary.csv
outputs/stage2_baseline/scenario_summary.csv
outputs/stage2_baseline/demographic_summary.csv         # NEW: per-year entries, exits, residuals
outputs/stage2_baseline/cashflows_by_type.csv           # NEW: PR/RP/KA/EX/IN totals per year
```

`outputs/stage1_baseline/*` is **never written by Stage 2**. The two output
trees coexist.

### 11.3 Demographic summary CSV

```text
projection_year, entries, exits, retirements, turnover_residual,
                 active_count_eop, retired_count_eop, member_count_eop
```

`eop` = "end of period" (year `t+1` in projection time).

## 12. Test Strategy

Mirror the Stage-1 testing pattern. Each new module gets a dedicated test
file with these mandatory test groups:

- **Unit / formula** — manually checkable single-cohort numerics (e.g. one
  cohort, salary growth 1.5 %, expected `gross_salary_next_year`).
- **Schema / contract** — emitted cashflow records validate against
  `validate_cashflow_dataframe`, source `"BVG"`, sign conventions.
- **Boundary / invalid input** — negative rates, rates > 1, NaN, bool, None.
- **Immutability** — input portfolio not mutated.

In addition, `tests/test_bvg_engine_stage2.py` must include:

- **Stage-1 equivalence test (mandatory)**: with
  `salary_growth_rate=0`, `turnover_rate=0`, `entry_count_per_year=0`, the
  Stage-2 engine produces **identical** `portfolio_states` and `cashflows`
  as `run_bvg_engine` for the same input. This is the central regression
  guard.
- **Population-balance test**: counts evolve according to section 5.2.
- **EX-payoff invariant**: total `EX` payoff equals total vested capital
  removed.
- **Stage-1 protection test**: `run_bvg_engine` and `run_stage1_baseline`
  remain bit-identical to their pre-Stage-2 outputs (asserted against
  `outputs/stage1_baseline/*` snapshots if present, otherwise re-run).

`tests/test_stage2_baseline_scenario.py` includes the corresponding
end-to-end test plus a CSV roundtrip.

## 13. Validation Strategy

External plausibility:

- Funding-ratio trajectory under Stage-2 defaults should **not** decline as
  steeply as Stage 1 because new entrants add young, low-capital active
  members and turnover removes vested capital before retirement age.
- Total active member count should remain **broadly stable** under
  `entry_count_per_year ≈ retirements + turnover_count`.
- Salary growth should lift PR contributions over the horizon — visible in
  `annual_cashflows.csv`.

Internal plausibility:

- Setting all Stage-2 levers to zero reproduces Stage 1 (mandatory test).
- `Pensionierungsverlust` per year should grow proportionally to the number
  of new retirements; entries should not affect it (entries are age 25, far
  from retirement).

## 14. Defaults Rationale

| Parameter | Default | Rationale |
|---|---|---|
| `salary_growth_rate` | 0.015 | Long-run Swiss nominal wage growth ~1–2 %; a flat 1.5 % is a transparent baseline, not a forecast |
| `turnover_rate` | 0.02 | 2 % annual turnover ≈ Schweizer Pensionskassen-Studie aggregate range (3–8 % including retirements); Stage-2 turnover is **net of retirements** so the lower end is the baseline |
| `entry_count_per_year` | 1 | The Stage-1 demo portfolio has 13 actives; one entry per year keeps the demo small and manually checkable. A calibrated scenario can override |
| `entry_age` | 25 | First age bracket with non-zero BVG age credit (25–34: 7 %) |
| `entry_gross_salary` | 65 000 CHF | Median Swiss entry salary ≈ AHV-Lohn-Median for age 25–29; deliberately a round number, not a calibrated value |
| `entry_capital_per_person` | 0 | Zero by default; if an entrant brings Freizügigkeitsleistung from a previous fund, the scenario sets it explicitly |

All defaults are **documentation choices**, not calibrations. Each value is
independently overridable via scenario kwargs.

## 15. Limitations of Stage 2

Even after Stage 2 is implemented, the model still excludes:

- **Mortality** (Stage 3) — retirees still run off only through `valuation_terminal_age = 90`.
- **Stochastic salary or stochastic turnover** (Stage 5).
- **Disability and survivor benefits**.
- **Multi-employer transitions** beyond the entry-capital scalar.
- **Reglements-specific Überobligatorium structures**.
- **Asset-side dynamics** beyond the deterministic Stage-1 roll-forward
  (Stage 4).

These are not Stage-2 bugs; they are explicit Stage-2 boundaries.

## 16. Acceptance Criteria for Sprint 10 (Implementation)

Sprint 10 (the Stage-2 implementation sprint) is complete when:

1. All Stage-2 modules in section 4 implement their specified APIs.
2. All test files in section 12 are green, including the **Stage-1
   equivalence test** and the **Stage-1 protection test**.
3. `run_stage2_baseline` produces the nine CSV files in section 11.2.
4. `docs/implementation_progress.md` records a Sprint 10 entry with the new
   passing test count and a note that Stage 1 is unaffected.
5. `README.md` mentions Stage 2 with a Quick-Run line and points to this
   spec.
6. The protected Stage-1 outputs (`outputs/stage1_baseline/*`) are
   bit-identical before and after Sprint 10.

Until Sprint 10 starts, the Stage-2 modules raise
`NotImplementedError("Stage 2 Bauplan: implementation deferred")`, and the
test stubs are skipped via `@pytest.mark.skip(reason="Stage 2 Bauplan")`.
