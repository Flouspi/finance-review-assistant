"""Public evaluation entrypoint; connection settings remain server controlled."""
import os
from pathlib import Path
import runpy

os.environ["EVALUATION_MODE"] = "true"
runpy.run_path(str(Path(__file__).resolve().parent / "app.py"), run_name="__main__")
