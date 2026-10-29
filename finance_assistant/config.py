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
    dify_api_key: str = field(default="", repr=False)
    dify_base_url: str = "https://api.dify.ai/v1"
    dify_dataset_id: str = ""
    dify_search_method: str = ""
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
            knowledge_backend=value("KNOWLEDGE_BACKEND", "local"),
            knowledge_dir=Path(value("KNOWLEDGE_DIR", str(ROOT / "knowledge"))),
            dify_api_key=value("DIFY_DATASET_API_KEY"),
            dify_base_url=value("DIFY_API_BASE", "https://api.dify.ai/v1").rstrip("/"),
            dify_dataset_id=value("DIFY_DATASET_ID"),
            dify_search_method=value("DIFY_SEARCH_METHOD"),
            timeout=float(value("MODEL_TIMEOUT", "120")),
            max_input_chars=int(value("MAX_INPUT_CHARS", "100000")),
            evaluation_mode=value("EVALUATION_MODE", "false").lower() in {"true", "1", "yes"},
        )
