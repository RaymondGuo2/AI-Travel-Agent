from __future__ import annotations

from pathlib import Path

import yaml

from travel_agent.policy.models import CompanyPolicy


def load_policy(path: str | Path) -> CompanyPolicy:
    with open(path) as f:
        data = yaml.safe_load(f)
    return CompanyPolicy.model_validate(data)


def load_default_policy() -> CompanyPolicy:
    config_path = Path(__file__).parent.parent.parent.parent / "config" / "company_policy.yaml"
    if config_path.exists():
        return load_policy(config_path)
    return CompanyPolicy()
