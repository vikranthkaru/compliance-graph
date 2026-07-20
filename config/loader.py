import os
import re
from pathlib import Path
from typing import Any

import yaml

from dotenv import load_dotenv

load_dotenv()
CONFIG_DIR = Path(__file__).resolve().parent

_ENV_PATTERN = re.compile(r"^\$\{([A-Z0-9_]+)\}$")


def _resolve_environment_variables(value: Any) -> Any:
    """
    Recursively replaces YAML values such as:

        ${SALESFORCE_USERNAME}

    with values from operating-system environment variables.
    """

    if isinstance(value, dict):
        return {
            key: _resolve_environment_variables(item)
            for key, item in value.items()
        }

    if isinstance(value, list):
        return [
            _resolve_environment_variables(item)
            for item in value
        ]

    if isinstance(value, str):
        match = _ENV_PATTERN.match(value)

        if not match:
            return value

        variable_name = match.group(1)
        environment_value = os.getenv(variable_name)

        if environment_value is None:
            raise RuntimeError(
                "Required environment variable is missing: "
                f"{variable_name}"
            )

        return environment_value

    return value


def load_yaml(file_name: str) -> dict:
    config_path = CONFIG_DIR / file_name

    if not config_path.exists():
        raise FileNotFoundError(
            f"Configuration file was not found: {config_path}"
        )

    with config_path.open(
        "r",
        encoding="utf-8",
    ) as config_file:
        config = yaml.safe_load(config_file) or {}

    return _resolve_environment_variables(config)