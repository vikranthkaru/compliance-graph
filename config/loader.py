from pathlib import Path
import yaml

BASE_DIR = Path(__file__).parent


def load_yaml(filename: str):
    with (BASE_DIR / filename).open() as f:
        return yaml.safe_load(f)