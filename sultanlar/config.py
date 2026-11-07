"""Project settings, read from config.json."""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CONFIG = json.loads((ROOT / "config.json").read_text(encoding="utf-8"))


def project_path(name):
    return ROOT / CONFIG["paths"][name]
