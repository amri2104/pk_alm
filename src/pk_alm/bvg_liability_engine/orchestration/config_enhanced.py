from dataclasses import dataclass
import json

@dataclass
class EnhancedBVGConfig:
    start_year: int = 2024
    projection_horizon: int = 10
    retirement_age: int = 65
    technical_interest_rate: float = 0.02
    conversion_rate: float = 0.05
    contribution_rate: float = 0.10
    salary_escalation_rate: float = 0.01
    withdrawal_rate: float = 0.02
    new_entrants_per_year: int = 0
    entry_age: int = 25
    entry_salary: float = 80000.0
    female_fraction: float = 0.5
    mortality_table_id: str = "EK0105"
    active_mortality_mode: str = "expected" # "off", "expected"
    retiree_mortality_mode: str = "expected" # "off", "expected"
    decrement_mode: str = "expected" # "expected" or "deterministic" (integer)

    @classmethod
    def from_dict(cls, data: dict) -> "EnhancedBVGConfig":
        valid_keys = {f.name for f in cls.__dataclass_fields__.values()}
        filtered_data = {k: v for k, v in data.items() if k in valid_keys}
        return cls(**filtered_data)

    @classmethod
    def from_json(cls, path: str) -> "EnhancedBVGConfig":
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        return cls.from_dict(data)
