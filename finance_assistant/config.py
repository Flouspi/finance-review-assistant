from dataclasses import dataclass, field
from pathlib import Path
import os

from dotenv import dotenv_values

ROOT = Path(__file__).resolve().parent.parent


@dataclass
class Settings:
    api_key: str = field(default="", repr=False)
    base_url: str = "https://api.deepseek.com"
    model: str = ""
    knowledge_backend: str = "local"
    knowledge_dir: Path = ROOT / "knowledge"
    timeout: float = 120
    max_input_chars: int = 100000
    evaluation_mode: bool = False

    @classmethod
    def load(cls, cloud=None):
        # Read afresh for each run; never log secrets or change process env.
        env = {**dotenv_values(ROOT / ".env"), **(cloud or {}), **os.environ}
        def value(name, default=""):
            return str(env.get(name) or default).strip()
        return cls(
            api_key=value("MODEL_API_KEY") or value("DEEPSEEK_API_KEY"),
            base_url=value("MODEL_BASE_URL", "https://api.deepseek.com").rstrip("/"),
            model=value("MODEL_NAME"),
            # This edition always uses the team's own document collection.
            # Ignore legacy cloud settings pointing to Dify during migration.
            knowledge_backend="local",
            knowledge_dir=Path(value("KNOWLEDGE_DIR", str(ROOT / "knowledge"))),
            timeout=float(value("MODEL_TIMEOUT", "120")),
            max_input_chars=int(value("MAX_INPUT_CHARS", "100000")),
            evaluation_mode=value("EVALUATION_MODE", "false").lower() in {"true", "1", "yes"},
        )
