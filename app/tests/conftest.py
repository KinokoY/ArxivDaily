"""Keep pytest and library temporary files inside this workspace by default."""
import os
from pathlib import Path
import tempfile


def pytest_configure(config):
    root = Path(__file__).resolve().parents[1] / "tmp"
    root.mkdir(parents=True, exist_ok=True)
    os.environ["TEMP"] = str(root)
    os.environ["TMP"] = str(root)
    tempfile.tempdir = str(root)
    if config.option.basetemp is None:
        config.option.basetemp = str(root / "pytest")
